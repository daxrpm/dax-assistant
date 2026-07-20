## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Project architecture

Dax is a single-user assistant with one always-on authoritative Python backend and three clients. The backend is the sole source of truth for SQLite, conversations, configuration, LLM routing, MCP, policy, approvals, voice processing, and persistence. `web/` is the browser client, `desktop/` is the first-class Tauri client, and `android/` is the native mobile client. Do not move business logic into a client.

An optional laptop runs `dax edge` as an outbound capability node. It contributes a bounded `dax-system` inventory while connected; it is never a second backend or storage authority. Laptop shutdown removes those tools but server/chat continue. Do not introduce backend fallback, authority election, state replication, active-active SQLite, or automatic movement between local and remote servers.

The backend follows hexagonal boundaries:

- `src/dax/core/`: configuration, domain models, ports, events, and policies.
- `src/dax/orchestrator/`: agent loop, approvals, tool gating, and message bus.
- `src/dax/llm/`: provider adapters and ordered provider failover within the one authority.
- `src/dax/mcp/`: MCP clients, lifecycle, registry, and environment resolution.
- `src/dax/channels/`: web, voice, Telegram, and WhatsApp adapters.
- `src/dax/voice/`: local/remote audio sources, wake word, VAD, STT, TTS, speaker verification, and the voice state machine.
- `src/dax/storage/`: SQLite conversations and encrypted secrets.
- `src/dax/web/`: authenticated HTTP and WebSocket contracts.

The async message bus is the spine. Channels publish inbound messages, the agent processes them, and the dispatcher sends responses to the originating channel. Tool execution is policy-gated and defaults to denial when an approval request times out or no UI is connected.

## Desktop architecture

`desktop/` uses Tauri v2, Rust, React 19, TypeScript, CSS Modules, and the dark-first "Orbita" design system.

- `desktop/src-tauri/`: OS integration only. It owns windows, tray, global shortcuts, autostart, notifications, systemd control, host metrics, keyring access, and validated backend connection settings. It must not proxy normal backend API calls.
- `desktop/src/api/`: typed HTTP contracts, bearer authentication, and active backend resolution.
- `desktop/src/stores/`: long-lived realtime stores. Voice and logs use one shared socket per window; chat uses an isolated store per `session_id`.
- `desktop/src/audio/`: remote microphone capture, resampling, PCM16 encoding, and cleanup.
- `desktop/src/components/`: command deck, command palette, pseudo-3D voice orb, compact window frame, markdown, and shared product components.
- `desktop/src/design/`: tokens and primitives. Separation comes from space, surface steps, and soft elevation, not visible panel outlines.
- `desktop/src/screens/settings/registry.json`: the structural settings contract. Every `DaxConfig` leaf must be represented; `tests/unit/test_settings_coverage.py` enforces exact coverage.
- `desktop/src/i18n/`: complete Spanish/English UI localization. Backend content, logs, tool names, and technical identifiers are not translated.
- `desktop/src/native/`: typed frontend bridges for Rust-owned capabilities, first-run onboarding, and the voice HUD.

The desktop UI talks directly to FastAPI over HTTP/WebSocket. HTTP uses `Authorization: Bearer`; browser WebSockets use the token query parameter. Remote backend URLs require HTTPS/WSS; HTTP/WS is accepted only for loopback.

## Realtime contracts

- `/ws/chat`: messages, agent activity, tool results, and approvals are correlated with `session_id`. Never merge frames from another session. Delivery is session-scoped: a client claims a session by publishing on it, and frames route only to claimants. Tool confirmations never fall back to a broadcast, and only a client that owns the session may resolve them.
- Clients authenticate with a password session or an enrolled-device token (`/api/auth/devices/*`). Device tokens are short-lived, salt-separated from session tokens, and stop validating the moment the device is revoked.
- `/ws/logs`: one-way bounded log stream. Keep buffers bounded and virtualize long views.
- `/ws/voice`: state, input/output levels, transcript, speaker verdict, and errors. The inbound direction accepts an authenticated, exclusively leased PCM16LE 16 kHz mono stream for remote push-to-talk.
- Voice level frames identify `source: input|output`. Preserve this distinction through stores and visualizers so microphone and TTS/Kokoro activity are represented independently.

## Desktop behavior

- The home screen is the command deck, not a permanent sidebar. Navigation is command-palette-first.
- The voice orb and HUD must not route level frames through React state. Pass complete `LevelFrame` objects to imperative sinks, keep separate input/output ring buffers, and stop animation frames after idle settles.
- The pseudo-3D orb is Canvas 2D by design: radial gradients, perspective ellipses, z-sorted particles, and source-specific wave rings. Do not replace it with WebGL or ASCII without a measured need.
- The backend connection strategy is only `local` or `remote` and is persisted by Rust schema v3 before authentication. Local deliberately selects the laptop's loopback service as the sole authority; remote selects one HTTPS server. Never add fallback between them. Schema-v2 `hybrid` is historical migration input only and migrates to remote using its configured `remote_url`.
- Authentication tokens are isolated by normalized backend origin and authoritative `instance_id`. Never reuse or copy a token when either changes. Health is accepted only for a ready `role=authoritative`, `api_protocol=dax`, compatible API identity.
- First-run onboarding must complete before backend authentication. It explains privacy, validates URLs, checks connectivity, and asks before starting the local systemd service.
- The local backend is the systemd user service `dax-assistant.service`; service actions are a fixed allowlist, never arbitrary shell commands.
- Remote audio is push-to-talk only. TTS plays on the server host unless a client claims `output.mode = "client_text"` on `remote_audio.acquire`, in which case the server emits `speech` events and synthesizes nothing. Streaming server-synthesized audio to a client is still not implemented; do not imply it.
- The main window defaults to the compact custom frame. Users may switch live to native decorations in Desktop Settings; the HUD never uses the main frame.
- The target packages are Fedora RPM and Debian/Ubuntu deb. Fedora/GNOME/Wayland is the primary runtime.

## Capability nodes and deployment

- Enrollment codes are created from authenticated desktop/web device UI with kind `capability_node`; the laptop runs `dax edge enroll --server URL --code CODE --name NAME`.
- Credentials default to `~/.local/state/dax-assistant/edge.json` (`0700` parent, `0600` file). `dax-assistant-node.service` is installed only on request and must not start before enrollment.
- Remote nodes require HTTPS/WSS and connect outbound. Their server-trusted inventory is ephemeral, generation-fenced, policy/approval-gated, and removed immediately on disconnect or revocation.
- Node paths resolve on the node under `DAX_SYSTEM_ROOTS`; shell calls remain server-allowlisted, argv-only, and reject shell metacharacters. Do not describe this as unrestricted shell access.
- Current scope is one live socket per enrolled node and the bundled trusted inventory, not arbitrary remote MCP discovery, queued offline execution, or multi-authority orchestration.
- Production is one `systemd --user` authoritative service. Back up a consistent database together with its matching `dax.key` or external `DAX_MASTER_KEY`; do not support active-active SQLite. See `docs/deployment.md` and `docs/capability-nodes.md`.

## Verification gates

Before declaring desktop work complete, run:

```bash
cd desktop && npm run typecheck && npm test && npm run build && npm audit --omit=dev
cd desktop/src-tauri && cargo fmt --all -- --check && cargo test --all-targets --all-features && cargo clippy --all-targets --all-features -- -D warnings
uv run pytest && uv run ruff check src tests && uv run mypy src
graphify update .
```

Hardware-dependent claims remain separate gates: microphone/speaker behavior, wake-word accuracy, remote audio between two hosts, final PSS/CPU profiling, Wayland HUD placement, and clean package installation must be reported honestly if they were not exercised.
