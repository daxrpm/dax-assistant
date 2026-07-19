# Graph Report - dax-assistant  (2026-07-19)

## Corpus Check
- 267 files · ~166,116 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 4089 nodes · 11279 edges · 232 communities (148 shown, 84 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 2366 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `06c74737`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Bundle Collection Utilities
- Voice Processing Pipeline
- Frontend Runtime Internals
- Agent Tool Policy
- Tree Collection Traversal
- Tool Dispatch Interfaces
- DOM Collection Mutation
- Application Storage Lifecycle
- Agent Message Processing
- OAuth Webhook Integration
- MCP Tool Registry
- Collection Cursor Operations
- Event Scheduling Runtime
- Voice Conversation State
- React Collection Rendering
- Conversation Data Models
- Speech Synthesis Engines
- Shared Web UI Components
- Configuration API Routes
- MCP Configuration Routes
- System API Tests
- Webhook API Tests
- System MCP Server
- Selection and Syntax Utilities
- Core Configuration Models
- Dashboard API Client
- LLM Router Failover
- Logging Event Buffer
- WhatsApp Channel Integration
- TypeScript Compiler Configuration
- Web Dependency Injection
- Human Approval Workflow
- System Status API
- Keyboard Collection Navigation
- MCP Lifecycle Manager
- Secure Configuration Serialization
- Realtime Chat Interface
- Frontend Runtime Dependencies
- Memory File Management
- LLM Provider Factory
- Token Authentication Manager
- MCP Client Connections
- System Prompt Construction
- Frontend Development Dependencies
- Logs and Configuration Types
- Gemini Provider Adapter
- useToast
- Anthropic Provider Adapter
- Encrypted Secret Storage
- Authentication API Routes
- Shell Command Allowlist
- Voice Activity Detection
- Audio Capture Playback
- Shared Test Fixtures
- filter_tools_by_relevance
- Wake Word Detection
- WebSocket Chat Server
- Collection Selection Management
- Configuration Serialization Tests
- Domain Error Hierarchy
- Password Authentication Tests
- Application Settings Models
- Voice Model Downloads
- OpenAI Provider Adapter
- VoiceConfig
- Web Application Entrypoint
- Codex Provider Adapter
- MCP Environment Resolution
- MCP Marketplace Interface
- Project Architecture Overview
- End-to-End Web Tests
- Collection Selection Queries
- Application Shell Theming
- Streaming Speech Synthesis
- Application Command Entrypoint
- Shell Command Parsing
- Remote Voice and Orbita
- Frontend Interaction Utilities
- Single Page Middleware
- Conversation API Routes
- WebSocket Channel Adapter
- Web Authentication Interface
- MCP Session Authentication
- Collection Tree Building
- ln
- Frontend State Utilities
- Production Social Icons
- Authentication Flow Tests
- test_webhooks.py
- Public Social Icons
- Local Voice Technology
- Interactive Installation Script
- Collection Filtering Operations
- SPA HTML Entrypoints
- LLM Routing Architecture
- Speaker Voice Enrollment
- MemoryTab.tsx
- Browser Test Polyfills
- Production Favicon Graphics
- Graphify Project Guidance
- Configuration Precedence Rules
- Graphify OpenCode Plugin
- auth_from_app
- System Service Installer
- Dax Package Metadata
- LLM Providers Package
- MCP Tool Server Lookup
- MCP Servers Package
- System MCP Package
- Voice Processing Package
- I18n.tsx
- mcp_tools_to_openai
- models.py
- Public Favicon Graphics
- Tool Reasoning Controls
- Python Package Metadata
- Secure Remote Access
- Frontend Build Pipeline
- Layered Safety Model
- LLM Environment Secret Resolution
- LLMProvider Port
- LLM Router Failover
- Async Message Bus Spine
- Multichannel Adapters
- Relevance-Budgeted Tool Selection
- Secret Indirection Pattern
- Session-Isolated Conversations
- SQLite Conversation Storage
- Hexagonal Architecture
- Kokoro and Piper TTS
- Layered PC-Control Safety
- openWakeWord
- Pluggable LLM Routing
- Silero VAD
- Voice Activation Conversation Scope
- Local Voice Assistant Pipeline
- test_legacy_oauth_files_migrate_encrypted
- McpServers.tsx
- TestYesNoParser
- getFullNode
- compilerOptions
- 6.2 Parity checklist
- permissions
- 4.2 HTTP routes — complete enumeration
- ._resolve_voice
- whatsapp_webhook
- Dax Desktop — Implementation Plan
- 10. Phased milestones
- 5. Design system specification
- toggle
- .transcribe
- 3. Architecture
- 6.0 SETTINGS INFORMATION ARCHITECTURE (authoritative, 2026-07-19)
- AppShell.tsx
- TestWebSocketAuthCredentials
- .from_config_path
- Dax Desktop
- Desktop System Architecture
- WebChannel
- TestEnums
- Logs.tsx
- build
- get_config
- Synthesizer
- Desktop Validation Gates
- Settings Coverage Contract
- _make_app
- .get_relevant_tools
- tts.py
- Desktop Deployment Packages
- _FallbackSynthesizer
- enroll_voice.py
- test_external_master_key_avoids_local_key_file
- test_settings_coverage.py
- LLM Failover Routing
- Desktop Architecture Boundaries
- Dax Agent Message Flow
- Policy-Gated Tool Execution
- Connection Schema v2
- Open Hardware Validation Gates
- 250 MB PSS Budget
- Tauri Stack Decision
- Separate Voice HUD
- Native First-Run Onboarding
- Wayland HUD Limitations
- Demand-Managed Realtime Stores
- Orbita Canvas Renderer
- Origin-Isolated Authentication Tokens
- Settings Registry Coverage
- Three Desktop Process Layers
- Authenticated Voice WebSocket
- Bounded PCM16 PTT Protocol
- Exclusive Remote Audio Lease
- Source-Separated Level Frames
- Server-Side Remote TTS Limit
- XDG Systemd Deployment
- .__init__
- WebChannel
- datetime
- .get_relevant_tools
- test_settings_coverage.py
- _get_oauth_token
- registry.py
- .unregister_server
- .clear
- .server_lookup
- .get_server_for_tool
- .is_available
- .start
- .stop
- .list_tools
- .get_relevant_tools
- .set_system_prompt
- .stop
- tool_gate.py

## God Nodes (most connected - your core abstractions)
1. `i()` - 172 edges
2. `n()` - 165 edges
3. `Message` - 158 edges
4. `t()` - 155 edges
5. `r()` - 143 edges
6. `MessageBus` - 115 edges
7. `a()` - 111 edges
8. `s()` - 100 edges
9. `push()` - 95 edges
10. `VoicePipeline` - 85 edges

## Surprising Connections (you probably didn't know these)
- `ModelSelector()` --indirect_call--> `m()`  [INFERRED]
  web/src/pages/Chat.tsx → src/dax/web/static/assets/index-CtpIuQcu.js
- `Production SPA Shell` --semantically_similar_to--> `Development SPA Shell`  [INFERRED] [semantically similar]
  src/dax/web/static/index.html → web/index.html
- `Native Linux Client` --conceptually_related_to--> `Dax Blue App Icon Master`  [INFERRED]
  README.md → desktop/src-tauri/icons/icon.png
- `CommandPalette()` --indirect_call--> `index()`  [INFERRED]
  desktop/src/components/CommandPalette.tsx → src/dax/web/static/assets/index-CtpIuQcu.js
- `CommandPalette()` --indirect_call--> `q()`  [INFERRED]
  desktop/src/components/CommandPalette.tsx → src/dax/web/static/assets/index-CtpIuQcu.js

## Import Cycles
- 1-file cycle: `desktop/src/screens/settings/registry.ts -> desktop/src/screens/settings/registry.ts`

## Hyperedges (group relationships)
- **Dax Async Message Lifecycle** — claude_multichannel_adapters, claude_message_bus_spine, claude_sqlite_conversation_storage, claude_llm_router_failover [EXTRACTED 1.00]
- **Dax Human-in-the-Loop Safety** — claude_dax_system_mcp_server, claude_approval_manager, claude_layered_safety_model, claude_web_realtime_protocol [EXTRACTED 1.00]
- **Local Voice Processing Stack** — readme_voice_assistant_pipeline, readme_openwakeword, readme_silero_vad, readme_faster_whisper, readme_kokoro_piper_tts [EXTRACTED 1.00]
- **Desktop Process Boundary Model** — agents_backend_source_of_truth, docs_desktop_architecture_three_process_layers, desktop_plan_tauri_stack_decision [EXTRACTED 1.00]
- **Remote Voice v1 Flow** — docs_voice_websocket_authenticated_voice_socket, docs_voice_websocket_exclusive_remote_audio_lease, docs_voice_websocket_bounded_pcm_protocol, readme_remote_voice_limit [EXTRACTED 1.00]
- **Orbita Realtime Rendering** — docs_desktop_architecture_demand_managed_realtime_stores, docs_desktop_architecture_orbita_canvas_renderer, docs_voice_websocket_source_separated_level_frames, desktop_plan_voice_hud [EXTRACTED 1.00]

## Communities (232 total, 84 thin omitted)

### Community 0 - "Bundle Collection Utilities"
Cohesion: 0.01
Nodes (151): ab(), addChild(), addDescendants(), addNode(), addText(), addTreeNode(), ak(), an() (+143 more)

### Community 1 - "Voice Processing Pipeline"
Cohesion: 0.06
Nodes (23): CallbackFlags, AudioPlayer, AudioSource, LocalAudioSource, ndarray, Protocol, Audio I/O — microphone capture and speaker playback.  Uses sounddevice for cross, sounddevice callback — runs on the audio thread. (+15 more)

### Community 2 - "Frontend Runtime Internals"
Cohesion: 0.06
Nodes (85): aa(), ac(), ae(), ao(), Ba(), bc(), Bi(), cc() (+77 more)

### Community 3 - "Agent Tool Policy"
Cohesion: 0.21
Nodes (12): DaxError, Exception, Domain exception hierarchy for Dax Assistant., MCP tool execution failed., Requested tool does not exist in the registry., Tool was found but execution failed., Database or persistence operation failed., Base exception for all Dax errors. (+4 more)

### Community 4 - "Tree Collection Traversal"
Cohesion: 0.09
Nodes (105): _(), aj(), ar(), b(), be(), br(), C(), ck() (+97 more)

### Community 5 - "Tool Dispatch Interfaces"
Cohesion: 0.12
Nodes (38): AtomicU64, analyze_spectrum(), CommandOutput, control(), current_player(), discover_players(), DuckingSession, DuckingState (+30 more)

### Community 6 - "DOM Collection Mutation"
Cohesion: 0.06
Nodes (110): a(), Ad(), add(), addEventListener(), Au(), bf(), bu(), ca() (+102 more)

### Community 7 - "Application Storage Lifecycle"
Cohesion: 0.03
Nodes (51): DaxApp, Apply the configured prompt to the live agent for its next turn., Expose FastAPI app for testing., Restart the Telegram channel to apply config changes without a full         app, Shut down all components in reverse order., Run the application with embedded uvicorn server., Run shutdown to completion even if uvicorn/request cancellation leaks., Signal handler — request graceful shutdown. (+43 more)

### Community 8 - "Agent Message Processing"
Cohesion: 0.09
Nodes (26): BadgeTone, ButtonProps, ButtonSize, ButtonVariant, Checkbox(), CodeBlock(), EmptyState(), IconButton() (+18 more)

### Community 9 - "OAuth Webhook Integration"
Cohesion: 0.07
Nodes (55): HTMLResponse, auth_logout(), auth_status(), _AuthStartResponse, _callback_html(), configure_oauth_store(), _delete_tokens(), _discover_auth() (+47 more)

### Community 10 - "MCP Tool Registry"
Cohesion: 0.12
Nodes (10): Tool registry — aggregates tools from all MCP servers.  Provides lookup by tool, Aggregates tool schemas from multiple MCP servers.      Maintains a mapping of t, Remove all tools belonging to a server (e.g. on disconnect)., Remove all registered tools., Return the tool_name → server_name mapping., Look up which server owns a tool., ToolRegistry, _make_tools() (+2 more)

### Community 11 - "Collection Cursor Operations"
Cohesion: 0.09
Nodes (36): __addSublanguage(), Bw(), bx(), consume(), currentNode(), cx(), ek(), fx() (+28 more)

### Community 12 - "Event Scheduling Runtime"
Cohesion: 0.15
Nodes (24): account(), clear(), delete(), entry(), get(), memory_fallback(), read(), Mutex (+16 more)

### Community 13 - "Voice Conversation State"
Cohesion: 0.04
Nodes (49): LevelSource, Which side of the conversation a level frame describes., _clean_for_speech(), _ends_with_question(), PipelineState, ndarray, StrEnum, Voice pipeline — wake word, listen, transcribe, respond.  Runs in a dedicated th (+41 more)

### Community 14 - "React Collection Rendering"
Cohesion: 0.07
Nodes (56): Av(), bg(), canSelectItem(), clearSelection(), Cm(), Dm(), Eg(), extendSelection() (+48 more)

### Community 15 - "Conversation Data Models"
Cohesion: 0.15
Nodes (30): BackendResolution, BackendSettings, BackendState, BackendStrategy, decode_settings(), is_loopback_host(), is_loopback_url(), LegacyMode (+22 more)

### Community 16 - "Speech Synthesis Engines"
Cohesion: 0.07
Nodes (34): currentToken(), ArrowDownIcon(), AgentEvent, ChatMessage, ChatSnapshot, ChatStatus, ChatStore, chatStores (+26 more)

### Community 17 - "Shared Web UI Components"
Cohesion: 0.12
Nodes (9): ndarray, Voice Activity Detection via Silero VAD.  Wraps Silero VAD behind a chunk-orient, Reset the iterator state between utterances., Detect speech start and end boundaries in streaming audio.      Args:         th, Load the Silero VAD model and create the iterator., Release model resources., Process a single VAD-sized audio chunk.          Args:             audio_chunk:, Return the raw speech probability (0..1) for a VAD-sized chunk.          Used by (+1 more)

### Community 18 - "Configuration API Routes"
Cohesion: 0.17
Nodes (20): File, _decode_enrollment_wav(), delete_voice_profile(), _encode_wav(), enroll_voice(), get_voice_profile(), preview_voice(), _push_to_talk() (+12 more)

### Community 19 - "MCP Configuration Routes"
Cohesion: 0.08
Nodes (13): Initialize all components in dependency order., Serialize live voice reloads so repeated UI saves remain safe., Restart the voice channel and pipeline with the live configuration., Voice channel adapter — bridges the dispatcher to the voice pipeline.  The voice, Voice channel adapter for the dispatcher.      Inbound messages are published by, No-op — the voice pipeline manages its own lifecycle., No-op — the voice pipeline manages its own lifecycle., Enqueue an outbound message for the voice pipeline to consume.          Called b (+5 more)

### Community 20 - "System API Tests"
Cohesion: 0.06
Nodes (22): Web channel — delegates to WebSocket manager.  The actual WebSocket handling is, Web UI channel adapter.      Bridges between the dispatcher and the WebSocket ma, Broadcast a message to all connected WebSocket clients., WebChannel, app(), bus(), client(), AsyncClient (+14 more)

### Community 21 - "Webhook API Tests"
Cohesion: 0.08
Nodes (29): create_app(), FastAPI, FastAPI application factory.  Creates the web server with lifespan management, C, Create and configure the FastAPI application., A fresh install must serve the desktop app without config changes.      The webv, test_desktop_webview_origin_is_allowed_by_default(), app(), bus() (+21 more)

### Community 22 - "System MCP Server"
Cohesion: 0.09
Nodes (17): FastMCP, main(), Run the dax-system MCP server over stdio: python -m dax.mcp_servers.system, allowed_roots(), build_server(), Path, `dax-system` — a local MCP server exposing safe, typed PC-control tools.  Runs a, Construct the FastMCP server with all dax-system tools registered. (+9 more)

### Community 23 - "Selection and Syntax Utilities"
Cohesion: 0.07
Nodes (43): A request to execute an MCP tool., ToolCall, Resolves an allow/ask/deny decision for a tool name., ToolPolicy, LLMProvider, Protocol, Protocol interfaces (ports) for the hexagonal architecture.  All adapters implem, Return the server that owns ``tool_name``, or None if unknown. (+35 more)

### Community 24 - "Core Configuration Models"
Cohesion: 0.11
Nodes (29): AnthropicProviderConfig, CodexProviderConfig, DeepSeekProviderConfig, GeminiProviderConfig, MCPConfig, OllamaProviderConfig, OpenAIProviderConfig, BaseModel (+21 more)

### Community 25 - "Dashboard API Client"
Cohesion: 0.13
Nodes (16): useLogStream(), wsUrl(), LEVEL_COLOR, LEVELS, LogsPage(), GeneralConfig, LLMConfig, LogEntry (+8 more)

### Community 26 - "LLM Router Failover"
Cohesion: 0.13
Nodes (12): LLMError, LLMProviderUnavailableError, LLM provider communication failed., No LLM provider is available to handle the request., LLMRouter, Any, LLM router — local-first fallback across decoupled providers.  Holds an ordered, Routes completion requests across an ordered list of providers. (+4 more)

### Community 27 - "Logging Event Buffer"
Cohesion: 0.16
Nodes (9): LogRecord, LogBuffer, AbstractEventLoop, Any, Queue, Stdlib log handler that retains recent records and fans them out live., Register the event loop used to deliver live records to subscribers., Return the most recent records (oldest first), capped at ``limit``. (+1 more)

### Community 28 - "WhatsApp Channel Integration"
Cohesion: 0.06
Nodes (25): Any, Telegram channel — long-polling bot via the Telegram Bot API.  Uses long-polling, Deliver an assistant reply back to the originating Telegram chat., Split text into chunks no longer than *limit* characters., Telegram bot channel using long-polling., Long-poll getUpdates and publish inbound text messages to the bus., _split_message(), TelegramChannel (+17 more)

### Community 29 - "TypeScript Compiler Configuration"
Cohesion: 0.08
Nodes (25): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+17 more)

### Community 30 - "Web Dependency Injection"
Cohesion: 0.12
Nodes (28): approval_from_app(), auth_from_app(), bus_from_app(), get_approval(), get_auth(), get_bus(), get_config(), get_llm_router() (+20 more)

### Community 32 - "System Status API"
Cohesion: 0.12
Nodes (28): get_host_metrics(), get_logs(), get_mcp_status(), get_status(), get_tool_audit(), get_tool_policy(), HostMetricsResponse, list_llm_models() (+20 more)

### Community 33 - "Keyboard Collection Navigation"
Cohesion: 0.07
Nodes (20): Message, Return the most recent message, or None if empty., A single message in a conversation.      Immutable value object. All messages fl, Append a message and update the timestamp., Send a completion request and return the assistant's response.          Args:, MessageBus, Async message bus for inter-component communication.  Decouples channels from th, Async message bus using asyncio queues.      Thread-safe for posting from voice (+12 more)

### Community 34 - "MCP Lifecycle Manager"
Cohesion: 0.15
Nodes (9): MCPServerConfig, MCPManager, Launch and connect to all enabled MCP servers., Connect to a server and register its tools live. Returns tool count.          Re, Disconnect a server (if connected) and drop its tools., Disconnect a server from the MCP lifecycle worker task., Disconnect from all MCP servers., Return which server owns ``tool_name`` (ToolProvider port). (+1 more)

### Community 35 - "Secure Configuration Serialization"
Cohesion: 0.11
Nodes (30): Mirror the live shell allowlist into encrypted configuration., _del_path(), dump_config_toml(), _env_var_for_header(), _env_var_for_mcp_env(), _extract_secrets(), _get_path(), _is_sensitive_header() (+22 more)

### Community 36 - "Realtime Chat Interface"
Cohesion: 0.11
Nodes (16): ConversationSummary, Markdown, Modal(), AgentEvent, ChatMessage, ConfirmationRequest, nextId(), Status (+8 more)

### Community 37 - "Frontend Runtime Dependencies"
Cohesion: 0.07
Nodes (71): api, FullConfig, MemoryType, RegistryServer, AlertIcon(), PlayIcon(), PlusIcon(), RefreshIcon() (+63 more)

### Community 38 - "Memory File Management"
Cohesion: 0.26
Nodes (20): create_memory(), delete_memory(), get_memory(), list_memory(), _memory_dir(), _memory_frontmatter(), _memory_path(), _memory_slug() (+12 more)

### Community 39 - "LLM Provider Factory"
Cohesion: 0.17
Nodes (15): LLMConfig, LLMConfig, LLM routing and provider configuration.      The local Ollama provider is the de, build_provider(), build_providers(), build_router(), _ollama_base_url(), Build the LLM router and providers from configuration.  This is the single place (+7 more)

### Community 40 - "Token Authentication Manager"
Cohesion: 0.11
Nodes (13): SecurityConfig, AuthManager, Request, Response, WebSocket, Extract the token from an ``Authorization: Bearer <token>`` header., Every credential the request offers, in preference order.          The browser S, First offered credential, or ``None``. Kept for compatibility. (+5 more)

### Community 41 - "MCP Client Connections"
Cohesion: 0.13
Nodes (10): MCPClient, Any, MCP client wrapper — manages a connection to a single MCP server.  Supports two, Connect via Streamable HTTP transport (remote server)., Close the session and terminate any subprocesses., Clean up resources, suppressing anyio cancel scope errors., Query the server for available tools and return their schemas., Wraps a connection to a single MCP server.      Args:         server_name: Uniqu (+2 more)

### Community 42 - "System Prompt Construction"
Cohesion: 0.12
Nodes (18): Any, System-prompt assembly for the agent.  Builds the per-turn system prompt from th, Append a concrete live tool inventory to the base system prompt.      Grouping b, Assembles the per-turn system prompt (tools + memory + voice style)., Replace the editable base prompt for subsequent turns., Return the full system prompt for this turn., Read user-curated memory files and format them for the system prompt.          E, SystemPromptBuilder (+10 more)

### Community 43 - "Frontend Development Dependencies"
Cohesion: 0.15
Nodes (16): _bootstrap_only(), _bootstrap_secrets(), _flatten_toml(), load_config(), Any, Path, Load encrypted configuration, importing a legacy TOML once when present.      Ar, Seed os.environ from the encrypted secret store before config is built.      Sec (+8 more)

### Community 44 - "Logs and Configuration Types"
Cohesion: 0.08
Nodes (52): browserDefaults(), clearToken(), connectionCandidates(), getConnectionSettings(), getWsUrl(), isLoopbackUrl(), isTauri(), loadConnectionSettings() (+44 more)

### Community 45 - "Gemini Provider Adapter"
Cohesion: 0.15
Nodes (9): Content, LLMTimeoutError, LLM request timed out., GeminiProvider, Any, Google Gemini provider adapter — official `google-genai` SDK.  Translates the Op, Implements the LLMProvider port over the Gemini generateContent API., TestGeminiProvider (+1 more)

### Community 46 - "useToast"
Cohesion: 0.11
Nodes (36): MCPServerConfig, Configuration for a single MCP server.      Supports two transport modes:     -, add_mcp_server(), delete_mcp_server(), get_claude_config(), get_codex_config(), get_system_shell_allow(), list_mcp_servers() (+28 more)

### Community 47 - "Anthropic Provider Adapter"
Cohesion: 0.19
Nodes (5): AnthropicProvider, Any, Anthropic (Claude) provider adapter — official `anthropic` SDK.  Translates the, Implements the LLMProvider port over the Anthropic Messages API., TestAnthropicProvider

### Community 48 - "Encrypted Secret Storage"
Cohesion: 0.13
Nodes (11): Connection, Path, Encrypted secret storage backed by SQLite.  Replaces the legacy ``.env`` file as, Seed ``os.environ`` from the store without clobbering real env vars.          Re, One-time migration: import ``KEY=value`` lines from a legacy .env.          Only, Encrypted key/value secret store on top of SQLite + a Fernet key file., Encrypt and persist a secret; also export it to ``os.environ``., SecretStore (+3 more)

### Community 49 - "Authentication API Routes"
Cohesion: 0.18
Nodes (20): AuthDep, auth_status(), AuthStatus, health(), HealthResponse, login(), LoginRequest, LoginResponse (+12 more)

### Community 50 - "Shell Command Allowlist"
Cohesion: 0.07
Nodes (22): build_messages_for_llm(), Any, Shared LLM helpers: the system prompt and the message builder.  The conversation, Build the OpenAI-format message list for an LLM call.      Converts our Message, Remove provider control markup that must never reach users or TTS., sanitize_assistant_text(), Any, Core agent loop — the brain of Dax Assistant.  Receives messages from the bus, s (+14 more)

### Community 51 - "Voice Activity Detection"
Cohesion: 0.08
Nodes (15): PipelineState, Voice pipeline component failed., VoiceError, Session scoping — what gives consecutive voice turns shared memory.      The ses, Back-to-back wake words must share one conversation., Once the user has been away long enough, context is dropped., session_ttl_minutes=0 opts back into a fresh session every time., An explicit goodbye drops context immediately, without waiting. (+7 more)

### Community 52 - "Audio Capture Playback"
Cohesion: 0.09
Nodes (37): ApiError, authHeaders(), request(), requestBlob(), requestForm(), responseError(), getBaseUrl(), AuthStatus (+29 more)

### Community 53 - "Shared Test Fixtures"
Cohesion: 0.13
Nodes (15): config_from_file(), database(), default_config(), isolate_config_env(), message_bus(), MonkeyPatch, Path, Shared test fixtures for Dax Assistant. (+7 more)

### Community 54 - "filter_tools_by_relevance"
Cohesion: 0.05
Nodes (41): PiperVoice, Voice pipeline configuration., VoiceConfig, Text-to-speech synthesis failed., TTSError, _build_local_tts(), _build_piper(), build_tts() (+33 more)

### Community 55 - "Wake Word Detection"
Cohesion: 0.05
Nodes (65): AppShell(), THEME_ORDER, CommandPalette(), fold(), PALETTE_ROUTES, PaletteRoute, ActivityIcon(), BrainIcon() (+57 more)

### Community 56 - "WebSocket Chat Server"
Cohesion: 0.19
Nodes (9): Any, WebSocket, WebSocket chat endpoint for the web UI.  Handles inbound messages from browser c, Manages active WebSocket connections.      For a single-user assistant, we typic, Send data to a specific WebSocket connection., Send data to all connected WebSocket clients., WebSocket endpoint for real-time chat with Dax.      Protocol:         Client se, websocket_chat() (+1 more)

### Community 58 - "Configuration Serialization Tests"
Cohesion: 0.09
Nodes (26): BaseSettings, PydanticBaseSettingsSource, DaxConfig, How a secret field is represented in the persisted TOML., SecretMode, Root configuration for Dax Assistant.      Settings are loaded in order of prior, Path, Tests for TOML config serialization + secret extraction (config_io). (+18 more)

### Community 59 - "Domain Error Hierarchy"
Cohesion: 0.12
Nodes (17): Audio troubleshooting, Choosing / adding LLM providers, Configuration, Dax Assistant, Desktop client, Development, Development quick start, Highlights (+9 more)

### Community 60 - "Password Authentication Tests"
Cohesion: 0.19
Nodes (11): hash_password(), _main(), Single-user authentication for the web UI and API.  Dax is a personal assistant:, Return an argon2id hash of ``password``., Check ``password`` against a stored argon2 hash., verify_password(), auth_app(), auth_client() (+3 more)

### Community 61 - "Application Settings Models"
Cohesion: 0.09
Nodes (9): Allow / ask / deny policy for tool execution (fnmatch patterns).      An empty `, ToolPolicyConfig, Decision, StrEnum, Update rules in place so the agent picks them up without a restart., In-memory storage that actually resumes conversations by session key., _StatefulStorage, Tests for the tool execution policy. (+1 more)

### Community 62 - "Voice Model Downloads"
Cohesion: 0.21
Nodes (13): _download(), download_kokoro(), download_piper_voices(), download_wake_word(), download_whisper(), main(), Path, Download voice models for Dax Assistant.  Fetches everything the voice pipeline (+5 more)

### Community 63 - "OpenAI Provider Adapter"
Cohesion: 0.16
Nodes (6): OpenAIProvider, Any, OpenAI provider adapter — official `openai` SDK (Chat Completions).  Also serves, Implements the LLMProvider port over the OpenAI Chat Completions API., Tests for the multi-provider LLM layer: adapters, router and factory., TestOpenAIProvider

### Community 64 - "VoiceConfig"
Cohesion: 0.17
Nodes (11): description, identifier, core:default, linux, macOS, windows, permissions, platforms (+3 more)

### Community 65 - "Web Application Entrypoint"
Cohesion: 0.12
Nodes (23): copy(), data(), Tabs(), useToast(), useConfig(), ExportPanel(), McpPage(), GeneralTab() (+15 more)

### Community 66 - "Codex Provider Adapter"
Cohesion: 0.19
Nodes (6): CodexProvider, Any, OpenAI Codex CLI provider.  Runs ``codex exec --json`` as a subprocess to use th, Parse the JSONL event stream and return the final agent message., Implements the LLMProvider port over the Codex CLI (`codex exec`)., Collapse the chat history into a single prompt string for Codex.          Codex

### Community 67 - "MCP Environment Resolution"
Cohesion: 0.13
Nodes (12): _get_oauth_token(), MCP server manager — implements the ToolProvider protocol.  Manages the lifecycl, Build an unconnected client for a server config (env resolved)., Replace {env:VAR_NAME} patterns with environment variable values., Resolve env vars in all values of a dict., Snapshot desktop-session vars present in the current environment., Get stored OAuth access token for an MCP server, if available., _resolve_env_dict() (+4 more)

### Community 68 - "MCP Marketplace Interface"
Cohesion: 0.36
Nodes (12): api, Badge(), Field(), Panel(), PanelHeader(), Select(), TextArea(), TextInput() (+4 more)

### Community 69 - "Project Architecture Overview"
Cohesion: 0.15
Nodes (11): Architecture, Channels (`channels/`), Commands, Config & secrets (`core/config.py`, `core/config_io.py`), LLM layer (`llm/`) — fully decoupled behind the `LLMProvider` port, MCP (`mcp/`) and the bundled server, Message flow (the spine), Safety model (+3 more)

### Community 70 - "End-to-End Web Tests"
Cohesion: 0.11
Nodes (14): Any, Queue, Voice event transport — thread-to-loop fan-out with no optional deps.  Lives in, The most recent state event, replayed to clients on connect.          Without th, Register a new subscriber and return its queue., Remove a subscriber's queue., Publish *event* to all subscribers. Safe to call from any thread.          Never, Push *event* onto every subscriber queue. Runs on the event loop. (+6 more)

### Community 71 - "Collection Selection Queries"
Cohesion: 0.07
Nodes (37): CommandDeck(), LiveOrb(), Meter(), MetricsPane(), PIPELINE_KEY, ToolRun, toOrbState(), useToolRuns() (+29 more)

### Community 72 - "Application Shell Theming"
Cohesion: 0.08
Nodes (46): formatMediaTime(), hashTrack(), mediaProvider, NowPlaying(), NowPlayingView(), progressWaveform(), media, RESIZE_HANDLES (+38 more)

### Community 73 - "Streaming Speech Synthesis"
Cohesion: 0.40
Nodes (3): Path, Smoke tests for the portable Linux installer., test_installer_dry_run_uses_xdg_layout()

### Community 74 - "Application Command Entrypoint"
Cohesion: 0.09
Nodes (13): Channel, Input/output channel for user interaction.      Channels receive messages from u, Unique channel identifier (e.g., 'voice', 'whatsapp', 'web')., Initialize and begin listening for messages., Gracefully shut down the channel., Yield incoming messages from this channel., Deliver a response message through this channel., Dispatcher (+5 more)

### Community 75 - "Shell Command Parsing"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 76 - "Remote Voice and Orbita"
Cohesion: 0.29
Nodes (6): Desktop architecture, Desktop behavior, graphify, Project architecture, Realtime contracts, Verification gates

### Community 78 - "Single Page Middleware"
Cohesion: 0.24
Nodes (7): Scope, Response, SPA-aware static file serving.  Subclasses Starlette's StaticFiles to return ind, StaticFiles that falls back to index.html for SPA routing.      For any path tha, Serve index.html as fallback., SPAStaticFiles, StaticFiles

### Community 79 - "Conversation API Routes"
Cohesion: 0.27
Nodes (9): delete_conversation(), get_conversation(), list_conversations(), Any, Request, Conversation history endpoints — list, fetch, delete web chats., List recent web conversations for the sidebar., Return a conversation with its messages. (+1 more)

### Community 80 - "WebSocket Channel Adapter"
Cohesion: 0.07
Nodes (16): The result of an MCP tool execution., ToolResult, Execute a tool call on the appropriate MCP server., Execute a tool call on this server., Execute a tool call on the appropriate MCP server., Apply the policy. Returns a blocking ToolResult, or None to proceed., Gate a shell_run call against the user-managed command allowlist.          Allow, Record a tool execution decision to the audit log, if supported. (+8 more)

### Community 81 - "Web Authentication Interface"
Cohesion: 0.31
Nodes (8): LevelSource, compute_level_frame(), emit_level(), Any, ndarray, Audio metering — turn raw capture chunks into compact waveform frames.  The tran, Reduce a raw audio chunk to a compact envelope + spectrum frame.      Args:, Emit a level frame for *chunk* on *hub*. No-op with no subscribers.      The sub

### Community 84 - "ln"
Cohesion: 0.08
Nodes (37): announce(), at(), bd(), bj(), Bp(), Bv(), canSelectItemIn(), cf() (+29 more)

### Community 86 - "Production Social Icons"
Cohesion: 0.48
Nodes (7): Bluesky Icon, Discord Icon, Documentation and Code Icon, GitHub Icon, Social Profile Icon, Web Icon Sprite, X Social Platform Icon

### Community 87 - "Authentication Flow Tests"
Cohesion: 0.15
Nodes (7): AsyncClient, FastAPI, The desktop client can't rely on a SameSite=lax cookie from a webview     custom, A cookie left over from a previous session must not shadow a good         bearer, Regression guard: the existing web UI must keep working., TestAuthFlow, TestBearerToken

### Community 88 - "test_webhooks.py"
Cohesion: 0.10
Nodes (40): persist_config(), Persist the live configuration as an encrypted SQLite document.      The single, change_password(), ChangePasswordRequest, GeneralConfigUpdate, get_config(), LLMConfigUpdate, Any (+32 more)

### Community 89 - "Public Social Icons"
Cohesion: 0.29
Nodes (7): Bluesky Butterfly Icon, Discord Mascot Icon, Documentation and Code Icon, GitHub Octocat Icon, Social and Navigation Icon Sprite, Social Profile and Star Icon, X Social Network Icon

### Community 91 - "Interactive Installation Script"
Cohesion: 0.24
Nodes (24): backup_database(), confirm(), die(), doctor(), download_models(), enable_service(), ensure_command(), ensure_uv() (+16 more)

### Community 93 - "SPA HTML Entrypoints"
Cohesion: 0.50
Nodes (4): Built Frontend Assets, Production SPA Shell, Development SPA Shell, React TypeScript Entrypoint

### Community 95 - "Speaker Voice Enrollment"
Cohesion: 0.12
Nodes (17): App(), createRemotePtt(), encodePcm16(), pushToTalk, RemoteMicrophone, remotePtt, resampleMono(), StreamingMonoResampler (+9 more)

### Community 96 - "MemoryTab.tsx"
Cohesion: 0.07
Nodes (45): Locale, APPLY_CLASS, APPLY_KEY, asNumber(), asString(), FieldControl(), FieldLabel(), fromIntLines() (+37 more)

### Community 98 - "Production Favicon Graphics"
Cohesion: 0.50
Nodes (4): Favicon Graphic, Lightning Bolt Symbol, Purple Angular Mark, Soft Glow Highlights

### Community 102 - "auth_from_app"
Cohesion: 0.15
Nodes (13): StrEnum, Discriminator for events on the voice stream., VoiceEventType, _idle_state(), _lease_from_app(), _pipeline_from_app(), Any, Exception (+5 more)

### Community 110 - "I18n.tsx"
Cohesion: 0.22
Nodes (9): Connection strategy, Desktop Architecture, First-run onboarding, Orbita rendering, Process boundaries, Realtime stores, Settings contract, Verification (+1 more)

### Community 111 - "mcp_tools_to_openai"
Cohesion: 0.07
Nodes (28): app, security, windows, build, beforeBuildCommand, beforeDevCommand, devUrl, frontendDist (+20 more)

### Community 112 - "models.py"
Cohesion: 0.33
Nodes (4): MCPServerStatus, ToolAuditEntry, useStatus(), DashboardPage()

### Community 150 - "test_legacy_oauth_files_migrate_encrypted"
Cohesion: 0.07
Nodes (27): compilerOptions, allowImportingTsExtensions, exactOptionalPropertyTypes, isolatedModules, jsx, lib, module, moduleResolution (+19 more)

### Community 151 - "McpServers.tsx"
Cohesion: 0.07
Nodes (29): Speech-to-text transcription failed., STTError, _build_prompt(), build_stt(), FallbackSpeechToText, OpenAISpeechToText, ndarray, VoiceConfig (+21 more)

### Community 152 - "TestYesNoParser"
Cohesion: 0.10
Nodes (46): af(), ah(), ap(), appendChild(), bt(), co(), createElement(), destroy() (+38 more)

### Community 153 - "getFullNode"
Cohesion: 0.09
Nodes (18): ApiError, AuthStatus, ConversationDetail, ConversationMessage, MemoryEntry, OllamaModel, requestBlob(), responseError() (+10 more)

### Community 154 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowSyntheticDefaultImports, composite, declarationDir, emitDeclarationOnly, isolatedModules, lib, module (+10 more)

### Community 155 - "6.2 Parity checklist"
Cohesion: 0.13
Nodes (12): filter_tools_by_relevance(), mcp_tools_to_openai(), parse_tool_calls_from_response(), Any, Maps MCP tool schemas to OpenAI function-calling format.  We use the OpenAI tool, Convert a list of MCP tool schemas to OpenAI function-calling format.      MCP f, Filter tools based on keyword relevance to the user's query.      Always include, Parse tool calls from a litellm response into our internal format.      Args: (+4 more)

### Community 156 - "permissions"
Cohesion: 0.08
Nodes (24): description, identifier, core:default, linux, macOS, windows, permissions, platforms (+16 more)

### Community 157 - "4.2 HTTP routes — complete enumeration"
Cohesion: 0.22
Nodes (9): 7. Milestone Results, M0 - Risk spike: passed (2026-07-18), M1 - Foundation: passed with visual caveat (2026-07-18), M2 - Chat: automated gate passed, M3 - Settings and screens: automated gate passed, M4 - Voice and HUD: software gate passed; hardware gate open, M5 - Native polish: software gate passed; human accessibility gate open, M6 - Packaging: build gate passed; clean-install gate open (+1 more)

### Community 158 - "._resolve_voice"
Cohesion: 0.10
Nodes (35): ai(), al(), bl(), bs(), dd(), es(), ex(), fl() (+27 more)

### Community 159 - "whatsapp_webhook"
Cohesion: 0.16
Nodes (13): BusDep, _extract_text(), Any, BaseModel, ConfigDep, Request, Response, Evolution API v2 webhook receiver.  Handles incoming WhatsApp messages (text and (+5 more)

### Community 160 - "Dax Desktop — Implementation Plan"
Cohesion: 0.25
Nodes (8): 10. Remaining Gates, 11. Ground Truth, 1. Scope, 5. Settings 6.0, 6. Voice HUD, 8. Automated Release Gate, 9. Reproducible Commands, Dax Desktop - Implementation Record

### Community 161 - "10. Phased milestones"
Cohesion: 0.20
Nodes (8): _configure_logging(), Path, Application bootstrap and lifecycle management.  Wires all components together v, Create a DaxApp instance from a config file path., Set up structlog with console rendering., main(), Entry point for running Dax Assistant: python -m dax, Parse arguments and run the application.

### Community 162 - "5. Design system specification"
Cohesion: 0.33
Nodes (6): 2. Closed Decisions, D1. Tauri v2 + Rust + React, D2. Same repository, D3. Native-inspired design, Linux first, D4. Python voice pipeline remains server-side, D5. Performance uses measured PSS

### Community 163 - "toggle"
Cohesion: 0.23
Nodes (14): handle_shortcut(), hide(), AppHandle, Option, R, Result, String, shortcut_action() (+6 more)

### Community 165 - "3. Architecture"
Cohesion: 0.33
Nodes (6): 3.1 Local deployment, 3.2 Remote deployment and URL security, 3.3 Native boundary, 3.4 Frontend loading and state, 3.5 Internationalization, 3. Shipped Architecture

### Community 166 - "6.0 SETTINGS INFORMATION ARCHITECTURE (authoritative, 2026-07-19)"
Cohesion: 0.40
Nodes (5): 4.1 Authentication and CORS, 4.2 Chat and `session_id`, 4.3 Voice state and expiry, 4.4 Remote audio protocol v1, 4. Backend Contracts

### Community 167 - "AppShell.tsx"
Cohesion: 0.10
Nodes (19): fail(), info(), message(), AppShell(), NAV, NavItem, TITLES, ThemeToggle() (+11 more)

### Community 169 - ".from_config_path"
Cohesion: 0.14
Nodes (6): Runtime allowlist of shell binaries the assistant may run on this PC.  This is t, Extract the bare binary name from a command string (``/bin/ls -l`` → ``ls``)., shell_binary(), Tests for the shell-command allowlist., TestShellAllowlist, TestShellBinary

### Community 170 - "Dax Desktop"
Cohesion: 0.25
Nodes (8): Dax Desktop, Desarrollo, Implementación, Límites verificados, Paquetes, Primera ejecución y conexión, Requisitos, Verificación reproducible

### Community 171 - "Desktop System Architecture"
Cohesion: 0.33
Nodes (6): Desktop React Entrypoint, Dax Blue App Icon 256, Dax Blue App Icon 128, Dax Blue App Icon 32, Dax Blue App Icon Master, Native Linux Client

### Community 172 - "WebChannel"
Cohesion: 0.14
Nodes (20): Ag(), CollectionBranch(), CollectionRoot(), Ef(), fp(), gp(), hg(), Hp() (+12 more)

### Community 173 - "TestEnums"
Cohesion: 0.15
Nodes (33): BackendResolution, BackendSettings, BackendStrategy, backend_resolve(), backend_settings_get(), backend_settings_set(), main_window_hide(), main_window_minimize() (+25 more)

### Community 174 - "Logs.tsx"
Cohesion: 0.20
Nodes (21): apply_frame(), apply_saved_frame(), decode_settings(), hide(), LegacyWindowSettings, main_window(), minimize(), persist_settings() (+13 more)

### Community 175 - "build"
Cohesion: 0.31
Nodes (8): build(), focus_main(), menu_action(), MenuAction, AppHandle, Option, R, Result

### Community 183 - "_make_app"
Cohesion: 0.17
Nodes (20): FakePipeline, _make_app(), Tests for the /ws/voice event stream.  The subscriber lifecycle matters more tha, A leaked subscriber would keep the pipeline metering forever., Build an app with a voice hub attached, mirroring DaxApp wiring., A client must get a definite starting state, not silence., Connecting mid-conversation must not render as idle., test_connect_replays_last_state() (+12 more)

### Community 188 - "enroll_voice.py"
Cohesion: 0.08
Nodes (17): main(), ndarray, Enroll the owner's voice for speaker verification (Voice ID).  Records a few sho, _record(), ndarray, Speaker verification (Voice ID) via Resemblyzer.  Optional, Alexa-style "only re, Compute a voice embedding for *audio* (float32, 16 kHz mono)., Return True if *audio* matches the owner (or if verification is off).          A (+9 more)

### Community 189 - "test_external_master_key_avoids_local_key_file"
Cohesion: 0.40
Nodes (4): MonkeyPatch, Path, Encrypted secret-store tests., test_external_master_key_avoids_local_key_file()

### Community 190 - "test_settings_coverage.py"
Cohesion: 0.36
Nodes (3): Remote input v1, Reproducible checks, Voice WebSocket protocol

### Community 213 - ".__init__"
Cohesion: 0.12
Nodes (12): Wake word detection failed., WakeWordError, AbstractEventLoop, VoiceConfig, ndarray, Wake word detection via OpenWakeWord.  Wraps the OpenWakeWord inference model be, Reset the model's internal state between activations., Detect wake words in streaming audio chunks.      Args:         model_names: Lis (+4 more)

### Community 214 - "WebChannel"
Cohesion: 0.19
Nodes (9): Language, MessageRole, StrEnum, Role of a message participant., Supported languages for voice interaction., _PTTCommand, Map a Whisper language code to the domain Language enum., One cross-thread push-to-talk transition and its acknowledgement. (+1 more)

### Community 215 - "datetime"
Cohesion: 0.22
Nodes (9): MCPPreset, RegistryServer, McpMarketplacePage(), envToText(), FormMode, headersToText(), parseEnv(), parseHeaders() (+1 more)

### Community 216 - ".get_relevant_tools"
Cohesion: 0.29
Nodes (4): Any, Register tools from an MCP server.          Each tool dict must include a 'serve, Return all registered tool schemas., Return the most relevant tools for a given query.          Uses keyword matching

### Community 217 - "test_settings_coverage.py"
Cohesion: 0.18
Nodes (8): datetime, Enum, In-memory log buffer + live fan-out for the web Logs viewer.  A single :class:`L, Domain models for Dax Assistant.  Pure dataclasses with no external dependencies, Tool execution policy — allow / ask / deny per tool name.  The agent consults th, _parse_datetime(), Conversation repository — implements the Storage protocol for SQLite., Parse an ISO format datetime string.

### Community 218 - "_get_oauth_token"
Cohesion: 0.33
Nodes (3): Map a spoken answer to a decision string (es/en)., The spoken-confirmation parser (voice approval)., TestYesNoParser

### Community 219 - "registry.py"
Cohesion: 0.29
Nodes (4): Any, Per-configured-server connection + tool status for the web UI., Return all available tool schemas across all servers., Return the tools most relevant to ``query`` (ToolProvider port).          Delega

### Community 220 - ".unregister_server"
Cohesion: 0.47
Nodes (5): collect(), DiskMetrics, String, Vec, SystemMetrics

### Community 221 - ".clear"
Cohesion: 0.40
Nodes (3): Any, Register the async callback that delivers requests to the UI., Ask the user to confirm a tool call.          Returns the chosen decision string

### Community 222 - ".server_lookup"
Cohesion: 0.50
Nodes (3): index(), PHRASES, VoiceEnrollment()

## Knowledge Gaps
- **373 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `$schema`, `identifier`, `description` (+368 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **84 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Message` connect `Keyboard Collection Navigation` to `Voice Processing Pipeline`, `Application Storage Lifecycle`, `Voice Conversation State`, `MCP Configuration Routes`, `System API Tests`, `Selection and Syntax Utilities`, `McpServers.tsx`, `LLM Router Failover`, `WhatsApp Channel Integration`, `whatsapp_webhook`, `LLM Provider Factory`, `Gemini Provider Adapter`, `Anthropic Provider Adapter`, `Shell Command Allowlist`, `Voice Activity Detection`, `Shared Test Fixtures`, `filter_tools_by_relevance`, `WebSocket Chat Server`, `enroll_voice.py`, `Application Settings Models`, `OpenAI Provider Adapter`, `Codex Provider Adapter`, `Application Command Entrypoint`, `WebSocket Channel Adapter`, `WebChannel`, `test_settings_coverage.py`, `_get_oauth_token`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `MessageBus` connect `Keyboard Collection Navigation` to `Voice Processing Pipeline`, `Application Storage Lifecycle`, `Voice Conversation State`, `MCP Configuration Routes`, `System API Tests`, `Webhook API Tests`, `Selection and Syntax Utilities`, `McpServers.tsx`, `WhatsApp Channel Integration`, `Web Dependency Injection`, `TestWebSocketAuthCredentials`, `Voice Activity Detection`, `Shared Test Fixtures`, `filter_tools_by_relevance`, `_make_app`, `Password Authentication Tests`, `Application Settings Models`, `enroll_voice.py`, `Application Command Entrypoint`, `.__init__`, `WebChannel`, `Authentication Flow Tests`, `_get_oauth_token`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `MCPManager` connect `MCP Lifecycle Manager` to `Agent Tool Policy`, `MCP Environment Resolution`, `Application Storage Lifecycle`, `MCP Client Connections`, `MCP Tool Registry`, `useToast`, `WebSocket Channel Adapter`, `Selection and Syntax Utilities`, `Core Configuration Models`, `registry.py`, `Web Dependency Injection`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 85 inferred relationships involving `i()` (e.g. with `index-CtpIuQcu.js` and `ac()`) actually correct?**
  _`i()` has 85 INFERRED edges - model-reasoned connections that need verification._
- **Are the 107 inferred relationships involving `n()` (e.g. with `fromIntLines()` and `index-CtpIuQcu.js`) actually correct?**
  _`n()` has 107 INFERRED edges - model-reasoned connections that need verification._
- **Are the 100 inferred relationships involving `Message` (e.g. with `TelegramChannel` and `VoiceChannel`) actually correct?**
  _`Message` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 95 inferred relationships involving `t()` (e.g. with `a()` and `ab()`) actually correct?**
  _`t()` has 95 INFERRED edges - model-reasoned connections that need verification._