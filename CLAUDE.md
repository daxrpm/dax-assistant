# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Dax is a self-hosted, single-user personal AI assistant. A FastAPI backend runs an agent loop that routes user messages (from web chat, WhatsApp, Telegram, or voice) through a pluggable LLM and a set of MCP tools, then streams replies back. The frontend is a React + HeroUI + Tailwind v4 SPA built into `src/dax/web/static` and served by FastAPI.

> Note: `README.md` says the UI is "React 19 + Mantine" — that is stale. The UI is **HeroUI v3 + Tailwind v4** with `.dark`-class theming.

## Commands

`uv` lives at `~/.local/bin/uv` and is often not on `PATH` — use the full path.

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

### Config & secrets (`core/config.py`, `web/routes/api.py`)

pydantic-settings, precedence **env > .env > TOML > defaults**, `DAX_` prefix with `__` as nested delimiter (e.g. `[security].password_hash` → `DAX_SECURITY__PASSWORD_HASH`). Critical conventions when adding config:

- **`web/routes/api.py::_save_config_to_toml` rewrites the *entire* TOML from the in-memory config.** Any new config field must be serialized there or it is lost on the next settings save.
- **Secrets never go in TOML.** Write them to `.env` via `_upsert_env_var()` and store a `{env:VAR}` reference in TOML (`_env_ref_for_secret()` / `_secure_headers_for_toml()`). Then resolve `{env:VAR}` at use-time (`factory._resolve_env` for LLM keys, `manager._resolve_env_dict` for MCP env/headers). `config/dax.toml` and `.env` are git-ignored; only `*.example` files are tracked — **never commit real secrets.**
- Settings edits mutate the live config object in place; some apply live (LLM router, tool policy via `policy.reload`), others (host/port, Telegram) need a restart.

### Channels (`channels/`)

`web` (WebSocket in `web/routes/chat.py` + `web_channel.py` broadcast), `whatsapp` (Evolution API: inbound webhook in `web/routes/webhooks.py`, outbound in the channel), `telegram` (httpx long-polling, **bidirectional** — owns both inbound polling and outbound send; no public URL needed), `voice` (optional `voice` extra). Inbound channels publish to the bus; the Dispatcher routes outbound by `message.channel`.

### Web realtime protocol

The agent streams activity via `agent.set_event_broadcaster()`. The chat WebSocket sends typed frames the frontend switches on: `{type:"agent_event", event}` (thinking / tool_call / tool_result / done — drives the live "thinking" panel), `{type:"message"}` (final assistant turn), and `{type:"tool_confirmation_request"}` (the human-in-the-loop approval modal). The `ApprovalManager` gates `ask`-classified tools and fail-safes to *deny* on timeout.

### Storage (`storage/`)

Async SQLite (`aiosqlite`), WAL mode, schema versioned in `database.py` (`SCHEMA_VERSION` — bump it and add a migration when changing schema; `tests/integration/test_storage.py` asserts the version). `ConversationRepository` persists conversations per `(channel, session_key)` and a tool-execution audit log.

## Safety model

`[tools.policy]` classifies every tool as `allow` / `ask` / `deny`; destructive tools default to `ask` and block on the confirmation modal. The `dax-system` server confines file paths to allowed roots (`DAX_SYSTEM_ROOTS`) and allowlists shell binaries (`DAX_SYSTEM_SHELL_ALLOW`). Auth (argon2 + signed cookies) is enforced on the API, the WebSocket, and the WhatsApp webhook; the app binds to `127.0.0.1` by default.
