# Dax Desktop - Implementation Record

**Status:** implementation complete; automated release gates pass.
**Document version:** 3 (2026-07-19).
**Target:** native Linux client in `desktop/` for the backend in `src/dax/`.

This document replaces the execution checklist with the implemented architecture,
measured results and remaining validation. When this document and source disagree,
source wins and this document must be updated.

[`../docs/desktop-architecture.md`](../docs/desktop-architecture.md) is the primary
reference for desktop boundaries and invariants; this plan records decisions,
milestones, measurements, and open gates.

## 1. Scope

Dax Desktop is a first-class client beside the browser SPA and Android app. It uses Tauri
v2, Rust, React 19 and TypeScript. It talks directly to the existing FastAPI HTTP
and WebSocket API; Rust does not proxy application requests or contain business
logic.

The desktop application provides chat, a command deck with host metrics, MCP management,
device enrollment, command allowlisting, logs, complete Settings, tray integration,
global shortcuts, autostart, notifications and a separate voice HUD.

## 2. Closed Decisions

Do not reopen these decisions.

### D1. Tauri v2 + Rust + React

Tauri remains the chosen shell over Electron and native immediate-mode UI
toolkits. Rust owns native boundaries; React renders the UI. The real WebKitGTK
memory floor invalidated the original 90-140 MB marketing-derived target but did
not reopen the stack decision.

### D2. Same repository

Desktop remains under `desktop/` in this monorepo so API and client contracts can
change together.

### D3. Native-inspired design, Linux first

The approved visual direction is **Orbita**, not a copy of `web/` and not the
rejected outlined admin layout. It uses CSS Modules and design tokens, generous
spacing/radii, elevation rather than panel borders, a command deck home and a
command palette. Linux cannot request real backdrop blur, so the design does not
depend on it.

### D4. Python voice pipeline remains server-side

STT, TTS, wake-word, VAD and speaker verification remain in Python. Input is
pluggable through `AudioSource`: `LocalAudioSource` captures on the backend host;
`RemoteAudioSource` accepts bounded authenticated PCM from the desktop client.
Default remote output is synthesized and reproduced on the server host. A
`client_text` lease instead emits sentence text without server synthesis or
playback. Streaming server-synthesized audio to the client is not implemented.

### D5. Performance uses measured PSS

The original 90-140 MB RSS target is retired. M0 measured the WebKitGTK floor:

| Build | RSS across 3 processes | PSS |
| --- | ---: | ---: |
| Debug, idle | 412.5 MB | 191.3 MB |
| Release, idle on Login | 422.7 MB | 197.9 MB |

The accepted full-app budget is **250 MB PSS**. The empty release binary measured
6.3 MB at M0; the current binary is 7,214,672 bytes. No post-completion PSS or
idle-CPU profiler run has been recorded, so that performance residue stays open.

## 3. Shipped Architecture

```text
+-------------------------------------------------------------+
| Dax Desktop                                                 |
|                                                             |
| Rust/Tauri                         React/WebKitGTK            |
| - keyring                          - command deck             |
| - tray/single instance             - all screens              |
| - HUD/window management    IPC     - HTTP client              |
| - global shortcuts          <-->   - chat/log/voice stores    |
| - autostart/notifications          - waveform + remote mic    |
| - host metrics/systemd                                      |
+----------------------+----------------------+-----------------+
                       | HTTP + WebSocket
                       | loopback or HTTPS/WSS
                       v
+-------------------------------------------------------------+
| Dax Python backend                                          |
| sole authority: FastAPI + agent + MCP + SQLite + voice      |
| local dax-assistant.service OR one remote host              |
+-------------------------------------------------------------+

Optional laptop node: outbound `dax edge` -> authority `/ws/capabilities`.
It contributes tools while online and owns no server state.
```

### 3.1 Local deployment

The desktop package does not bundle or spawn Python. The supported local backend
is `dax-assistant.service`, installed by `scripts/install.sh`, at
`http://127.0.0.1:8420`. Rust exposes only a fixed allowlist of `systemctl --user`
`status`, `start`, `stop` and `restart` operations with bounded timeouts. It also
collects CPU, logical CPU count, memory, uptime and disk metrics through
`sysinfo`.

The versioned native connection document uses schema v3 and supports `local`
and `remote`. Local probes only the validated loopback URL and intentionally
makes that service the sole authority. Remote probes only its validated HTTPS
URL. There is no fallback between them. A legacy v1 `{mode,url}` document is
migrated on read. Schema-v2 local/remote settings retain their meaning;
schema-v2 `hybrid` is historical input and migrates to remote using its
configured `remote_url`. Migrated settings are rewritten atomically as v3.

First-run onboarding runs before backend authentication. It explains privacy,
selects a strategy, validates URLs, checks connectivity, and asks for explicit
consent before starting the existing `dax-assistant.service`. The package does
not silently install or start Python. The same controls remain in Desktop
Settings and on the unreachable-backend screen for later reconfiguration.

### 3.2 Remote deployment and URL security

Both Rust and TypeScript validate connection URLs:

- HTTP and WS are allowed only for loopback (`localhost`, IPv4 or IPv6 loopback).
- Non-loopback URLs require HTTPS and derived WebSockets require WSS.
- Credentials, query strings, fragments and non-HTTP schemes are rejected.
- CSP permits HTTPS/WSS remote connections.

Remote input sends microphone audio to the server. Default output does not
return synthesized audio; TTS plays through the backend host's speakers.
`client_text` output suppresses server synthesis/playback and emits speech text
for local client synthesis. No mode streams server-synthesized PCM.

### 3.3 Native boundary

Implemented Rust commands are token get/set/clear, backend settings/status,
system metrics, systemd service control, and HUD show/hide/toggle. Scoped Tauri
plugins provide single-instance behavior, URL opening, global shortcuts,
autostart and notifications.

Health is accepted only from a ready authoritative Dax API with compatible
protocol identity and a non-empty `instance_id`. Tokens are stored in the OS
keyring by normalized backend origin plus that instance identity. Changing
either closes realtime stores and restarts authentication; credentials are
never copied or reused across authorities. The
documented in-memory fallback applies when Secret Service is unavailable.
Non-secret browser-development fallbacks use web storage; the packaged token
does not use `localStorage`.

Global bindings are:

| Binding | Action |
| --- | --- |
| `Super+Shift+D` | Focus the main window |
| `Ctrl+Space` press/release | Show HUD and drive PTT down/up |

### 3.4 Frontend loading and state

Chat, Logs, Marketplace, MCP and Settings are lazy-loaded route chunks. The
production build emits separate route, React-vendor and Markdown-vendor chunks.
Shared chat/log/voice stores use
`useSyncExternalStore` and demand-based lifecycles, survive route hand-offs and
close on logout.

CSS has responsive adaptations at 900 px and 720 px. The Tauri main window has a
720 px minimum width; command deck, chat, Settings, memory and primitives collapse
appropriately at the 720 px boundary.

Orbita uses a blue-black ground and stepped cool surfaces, separated by space,
luminance and soft elevation rather than visible panel outlines. The main window
defaults to a persisted custom 31 px frame; Desktop Settings can switch live to
native compositor decorations. The voice HUD remains independently undecorated.

### 3.5 Internationalization

The desktop UI ships Spanish and English catalogs. It detects supported browser
locales, defaults to Spanish, persists the explicit choice and updates the HTML
`lang` attribute. The Settings registry is localized in both languages.

## 4. Backend Contracts

The authoritative sources are `src/dax/web/routes/*.py`,
`src/dax/web/auth.py`, `src/dax/core/voice_events.py` and the client types under
`desktop/src/api/`.

### 4.1 Authentication and CORS

Login/setup return the signed session token while preserving the browser cookie
flow. Desktop HTTP sends `Authorization: Bearer`; browser WebSocket APIs append
`?token=`. Authentication validates offered credentials so a stale cookie does
not shadow a valid bearer token.

The backend always adds `tauri://localhost` and `http://tauri.localhost` to CORS.
A fresh packaged installation requires no manual `web.cors_origins` entry.
`http://localhost:5273` is only the desktop Vite development origin and may be
added to a development backend when those processes are cross-origin.

### 4.2 Chat and `session_id`

Client messages contain `content`, `language` and `session_id`. The backend uses
that ID as the persisted conversation key and propagates it through:

- thinking, tool-call, tool-result and done agent events;
- tool-confirmation requests;
- final assistant message frames.

Desktop stores filter correlated frames by `session_id`, preventing another tab
or client from mixing broadcast activity into the active conversation. Approval
timeouts fail safe to deny and the modal exposes the server-provided countdown.

### 4.3 Voice state and expiry

`/ws/voice` is implemented and authenticated. Server events are `state`, `level`,
`transcript`, `speech`, `speaker` and `error`. `transcript` is user speech;
in default server-output mode, `speech` is emitted after synthesis and
immediately before each Kokoro sentence plays. With a `client_text` lease it is
the sentence for client-side synthesis and no server audio is produced.
State data contains:

```json
{
  "state": "idle|listening|processing|speaking|conversing",
  "conversation_id": "voice-session-id-or-null",
  "session_expires_at": 1752871834.567
}
```

The pipeline reuses its voice `session_id` across activations until the configured
inactivity TTL expires, or an explicit farewell ends it. `session_expires_at` is
an absolute Unix timestamp and is `null` without an active session. The desktop
therefore renders real server expiry rather than estimating it.

On connection, the route replays the latest state or sends synthetic idle. It
unsubscribes and releases remote input on every disconnect path so metering and
leases cannot leak.

### 4.4 Remote audio protocol v1

The complete protocol is in [`../docs/voice-websocket.md`](../docs/voice-websocket.md).
Its fixed behavior is:

- one authenticated owner lease at a time;
- JSON `remote_audio.acquire`, `start`, `stop` and `release` controls;
- binary mono 16 kHz signed PCM16 little-endian frames while started;
- maximum 3,200 bytes per frame, 30 seconds per utterance and 50 queued frames;
- stable JSON errors and policy/size/retry close codes for invalid order,
  malformed controls, unsupported formats, overflow and backpressure;
- PTT only, with no remote wake-word/continuous-capture mode;
- output negotiation supports default `server` and optional `client_text`;
- `client_text` emits sentence text and suppresses server synthesis/playback;
- `client_audio_supported` remains `false` because synthesized PCM streaming is
  not implemented.

Desktop capture uses `getUserMedia`, prefers `AudioWorklet`, falls back to
`ScriptProcessorNode`, resamples to 16 kHz and encodes PCM16.

## 5. Settings 6.0

The approved search-first information architecture is implemented. It replaces
the browser SPA's old one-domain-per-tab layout with seven task-named sections:

1. **Voz** - live status, listening, conversation, TTS, STT, speaker identity and enrollment.
2. **Inteligencia** - provider routing, budgets and provider-specific configuration.
3. **Capacidades** - MCP servers, tool policy and shell allowlist.
4. **Memoria** - system prompt, memory path and memory CRUD.
5. **Canales** - Telegram and WhatsApp.
6. **Acceso** - account, session security and network exposure.
7. **Sistema** - identity, storage and desktop-native preferences/service controls.

`registry.json` is data rather than JSX. The renderer supports explicit per-group
save, dirty state, live/reload/restart annotations, advanced disclosure, secret
mask semantics and accent-insensitive search over labels, descriptions and config
keys. `tests/unit/test_settings_coverage.py` recursively compares the registry
against every `DaxConfig` leaf so new backend fields cannot silently lack a UI.

Autostart and notifications are shipped under Sistema. Notifications require an
explicit permission-granting user gesture and persisted opt-in. Backend
disconnect notification fires once after three consecutive failed 15-second
health checks and resets after recovery.

Media ducking is also a persisted device preference. Its enabled state and
speaking-volume slider are live: changing the 10–100% factor reapplies the
current MPRIS state without losing the original volume. Listening and processing
retain 60% and 75% floors, and idle restores the exact captured volume.

## 6. Voice HUD

The `voice-hud` is a separate undecorated, always-on-top, skip-taskbar Tauri
window. It shows state, the current Kokoro sentence (or latest user transcript),
speaker verification, PTT errors and a Canvas
2D pseudo-3D orb. A radial-gradient sphere, perspective ellipses, and z-sorted
particles create depth. Separate input and output ring buffers drive distinct
waves from each frame's RMS, peak, and spectrum data: the outer, sharper wave is
microphone input and the inner, perspective-compressed wave is TTS output.
Complete level frames flow through imperative refs and never through React state.
The animation loop stops after both sources settle in idle.

GNOME/Wayland was measured to create the transparent always-on-top window, but it
ignored requested positioning and did not honor exact logical sizing. The HUD
must accept compositor placement. Shadow clipping could not be inspected because
the non-interactive screenshot portal denied capture.

## 7. Milestone Results

### M0 - Risk spike: passed (2026-07-18)

- Confirmed packaged Linux webview origin `tauri://localhost`.
- Added and exercised bearer-only auth over real uvicorn HTTP; browser cookies
  remained compatible.
- Confirmed authenticated `?token=` WebSocket connection.
- Confirmed GNOME/Wayland HUD creation and the positioning/sizing caveat.
- Measured the WebKitGTK memory floor and revised D5 with user acceptance.
- Adopted hash routing.
- Built initial RPM and deb bundles.

This was protocol/runtime verification, not a human visual review.

### M1 - Foundation: passed with visual caveat (2026-07-18)

Tauri/React scaffold, Orbita foundations, login/setup, bearer client, keyring,
single instance, tray, persistent backend URL, health and dashboard worked end to
end. The packaged app executed JS and reached the backend, and the exact auth
sequence was exercised over real HTTP. The environment could not display or
capture the rendered window, so visual correctness was not proven.

### M2 - Chat: automated gate passed

Conversation persistence, Markdown/highlighting, activity trail, model selection,
approval countdown, reconnect and complete `session_id` correlation are
implemented and unit-tested. A human full conversation with a real ask-classified
tool was not performed in this final pass.

### M3 - Settings and screens: automated gate passed

Settings 6.0, full config coverage, memory, MCP, devices, commands, virtualized
logs, i18n, responsive 720 px behavior, stores and lazy chunks are implemented.
The original 10k-log PSS gate was not rerun.

### M4 - Voice and HUD: software gate passed; hardware gate open

Voice WebSocket, server expiry, HUD, PTT, waveform, transcript, speaker state,
tray controls and enrollment/preview are implemented. No human wake-word,
microphone, speakers, visual waveform or idle CPU profiler test is claimed.

### M5 - Native polish: software gate passed; human accessibility gate open

Autostart, native notifications, command palette, global shortcuts,
reduced-motion handling and screen states are implemented. A keyboard-only,
focus, labels/roles and contrast review by a human remains.

### M6 - Packaging: build gate passed; clean-install gate open

RPM and deb are the only configured targets. A release build produced both
packages, but neither a clean Fedora install nor uninstall was performed.

### M7 - Remote audio: protocol gate passed; two-host hardware gate open

Audio source abstraction, bounded remote source, browser mic capture, resampling,
PCM encoding, PTT controls, errors and cleanup are tested. A real remote-host
conversation was not performed. Default output remains on the server;
`client_text` is text-only client-owned output.

## 8. Automated Release Gate

Use the reproducible commands below rather than recording test counts or exact
artifact sizes, which become stale immediately. Passing automated and build
gates does not imply visual approval, hardware audio, idle profiling,
accessibility review, remote two-host audio, signing, or clean-system
installation.

## 9. Reproducible Commands

Backend, lint and strict types from repository root:

```bash
~/.local/bin/uv run pytest -q
~/.local/bin/uv run ruff check src tests
~/.local/bin/uv run mypy src
```

Frontend:

```bash
cd desktop
npm install
npm run typecheck
npm test
npm run build
npm audit --omit=dev
npm run tauri dev
```

Rust and release bundles:

```bash
cd desktop/src-tauri
cargo fmt --all -- --check
cargo test --all-targets --all-features
cargo clippy --all-targets --all-features -- -D warnings

cd ..
npm run tauri build
npm run tauri build -- --bundles rpm
npm run tauri build -- --bundles deb
```

A plain `cargo build` does not embed `dist/`; it expects Vite at `devUrl` and can
show a blank window when launched alone. Use `npm run tauri dev` or a Tauri
release build.

## 10. Remaining Gates

Only mark these complete after the stated evidence exists:

- Human visual review of all screens in light/dark and ES/EN.
- Keyboard-only and accessibility audit.
- Real microphone, speakers, wake-word, local PTT and voice-enrollment run.
- Idle CPU and full-app PSS profiling against the accepted 250 MB PSS budget.
- Interactive Wayland HUD placement/shadow inspection; positioning remains a
  compositor limitation, not a code gate.
- Real two-host HTTPS/WSS remote PTT conversation, remembering that TTS plays on
  the server in default output mode and `client_text` produces no server audio.
- RPM install, launch, connection and uninstall on a clean Fedora 44 system.

## 11. Ground Truth

| Concern | Source |
| --- | --- |
| HTTP/WS mounting and automatic CORS | `src/dax/web/server.py` |
| Auth | `src/dax/web/auth.py`, `src/dax/web/routes/auth.py` |
| Chat contract | `src/dax/web/routes/chat.py`, `desktop/src/hooks/useChatSocket.ts` |
| Voice protocol | `src/dax/web/routes/voice_ws.py`, `docs/voice-websocket.md` |
| Desktop architecture and invariants | `docs/desktop-architecture.md` |
| Voice session expiry | `src/dax/voice/pipeline.py`, `src/dax/core/voice_events.py` |
| Audio sources | `src/dax/voice/audio_io.py`, `desktop/src/audio/remoteAudio.ts` |
| Settings | `desktop/src/screens/settings/registry.json` |
| Native integration | `desktop/src-tauri/src/*.rs`, `desktop/src/native/` |
| Bundle targets | `desktop/src-tauri/tauri.conf.json` |
| Capability nodes | `docs/capability-nodes.md`, `src/dax/capabilities/`, `src/dax/edge/` |
| Deployment and releases | `docs/deployment.md`, `README.md` |

The knowledge graph at `graphify-out/graph.json` is useful for orientation.
Source remains implementation truth, while `docs/desktop-architecture.md` is the
primary architectural reference and focused protocol documents define their
wire contracts.
