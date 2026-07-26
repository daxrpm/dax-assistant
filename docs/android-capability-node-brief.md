# Brief: turn the Android app into a capability node

Paste everything below the line into a fresh agent session, started in the
repository root. It is written to be read cold — it assumes no memory of the
work that led here.

---

## What I want

The Dax Android app should become a **capability node**, the way the laptop
already is: it connects outbound to the backend, advertises a small set of
tools, and executes them when the backend routes a call to it. The goal is for
the assistant to actually *do things on my phone* — open apps, control what is
playing, place a call, tell me what notifications I missed.

Start by researching what Android genuinely permits, from official
documentation, and tell me what the full menu looks like before you build. I
want the honest version: what works, what needs a special permission, what
Android has closed off, and what only works via fragile workarounds. Then
implement it, and walk me through anything I have to do on the phone myself.

## The codebase you are joining

Dax is a self-hosted single-user assistant. One always-on FastAPI backend is
authoritative for storage, config, LLM routing, tools, policy and approvals.
Web, desktop and Android are clients. A laptop runs `dax edge`, an outbound
**capability node** that lends tools to the backend.

Read `CLAUDE.md` first — it is accurate and explains the invariants. Then read,
in this order:

| Path | Why |
| --- | --- |
| `src/dax/capabilities/protocol.py` | The wire protocol you are implementing a second client for |
| `src/dax/capabilities/hub.py` | The backend side: connection lifecycle, generations, trusted inventory |
| `src/dax/edge/daemon.py` | The existing node client — your reference implementation |
| `src/dax/core/config.py` (`NodePolicyConfig`, `NodesConfig`) | Per-node policy, keyed by device id |
| `android/app/src/main/kotlin/com/dax/assistant/data/transport/ChatSocket.kt` | How the app already does authenticated WebSockets |

A capability node authenticates with a **capability token** (`aud=capability-node`),
obtained by POSTing device credentials to `/api/auth/devices/token`, and connects
to `/ws/capabilities`. Note `AuthManager.device_from_token` deliberately refuses
capability nodes, and `issue_capability_token` refuses ordinary clients — the two
scopes are separate on purpose. The phone is currently enrolled as a `client`
device, so it will need a **second, separate enrolment** as a capability node.
Do not try to make one device be both; work out the cleanest way to express
"this phone is also a node" and propose it before implementing.

## Invariants you must not break

These are load-bearing. If one seems to be in your way, say so rather than
working around it.

1. **The node proposes, the backend decides.** A node advertises tool *names*
   only. Descriptions and schemas come from the server-owned table in
   `protocol.BUNDLED_TOOLS`, never from the node. You will be adding entries
   there for the Android tools. `trusted_inventory` re-derives everything.
2. **Node execution stays policy- and approval-gated.** Anything with real
   effect goes through the confirmation gate. See `ToolGate._gate_shell` for how
   a node's shell call is handled — always one-time approval, never savable.
3. **Human approval is carried explicitly.** `ToolCall.human_approved` rides in
   the `execute` frame as `approved`. An executor that enforces its own local
   restrictions must consult it, or approving on screen will do nothing. This
   was a real bug on the laptop; do not reintroduce its shape on the phone.
4. **Trust flows from the backend, never from the LAN.** Discovery may hint a
   node exists; it is never evidence of identity.
5. **Inventory is live-socket-only** and is removed on disconnect or revocation.

## The constraint that makes this different from the laptop

**A phone is not a laptop.** It sleeps, loses the network, runs on battery, and
Android will kill background work. The laptop node can be assumed present while
it is at home; the phone cannot. So:

- Tools must be advertised as best-effort, and the backend must degrade
  gracefully when the phone is absent rather than failing a turn.
- Think hard about foreground services, Doze, and battery optimisation
  exemptions — and about what you are asking me to accept when you request them.
- Copying `edge/daemon.py`'s always-connected assumption would be a mistake.

Decide and justify: does the node connection live in the existing
`AssistantService` foreground service, a new one, or something schedulable?

## Capability research — go wide, then tell me

Work from official Android documentation and verify against the app's
`compileSdk`. For each capability report: the API, the permission, the minimum
API level, whether it works from the background, and any restriction that has
landed in recent Android versions. Cover at least:

- Launching apps and deep links — `PackageManager.getLaunchIntentForPackage`,
  `Intent.ACTION_VIEW`, and the `<queries>` manifest element that Android 11+
  package visibility requires. Without `<queries>` you will silently see nothing.
- Media control via `MediaSession` / `MediaController` — play, pause, skip,
  and reading what is currently playing, for any app, without that app's API.
- Reading notifications via `NotificationListenerService`, and posting them.
- Telephony: placing calls, the call log, and sending SMS. Establish clearly
  which of these can complete without me touching the screen.
- Location, including geofencing.
- Contacts and calendar through their content providers.
- Device state: battery, connectivity, Do Not Disturb, volume, brightness.
- Camera and the media store.
- Files via the Storage Access Framework.

Also establish clearly what is **not** possible, so I stop asking. I already
know two: toggling Wi-Fi/Bluetooth programmatically was removed in Android 10,
and reading the clipboard from the background was restricted in the same
release. Find the rest.

On WhatsApp specifically: this backend already sends WhatsApp through the
Evolution API in `src/dax/channels/whatsapp_channel.py`, server-side, which
works while the phone is asleep. Do not route WhatsApp through the phone, and
do not propose an `AccessibilityService` for it. If you think accessibility is
warranted for something else, argue for it explicitly rather than slipping it in.

## Build it in this order

Land each step working before starting the next. I would rather have step 2
solid than five steps half-done.

1. **Transport only, zero tools.** A capability client that speaks protocol v1,
   enrols, connects, survives reconnection and generation fencing, and appears
   under Devices in the desktop app. This validates the hard part before any
   tool exists. Ship it advertising nothing.
2. **`app_open` and `app_deeplink`**, with `<queries>`. This is my original use
   case — "open Spotify on my phone" — and it exercises the whole path.
3. **`media_control`** via `MediaSession`.
4. **`notifications_read`.** The one I most want: "what did I miss?" should
   have a real answer.
5. **Telephony**: place a call, send an SMS.

## How to work

- `~/.local/bin/uv` is often not on `PATH`; use the full path.
- Backend: `~/.local/bin/uv run pytest -q`, `ruff check src tests`,
  `mypy src` (strict). All three must pass.
- Android: `cd android && source env.sh && gradle :app:testDebugUnitTest`.
  The toolchain lives on an external volume; `env.sh` sets it up.
- `tests/unit/test_settings_coverage.py` fails the build if a new `DaxConfig`
  leaf is missing from `desktop/src/screens/settings/registry.json`. Add the
  setting to the JSON, not to a component.
- Release APKs need my keystore (`DAX_ANDROID_KEYSTORE`,
  `DAX_ANDROID_KEY_PASSWORD`, `DAX_ANDROID_CERT_SHA256`). You cannot sign; hand
  me the command when it is time to install.
- The backend runs on `daxrpm@home-server` over SSH. Deploy with
  `scripts/release.py build` then `install.sh --manifest`, using
  `scripts/localize-manifest.py` to point the manifest at local artifacts.

Write tests that describe the failure a user would notice, not the mechanics.

## What I want from you as we go

Tell me each runtime permission before you need it and what it actually grants —
`NotificationListenerService` in particular reads *every* notification on the
device, and I want to make that call knowingly. Where a capability is possible
but a bad idea, say so. And when you hand me something to install, tell me how
to verify it worked and how to undo it.

Start with the research. Do not write code until we have agreed on the menu.
