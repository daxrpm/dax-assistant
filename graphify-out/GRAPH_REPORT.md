# Graph Report - dax-assistant  (2026-07-19)

## Corpus Check
- 315 files · ~528,644 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 4743 nodes · 12529 edges · 258 communities (177 shown, 81 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 2455 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d1614206`
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
- VoicePreviewRequest
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
- .bind_loop
- get_config
- .to_json
- .unregister_server
- .has_subscribers
- .server_lookup
- .events
- test_settings_coverage.py
- _get_oauth_token
- oauth_callback
- TestEnums
- env.sh
- _StatefulStorage
- voice_events.py
- .subscribe
- test_settings_coverage.py
- _get_oauth_token
- DaxApplication
- .to_json
- .has_subscribers
- AppViewModel
- AssistantStateTest
- DiagnosticsViewModel
- DiagnosticsScreen
- .from_config_path
- Speaker
- TestDeviceRegistry
- DaxRecognitionService
- filter_tools_by_relevance
- ApprovalSheet
- enroll_voice.py
- .get_relevant_tools
- app
- .bind_loop
- .list_tools
- VoiceOrb
- .send
- .get_response

## God Nodes (most connected - your core abstractions)
1. `i()` - 172 edges
2. `n()` - 165 edges
3. `Message` - 158 edges
4. `t()` - 155 edges
5. `r()` - 143 edges
6. `MessageBus` - 123 edges
7. `a()` - 111 edges
8. `s()` - 100 edges
9. `push()` - 95 edges
10. `VoicePipeline` - 87 edges

## Surprising Connections (you probably didn't know these)
- `ModelSelector()` --indirect_call--> `m()`  [INFERRED]
  web/src/pages/Chat.tsx → src/dax/web/static/assets/index-CtpIuQcu.js
- `Production SPA Shell` --semantically_similar_to--> `Development SPA Shell`  [INFERRED] [semantically similar]
  src/dax/web/static/index.html → web/index.html
- `Native Linux Client` --conceptually_related_to--> `Dax Blue App Icon Master`  [INFERRED]
  README.md → desktop/src-tauri/icons/icon.png
- `encodePcm16()` --indirect_call--> `value()`  [INFERRED]
  desktop/src/audio/remoteAudio.ts → src/dax/web/static/assets/index-CtpIuQcu.js
- `CommandPalette()` --indirect_call--> `index()`  [INFERRED]
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

## Communities (258 total, 81 thin omitted)

### Community 0 - "Bundle Collection Utilities"
Cohesion: 0.01
Nodes (184): add(), addDescendants(), addText(), Ag(), ak(), as(), ay(), basename() (+176 more)

### Community 1 - "Voice Processing Pipeline"
Cohesion: 0.10
Nodes (11): CallbackFlags, LocalAudioSource, ndarray, sounddevice callback — runs on the audio thread., Play a full audio buffer and block until playback finishes.          Args:, Play an int16 buffer in small blocks, stopping early on demand.          ``shoul, Play audio from an iterable of raw ``int16`` byte chunks.          Useful for lo, Capture audio from the default microphone in fixed-size chunks.      Chunks are (+3 more)

### Community 2 - "Frontend Runtime Internals"
Cohesion: 0.05
Nodes (110): aa(), ac(), ae(), af(), ah(), announce(), ao(), appendChild() (+102 more)

### Community 3 - "Agent Tool Policy"
Cohesion: 0.09
Nodes (30): generate_pairing_code(), _codes(), delete_device(), DeviceListResponse, enroll_device(), EnrollRequest, EnrollResponse, issue_device_token() (+22 more)

### Community 4 - "Tree Collection Traversal"
Cohesion: 0.09
Nodes (120): _(), a(), aj(), ar(), b(), be(), bn(), br() (+112 more)

### Community 5 - "Tool Dispatch Interfaces"
Cohesion: 0.09
Nodes (49): AsyncMutex, AtomicU64, analyze_spectrum(), artwork_data_url(), browser_art_path(), CommandOutput, control(), current_player() (+41 more)

### Community 6 - "DOM Collection Mutation"
Cohesion: 0.06
Nodes (105): Ad(), addChild(), addEventListener(), addTreeNode(), al(), an(), Au(), bl() (+97 more)

### Community 7 - "Application Storage Lifecycle"
Cohesion: 0.06
Nodes (25): Database, Connection, SQLite database initialization and connection management., Close the database connection., Return the active connection, raising if not started., Create tables if they don't exist and track schema version., Apply additive migrations for databases created before this version., Async SQLite database wrapper.      Manages the connection lifecycle and schema (+17 more)

### Community 8 - "Agent Message Processing"
Cohesion: 0.19
Nodes (16): Av(), bj(), Er(), Fj(), Fv(), gv(), Iv(), Nj() (+8 more)

### Community 9 - "OAuth Webhook Integration"
Cohesion: 0.07
Nodes (55): HTMLResponse, auth_logout(), auth_status(), _AuthStartResponse, _callback_html(), configure_oauth_store(), _delete_tokens(), _discover_auth() (+47 more)

### Community 10 - "MCP Tool Registry"
Cohesion: 0.12
Nodes (10): Tool registry — aggregates tools from all MCP servers.  Provides lookup by tool, Aggregates tool schemas from multiple MCP servers.      Maintains a mapping of t, Remove all tools belonging to a server (e.g. on disconnect)., Remove all registered tools., Return the tool_name → server_name mapping., Look up which server owns a tool., ToolRegistry, _make_tools() (+2 more)

### Community 11 - "Collection Cursor Operations"
Cohesion: 0.03
Nodes (42): Channel, LLMProvider, Protocol, Protocol interfaces (ports) for the hexagonal architecture.  All adapters implem, Launch and connect to all configured MCP servers., Shut down all MCP server connections., Return all available tool schemas across all servers., Return the tool schemas most relevant to ``query``, capped at         ``max_tool (+34 more)

### Community 12 - "Event Scheduling Runtime"
Cohesion: 0.24
Nodes (5): Runtime allowlist of shell binaries the assistant may run on this PC.  This is t, Extract the bare binary name from a command string (``/bin/ls -l`` → ``ls``)., shell_binary(), Tests for the shell-command allowlist., TestShellBinary

### Community 13 - "Voice Conversation State"
Cohesion: 0.03
Nodes (42): build_messages_for_llm(), Any, Shared LLM helpers: the system prompt and the message builder.  The conversation, Build the OpenAI-format message list for an LLM call.      Converts our Message, Remove provider control markup that must never reach users or TTS., sanitize_assistant_text(), _clean_for_speech(), _ends_with_question() (+34 more)

### Community 14 - "React Collection Rendering"
Cohesion: 0.11
Nodes (36): MCPServerConfig, Configuration for a single MCP server.      Supports two transport modes:     -, add_mcp_server(), delete_mcp_server(), get_claude_config(), get_codex_config(), get_system_shell_allow(), list_mcp_servers() (+28 more)

### Community 15 - "Conversation Data Models"
Cohesion: 0.06
Nodes (83): Arc, BackendResolution, BackendSettings, BackendStrategy, BackendResolution, BackendSettings, BackendState, BackendStateInner (+75 more)

### Community 16 - "Speech Synthesis Engines"
Cohesion: 0.06
Nodes (38): currentToken(), LogEntry, AgentEvent, boundMessages(), ChatMessage, ChatSnapshot, ChatStatus, ChatStore (+30 more)

### Community 17 - "Shared Web UI Components"
Cohesion: 0.08
Nodes (14): Device, DeviceRegistry, generate_device_secret(), _now(), Enrolled client devices and their credentials.  A single password is the right e, True when the device exists and has not been revoked., Constant-time-ish check of a presented device secret., Create a device and return it with its one-time plaintext secret. (+6 more)

### Community 18 - "Configuration API Routes"
Cohesion: 0.17
Nodes (20): File, _decode_enrollment_wav(), delete_voice_profile(), _encode_wav(), enroll_voice(), get_voice_profile(), preview_voice(), _push_to_talk() (+12 more)

### Community 19 - "MCP Configuration Routes"
Cohesion: 0.14
Nodes (11): bus(), client(), _enroll(), AsyncClient, FastAPI, End-to-end device enrolment over the HTTP API.  Covers the gating each endpoint, With auth on, only a session may pair or manage devices., The whole point: a device token is a first-class credential. (+3 more)

### Community 20 - "System API Tests"
Cohesion: 0.08
Nodes (7): AsyncClient, MonkeyPatch, Path, TestConfigUpdate, TestMCPServers, TestNewEndpoints, _wav_recording()

### Community 21 - "Webhook API Tests"
Cohesion: 0.10
Nodes (23): app(), bus(), client(), _make_audio_webhook(), _make_extended_text_webhook(), _make_text_webhook(), AsyncClient, FastAPI (+15 more)

### Community 22 - "System MCP Server"
Cohesion: 0.09
Nodes (17): FastMCP, main(), Run the dax-system MCP server over stdio: python -m dax.mcp_servers.system, allowed_roots(), build_server(), Path, `dax-system` — a local MCP server exposing safe, typed PC-control tools.  Runs a, Construct the FastMCP server with all dax-system tools registered. (+9 more)

### Community 23 - "Selection and Syntax Utilities"
Cohesion: 0.04
Nodes (66): Message, A request to execute an MCP tool., The result of an MCP tool execution., A single message in a conversation.      Immutable value object. All messages fl, ToolCall, ToolResult, Decision, StrEnum (+58 more)

### Community 24 - "Core Configuration Models"
Cohesion: 0.11
Nodes (29): AnthropicProviderConfig, CodexProviderConfig, DeepSeekProviderConfig, GeminiProviderConfig, MCPConfig, OllamaProviderConfig, OpenAIProviderConfig, BaseModel (+21 more)

### Community 25 - "Dashboard API Client"
Cohesion: 0.09
Nodes (20): data(), MemoryEntry, useStatus(), DashboardPage(), EMPTY_DRAFT, MEMORY_TYPES, MemoryDraft, MemoryTab() (+12 more)

### Community 26 - "LLM Router Failover"
Cohesion: 0.12
Nodes (11): LLMProviderUnavailableError, No LLM provider is available to handle the request., LLMRouter, Any, LLM router — local-first fallback across decoupled providers.  Holds an ordered, Routes completion requests across an ordered list of providers., Swap the provider list in place (e.g. after a config change).          Mutates t, _FakeProvider (+3 more)

### Community 27 - "Logging Event Buffer"
Cohesion: 0.11
Nodes (14): datetime, LogRecord, LogBuffer, AbstractEventLoop, Any, Queue, In-memory log buffer + live fan-out for the web Logs viewer.  A single :class:`L, Stdlib log handler that retains recent records and fans them out live. (+6 more)

### Community 28 - "WhatsApp Channel Integration"
Cohesion: 0.11
Nodes (16): Any, WhatsApp channel — sends responses via Evolution API v2.  Incoming messages are, Send a voice note via Evolution API v2.          POST /message/sendWhatsAppAudio, WhatsApp outbound channel via Evolution API v2.      Sends text (and optionally, Initialize the HTTP client for Evolution API calls., Close the HTTP client., Send a response message to a WhatsApp contact.          The recipient JID is ext, Send a text message via Evolution API v2.          POST /message/sendText/{insta (+8 more)

### Community 29 - "TypeScript Compiler Configuration"
Cohesion: 0.08
Nodes (25): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+17 more)

### Community 30 - "Web Dependency Injection"
Cohesion: 0.14
Nodes (24): approval_from_app(), auth_from_app(), bus_from_app(), get_approval(), get_auth(), get_bus(), get_config(), get_llm_router() (+16 more)

### Community 31 - "Human Approval Workflow"
Cohesion: 0.08
Nodes (14): ApprovalManager, Any, Human-in-the-loop approval gate for gated tool calls.  When the policy says a to, The session that raised ``approval_id``, or None if unscoped/unknown.          T, Resolve a pending request. Returns True if it matched a pending one.          Re, Tracks pending tool-confirmation requests and their resolutions., Register the async callback that delivers requests to the UI., Register the spoken-confirmation handler used for voice turns.          When a g (+6 more)

### Community 32 - "System Status API"
Cohesion: 0.12
Nodes (28): get_host_metrics(), get_logs(), get_mcp_status(), get_status(), get_tool_audit(), get_tool_policy(), HostMetricsResponse, list_llm_models() (+20 more)

### Community 33 - "Keyboard Collection Navigation"
Cohesion: 0.08
Nodes (37): addNode(), at(), bd(), Bp(), Bv(), canSelectItemIn(), cf(), commit() (+29 more)

### Community 34 - "MCP Lifecycle Manager"
Cohesion: 0.15
Nodes (9): MCPServerConfig, MCPManager, Launch and connect to all enabled MCP servers., Connect to a server and register its tools live. Returns tool count.          Re, Disconnect a server (if connected) and drop its tools., Disconnect a server from the MCP lifecycle worker task., Disconnect from all MCP servers., Return which server owns ``tool_name`` (ToolProvider port). (+1 more)

### Community 35 - "Secure Configuration Serialization"
Cohesion: 0.11
Nodes (30): Mirror the live shell allowlist into encrypted configuration., _del_path(), dump_config_toml(), _env_var_for_header(), _env_var_for_mcp_env(), _extract_secrets(), _get_path(), _is_sensitive_header() (+22 more)

### Community 36 - "Realtime Chat Interface"
Cohesion: 0.13
Nodes (15): ConversationSummary, Modal(), AgentEvent, ChatMessage, ConfirmationRequest, nextId(), Status, useChatSocket() (+7 more)

### Community 37 - "Frontend Runtime Dependencies"
Cohesion: 0.05
Nodes (92): api, ApiError, getBaseUrl(), FullConfig, DesktopRuntimeError(), AlertIcon(), PlayIcon(), PlusIcon() (+84 more)

### Community 38 - "Memory File Management"
Cohesion: 0.26
Nodes (20): create_memory(), delete_memory(), get_memory(), list_memory(), _memory_dir(), _memory_frontmatter(), _memory_path(), _memory_slug() (+12 more)

### Community 39 - "LLM Provider Factory"
Cohesion: 0.17
Nodes (15): LLMConfig, LLMConfig, LLM routing and provider configuration.      The local Ollama provider is the de, build_provider(), build_providers(), build_router(), _ollama_base_url(), Build the LLM router and providers from configuration.  This is the single place (+7 more)

### Community 40 - "Token Authentication Manager"
Cohesion: 0.09
Nodes (16): SecurityConfig, AuthManager, Request, Response, WebSocket, True when a password is set (login is possible)., Mint a short-lived access token for an enrolled device., True when *token* is a live user session or a live device token. (+8 more)

### Community 41 - "MCP Client Connections"
Cohesion: 0.13
Nodes (10): MCPClient, Any, MCP client wrapper — manages a connection to a single MCP server.  Supports two, Connect via Streamable HTTP transport (remote server)., Close the session and terminate any subprocesses., Clean up resources, suppressing anyio cancel scope errors., Query the server for available tools and return their schemas., Wraps a connection to a single MCP server.      Args:         server_name: Uniqu (+2 more)

### Community 42 - "System Prompt Construction"
Cohesion: 0.12
Nodes (18): Any, System-prompt assembly for the agent.  Builds the per-turn system prompt from th, Append a concrete live tool inventory to the base system prompt.      Grouping b, Assembles the per-turn system prompt (tools + memory + voice style)., Replace the editable base prompt for subsequent turns., Return the full system prompt for this turn., Read user-curated memory files and format them for the system prompt.          E, SystemPromptBuilder (+10 more)

### Community 43 - "Frontend Development Dependencies"
Cohesion: 0.05
Nodes (65): ab(), __addSublanguage(), bb(), bo(), Bw(), bx(), cb(), consume() (+57 more)

### Community 44 - "Logs and Configuration Types"
Cohesion: 0.08
Nodes (49): browserDefaults(), clearToken(), connectionCandidates(), getWsUrl(), isLoopbackUrl(), isTauri(), loadConnectionSettings(), loadToken() (+41 more)

### Community 45 - "Gemini Provider Adapter"
Cohesion: 0.16
Nodes (7): Content, GeminiProvider, Any, Google Gemini provider adapter — official `google-genai` SDK.  Translates the Op, Implements the LLMProvider port over the Gemini generateContent API., TestGeminiProvider, Tool

### Community 46 - "useToast"
Cohesion: 0.23
Nodes (5): _auth(), Device enrolment, short-lived tokens, and revocation., Salt separation: a browser session must not authenticate as a device., registry(), TestDeviceTokens

### Community 47 - "Anthropic Provider Adapter"
Cohesion: 0.19
Nodes (5): AnthropicProvider, Any, Anthropic (Claude) provider adapter — official `anthropic` SDK.  Translates the, Implements the LLMProvider port over the Anthropic Messages API., TestAnthropicProvider

### Community 48 - "Encrypted Secret Storage"
Cohesion: 0.13
Nodes (11): Connection, Path, Encrypted secret storage backed by SQLite.  Replaces the legacy ``.env`` file as, Seed ``os.environ`` from the store without clobbering real env vars.          Re, One-time migration: import ``KEY=value`` lines from a legacy .env.          Only, Encrypted key/value secret store on top of SQLite + a Fernet key file., Encrypt and persist a secret; also export it to ``os.environ``., SecretStore (+3 more)

### Community 49 - "Authentication API Routes"
Cohesion: 0.18
Nodes (20): auth_status(), AuthStatus, health(), HealthResponse, login(), LoginRequest, LoginResponse, logout() (+12 more)

### Community 50 - "Shell Command Allowlist"
Cohesion: 0.20
Nodes (8): _configure_logging(), Path, Application bootstrap and lifecycle management.  Wires all components together v, Create a DaxApp instance from a config file path., Set up structlog with console rendering., main(), Entry point for running Dax Assistant: python -m dax, Parse arguments and run the application.

### Community 51 - "Voice Activity Detection"
Cohesion: 0.08
Nodes (11): PipelineState, Back-to-back wake words must share one conversation., Once the user has been away long enough, context is dropped., session_ttl_minutes=0 opts back into a fresh session every time., An explicit goodbye drops context immediately, without waiting., Feed one 80 ms chunk per flag, voiced or not., A brief dip below threshold must not discard accumulated speech., Speech interrupted by a micro-pause still triggers follow-up. (+3 more)

### Community 52 - "Audio Capture Playback"
Cohesion: 0.08
Nodes (37): authHeaders(), request(), requestBlob(), requestForm(), responseError(), ConversationDetail, ConversationMessage, ConversationSummary (+29 more)

### Community 53 - "Shared Test Fixtures"
Cohesion: 0.13
Nodes (15): config_from_file(), database(), default_config(), isolate_config_env(), message_bus(), MonkeyPatch, Path, Shared test fixtures for Dax Assistant. (+7 more)

### Community 54 - "filter_tools_by_relevance"
Cohesion: 0.05
Nodes (26): PiperVoice, _build_local_tts(), _build_piper(), build_tts(), _FallbackSynthesizer, KokoroTTS, ndarray, Text-to-Speech via Kokoro (kokoro-onnx).  Kokoro is a small (82M) Apache-2.0 neu (+18 more)

### Community 55 - "Wake Word Detection"
Cohesion: 0.06
Nodes (51): CommandPalette(), fold(), PaletteAction, PaletteRoute, ActivityIcon(), ArrowDownIcon(), BrainIcon(), ChatIcon() (+43 more)

### Community 56 - "WebSocket Chat Server"
Cohesion: 0.15
Nodes (10): CapabilityProbe, CaptureOutcome, Boolean, Int, List, Pair, String, StabilityOutcome (+2 more)

### Community 57 - "Collection Selection Management"
Cohesion: 0.17
Nodes (5): Mutable, observable set of allowed shell binaries (order preserved)., Append a binary if new. Returns True if it was actually added., Replace the whole list (de-duped, order preserved) and persist., ShellAllowlist, TestShellAllowlist

### Community 58 - "Configuration Serialization Tests"
Cohesion: 0.09
Nodes (26): BaseSettings, PydanticBaseSettingsSource, DaxConfig, How a secret field is represented in the persisted TOML., SecretMode, Root configuration for Dax Assistant.      Settings are loaded in order of prior, Path, Tests for TOML config serialization + secret extraction (config_io). (+18 more)

### Community 59 - "Domain Error Hierarchy"
Cohesion: 0.12
Nodes (17): Audio troubleshooting, Choosing / adding LLM providers, Configuration, Dax Assistant, Desktop client, Development, Development quick start, Highlights (+9 more)

### Community 60 - "Password Authentication Tests"
Cohesion: 0.09
Nodes (25): hash_password(), _main(), Single-user authentication for the web UI and API.  Dax is a personal assistant:, Return an argon2id hash of ``password``., Check ``password`` against a stored argon2 hash., verify_password(), create_app(), FastAPI (+17 more)

### Community 61 - "Application Settings Models"
Cohesion: 0.17
Nodes (8): AppModule, ChatSocket, Context, BackendAuth, CoroutineDispatcher, CoroutineScope, CredentialStore, OkHttpClient

### Community 62 - "Voice Model Downloads"
Cohesion: 0.21
Nodes (13): _download(), download_kokoro(), download_piper_voices(), download_wake_word(), download_whisper(), main(), Path, Download voice models for Dax Assistant.  Fetches everything the voice pipeline (+5 more)

### Community 63 - "OpenAI Provider Adapter"
Cohesion: 0.19
Nodes (5): OpenAIProvider, Any, OpenAI provider adapter — official `openai` SDK (Chat Completions).  Also serves, Implements the LLMProvider port over the OpenAI Chat Completions API., TestOpenAIProvider

### Community 64 - "VoiceConfig"
Cohesion: 0.18
Nodes (10): description, identifier, linux, macOS, windows, permissions, platforms, $schema (+2 more)

### Community 65 - "Web Application Entrypoint"
Cohesion: 0.22
Nodes (12): PanelHeader(), useConfig(), ExportPanel(), McpPage(), envToText(), FormMode, headersToText(), McpTab() (+4 more)

### Community 66 - "Codex Provider Adapter"
Cohesion: 0.16
Nodes (10): LLMError, LLMTimeoutError, LLM provider communication failed., LLM request timed out., CodexProvider, Any, OpenAI Codex CLI provider.  Runs ``codex exec --json`` as a subprocess to use th, Parse the JSONL event stream and return the final agent message. (+2 more)

### Community 67 - "MCP Environment Resolution"
Cohesion: 0.13
Nodes (12): _get_oauth_token(), MCP server manager — implements the ToolProvider protocol.  Manages the lifecycl, Build an unconnected client for a server config (env resolved)., Replace {env:VAR_NAME} patterns with environment variable values., Resolve env vars in all values of a dict., Snapshot desktop-session vars present in the current environment., Get stored OAuth access token for an MCP server, if available., _resolve_env_dict() (+4 more)

### Community 68 - "MCP Marketplace Interface"
Cohesion: 0.15
Nodes (25): index(), api, Field(), Select(), Tabs(), TextArea(), TextInput(), Toggle() (+17 more)

### Community 69 - "Project Architecture Overview"
Cohesion: 0.15
Nodes (11): Architecture, Channels (`channels/`), Commands, Config & secrets (`core/config.py`, `core/config_io.py`), LLM layer (`llm/`) — fully decoupled behind the `LLMProvider` port, MCP (`mcp/`) and the bundled server, Message flow (the spine), Safety model (+3 more)

### Community 70 - "End-to-End Web Tests"
Cohesion: 0.11
Nodes (15): Any, Queue, Voice event transport — thread-to-loop fan-out with no optional deps.  Lives in, The most recent state event, replayed to clients on connect.          Without th, Register a new subscriber and return its queue., Remove a subscriber's queue., Publish *event* to all subscribers. Safe to call from any thread.          Never, Push *event* onto every subscriber queue. Runs on the event loop. (+7 more)

### Community 71 - "Collection Selection Queries"
Cohesion: 0.06
Nodes (44): usesRemoteAudio(), MCPServerStatus, ToolAuditEntry, CommandDeck(), LiveOrb(), Meter(), MetricsPane(), PIPELINE_KEY (+36 more)

### Community 72 - "Application Shell Theming"
Cohesion: 0.08
Nodes (48): getConnectionSettings(), RESIZE_HANDLES, ResizeHandles(), TitleBar(), TitleBarProps, useWindowFrame(), WindowFrame(), WindowFrameContext (+40 more)

### Community 73 - "Streaming Speech Synthesis"
Cohesion: 0.40
Nodes (3): Path, Smoke tests for the portable Linux installer., test_installer_dry_run_uses_xdg_layout()

### Community 74 - "Application Command Entrypoint"
Cohesion: 0.48
Nodes (10): account(), clear(), delete(), entry(), get(), read(), Option, Result (+2 more)

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
Cohesion: 0.17
Nodes (8): AssistantController, Boolean, List, StateFlow, String, Turn, Job, ServerFrame

### Community 81 - "Web Authentication Interface"
Cohesion: 0.31
Nodes (8): LevelSource, compute_level_frame(), emit_level(), Any, ndarray, Audio metering — turn raw capture chunks into compact waveform frames.  The tran, Reduce a raw audio chunk to a compact envelope + spectrum frame.      Args:, Emit a level frame for *chunk* on *hub*. No-op with no subscribers.      The sub

### Community 84 - "ln"
Cohesion: 0.21
Nodes (4): Allow / ask / deny policy for tool execution (fnmatch patterns).      An empty `, ToolPolicyConfig, Tests for the tool execution policy., TestToolPolicy

### Community 86 - "Production Social Icons"
Cohesion: 0.48
Nodes (7): Bluesky Icon, Discord Icon, Documentation and Code Icon, GitHub Icon, Social Profile Icon, Web Icon Sprite, X Social Platform Icon

### Community 87 - "Authentication Flow Tests"
Cohesion: 0.13
Nodes (10): auth_client(), AsyncClient, FastAPI, Tests for single-user web authentication., The desktop client can't rely on a SameSite=lax cookie from a webview     custom, A cookie left over from a previous session must not shadow a good         bearer, Regression guard: the existing web UI must keep working., test_token_roundtrip() (+2 more)

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
Cohesion: 0.23
Nodes (9): createRemotePtt(), encodePcm16(), PcmFrameBatcher, pushToTalk, RemoteMicrophone, remotePtt, resampleMono(), StreamingMonoResampler (+1 more)

### Community 96 - "MemoryTab.tsx"
Cohesion: 0.06
Nodes (53): ChevronRightIcon(), Locale, APPLY_CLASS, APPLY_KEY, asNumber(), asString(), FieldControl(), FieldLabel() (+45 more)

### Community 98 - "Production Favicon Graphics"
Cohesion: 0.50
Nodes (4): Favicon Graphic, Lightning Bolt Symbol, Purple Angular Mark, Soft Glow Highlights

### Community 102 - "auth_from_app"
Cohesion: 0.11
Nodes (20): StrEnum, Discriminator for events on the voice stream., VoiceEventType, voice_events_from_app(), _idle_state(), _lease_from_app(), _pipeline_from_app(), Any (+12 more)

### Community 110 - "I18n.tsx"
Cohesion: 0.20
Nodes (10): Connection strategy, Desktop Architecture, First-run onboarding, Media integration, Orbita rendering, Process boundaries, Realtime stores, Settings contract (+2 more)

### Community 111 - "mcp_tools_to_openai"
Cohesion: 0.06
Nodes (30): app, security, windows, build, beforeBuildCommand, beforeDevCommand, devUrl, frontendDist (+22 more)

### Community 112 - "models.py"
Cohesion: 0.19
Nodes (17): formatMediaTime(), hashTrack(), mediaProvider, NowPlaying(), NowPlayingView(), progressWaveform(), media, controlMedia() (+9 more)

### Community 150 - "test_legacy_oauth_files_migrate_encrypted"
Cohesion: 0.07
Nodes (27): compilerOptions, allowImportingTsExtensions, exactOptionalPropertyTypes, isolatedModules, jsx, lib, module, moduleResolution (+19 more)

### Community 151 - "McpServers.tsx"
Cohesion: 0.03
Nodes (105): Voice channel adapter — bridges the dispatcher to the voice pipeline.  The voice, Voice channel adapter for the dispatcher.      Inbound messages are published by, No-op — the voice pipeline manages its own lifecycle., No-op — the voice pipeline manages its own lifecycle., Discard any queued responses left over from a previous turn.          The pipeli, VoiceChannel, Voice pipeline configuration., VoiceConfig (+97 more)

### Community 152 - "TestYesNoParser"
Cohesion: 0.25
Nodes (11): cn(), dn(), gn(), hn(), mn(), on(), Qt(), sn() (+3 more)

### Community 153 - "getFullNode"
Cohesion: 0.10
Nodes (16): ApiError, ConversationDetail, ConversationMessage, MCPPreset, MCPServerStatus, OllamaModel, RegistryServer, requestBlob() (+8 more)

### Community 154 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowSyntheticDefaultImports, composite, declarationDir, emitDeclarationOnly, isolatedModules, lib, module (+10 more)

### Community 155 - "6.2 Parity checklist"
Cohesion: 0.08
Nodes (24): _device_for(), Any, WebSocket, WebSocket chat endpoint for the web UI.  Handles inbound messages from browser c, Send data to a specific WebSocket connection., Send data to all connected WebSocket clients., Route *data* by its ``session_id``, falling back to a broadcast.          Sessio, Deliver a confirmation request only to the client that can answer it.          U (+16 more)

### Community 156 - "permissions"
Cohesion: 0.08
Nodes (23): description, identifier, linux, macOS, windows, permissions, platforms, $schema (+15 more)

### Community 157 - "4.2 HTTP routes — complete enumeration"
Cohesion: 0.22
Nodes (9): 7. Milestone Results, M0 - Risk spike: passed (2026-07-18), M1 - Foundation: passed with visual caveat (2026-07-18), M2 - Chat: automated gate passed, M3 - Settings and screens: automated gate passed, M4 - Voice and HUD: software gate passed; hardware gate open, M5 - Native polish: software gate passed; human accessibility gate open, M6 - Packaging: build gate passed; clean-install gate open (+1 more)

### Community 158 - "._resolve_voice"
Cohesion: 0.12
Nodes (25): ai(), ap(), dp(), fp(), gp(), Ha(), Hp(), ii() (+17 more)

### Community 159 - "whatsapp_webhook"
Cohesion: 0.20
Nodes (10): BusDep, _extract_text(), Any, ConfigDep, Request, Response, Evolution API v2 webhook receiver.  Handles incoming WhatsApp messages (text and, Extract text content from various WhatsApp message types.      Supports:     - c (+2 more)

### Community 160 - "Dax Desktop — Implementation Plan"
Cohesion: 0.25
Nodes (8): 10. Remaining Gates, 11. Ground Truth, 1. Scope, 5. Settings 6.0, 6. Voice HUD, 8. Automated Release Gate, 9. Reproducible Commands, Dax Desktop - Implementation Record

### Community 161 - "10. Phased milestones"
Cohesion: 0.15
Nodes (10): Boolean, OrbitaTheme(), DaxApp(), Bundle, ComponentActivity, MainActivity, Screen, ASSISTANT (+2 more)

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
Cohesion: 0.24
Nodes (9): AppShell(), NAV, NavItem, TITLES, ThemeToggle(), apply(), resolveInitial(), Theme (+1 more)

### Community 169 - ".from_config_path"
Cohesion: 0.13
Nodes (12): filter_tools_by_relevance(), mcp_tools_to_openai(), parse_tool_calls_from_response(), Any, Maps MCP tool schemas to OpenAI function-calling format.  We use the OpenAI tool, Convert a list of MCP tool schemas to OpenAI function-calling format.      MCP f, Filter tools based on keyword relevance to the user's query.      Always include, Parse tool calls from a litellm response into our internal format.      Args: (+4 more)

### Community 170 - "Dax Desktop"
Cohesion: 0.25
Nodes (8): Dax Desktop, Desarrollo, Implementación, Límites verificados, Paquetes, Primera ejecución y conexión, Requisitos, Verificación reproducible

### Community 171 - "Desktop System Architecture"
Cohesion: 0.33
Nodes (6): Desktop React Entrypoint, Dax Blue App Icon 256, Dax Blue App Icon 128, Dax Blue App Icon 32, Dax Blue App Icon Master, Native Linux Client

### Community 172 - "WebChannel"
Cohesion: 0.07
Nodes (21): DaxApp, Apply the configured prompt to the live agent for its next turn., Expose FastAPI app for testing., Initialize all components in dependency order., Restart the Telegram channel to apply config changes without a full         app, Serialize live voice reloads so repeated UI saves remain safe., Restart the voice channel and pipeline with the live configuration., Shut down all components in reverse order. (+13 more)

### Community 173 - "TestEnums"
Cohesion: 0.15
Nodes (23): AgentActivity, AssistantError, AssistantState, Audio, Authentication, AwaitingApproval, Backend, Cancelled (+15 more)

### Community 174 - "Logs.tsx"
Cohesion: 0.19
Nodes (24): apply_frame(), apply_saved_frame(), decode_settings(), get_or_create(), hide(), LegacyWindowSettings, main_window(), malformed_settings_recover_to_custom_frame() (+16 more)

### Community 175 - "build"
Cohesion: 0.31
Nodes (8): build(), focus_main(), menu_action(), MenuAction, AppHandle, Option, R, Result

### Community 183 - "_make_app"
Cohesion: 0.14
Nodes (30): _acquire(), FakePipeline, _make_app(), Tests for the /ws/voice event stream.  The subscriber lifecycle matters more tha, A leaked subscriber would keep the pipeline metering forever., Omitting `output` must preserve the pre-existing behaviour exactly., The failure that would otherwise mute the backend permanently., Build an app with a voice hub attached, mirroring DaxApp wiring. (+22 more)

### Community 185 - "VoicePreviewRequest"
Cohesion: 0.31
Nodes (8): Orbita, OrbitaType, OrbitaColors, OrbitaElevation, OrbitaMotion, OrbitaRadii, OrbitaSizing, OrbitaSpacing

### Community 188 - "enroll_voice.py"
Cohesion: 0.38
Nodes (4): ndarray, Compute a voice embedding for *audio* (float32, 16 kHz mono)., Return True if *audio* matches the owner (or if verification is off).          A, Build and persist an owner profile from one or more recordings.          The ref

### Community 189 - "test_external_master_key_avoids_local_key_file"
Cohesion: 0.25
Nodes (11): concise_output(), control(), parse_status(), parses_systemctl_properties_independent_of_order(), Option, Result, String, run_systemctl() (+3 more)

### Community 190 - "test_settings_coverage.py"
Cohesion: 0.31
Nodes (4): Output ownership, Remote input v1, Reproducible checks, Voice WebSocket protocol

### Community 213 - ".__init__"
Cohesion: 0.14
Nodes (8): ndarray, Wake word detection via OpenWakeWord.  Wraps the OpenWakeWord inference model be, Reset the model's internal state between activations., Detect wake words in streaming audio chunks.      Args:         model_names: Lis, Download models (if needed) and initialise the detector., Release the model resources., Check whether a wake word was detected in an audio chunk.          Args:, WakeWordDetector

### Community 214 - "WebChannel"
Cohesion: 0.21
Nodes (8): Badge(), useLogStream(), wsUrl(), LEVEL_COLOR, LEVELS, LogsPage(), ShellPage(), LogEntry

### Community 215 - "datetime"
Cohesion: 0.21
Nodes (10): fail(), info(), message(), COLORS, ICONS, ToastProvider(), BadgeColor, Toast (+2 more)

### Community 216 - ".get_relevant_tools"
Cohesion: 0.12
Nodes (17): ToastApi, ToastContext, ToastItem, ToastProvider(), ToastTone, en, es, MessageKey (+9 more)

### Community 217 - ".bind_loop"
Cohesion: 0.18
Nodes (11): DaxError, Exception, MCP tool execution failed., Requested tool does not exist in the registry., Tool was found but execution failed., Database or persistence operation failed., Base exception for all Dax errors., StorageError (+3 more)

### Community 218 - "get_config"
Cohesion: 0.16
Nodes (11): AssistantService, ensureRunning(), ChatSocket, Context, Int, String, triggerTurn(), Intent (+3 more)

### Community 219 - ".to_json"
Cohesion: 0.17
Nodes (11): AssistActivity, DaxVoiceInteractionService, DaxVoiceInteractionSession, DaxVoiceInteractionSessionService, Bundle, ComponentActivity, Int, VoiceCommandActivity (+3 more)

### Community 220 - ".unregister_server"
Cohesion: 0.12
Nodes (9): ndarray, Voice Activity Detection via Silero VAD.  Wraps Silero VAD behind a chunk-orient, Reset the iterator state between utterances., Detect speech start and end boundaries in streaming audio.      Args:         th, Load the Silero VAD model and create the iterator., Release model resources., Process a single VAD-sized audio chunk.          Args:             audio_chunk:, Return the raw speech probability (0..1) for a VAD-sized chunk.          Used by (+1 more)

### Community 221 - ".has_subscribers"
Cohesion: 0.09
Nodes (19): CapabilityCheck, CapabilityReport, CheckId, AUDIO_FORMAT, COMMUNICATION_DEVICE_SELECTABLE, HFP_PROFILE, MEDIA_BUTTON, MICROPHONE_CAPTURE (+11 more)

### Community 222 - ".server_lookup"
Cohesion: 0.23
Nodes (12): Failed, Final, Boolean, Int, Pair, String, Partial, ReadyForSpeech (+4 more)

### Community 223 - ".events"
Cohesion: 0.28
Nodes (9): dd(), fd(), gd(), ma(), Ot(), pd(), rt(), Se() (+1 more)

### Community 225 - "_get_oauth_token"
Cohesion: 0.32
Nodes (5): DaxLog, List, String, Regex, Throwable

### Community 226 - "oauth_callback"
Cohesion: 0.26
Nodes (14): AssistantScreen(), CancelControl(), describeActivity(), describeError(), describeForAccessibility(), EmptyState(), History(), List (+6 more)

### Community 227 - "TestEnums"
Cohesion: 0.25
Nodes (7): Building, Dax Android, Layout, Security posture, Verdict: the Redmi Watch 5 Lite cannot carry third-party audio, Watch audio is a runtime feature, never an assumption, What this means for the architecture

### Community 228 - "env.sh"
Cohesion: 0.29
Nodes (6): ANDROID_HOME, ANDROID_SDK_ROOT, GRADLE_USER_HOME, JAVA_HOME, PATH, env.sh script

### Community 229 - "_StatefulStorage"
Cohesion: 0.04
Nodes (42): Enum, Web channel — delegates to WebSocket manager.  The actual WebSocket handling is, Web UI channel adapter.      Bridges between the dispatcher and the WebSocket ma, Broadcast a message to all connected WebSocket clients., WebChannel, ChannelType, Conversation, MessageRole (+34 more)

### Community 232 - "test_settings_coverage.py"
Cohesion: 0.40
Nodes (4): MonkeyPatch, Path, Encrypted secret-store tests., test_external_master_key_avoids_local_key_file()

### Community 233 - "_get_oauth_token"
Cohesion: 0.17
Nodes (9): AudioRoute, fromDeviceInfo(), Boolean, AudioRouteManager, Boolean, Int, List, StateFlow (+1 more)

### Community 235 - ".to_json"
Cohesion: 0.15
Nodes (16): _bootstrap_only(), _bootstrap_secrets(), _flatten_toml(), load_config(), Any, Path, Load encrypted configuration, importing a legacy TOML once when present.      Ar, Seed os.environ from the encrypted secret store before config is built.      Sec (+8 more)

### Community 236 - ".has_subscribers"
Cohesion: 0.29
Nodes (4): Boolean, Int, MediaButtonTrigger, MediaSession

### Community 237 - "AppViewModel"
Cohesion: 0.23
Nodes (6): AppViewModel, Boolean, StateFlow, String, ViewModel, SetupUiState

### Community 241 - "AssistantStateTest"
Cohesion: 0.12
Nodes (7): ApprovalRequest, ApprovalSheet(), DecisionButton(), Modifier, String, AssistantStateTest, Color

### Community 242 - "DiagnosticsViewModel"
Cohesion: 0.20
Nodes (6): DiagnosticsUiState, DiagnosticsViewModel, Boolean, StateFlow, String, ViewModel

### Community 243 - "DiagnosticsScreen"
Cohesion: 0.38
Nodes (10): CheckRow(), DiagnosticsScreen(), Boolean, Modifier, String, PermissionPrompt(), PrimaryAction(), PrivacySection() (+2 more)

### Community 244 - ".from_config_path"
Cohesion: 0.33
Nodes (6): Field(), Modifier, String, SetupScreen(), KeyboardCapitalization, KeyboardType

### Community 245 - "Speaker"
Cohesion: 0.33
Nodes (3): Boolean, String, Speaker

### Community 246 - "TestDeviceRegistry"
Cohesion: 0.40
Nodes (3): BackendEndpointPolicy, Boolean, String

### Community 247 - "DaxRecognitionService"
Cohesion: 0.32
Nodes (4): android, DaxRecognitionService, Callback, RecognitionService

### Community 249 - "ApprovalSheet"
Cohesion: 0.36
Nodes (4): AuthStatus, AuthGate(), Markdown, LoginPage()

### Community 250 - "enroll_voice.py"
Cohesion: 0.50
Nodes (4): main(), ndarray, Enroll the owner's voice for speaker verification (Voice ID).  Records a few sho, _record()

### Community 251 - ".get_relevant_tools"
Cohesion: 0.29
Nodes (4): Any, Register tools from an MCP server.          Each tool dict must include a 'serve, Return all registered tool schemas., Return the most relevant tools for a given query.          Uses keyword matching

### Community 252 - "app"
Cohesion: 0.50
Nodes (4): AudioRouteKind, BLUETOOTH_SCO, PHONE, WIRED

### Community 254 - ".list_tools"
Cohesion: 0.29
Nodes (4): Any, Per-configured-server connection + tool status for the web UI., Return all available tool schemas across all servers., Return the tools most relevant to ``query`` (ToolProvider port).          Delega

## Knowledge Gaps
- **415 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `PHONE`, `BLUETOOTH_SCO`, `WIRED` (+410 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **81 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Message` connect `Selection and Syntax Utilities` to `.send`, `.get_response`, `Application Storage Lifecycle`, `Collection Cursor Operations`, `Voice Conversation State`, `System API Tests`, `McpServers.tsx`, `LLM Router Failover`, `6.2 Parity checklist`, `WhatsApp Channel Integration`, `whatsapp_webhook`, `LLM Provider Factory`, `WebChannel`, `Gemini Provider Adapter`, `Anthropic Provider Adapter`, `Voice Activity Detection`, `Shared Test Fixtures`, `OpenAI Provider Adapter`, `Codex Provider Adapter`, `_StatefulStorage`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `DaxApp` connect `WebChannel` to `MCP Lifecycle Manager`, `Secure Configuration Serialization`, `_StatefulStorage`, `End-to-End Web Tests`, `Application Storage Lifecycle`, `OAuth Webhook Integration`, `Collection Cursor Operations`, `Encrypted Secret Storage`, `Shared Web UI Components`, `Shell Command Allowlist`, `Selection and Syntax Utilities`, `McpServers.tsx`, `Collection Selection Management`, `Configuration Serialization Tests`, `Logging Event Buffer`, `WhatsApp Channel Integration`, `Human Approval Workflow`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `SecretStore` connect `Encrypted Secret Storage` to `Secure Configuration Serialization`, `_StatefulStorage`, `Application Storage Lifecycle`, `LLM Provider Factory`, `OAuth Webhook Integration`, `test_settings_coverage.py`, `.to_json`, `WebChannel`, `React Collection Rendering`, `ln`, `System API Tests`, `McpServers.tsx`, `Core Configuration Models`, `Configuration Serialization Tests`, `WhatsApp Channel Integration`, `Web Dependency Injection`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 85 inferred relationships involving `i()` (e.g. with `index-CtpIuQcu.js` and `ac()`) actually correct?**
  _`i()` has 85 INFERRED edges - model-reasoned connections that need verification._
- **Are the 107 inferred relationships involving `n()` (e.g. with `fromIntLines()` and `index-CtpIuQcu.js`) actually correct?**
  _`n()` has 107 INFERRED edges - model-reasoned connections that need verification._
- **Are the 100 inferred relationships involving `Message` (e.g. with `TelegramChannel` and `VoiceChannel`) actually correct?**
  _`Message` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 95 inferred relationships involving `t()` (e.g. with `a()` and `ab()`) actually correct?**
  _`t()` has 95 INFERRED edges - model-reasoned connections that need verification._