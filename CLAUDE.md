# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Dax is a self-hosted, single-user personal AI assistant. One always-on FastAPI backend is authoritative for SQLite, configuration, conversations, LLM routing, tools, policy, approvals, and voice. Web, desktop, and Android are clients. An optional laptop can run the outbound `dax edge` capability node, which contributes ephemeral tools but never becomes a backend or fallback authority.

The web frontend is React + HeroUI v3 + Tailwind v4 with `.dark`-class theming. It is built into `src/dax/web/static` and served by FastAPI.

## Commands

`uv` lives at `~/.local/bin/uv` and is often not on `PATH` — use the full path.
Production deployments use the generated `systemd --user` unit from
`scripts/install.sh`; the checked-in unit is a reference for default XDG paths.

```bash
# Backend
~/.local/bin/uv sync --all-extras           # install deps (creates .venv)
~/.local/bin/uv run dax                      # run the app (serves http://127.0.0.1:8420)
~/.local/bin/uv run pytest -q                # all tests
~/.local/bin/uv run pytest tests/integration/test_storage.py::TestDatabase::test_schema_version  # single test
~/.local/bin/uv run pytest -m "not integration"   # skip integration tests
~/.local/bin/uv run ruff check src tests     # lint
~/.local/bin/uv run mypy src                 # type-check (strict)

# Frontend (from web/)
npm install
npm run dev          # Vite dev server — set [web] dev_mode = true in config for CORS
npm run build        # tsc -b && vite build → outputs into src/dax/web/static
npx tsc -b           # type-check only
npm run test:run     # vitest
```

`pytest` runs with `asyncio_mode = "auto"` (async tests need no decorator). After changing frontend code you must `npm run build` and commit the regenerated `src/dax/web/static/assets/*` for the change to appear in the running app.

## Architecture

### Message flow (the spine)

Everything funnels through an async message bus (`orchestrator/bus.py`):

```
inbound channel → bus.publish_inbound → Agent._process_loop (orchestrator/agent.py)
  → _handle_message: load conversation history, pick relevant tools, call LLM,
    run any tool calls (looping up to MAX_TOOL_ITERATIONS), persist
  → bus.publish_outbound → Dispatcher (orchestrator/dispatcher.py)
  → Channel.send for message.channel  (web / whatsapp / telegram / voice)
```

A `Message` carries a `channel` and a `metadata` dict; `metadata["session_id"]` (web/Telegram) selects which persisted conversation to resume, keeping chats isolated. `DaxApp` in `app.py` wires every component together in dependency order.

### LLM layer (`llm/`) — fully decoupled behind the `LLMProvider` port

`factory.build_router(config.llm)` builds an ordered `LLMRouter` (default provider + `fallback_order`); the router fails over automatically. Providers: `openai`, `anthropic`, `gemini`, `ollama` (OpenAIProvider with a `base_url`), and `codex` (subprocess running `codex exec --json`, text-only — Codex runs its own tool loop). Changing LLM config via the API calls `router.set_providers(build_providers(...))` to rebuild **in place** — no restart.

Two non-obvious provider rules (both were live bugs):
- **API keys are stored in TOML as `{env:VAR}` and must be resolved before use.** `factory._resolve_env()` does this for LLM keys. The OpenAI SDK will use a literal `{env:...}` string verbatim → 401 otherwise.
- **`reasoning_effort` is incompatible with function tools** on `/v1/chat/completions` for gpt-5.x → the OpenAI provider only sends it on tool-less turns.

### Tool selection (`mcp/registry.py` + `llm/tool_mapper.py`) — performance-critical

The agent does **not** send all tools to the LLM. `registry.get_relevant_tools(query, max_tools=config.llm.max_tools)`:
- always includes `dax-system` tools (`_ALWAYS_INCLUDE_SERVERS` in `tool_mapper.py`),
- fills the remaining budget by keyword-relevance score, with Spanish→English expansion (`_ES_EN_KEYWORDS`).

`max_tools` (default **45**) is a latency lever: too low and tools never reach the model (a `max_tools=8` default once excluded Nextcloud entirely because dax-system alone exceeded the budget); too high (e.g. 120) and prompts balloon to ~85 s responses. The system-prompt inventory in `agent._build_system_prompt()` lists only the tools actually passed that turn, for the same reason.

### MCP (`mcp/`) and the bundled server

`MCPManager` holds one persistent `MCPClient` session per server (stdio subprocess or streamable-HTTP). `mcp_servers/system/server.py` is the bundled **`dax-system`** server giving the assistant typed, path-confined, allowlisted PC-control tools. OAuth for remote MCP servers lives in `web/routes/oauth.py` (PKCE + dynamic client registration); after the callback it **reconnects** the server so the Bearer token takes effect without a restart, and refreshes expired tokens before reconnecting.

`capabilities/` registers the trusted bundled inventory from authenticated edge nodes under canonical node-prefixed names; `edge/` is the outbound laptop daemon. Inventory is live-socket-only and removed on disconnect/revocation. Node execution remains policy/approval-gated, path-confined on the node, and argv-only for shell calls. Do not add arbitrary node MCP discovery.

### Node processing policy

`[nodes]` decides what each laptop is asked to do: `process_locally` (host a
session and run the turn, versus only lend tools), plus `inference` and `voice`
in `auto` / `local` / `server`. Policy is keyed by device id and owned by the
backend, so a node reads its own entry on connect rather than keeping a copy —
that is what makes "stop processing on the laptop" work from whichever client is
in reach. `CapabilityHub.send_policy` pushes changes to a connected node, best
effort; the backend enforces its side regardless, and nothing in that push is a
security control.

Keep `inference` on `auto`. It pins the model to the node only when the model is
itself local (Ollama on the node's GPU). A cloud provider is dominated by the
round trip to the provider, so routing that HTTPS call through a laptop adds a
hop and removes none. The real win is `voice` — audio is bulky, and keeping
speech next to the microphone avoids crossing the network twice.

The desktop settings registry (`desktop/src/screens/settings/registry.json`) is
gated by `tests/unit/test_settings_coverage.py`: every `DaxConfig` leaf must
appear there. Add a setting to the JSON, not to a component.

### Direct client sessions on a node (in progress)

The intended end state is that the phone connects **directly** to the laptop
when it is up, and the laptop runs the turn, while the backend stays the owner
of conversation state. Two rules govern that work and neither is optional:

* **Trust flows from the backend, never from the LAN.** Discovery may hint that
  a node exists; it is never evidence of identity. A client verifies a node
  against something the backend vouched for, and a node verifies the client the
  same way. mDNS presence alone must never be sufficient, or anyone on the WiFi
  can answer as Dax.
* **The node is a subordinate session host, not a second authority.** It runs
  the turn and writes through to the backend. It does not become the source of
  truth for conversations, and it does not mint client credentials.

The trust half is built. `capabilities/tickets.py` signs short-lived session
tickets with Ed25519 — asymmetric on purpose, because the existing session and
device tokens are HMAC and a node holding that shared secret could mint device
tokens and session cookies for the backend itself. A ticket names one node and
one device, so it cannot be replayed at a different laptop, and there is no
algorithm field to downgrade. `POST /api/nodes/{id}/session-ticket` is
device-authenticated and refuses what the node cannot check for itself: a
switched-off fleet, a node not meant to host, a disconnected node, a revoked
phone. The node receives the verifying public key in its `ready` frame.

Node addresses follow the same rule as node tool schemas: proposed, not trusted.
`trusted_endpoints` keeps private, link-local, and loopback literals and drops
everything else — an address the backend repeats to a phone is an instruction
about where to send a credential, so a node must not be able to name a routable
one.

What is still missing is the session server itself: the node does not yet listen,
so it advertises no endpoints, and nothing hosts a turn. `process_locally` is
stored, pushed, and enforced at ticket issue, but the socket it gates does not
exist yet.

### Desktop authority selection

Desktop schema v3 supports only `local` and `remote`. Local intentionally selects loopback as the sole authority; remote selects exactly one HTTPS origin. Schema-v2 `hybrid` is accepted only as migration input and becomes remote using `remote_url`. Health must identify a ready `role=authoritative` Dax API, and tokens are scoped by normalized origin plus `instance_id`.

### Config & secrets (`core/config.py`, `core/config_io.py`)

pydantic-settings, precedence **env > encrypted SQLite config > defaults**, `DAX_` prefix with `__` as nested delimiter (e.g. `security.password_hash` → `DAX_SECURITY__PASSWORD_HASH`). Critical conventions when adding config:

- **`config_io.save_encrypted_config()` writes the complete validated config as encrypted JSON in the SQLite `secrets` table.** Persistence is model-driven, so new Pydantic fields round-trip automatically.
- **Secret fields, MCP headers, and all MCP environment values are separate encrypted entries.** The config document contains only `{env:VAR}` references. API responses mask these values and PATCH restores unchanged masks server-side.
- `config/dax.toml` and `.env` are legacy one-time imports. After a successful migration the full TOML is removed; a custom database location may retain a bootstrap containing only `storage.database_path`.
- Settings edits mutate the live config object in place; some apply live (LLM router, tool policy via `policy.reload`), others (host/port, Telegram) need a restart.

### Channels (`channels/`)

`web` (WebSocket in `web/routes/chat.py` + `web_channel.py` broadcast), `whatsapp` (Evolution API: inbound webhook in `web/routes/webhooks.py`, outbound in the channel), `telegram` (httpx long-polling, **bidirectional** — owns both inbound polling and outbound send; no public URL needed), `voice` (optional `voice` extra). Inbound channels publish to the bus; the Dispatcher routes outbound by `message.channel`.

### Web realtime protocol

The agent streams activity via `agent.set_event_broadcaster()`. The chat WebSocket sends typed frames the frontend switches on: `{type:"agent_event", event}` (thinking / tool_call / tool_result / done — drives the live "thinking" panel), `{type:"message"}` (final assistant turn), and `{type:"tool_confirmation_request"}` (the human-in-the-loop approval modal). The `ApprovalManager` gates `ask`-classified tools and fail-safes to *deny* on timeout.

### Storage (`storage/`)

Async SQLite (`aiosqlite`), WAL mode, schema versioned in `database.py` (`SCHEMA_VERSION` — bump it and add a migration when changing schema; `tests/integration/test_storage.py` asserts the version). `ConversationRepository` persists conversations per `(channel, session_key)` and a tool-execution audit log.

## Safety model

`[tools.policy]` classifies every tool as `allow` / `ask` / `deny`; destructive tools default to `ask` and block on the confirmation modal. The `dax-system` server confines file paths to allowed roots (`DAX_SYSTEM_ROOTS`) and allowlists shell binaries (`DAX_SYSTEM_SHELL_ALLOW`). Auth (argon2 + signed cookies) is enforced on the API, the WebSocket, and the WhatsApp webhook; the app binds to `127.0.0.1` by default.
