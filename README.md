# Dax Assistant

A self-hosted, voice-first personal AI assistant — Jarvis-style, but yours. Dax runs
locally, talks to **any** LLM (local Ollama by default, or the official Anthropic, OpenAI
and Gemini SDKs), can **act on your computer** through a sandboxed tool layer, and ships
with a modern web UI (chat + dashboard + settings, light/dark).

Built on a hexagonal architecture (ports & adapters): channels, LLM providers, MCP tools
and storage are all swappable behind small interfaces.

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

## Requirements

- Python **3.11** (the project pins `>=3.11,<3.12`).
- [`uv`](https://docs.astral.sh/uv/) for dependency management.
- Linux with `systemd --user`. The installer supports Fedora/RHEL, Debian/Ubuntu, Arch,
  and openSUSE and installs Python 3.11 through `uv` when needed.
- [Ollama](https://ollama.com/) running locally if you want the default local provider
  (otherwise set a cloud provider as default).
- Node.js (only to rebuild the web UI from source).

> `uv` is installed at `~/.local/bin/uv` and may not be on your `PATH`. Use the full path
> or add `~/.local/bin` to `PATH`.

---

## Production install

Install the latest release and all voice/audio dependencies for the current user:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/daxrpm/dax-assistant/main/scripts/install.sh)
```

From an existing checkout, run `./scripts/install.sh install`. The installer prompts for
English or Spanish models, creates an isolated Python 3.11 environment, and starts a
hardened `systemd --user` service. It does not require root except when the selected
distribution's package manager installs missing system libraries. Production web assets
are included; Node.js is not required.

Default paths follow the XDG base-directory specification:

| Content | Default path |
| --- | --- |
| Application | `~/.local/share/dax-assistant/app` |
| Models | `~/.local/share/dax-assistant/models` |
| Database and key | `~/.local/state/dax-assistant/` |
| Service unit | `~/.config/systemd/user/dax-assistant.service` |
| Caches | `~/.cache/dax-assistant/` |

Use `--install-dir PATH`, `--models-dir PATH`, or the corresponding XDG environment
variables to change these locations. Run `./scripts/install.sh --help` for all options.

### Operations

```bash
systemctl --user status dax-assistant
journalctl --user -u dax-assistant -f
./scripts/install.sh doctor
./scripts/install.sh update
./scripts/install.sh uninstall          # preserves state and models
./scripts/install.sh uninstall --purge  # also removes state, models, and caches
```

Updates create a timestamped database/key backup under
`~/.local/state/dax-assistant/backups`, update the application and dependencies, restart
the service, and roll back the application if startup fails. To restore a local-key
installation manually, stop the service and copy a matching `.db` and `.key` backup pair
over `dax.db` and `dax.key` before restarting it. Never restore one without the other.

For external key management, set `DAX_MASTER_KEY` in the service environment and keep it
separate from the database. The value must be the same Fernet key on every restart and
must be backed up independently; losing it makes the encrypted configuration
unrecoverable. A mode-`0600` systemd `EnvironmentFile` in `~/.config/dax-assistant/` is a
simple option. Run `systemctl --user edit dax-assistant`, add the directive below, then
reload and restart the service:

```ini
[Service]
EnvironmentFile=%h/.config/dax-assistant/environment
```

### Audio troubleshooting

The service joins your graphical user session so it can use PipeWire/PulseAudio. If voice
does not start, run `./scripts/install.sh doctor`, confirm that
`systemctl --user status pipewire pipewire-pulse` is healthy, and inspect the service log.
Verify input devices independently with `wpctl status` or `arecord -l`. Remote SSH-only
sessions may not have access to the desktop audio session; install and run Dax as the
logged-in desktop user.

`systemd --user` is the supported deployment model. A container is not the default
because microphone capture, PipeWire playback, desktop notifications, clipboard access,
and user-approved PC-control tools all depend on the host graphical session. Passing
those sockets and devices into Docker reduces isolation while adding substantial setup.

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

### Desktop client

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

There is no bundled Python sidecar. For a remote backend, the desktop client
requires HTTPS/WSS; HTTP/WS is accepted only for loopback. The backend
automatically trusts the packaged Tauri webview origins, so a fresh installation
does not require a manual CORS entry.

Native first-run onboarding completes before authentication and configures a
schema-v2 `local`, `remote`, or `hybrid` strategy. Starting the existing local
systemd service requires explicit consent. Hybrid is remote-first, falls back to
loopback after three confirmed failures, and does not fail back during the active
session. Authentication tokens are isolated by backend origin. The same
connection editor is available later in Desktop Settings.

Orbita uses stepped cool surfaces over a blue-black ground. Its default main
window chrome is a 31 px custom frame, with native decorations configurable in
Settings. The voice orb is pseudo-3D Canvas 2D: separate input/output waves use
RMS, peak, and spectrum frames through imperative buffers without routing level
data through React state.

See [`desktop/README.md`](desktop/README.md) for prerequisites, development,
packaging, verified test counts and known validation gaps. See
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

- **Path confinement.** File tools resolve paths and reject anything outside the allowed
  roots (default: your home directory; override with `DAX_SYSTEM_ROOTS`).
- **Shell allowlist.** `shell_run` only accepts allowlisted binaries (`DAX_SYSTEM_SHELL_ALLOW`)
  and rejects shell metacharacters (`|`, `;`, `&`, redirects, …).
- **Confirmation gate.** The `[tools.policy]` rules classify each tool as `allow` / `ask` /
  `deny`. Destructive tools (write/delete/shell/exec/launch …) default to `ask`, which
  blocks execution until you approve — the modal in the web UI, or a **spoken yes/no** when
  the request came from the voice channel (with a timeout that fail-safes to *deny*).
- **Audit log.** Every gated execution is recorded and visible on the dashboard.

Disable PC control entirely by setting `enabled = false` on the `dax-system` server.

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
npm test           # 49 tests in the recorded 2026-07-19 run
npm run build
npm audit --omit=dev # 0 vulnerabilities in the recorded run
cd src-tauri
cargo test --all-targets --all-features # 16 tests in the recorded run
cargo clippy --all-targets --all-features -- -D warnings
```

The same recorded run passed 312 backend tests; ruff, mypy and clippy were
clean, as was the frontend build. These automated gates do not claim a human
visual review, hardware audio, interactive Wayland behavior, remote audio
between two hosts, or clean-system package installation.

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
  channels/     web / whatsapp / voice adapters
  storage/      async SQLite database + repository
  web/          FastAPI app, auth, routes, static (built UI)
  voice/        wake-word, STT, TTS pipeline (optional `voice` extra)
```

---

## Remote access

`uv run dax` binds to `0.0.0.0` by default so first-party mobile clients can pair over
the LAN. Authentication is still enforced, but the first-run setup endpoint is reachable:
pair and configure the owner account only on a trusted network. Restrict TCP port 8420 to
the trusted subnet in the host firewall and never forward it directly to the internet.
Set `[web] expose_lan = false` to return to loopback-only operation. For access beyond the
LAN, prefer a private overlay (Tailscale, WireGuard) or an authenticated HTTPS reverse
proxy. Preserve WebSocket upgrades and proxy to `http://127.0.0.1:8420`.

For desktop remote voice, microphone PCM travels from the client to
`/ws/voice` as bounded PTT-only mono 16 kHz PCM. In protocol v1, synthesized
speech is played on the backend server's speakers; audio output is not streamed
back to the desktop client. See [`docs/voice-websocket.md`](docs/voice-websocket.md).

---

## License

MIT.
