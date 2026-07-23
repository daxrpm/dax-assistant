# Dax Assistant

A self-hosted, voice-first personal AI assistant — Jarvis-style, but yours. Dax runs
locally, talks to **any** LLM (local Ollama by default, or the official Anthropic, OpenAI
and Gemini SDKs), can **act on your computer** through a sandboxed tool layer, and ships
with a modern web UI (chat + dashboard + settings, light/dark).

Built on a hexagonal architecture (ports & adapters): channels, LLM providers, MCP tools
and storage are all swappable behind small interfaces.

## Topology

Every installation has exactly one always-on authoritative backend. It owns
SQLite, encrypted configuration, conversations, LLM routing, MCP, policy,
approvals, audit data, and voice processing. The browser, Linux desktop, and
Android apps are clients of that authority.

A laptop can optionally run `dax edge` as an outbound capability node. While it
is connected, the server may invoke its bounded, policy-gated `dax-system` tool
inventory. Turning off the laptop removes those tools but does not interrupt the
server or chat. The node is not another backend, does not replicate state, and
does not provide authority fallback. See
[`docs/capability-nodes.md`](docs/capability-nodes.md).

---

## Highlights

- **Decoupled LLM layer.** One `LLMProvider` port, four adapters out of the box:
  - `ollama` — local, **default**, via an OpenAI-compatible endpoint.
  - `anthropic` — official `anthropic` SDK (`claude-opus-4-8`, adaptive thinking).
  - `openai` — official `openai` SDK (`gpt-5.5`); point `base_url` at *any*
    OpenAI-compatible API to add a new provider with zero code.
  - `gemini` — official `google-genai` SDK (`gemini-3.5-flash`).
  - Pick a `default_provider` and a `fallback_order`; the router fails over automatically.
- **Acts on your PC, safely.** A bundled `dax-system` MCP server exposes typed tools
  (read files, search, write files, run allowlisted shell commands, open paths, clipboard,
  notifications, system info). Every destructive action is path-confined and gated by a
  **confirmation policy** — the web UI pops a modal you must approve before it runs.
- **Secure by default.** Binds to `127.0.0.1`, single-user login (argon2 password hash +
  signed session cookies), auth enforced on the API, the WebSocket, and the WhatsApp
  webhook. Configuration and credentials are encrypted at rest in SQLite.
- **Memory.** Conversations are persisted per channel/session in SQLite and replayed into
  each turn, plus a tool-execution audit log.
- **Modern web UI.** React + HeroUI v3 + Tailwind v4, minimalist, light/dark (follows your OS theme).
- **Native Linux client.** Tauri v2 + React desktop app with chat, declarative
  Settings, system metrics, systemd controls, tray, native notifications,
  autostart, global PTT, a configurable custom/native frame, and a separate
  Canvas 2D voice HUD.

---

## Install

Dax is four pieces and only the first is required. Everything else is a client
that needs a backend to talk to, so install the backend first.

| Piece | What it is |
| --- | --- |
| **Backend** | The authority: SQLite, encrypted config, conversations, LLM routing, policy, approvals |
| **Desktop** | A client for Linux, and the machine that can also act as a capability node |
| **Android** | A client |
| **Capability node** | An optional laptop daemon that lends its tools to the backend |

**Requirements.** Linux with `systemd --user`, on Fedora/RHEL or Debian/Ubuntu.
Everything else — Python 3.11, `uv`, the audio libraries — the installer sets up
or asks about. You do **not** need the GitHub CLI.

### Install the backend

Run this on the machine that will host Dax — a home server, or your laptop if
that is all you have:

```bash
curl -fsSLO https://github.com/daxrpm/dax-assistant/releases/latest/download/install.sh
bash install.sh
```

It asks what to install, verifies and installs it, prompts for the password of
your one account, and finishes by printing the two addresses you can reach it
on. That is the whole process.

Prefer to read the script before running it, which is a reasonable habit for
anything installing a service: it downloads as a file above rather than piping
into a shell, so `less install.sh` works before you run it.

To skip the questions:

```bash
bash install.sh --backend --yes      # backend only, no prompts
bash install.sh --all                # backend and desktop client
bash install.sh --dry-run --all      # verify everything, install nothing
```

### Connect your other devices

The installer prints something like:

```text
From your other devices
  http://192.168.100.100:8420
```

Type **that exact address** into the desktop app and the Android app.

Clients accept a plain `http://` backend only when the host is a literal private
address: `10.x`, `172.16–31.x`, `192.168.x`, loopback, an IPv6 ULA/link-local
address, or `100.64–127.x` — the range Tailscale and similar overlays assign
from. Anything else must be `https://`.

A session token is being sent, and a private literal is the only form that
proves the traffic cannot leave your network. This is why a name like
`http://home-server:8420` is refused even though it works in a browser: DNS can
be repointed at a public address, so the name proves nothing. Use the address,
not the name.

To reach Dax from outside your network, use a private overlay (Tailscale,
WireGuard) or an authenticated HTTPS reverse proxy — never forward port 8420 to
the internet. Over Tailscale, use the machine's `100.x` address and cleartext is
fine: the tunnel is already encrypted end to end.

### The account

The first account can only be created from the machine the backend runs on. An
unclaimed backend on a network would otherwise be claimable by whoever reached
it first, and that account owns everything.

The installer normally does this for you. On a headless server installed without
a terminal, create it over SSH afterwards:

```bash
~/.local/share/dax-assistant/current/.venv/bin/dax claim
```

Then sign in from any client with that password. Every other setting — model,
API keys, voice, tools, integrations — is configured from a client once you are
signed in; the backend has no configuration UI of its own by design.

### Desktop client

```bash
bash install.sh --desktop
```

First launch asks for the backend address, verifies it responds, and then asks
you to sign in. After login it offers to pick a model, enrol this laptop as a
capability node, and pair your phone — each step skippable, and re-openable from
**Settings → Desktop → Run setup again**.

No API key is ever stored on the desktop; keys go to the backend's encrypted
store. Session credentials are kept per origin in the system keyring.

### Android

The APK is not published yet — the release pipeline needs a signing keystore
that is not configured, so releases currently ship without it. Build it from
`android/` in the meantime. Once installed, first run asks for the backend
address, then a pairing code generated on an already-signed-in client under
**Settings → Access → Devices**.

### Capability node

A node lets the backend use tools on a laptop without moving the backend there.

```bash
bash install.sh --node
```

It installs stopped, because a node has nothing to connect to until it is
enrolled. Enrol it from the desktop app under **Settings → Access → Devices**,
then start it. Behaviour, safety model, and revocation are in
[`docs/capability-nodes.md`](docs/capability-nodes.md).

Voice is the setting worth changing on a node: `voice = auto` runs mobile speech
synthesis on the laptop next to the microphone instead of crossing the network
twice. Leave `inference` on `auto` — it only pins the model to the node when the
model is itself local, and routing a cloud API call through a laptop adds a hop
without removing one.

### Managing an installation

```bash
bash install.sh status        # version, whether it is running and ready, its addresses
bash install.sh list          # installed releases, with the active one marked
bash install.sh               # re-run to upgrade to the newest release
bash install.sh rollback      # switch to the previous installed release
bash install.sh uninstall     # remove services and releases, keep the database
bash install.sh uninstall --purge   # also delete the database and secret key
```

The three newest releases are kept (`--keep N` to change), so a rollback needs
no network. Every upgrade and rollback backs up the database and its key to
`~/.local/state/dax-assistant/backups/` first.

Rollback carries a real caveat: schema migrations only run forward. If the newer
release migrated the database, the older one may refuse to open it. The command
warns and takes a backup before switching, and returns to the previous release
automatically if the older one fails to become ready.

```bash
journalctl --user -u dax-assistant -f     # logs
systemctl --user status dax-assistant     # service state
```

### What the installer verifies

Every artifact is checked for exact size and SHA-256 against the release
manifest, and the manifest against the release's `SHA256SUMS` over TLS. A
manifest may only name artifacts inside the release it claims to describe, so it
cannot redirect a download elsewhere.

If the GitHub CLI happens to be installed and authenticated, build provenance is
verified too, and `--require-attestation` makes that mandatory. It is not
required by default: needing `gh auth login` before you can install a program is
a barrier, not security.

`--manifest` and `--checksums` install from a manifest on local disk, for
mirrored or air-gapped installs.

### Audio troubleshooting

The service joins your graphical user session so it can use PipeWire/PulseAudio.
If voice does not start, check `systemctl --user status dax-assistant pipewire
pipewire-pulse` and `journalctl --user -u dax-assistant`, then verify input
devices with `wpctl status` or `arecord -l`. An SSH-only session may have no
access to the desktop audio session; install and run Dax as the logged-in
desktop user if you want voice on that machine.

`systemd --user` is the supported deployment model. A container is not the
default because microphone capture, PipeWire playback, notifications, clipboard
access, and user-approved PC-control tools all depend on the host graphical
session. Passing those sockets and devices into Docker reduces isolation while
adding substantial setup.

---

## Development quick start

```bash
# 1. Install dependencies (creates the .venv)
~/.local/bin/uv sync --all-extras

# 2. Run; defaults and a persistent session secret are initialized automatically
~/.local/bin/uv run dax
```

Then open **http://127.0.0.1:8420**, create the login password, and configure
providers, integrations, voice, and MCP servers from Settings.

If you only want the default local provider, make sure Ollama is running and has the model
selected in Settings, e.g. `ollama pull llama3.1:8b`.

### Desktop client architecture

The desktop client is a separate first-class UI under `desktop/`. It connects
directly to the same authenticated HTTP and WebSocket API. The supported local
architecture is:

```text
Dax Desktop (Tauri/Rust + React)
  ├─ HTTP + /ws/chat + /ws/logs + /ws/voice
  ├─ OS keyring, tray, HUD, shortcuts, notifications, autostart
  └─ systemctl --user control + host metrics
                    │
                    ▼
dax-assistant.service (FastAPI + agent + MCP + voice)
```

There is no bundled Python sidecar. A remote backend must be HTTPS/WSS unless its
host is a literal private address (RFC 1918, loopback, IPv6 ULA/link-local, or the
RFC 6598 range overlays such as Tailscale assign from), which is the one case where
cleartext provably cannot leave the local network. The backend automatically trusts
the packaged Tauri webview origins, so a fresh installation does not require a manual
CORS entry.

Native first-run onboarding completes before authentication and configures a
schema-v3 `local` or `remote` strategy. Local deliberately uses this laptop's
loopback service as the sole authority; remote uses one HTTPS server. There is no
fallback between them. Schema-v2 `hybrid` settings are historical migration
input: they become remote-only using the configured `remote_url`. Starting the
existing local systemd service requires explicit consent.

Desktop accepts health only from a ready authoritative Dax API with the expected
protocol/version and a non-empty `instance_id`. Authentication tokens are bound
to normalized backend origin plus that instance identity, so replacing a server
at the same URL does not reuse its predecessor's token. The connection editor is
available later in Desktop Settings.

Orbita uses stepped cool surfaces over a blue-black ground. Its default main
window chrome is a 31 px custom frame, with native decorations configurable in
Settings. The voice orb is pseudo-3D Canvas 2D: separate input/output waves use
RMS, peak, and spectrum frames through imperative buffers without routing level
data through React state.

See [`desktop/README.md`](desktop/README.md) for prerequisites, development,
packaging, verification commands, and known validation gaps. See
[`docs/desktop-architecture.md`](docs/desktop-architecture.md) for the primary
desktop architecture reference.

---

## Configuration

Settings are stored as a versioned encrypted document in `data/dax.db`. Secret fields,
MCP headers, and MCP environment values are independently encrypted and represented only
by references inside that document. Environment variables use the `DAX_` prefix with `__`
as the nested delimiter and override the database configuration.

`config/dax.toml.example` and `.env.example` remain migration templates. When a legacy
`config/dax.toml` is found, Dax imports it once and removes it after successful encryption.

### Secrets

| Variable | Purpose |
| --- | --- |
| `DAX_SECURITY__PASSWORD_HASH` | argon2 hash of your web login password |
| `DAX_SECURITY__SESSION_SECRET` | random string used to sign session cookies |
| `ANTHROPIC_API_KEY` | Claude (read by the official SDK) |
| `OPENAI_API_KEY` | OpenAI (read by the official SDK) |
| `GEMINI_API_KEY` | Gemini (read by the official SDK) |
| `DAX_WHATSAPP__EVOLUTION_API_KEY` | Evolution API key (if WhatsApp is enabled) |
| `DAX_WHATSAPP__WEBHOOK_SECRET` | shared secret required on inbound webhooks |

Use the Settings UI for secrets. Values are write-only in the API, encrypted with Fernet,
and never returned to the browser. The database and master-key files are mode `0600` and
git-ignored. For stronger key separation, set `DAX_MASTER_KEY` from a system credential
manager; otherwise Dax creates `data/dax.key`. Environment variables remain available for
deployment-time overrides.

### Choosing / adding LLM providers

```toml
[llm]
default_provider = "ollama"          # ollama | anthropic | openai | gemini
fallback_order   = ["gemini"]        # tried in order if the default fails
```

To use any other OpenAI-compatible API, set `[llm.openai] base_url` and its key — no code
changes required.

---

## PC control & safety

The bundled `dax-system` MCP server, managed from Settings, gives
the assistant typed tools to operate the machine. Safety is layered:

- **Path confinement.** Typed file tools reject paths outside `DAX_SYSTEM_ROOTS`. Generic
  command arguments are not claimed to be path-confined.
- **Shell isolation.** Node `shell_run` is disabled by default, always requires one-time
  approval, accepts only binaries in that PC's `DAX_SYSTEM_SHELL_ALLOW`, executes argv
  directly, and rejects shell metacharacters (`|`, `;`, `&`, redirects, …). It is not SSH.
- **Confirmation gate.** The `[tools.policy]` rules classify each tool as `allow` / `ask` /
  `deny`. Destructive tools (write/delete/shell/exec/launch …) default to `ask`, which
  blocks execution until you approve — the modal in the web UI, or a **spoken yes/no** when
  the request came from the voice channel (with a timeout that fail-safes to *deny*).
- **Audit log.** Every gated execution is recorded and visible on the dashboard.

Disable PC control entirely by setting `enabled = false` on the `dax-system` server.
The optional laptop node exposes the corresponding trusted inventory under
node-prefixed names, with paths resolved on that laptop and the same authoritative
policy/approval gate. It is not unrestricted remote shell access; see
[`docs/capability-nodes.md`](docs/capability-nodes.md).

---

## Voice assistant (Alexa-style, 100% open source)

Say the wake word and talk — Dax wakes, listens, transcribes, answers out loud, and keeps
the conversation going for follow-ups without re-triggering. In the normal deployment,
everything runs locally on the backend host.

**The stack**

| Stage | Engine | Notes |
| --- | --- | --- |
| Wake word | [openWakeWord](https://github.com/dscripka/openWakeWord) | default `hey_jarvis`; set `[voice] wake_word_model` to another built-in (e.g. `alexa`) or a custom `.onnx` |
| VAD / endpointing | [Silero VAD](https://github.com/snakers4/silero-vad) | adaptive: short pause for quick commands, longer for sentences |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | default `large-v3-turbo` (int8); language **pinned** to avoid mis-detection |
| TTS | [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) (default) / [Piper](https://github.com/rhasspy/piper) (fallback) | natural neural voice; auto-falls back to Piper if Kokoro is missing |
| Voice ID *(optional)* | [Resemblyzer](https://github.com/resemble-ai/Resemblyzer) | enroll your voice so other people can't drive the assistant |

The production installer prompts for Spanish/English and downloads the right models. To
fetch models manually for one language:

```bash
~/.local/bin/uv run python scripts/download_models.py --language es --models-dir data/models
```

**Key settings** (editable from Settings → Voice):

```toml
[voice]
enabled = true
wake_word_model = "hey_jarvis"     # built-in name or path to a custom .onnx
stt_model = "large-v3-turbo"       # large-v3-turbo | small | base | …
stt_language = "es"                # PIN to "es"/"en" — fixes "ru" mis-detection
tts_engine = "kokoro"              # kokoro (natural) | piper (fast)
voice_confirm = true               # confirm gated tools BY VOICE, not the web modal
response_timeout_s = 180           # let long tool chains finish before giving up
require_wake_word_each_turn = false # set true in noisy/shared rooms
speaker_verification = false       # set true after enrolling your voice
```

**Voice behaviour worth knowing**

- **Session-scoped context.** Voice turns reuse a `session_id` across activations until its
  inactivity TTL expires (or an explicit farewell ends it), preserving useful follow-up
  context without retaining it indefinitely. `/ws/voice` reports the absolute
  `session_expires_at` value.
- **Spoken confirmations.** When a tool needs approval and the request came from voice, Dax
  asks out loud (“¿lo ejecuto? sí/no”) instead of waiting on the (unseen) web modal.
- **Voice ID.** Enroll once, then enable it to ignore other voices:

  ```bash
  ~/.local/bin/uv run python scripts/enroll_voice.py   # records a few clips
  # then set [voice] speaker_verification = true
  ```

---

## Development

```bash
# Backend tests
~/.local/bin/uv run pytest -q

# Lint
~/.local/bin/uv run ruff check src tests

# Strict type check
~/.local/bin/uv run mypy src

# Web UI (from web/)
cd web
npm install
npm run dev        # Vite dev server (set [web] dev_mode = true for CORS)
npm run build      # outputs into src/dax/web/static, served by FastAPI
npm run test:run   # vitest
```

Desktop verification and packaging:

```bash
cd desktop
npm run typecheck
npm test
npm run build
npm audit --omit=dev
cd src-tauri
cargo fmt --all -- --check
cargo test --all-targets --all-features
cargo clippy --all-targets --all-features -- -D warnings
```

These automated gates do not claim a human
visual review, hardware audio, interactive Wayland behavior, remote audio
between two hosts, signing, or clean-system package installation.

The wheel `force-include`s `src/dax/web/static`, so a production build of the web UI is
served directly by the FastAPI app at `/`.

### Layout

```
src/dax/
  core/         config, models, ports, tool policy
  orchestrator/ agent, message bus, approval (human-in-the-loop) gate
  llm/          providers/ (ollama, anthropic, openai, gemini), router, factory
  mcp/          MCP client manager
  mcp_servers/  system/  -> the bundled dax-system PC-control server
  capabilities/ authoritative registry for ephemeral node tools
  edge/         outbound laptop capability-node client
  channels/     web / whatsapp / voice adapters
  storage/      async SQLite database + repository
  web/          FastAPI app, auth, routes, static (built UI)
  voice/        wake-word, STT, TTS pipeline (optional `voice` extra)
```

---

## Remote access

Dax binds to `0.0.0.0` by default so first-party clients can reach it over the LAN.
Authentication is enforced on every route, and first-run account creation is refused
from anything but loopback, so an unclaimed backend cannot be claimed over the network.
Still restrict TCP port 8420 to the trusted subnet in the host firewall and never forward
it directly to the internet. Set `[web] expose_lan = false` to return to loopback-only
operation. For access beyond the LAN, prefer a private overlay (Tailscale, WireGuard) or
an authenticated HTTPS reverse proxy. Preserve WebSocket upgrades and proxy to
`http://127.0.0.1:8420`.

For remote voice, microphone PCM travels from the client to `/ws/voice` as
bounded PTT-only mono 16 kHz PCM. Default `server` output synthesizes and plays
on the backend host. A client that acquires `client_text` output receives
sentence `speech` events and the server performs no synthesis, playback, or
earcon; the client may synthesize locally. Streaming server-synthesized audio to
a client is not implemented. See
[`docs/voice-websocket.md`](docs/voice-websocket.md).

---

## License

MIT.
