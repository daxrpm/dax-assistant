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
  webhook. Secrets live in `.env`, never in the committed config.
- **Memory.** Conversations are persisted per channel/session in SQLite and replayed into
  each turn, plus a tool-execution audit log.
- **Modern web UI.** React + HeroUI v3 + Tailwind v4, minimalist, light/dark (follows your OS theme).

---

## Requirements

- Python **3.11** (the project pins `>=3.11,<3.12`).
- [`uv`](https://docs.astral.sh/uv/) for dependency management.
- [Ollama](https://ollama.com/) running locally if you want the default local provider
  (otherwise set a cloud provider as default).
- Node.js (only to rebuild the web UI from source).

> `uv` is installed at `~/.local/bin/uv` and may not be on your `PATH`. Use the full path
> or add `~/.local/bin` to `PATH`.

---

## Quick start

```bash
# 1. Install dependencies (creates the .venv)
~/.local/bin/uv sync --all-extras

# 2. Create your config and secrets
cp config/dax.toml.example config/dax.toml
cp .env.example .env

# 3. Generate a login password hash and paste it into .env
~/.local/bin/uv run python -m dax.web.auth 'your-password'
#  -> $argon2id$v=19$...   (set DAX_SECURITY__PASSWORD_HASH to this)

# 4. Generate a session secret and paste it into .env too
openssl rand -hex 32
#  -> set DAX_SECURITY__SESSION_SECRET to this

# 5. (optional) Add cloud API keys to .env: ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY

# 6. Run
~/.local/bin/uv run dax
```

Then open **http://127.0.0.1:8420** and log in with the password from step 3.

If you only want the default local provider, make sure Ollama is running and has the model
referenced in `config/dax.toml` (`[llm.ollama] model`), e.g. `ollama pull llama3.1:8b`.

---

## Configuration

Settings come from `config/dax.toml` (structure) and environment variables / `.env`
(**secrets**). Env vars use the `DAX_` prefix with `__` as the nested delimiter and
**override** the TOML file. For example `[security].password_hash` maps to
`DAX_SECURITY__PASSWORD_HASH`.

See [`config/dax.toml.example`](config/dax.toml.example) for the full annotated config and
[`.env.example`](.env.example) for every secret.

### Secrets (always in `.env`, never committed)

| Variable | Purpose |
| --- | --- |
| `DAX_SECURITY__PASSWORD_HASH` | argon2 hash of your web login password |
| `DAX_SECURITY__SESSION_SECRET` | random string used to sign session cookies |
| `ANTHROPIC_API_KEY` | Claude (read by the official SDK) |
| `OPENAI_API_KEY` | OpenAI (read by the official SDK) |
| `GEMINI_API_KEY` | Gemini (read by the official SDK) |
| `DAX_WHATSAPP__EVOLUTION_API_KEY` | Evolution API key (if WhatsApp is enabled) |
| `DAX_WHATSAPP__WEBHOOK_SECRET` | shared secret required on inbound webhooks |

`config/dax.toml` and `.env` are git-ignored; only the `*.example` files are tracked.

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

The bundled `dax-system` MCP server (`config/dax.toml` → `[mcp.servers.dax-system]`) gives
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
the conversation going for follow-ups without re-triggering. Everything runs locally.

**The stack**

| Stage | Engine | Notes |
| --- | --- | --- |
| Wake word | [openWakeWord](https://github.com/dscripka/openWakeWord) | default `hey_jarvis`; set `[voice] wake_word_model` to another built-in (e.g. `alexa`) or a custom `.onnx` |
| VAD / endpointing | [Silero VAD](https://github.com/snakers4/silero-vad) | adaptive: short pause for quick commands, longer for sentences |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | default `large-v3-turbo` (int8); language **pinned** to avoid mis-detection |
| TTS | [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) (default) / [Piper](https://github.com/rhasspy/piper) (fallback) | natural neural voice; auto-falls back to Piper if Kokoro is missing |
| Voice ID *(optional)* | [Resemblyzer](https://github.com/resemble-ai/Resemblyzer) | enroll your voice so other people can't drive the assistant |

**One-command install** (prompts for Spanish/English and downloads the right models):

```bash
./scripts/install.sh
# or fetch models manually for one language:
~/.local/bin/uv run python scripts/download_models.py --language es
```

**Key settings** (`config/dax.toml` → `[voice]`):

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

- **Fresh per activation.** Each wake word starts a new conversation scope, so Dax doesn't
  bleed context from past chats; follow-ups within the same activation keep context.
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

# Web UI (from web/)
cd web
npm install
npm run dev        # Vite dev server (set [web] dev_mode = true for CORS)
npm run build      # outputs into src/dax/web/static, served by FastAPI
npm run test:run   # vitest
```

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

Dax binds to loopback. To reach it from another device, prefer a private overlay
(Tailscale, WireGuard) or an authenticated reverse proxy over HTTPS rather than exposing
the port. If you must listen on the LAN, set `[web] expose_lan = true` and
`[security] cookie_secure = true` behind TLS — auth is still enforced.

---

## License

MIT.
