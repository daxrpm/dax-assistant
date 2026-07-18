# Graph Report - dax-assistant  (2026-07-18)

## Corpus Check
- 145 files · ~88,854 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2792 nodes · 7814 edges · 166 communities (118 shown, 48 thin omitted)
- Extraction: 75% EXTRACTED · 25% INFERRED · 0% AMBIGUOUS · INFERRED: 1948 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8f400b56`
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
- Telegram Bot Channel
- Anthropic Provider Adapter
- Encrypted Secret Storage
- Authentication API Routes
- Shell Command Allowlist
- Voice Activity Detection
- Audio Capture Playback
- Shared Test Fixtures
- Configuration Loading Tests
- Wake Word Detection
- WebSocket Chat Server
- Collection Selection Management
- Configuration Serialization Tests
- Domain Error Hierarchy
- Password Authentication Tests
- Application Settings Models
- Voice Model Downloads
- OpenAI Provider Adapter
- Mutable Collection State
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
- Accessibility DOM Utilities
- Frontend Interaction Utilities
- Single Page Middleware
- Conversation API Routes
- WebSocket Channel Adapter
- Web Authentication Interface
- MCP Session Authentication
- Collection Tree Building
- Speaker Verification Embeddings
- Frontend State Utilities
- Production Social Icons
- Authentication Flow Tests
- Frontend Build Scripts
- Public Social Icons
- Local Voice Technology
- Interactive Installation Script
- Collection Filtering Operations
- SPA HTML Entrypoints
- LLM Routing Architecture
- Speaker Voice Enrollment
- Frontend Package Metadata
- Browser Test Polyfills
- Production Favicon Graphics
- Graphify Project Guidance
- Configuration Precedence Rules
- Graphify OpenCode Plugin
- React Runtime Dependency
- System Service Installer
- Dax Package Metadata
- LLM Providers Package
- MCP Tool Server Lookup
- MCP Servers Package
- System MCP Package
- Voice Processing Package
- User Event Test Dependency
- TypeScript Toolchain Dependency
- Vite Build Dependency
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
- MCPConfig
- Badge
- ._make_client
- getFullNode
- vg
- ._initialize_schema
- zy
- .connection
- clsx
- .get_server_for_tool
- Ow
- zy
- bh
- freeze
- Lm
- react

## God Nodes (most connected - your core abstractions)
1. `i()` - 163 edges
2. `n()` - 162 edges
3. `r()` - 142 edges
4. `Message` - 139 edges
5. `t()` - 138 edges
6. `a()` - 114 edges
7. `MessageBus` - 97 edges
8. `s()` - 95 edges
9. `push()` - 95 edges
10. `l()` - 68 edges

## Surprising Connections (you probably didn't know these)
- `ModelSelector()` --indirect_call--> `m()`  [INFERRED]
  web/src/pages/Chat.tsx → src/dax/web/static/assets/index-Dv7mEN36.js
- `Development SPA Shell` --semantically_similar_to--> `Production SPA Shell`  [INFERRED] [semantically similar]
  web/index.html → src/dax/web/static/index.html
- `TestAudioCapture` --uses--> `VoiceChannel`  [INFERRED]
  tests/unit/test_voice.py → src/dax/channels/voice_channel.py
- `TestAudioPlayer` --uses--> `VoiceChannel`  [INFERRED]
  tests/unit/test_voice.py → src/dax/channels/voice_channel.py
- `TestBuildTTS` --uses--> `VoiceChannel`  [INFERRED]
  tests/unit/test_voice.py → src/dax/channels/voice_channel.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Dax Async Message Lifecycle** — claude_multichannel_adapters, claude_message_bus_spine, claude_sqlite_conversation_storage, claude_llm_router_failover [EXTRACTED 1.00]
- **Dax Human-in-the-Loop Safety** — claude_dax_system_mcp_server, claude_approval_manager, claude_layered_safety_model, claude_web_realtime_protocol [EXTRACTED 1.00]
- **Local Voice Processing Stack** — readme_voice_assistant_pipeline, readme_openwakeword, readme_silero_vad, readme_faster_whisper, readme_kokoro_piper_tts [EXTRACTED 1.00]

## Communities (166 total, 48 thin omitted)

### Community 0 - "Bundle Collection Utilities"
Cohesion: 0.10
Nodes (114): __(), a(), ae(), b(), be(), bj(), bl(), bn() (+106 more)

### Community 1 - "Voice Processing Pipeline"
Cohesion: 0.10
Nodes (13): CallbackFlags, AudioCapture, ndarray, Audio I/O — microphone capture and speaker playback.  Uses sounddevice for cross, sounddevice callback — runs on the audio thread., Play a full audio buffer and block until playback finishes.          Args:, Play an int16 buffer in small blocks, stopping early on demand.          ``shoul, Play audio from an iterable of raw ``int16`` byte chunks.          Useful for lo (+5 more)

### Community 2 - "Frontend Runtime Internals"
Cohesion: 0.02
Nodes (27): ax(), Ck(), fn(), getGlobalDictionaryForPackage(), getStringForLocale(), getStringsForLocale(), gw(), hw() (+19 more)

### Community 3 - "Agent Tool Policy"
Cohesion: 0.10
Nodes (28): A request to execute an MCP tool., ToolCall, Decision, StrEnum, Tool execution policy — allow / ask / deny per tool name.  The agent consults th, Resolves an allow/ask/deny decision for a tool name., Update rules in place so the agent picks them up without a restart., ToolPolicy (+20 more)

### Community 4 - "Tree Collection Traversal"
Cohesion: 0.06
Nodes (92): aa(), addChild(), addEventListener(), addTreeNode(), al(), an(), Au(), bg() (+84 more)

### Community 5 - "Tool Dispatch Interfaces"
Cohesion: 0.04
Nodes (34): The result of an MCP tool execution., ToolResult, LLMProvider, Protocol, Protocol interfaces (ports) for the hexagonal architecture.  All adapters implem, Launch and connect to all configured MCP servers., Shut down all MCP server connections., Return all available tool schemas across all servers. (+26 more)

### Community 6 - "DOM Collection Mutation"
Cohesion: 0.08
Nodes (62): announce(), Ap(), appendChild(), Bd(), bf(), bt(), cf(), cl() (+54 more)

### Community 7 - "Application Storage Lifecycle"
Cohesion: 0.06
Nodes (29): Database, Connection, SQLite database initialization and connection management., Create tables if they don't exist and track schema version., Apply additive migrations for databases created before this version., Async SQLite database wrapper.      Manages the connection lifecycle and schema, Open the database connection and initialize the schema., Close the database connection. (+21 more)

### Community 8 - "Agent Message Processing"
Cohesion: 0.08
Nodes (15): Message, A single message in a conversation.      Immutable value object. All messages fl, MessageBus, Async message bus for inter-component communication.  Decouples channels from th, Async message bus using asyncio queues.      Thread-safe for posting from voice, Initialize the queues. Must be called from an async context., Publish a message from a channel to the orchestrator., Wait for and return the next inbound message. (+7 more)

### Community 9 - "OAuth Webhook Integration"
Cohesion: 0.05
Nodes (59): BusDep, HTMLResponse, Encrypted secret storage backed by SQLite.  Replaces the legacy ``.env`` file as, auth_logout(), auth_status(), _AuthStartResponse, _callback_html(), _delete_tokens() (+51 more)

### Community 10 - "MCP Tool Registry"
Cohesion: 0.05
Nodes (26): filter_tools_by_relevance(), mcp_tools_to_openai(), parse_tool_calls_from_response(), Any, Maps MCP tool schemas to OpenAI function-calling format.  We use the OpenAI tool, Convert a list of MCP tool schemas to OpenAI function-calling format.      MCP f, Filter tools based on keyword relevance to the user's query.      Always include, Parse tool calls from a litellm response into our internal format.      Args: (+18 more)

### Community 11 - "Collection Cursor Operations"
Cohesion: 0.08
Nodes (58): ac(), af(), bc(), cc(), ci(), Co(), dc(), df() (+50 more)

### Community 12 - "Event Scheduling Runtime"
Cohesion: 0.09
Nodes (21): Speech-to-text transcription failed., STTError, build_stt(), FallbackSpeechToText, OpenAISpeechToText, ndarray, VoiceConfig, Speech-to-Text via faster-whisper.  Wraps the CTranslate2-based Whisper model fo (+13 more)

### Community 13 - "Voice Conversation State"
Cohesion: 0.06
Nodes (31): _clean_for_speech(), ndarray, Voice pipeline — wake word, listen, transcribe, respond.  Runs in a dedicated th, Full voice pipeline: wake -> listen -> transcribe -> respond -> converse.      R, Start all voice components and launch the pipeline thread., Stop the pipeline thread and all components., State-machine loop in the voice-pipeline thread., IDLE — listen for wake word activation. (+23 more)

### Community 14 - "React Collection Rendering"
Cohesion: 0.08
Nodes (17): build_messages_for_llm(), Any, Build the OpenAI-format message list for an LLM call.      Converts our Message, Any, Core agent loop — the brain of Dax Assistant.  Receives messages from the bus, s, Wire a callback that receives real-time agent events (tool calls, etc.)., Fire an agent event to the broadcaster, silently ignoring errors., Begin the agent processing loop. (+9 more)

### Community 15 - "Conversation Data Models"
Cohesion: 0.06
Nodes (53): Ad(), ar(), Av(), cn(), cr(), Ct(), dj(), dn() (+45 more)

### Community 16 - "Speech Synthesis Engines"
Cohesion: 0.05
Nodes (35): PiperVoice, Voice pipeline configuration., VoiceConfig, Text-to-speech synthesis failed., TTSError, _build_piper(), build_tts(), _FallbackSynthesizer (+27 more)

### Community 17 - "Shared Web UI Components"
Cohesion: 0.15
Nodes (28): COLORS, ICONS, BadgeColor, Field(), Panel(), PanelHeader(), Select(), Tabs() (+20 more)

### Community 18 - "Configuration API Routes"
Cohesion: 0.11
Nodes (38): persist_config(), Serialize the live config to TOML (secrets extracted to the store).      The sin, change_password(), ChangePasswordRequest, GeneralConfigUpdate, get_config(), LLMConfigUpdate, Any (+30 more)

### Community 19 - "MCP Configuration Routes"
Cohesion: 0.12
Nodes (34): MCPServerConfig, Configuration for a single MCP server.      Supports two transport modes:     -, add_mcp_server(), delete_mcp_server(), get_claude_config(), get_codex_config(), get_system_shell_allow(), list_mcp_servers() (+26 more)

### Community 20 - "System API Tests"
Cohesion: 0.10
Nodes (14): app(), bus(), client(), AsyncClient, FastAPI, MonkeyPatch, Path, Tests for the REST API endpoints. (+6 more)

### Community 21 - "Webhook API Tests"
Cohesion: 0.15
Nodes (12): _make_text_webhook(), AsyncClient, Text messages should be published to the inbound bus., Extended text messages (with URL preview) should extract text., Audio messages should be queued with metadata., Messages sent by us (fromMe=True) should be ignored., Non-message events should be acknowledged but not processed., Unsupported message types (sticker, location, etc.) should be ignored. (+4 more)

### Community 22 - "System MCP Server"
Cohesion: 0.09
Nodes (17): FastMCP, main(), Run the dax-system MCP server over stdio: python -m dax.mcp_servers.system, allowed_roots(), build_server(), Path, `dax-system` — a local MCP server exposing safe, typed PC-control tools.  Runs a, Construct the FastMCP server with all dax-system tools registered. (+9 more)

### Community 23 - "Selection and Syntax Utilities"
Cohesion: 0.08
Nodes (28): Enum, ChannelType, Language, MessageRole, StrEnum, Domain models for Dax Assistant.  Pure dataclasses with no external dependencies, Supported communication channels., Role of a message participant. (+20 more)

### Community 24 - "Core Configuration Models"
Cohesion: 0.09
Nodes (27): AnthropicProviderConfig, CodexProviderConfig, DeepSeekProviderConfig, GeminiProviderConfig, MCPConfig, OllamaProviderConfig, OpenAIProviderConfig, BaseModel (+19 more)

### Community 25 - "Dashboard API Client"
Cohesion: 0.09
Nodes (20): copy(), data(), ApiError, ConversationDetail, ConversationMessage, MCPServerStatus, MemoryEntry, OllamaModel (+12 more)

### Community 26 - "LLM Router Failover"
Cohesion: 0.12
Nodes (11): LLMProviderUnavailableError, No LLM provider is available to handle the request., LLMRouter, Any, LLM router — local-first fallback across decoupled providers.  Holds an ordered, Routes completion requests across an ordered list of providers., Swap the provider list in place (e.g. after a config change).          Mutates t, _FakeProvider (+3 more)

### Community 27 - "Logging Event Buffer"
Cohesion: 0.10
Nodes (15): datetime, LogRecord, Queue, LogBuffer, AbstractEventLoop, Any, In-memory log buffer + live fan-out for the web Logs viewer.  A single :class:`L, Stdlib log handler that retains recent records and fans them out live. (+7 more)

### Community 28 - "WhatsApp Channel Integration"
Cohesion: 0.06
Nodes (25): Any, Telegram channel — long-polling bot via the Telegram Bot API.  Uses long-polling, Deliver an assistant reply back to the originating Telegram chat., Split text into chunks no longer than *limit* characters., Telegram bot channel using long-polling., Long-poll getUpdates and publish inbound text messages to the bus., _split_message(), TelegramChannel (+17 more)

### Community 29 - "TypeScript Compiler Configuration"
Cohesion: 0.08
Nodes (25): DOM, DOM.Iterable, ES2023, src, vite/client, compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly (+17 more)

### Community 30 - "Web Dependency Injection"
Cohesion: 0.14
Nodes (23): auth_from_app(), bus_from_app(), get_approval(), get_auth(), get_bus(), get_config(), get_llm_router(), get_mcp_manager() (+15 more)

### Community 31 - "Human Approval Workflow"
Cohesion: 0.10
Nodes (11): ApprovalManager, Any, Human-in-the-loop approval gate for gated tool calls.  When the policy says a to, Resolve a pending request. Returns True if it matched a pending one., Tracks pending tool-confirmation requests and their resolutions., Register the async callback that delivers requests to the UI., Register the spoken-confirmation handler used for voice turns.          When a g, Ask the user to confirm a tool call.          Returns the chosen decision string (+3 more)

### Community 32 - "System Status API"
Cohesion: 0.14
Nodes (24): get_logs(), get_mcp_status(), get_status(), get_tool_audit(), get_tool_policy(), list_llm_models(), list_ollama_models(), Any (+16 more)

### Community 33 - "Keyboard Collection Navigation"
Cohesion: 0.09
Nodes (39): ai(), as(), Ba(), bo(), cp(), cs(), dp(), ds() (+31 more)

### Community 34 - "MCP Lifecycle Manager"
Cohesion: 0.15
Nodes (11): MCPManager, Any, Launch and connect to all enabled MCP servers., Connect to a server and register its tools live. Returns tool count.          Re, Disconnect a server (if connected) and drop its tools., Disconnect a server from the MCP lifecycle worker task., Disconnect from all MCP servers., Per-configured-server connection + tool status for the web UI. (+3 more)

### Community 35 - "Secure Configuration Serialization"
Cohesion: 0.14
Nodes (22): _del_path(), dump_config_toml(), _env_var_for_header(), _extract_secrets(), _get_path(), _is_sensitive_header(), Any, Path (+14 more)

### Community 36 - "Realtime Chat Interface"
Cohesion: 0.13
Nodes (15): ConversationSummary, Modal(), AgentEvent, ChatMessage, ConfirmationRequest, nextId(), Status, useChatSocket() (+7 more)

### Community 37 - "Frontend Runtime Dependencies"
Cohesion: 0.10
Nodes (21): clsx, @heroui/react, @heroui/styles, highlight.js, lucide-react, react-dom, react-markdown, react-router (+13 more)

### Community 38 - "Memory File Management"
Cohesion: 0.26
Nodes (20): create_memory(), delete_memory(), get_memory(), list_memory(), _memory_dir(), _memory_frontmatter(), _memory_path(), _memory_slug() (+12 more)

### Community 39 - "LLM Provider Factory"
Cohesion: 0.17
Nodes (15): LLMConfig, LLMConfig, LLM routing and provider configuration.      The local Ollama provider is the de, build_provider(), build_providers(), build_router(), _ollama_base_url(), Build the LLM router and providers from configuration.  This is the single place (+7 more)

### Community 40 - "Token Authentication Manager"
Cohesion: 0.13
Nodes (10): SecurityConfig, AuthManager, Request, Response, WebSocket, Validate a WebSocket connection via cookie or ?token= query param., FastAPI dependency that rejects unauthenticated requests with 401., Validates logins and issues/validates signed session tokens.      Lives on ``app (+2 more)

### Community 41 - "MCP Client Connections"
Cohesion: 0.13
Nodes (10): MCPClient, Any, MCP client wrapper — manages a connection to a single MCP server.  Supports two, Connect via Streamable HTTP transport (remote server)., Close the session and terminate any subprocesses., Clean up resources, suppressing anyio cancel scope errors., Query the server for available tools and return their schemas., Wraps a connection to a single MCP server.      Args:         server_name: Uniqu (+2 more)

### Community 42 - "System Prompt Construction"
Cohesion: 0.14
Nodes (15): Any, System-prompt assembly for the agent.  Builds the per-turn system prompt from th, Append a concrete live tool inventory to the base system prompt.      Grouping b, Assembles the per-turn system prompt (tools + memory + voice style)., Return the full system prompt for this turn., Read user-curated memory files and format them for the system prompt.          E, SystemPromptBuilder, _tool_inventory() (+7 more)

### Community 43 - "Frontend Development Dependencies"
Cohesion: 0.11
Nodes (19): jsdom, tailwindcss, @tailwindcss/vite, @testing-library/jest-dom, @testing-library/react, @types/react, @types/react-dom, @vitejs/plugin-react-swc (+11 more)

### Community 44 - "Logs and Configuration Types"
Cohesion: 0.13
Nodes (16): Badge(), useLogStream(), wsUrl(), LEVEL_COLOR, LEVELS, LogsPage(), GeneralConfig, LLMConfig (+8 more)

### Community 45 - "Gemini Provider Adapter"
Cohesion: 0.16
Nodes (7): Content, GeminiProvider, Any, Google Gemini provider adapter — official `google-genai` SDK.  Translates the Op, Implements the LLMProvider port over the Gemini generateContent API., TestGeminiProvider, Tool

### Community 46 - "Telegram Bot Channel"
Cohesion: 0.07
Nodes (15): Conversation, Return the most recent message, or None if empty., An ordered sequence of messages within a channel session.      Mutable — message, Append a message and update the timestamp., Persist a conversation and its messages., Retrieve a conversation by ID, or None if not found., Return the conversation for (channel, session_key), creating one if needed., Retrieve the most recent conversations for a channel. (+7 more)

### Community 47 - "Anthropic Provider Adapter"
Cohesion: 0.19
Nodes (5): AnthropicProvider, Any, Anthropic (Claude) provider adapter — official `anthropic` SDK.  Translates the, Implements the LLMProvider port over the Anthropic Messages API., TestAnthropicProvider

### Community 48 - "Encrypted Secret Storage"
Cohesion: 0.19
Nodes (7): Connection, Path, Seed ``os.environ`` from the store without clobbering real env vars.          Re, One-time migration: import ``KEY=value`` lines from a legacy .env.          Only, Encrypted key/value secret store on top of SQLite + a Fernet key file., Encrypt and persist a secret; also export it to ``os.environ``., SecretStore

### Community 49 - "Authentication API Routes"
Cohesion: 0.23
Nodes (16): AuthDep, auth_status(), AuthStatus, login(), LoginRequest, LoginResponse, logout(), BaseModel (+8 more)

### Community 50 - "Shell Command Allowlist"
Cohesion: 0.09
Nodes (13): Channel, Input/output channel for user interaction.      Channels receive messages from u, Unique channel identifier (e.g., 'voice', 'whatsapp', 'web')., Initialize and begin listening for messages., Gracefully shut down the channel., Yield incoming messages from this channel., Deliver a response message through this channel., Dispatcher (+5 more)

### Community 51 - "Voice Activity Detection"
Cohesion: 0.08
Nodes (25): Exception, ConfigError, DaxError, Domain exception hierarchy for Dax Assistant., MCP tool execution failed., Requested tool does not exist in the registry., Tool was found but execution failed., Database or persistence operation failed. (+17 more)

### Community 52 - "Audio Capture Playback"
Cohesion: 0.10
Nodes (36): Am(), bm(), br(), canSelectItem(), clearSelection(), da(), dm(), eh() (+28 more)

### Community 53 - "Shared Test Fixtures"
Cohesion: 0.12
Nodes (17): config_from_file(), database(), default_config(), isolate_config_env(), message_bus(), MonkeyPatch, Path, Shared test fixtures for Dax Assistant. (+9 more)

### Community 54 - "Configuration Loading Tests"
Cohesion: 0.18
Nodes (11): _bootstrap_secrets(), _flatten_toml(), load_config(), Any, Path, Load configuration from TOML file and environment variables.      Args:, Seed os.environ from the encrypted secret store before config is built.      Sec, Convert nested TOML dict to the format Pydantic Settings expects.      Keeps nes (+3 more)

### Community 55 - "Wake Word Detection"
Cohesion: 0.12
Nodes (12): Wake word detection failed., WakeWordError, AbstractEventLoop, VoiceConfig, ndarray, Wake word detection via OpenWakeWord.  Wraps the OpenWakeWord inference model be, Reset the model's internal state between activations., Detect wake words in streaming audio chunks.      Args:         model_names: Lis (+4 more)

### Community 56 - "WebSocket Chat Server"
Cohesion: 0.18
Nodes (10): approval_from_app(), Any, WebSocket, WebSocket chat endpoint for the web UI.  Handles inbound messages from browser c, Manages active WebSocket connections.      For a single-user assistant, we typic, Send data to a specific WebSocket connection., Send data to all connected WebSocket clients., WebSocket endpoint for real-time chat with Dax.      Protocol:         Client se (+2 more)

### Community 57 - "Collection Selection Management"
Cohesion: 0.16
Nodes (15): create_app(), FastAPI, FastAPI application factory.  Creates the web server with lifespan management, C, Create and configure the FastAPI application., app(), bus(), client(), _make_audio_webhook() (+7 more)

### Community 58 - "Configuration Serialization Tests"
Cohesion: 0.11
Nodes (20): BaseSettings, PydanticBaseSettingsSource, DaxConfig, Root configuration for Dax Assistant.      Settings are loaded in order of prior, Path, Tests for TOML config serialization + secret extraction (config_io)., A field already holding an {env:…} ref is kept verbatim, not re-stored., Authorization-style headers move to the store as {env:…} refs. (+12 more)

### Community 59 - "Domain Error Hierarchy"
Cohesion: 0.14
Nodes (13): Choosing / adding LLM providers, Configuration, Dax Assistant, Development, Highlights, Layout, License, PC control & safety (+5 more)

### Community 60 - "Password Authentication Tests"
Cohesion: 0.19
Nodes (12): hash_password(), _main(), Single-user authentication for the web UI and API.  Dax is a personal assistant:, Return an argon2id hash of ``password``., Check ``password`` against a stored argon2 hash., verify_password(), auth_app(), auth_client() (+4 more)

### Community 61 - "Application Settings Models"
Cohesion: 0.21
Nodes (4): Allow / ask / deny policy for tool execution (fnmatch patterns).      An empty `, ToolPolicyConfig, Tests for the tool execution policy., TestToolPolicy

### Community 62 - "Voice Model Downloads"
Cohesion: 0.21
Nodes (13): _download(), download_kokoro(), download_piper_voices(), download_wake_word(), download_whisper(), main(), Path, Download voice models for Dax Assistant.  Fetches everything the voice pipeline (+5 more)

### Community 63 - "OpenAI Provider Adapter"
Cohesion: 0.19
Nodes (5): OpenAIProvider, Any, OpenAI provider adapter — official `openai` SDK (Chat Completions).  Also serves, Implements the LLMProvider port over the OpenAI Chat Completions API., TestOpenAIProvider

### Community 64 - "Mutable Collection State"
Cohesion: 0.08
Nodes (14): Initialize all components in dependency order., Serialize live voice reloads so repeated UI saves remain safe., Restart the voice channel and pipeline with the live configuration., Voice channel adapter — bridges the dispatcher to the voice pipeline.  The voice, Voice channel adapter for the dispatcher.      Inbound messages are published by, No-op — the voice pipeline manages its own lifecycle., No-op — the voice pipeline manages its own lifecycle., Enqueue an outbound message for the voice pipeline to consume.          Called b (+6 more)

### Community 65 - "Web Application Entrypoint"
Cohesion: 0.18
Nodes (10): fail(), info(), message(), toHTML(), value(), ToastProvider(), useConfig(), McpPage() (+2 more)

### Community 66 - "Codex Provider Adapter"
Cohesion: 0.16
Nodes (10): LLMError, LLMTimeoutError, LLM provider communication failed., LLM request timed out., CodexProvider, Any, OpenAI Codex CLI provider.  Runs ``codex exec --json`` as a subprocess to use th, Parse the JSONL event stream and return the final agent message. (+2 more)

### Community 67 - "MCP Environment Resolution"
Cohesion: 0.22
Nodes (6): Replace {env:VAR_NAME} patterns with environment variable values., Resolve env vars in all values of a dict., _resolve_env_dict(), _resolve_env_vars(), Tests for MCP manager env var resolution and transport selection., TestEnvVarResolution

### Community 68 - "MCP Marketplace Interface"
Cohesion: 0.22
Nodes (9): MCPPreset, RegistryServer, McpMarketplacePage(), envToText(), FormMode, headersToText(), parseEnv(), parseHeaders() (+1 more)

### Community 69 - "Project Architecture Overview"
Cohesion: 0.15
Nodes (11): Architecture, Channels (`channels/`), Commands, Config & secrets (`core/config.py`, `web/routes/api.py`), LLM layer (`llm/`) — fully decoupled behind the `LLMProvider` port, MCP (`mcp/`) and the bundled server, Message flow (the spine), Safety model (+3 more)

### Community 70 - "End-to-End Web Tests"
Cohesion: 0.13
Nodes (23): Ag(), at(), canSelectItemIn(), Cw(), dg(), Eg(), getItem(), getKeyAfter() (+15 more)

### Community 71 - "Collection Selection Queries"
Cohesion: 0.13
Nodes (16): addNode(), getCollection(), getMutableCollection(), getMutableNode(), hf(), it(), Np(), removeNode() (+8 more)

### Community 72 - "Application Shell Theming"
Cohesion: 0.24
Nodes (9): AppShell(), NAV, NavItem, TITLES, ThemeToggle(), apply(), resolveInitial(), Theme (+1 more)

### Community 73 - "Streaming Speech Synthesis"
Cohesion: 0.20
Nodes (17): Fg(), findKey(), findNextNonDisabled(), getFirstKey(), getKeyAbove(), getKeyBelow(), getKeyForSearch(), getKeyLeftOf() (+9 more)

### Community 74 - "Application Command Entrypoint"
Cohesion: 0.06
Nodes (21): _configure_logging(), DaxApp, Path, Application bootstrap and lifecycle management.  Wires all components together v, Create a DaxApp instance from a config file path., Mirror the live shell allowlist into config and rewrite the TOML., Expose FastAPI app for testing., Restart the Telegram channel to apply config changes without a full         app (+13 more)

### Community 75 - "Shell Command Parsing"
Cohesion: 0.10
Nodes (10): Runtime allowlist of shell binaries the assistant may run on this PC.  This is t, Extract the bare binary name from a command string (``/bin/ls -l`` → ``ls``)., Mutable, observable set of allowed shell binaries (order preserved)., Append a binary if new. Returns True if it was actually added., Replace the whole list (de-duped, order preserved) and persist., shell_binary(), ShellAllowlist, Tests for the shell-command allowlist. (+2 more)

### Community 78 - "Single Page Middleware"
Cohesion: 0.24
Nodes (7): Scope, Response, SPA-aware static file serving.  Subclasses Starlette's StaticFiles to return ind, StaticFiles that falls back to index.html for SPA routing.      For any path tha, Serve index.html as fallback., SPAStaticFiles, StaticFiles

### Community 79 - "Conversation API Routes"
Cohesion: 0.27
Nodes (9): delete_conversation(), get_conversation(), list_conversations(), Any, Request, Conversation history endpoints — list, fetch, delete web chats., List recent web conversations for the sidebar., Return a conversation with its messages. (+1 more)

### Community 80 - "WebSocket Channel Adapter"
Cohesion: 0.17
Nodes (16): add(), __addSublanguage(), addText(), componentDidCatch(), currentNode(), dw(), Jk(), jo() (+8 more)

### Community 81 - "Web Authentication Interface"
Cohesion: 0.21
Nodes (14): ab(), db(), eb(), hb(), ib(), jb(), mb(), nb() (+6 more)

### Community 84 - "Speaker Verification Embeddings"
Cohesion: 0.08
Nodes (16): main(), ndarray, Enroll the owner's voice for speaker verification (Voice ID).  Records a few sho, _record(), Map a spoken answer to a decision string (es/en)., ndarray, Speaker verification (Voice ID) via Resemblyzer.  Optional, Alexa-style "only re, Build and persist an owner profile from one or more recordings.          The ref (+8 more)

### Community 86 - "Production Social Icons"
Cohesion: 0.48
Nodes (7): Bluesky Icon, Discord Icon, Documentation and Code Icon, GitHub Icon, Social Profile Icon, Web Icon Sprite, X Social Platform Icon

### Community 88 - "Frontend Build Scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, preview, test, test:coverage, test:run

### Community 89 - "Public Social Icons"
Cohesion: 0.29
Nodes (7): Bluesky Butterfly Icon, Discord Mascot Icon, Documentation and Code Icon, GitHub Octocat Icon, Social and Navigation Icon Sprite, Social Profile and Star Icon, X Social Network Icon

### Community 91 - "Interactive Installation Script"
Cohesion: 0.60
Nodes (5): fail(), info(), ok(), install.sh script, warn()

### Community 93 - "SPA HTML Entrypoints"
Cohesion: 0.50
Nodes (4): Built Frontend Assets, Production SPA Shell, Development SPA Shell, React TypeScript Entrypoint

### Community 95 - "Speaker Voice Enrollment"
Cohesion: 0.15
Nodes (13): Ea(), fy(), ignoreMatch(), Ij(), Lj(), mk(), mx(), Nw() (+5 more)

### Community 96 - "Frontend Package Metadata"
Cohesion: 0.40
Nodes (4): name, private, type, version

### Community 98 - "Production Favicon Graphics"
Cohesion: 0.50
Nodes (4): Favicon Graphic, Lightning Bolt Symbol, Purple Angular Mark, Soft Glow Highlights

### Community 102 - "React Runtime Dependency"
Cohesion: 0.17
Nodes (12): addDescendants(), bp(), commit(), filter(), fm(), getChildren(), jm(), jp() (+4 more)

### Community 150 - "MCPConfig"
Cohesion: 0.24
Nodes (10): Ao(), ix(), ks(), ls(), nx(), ox(), QA(), splice() (+2 more)

### Community 151 - "Badge"
Cohesion: 0.20
Nodes (10): Go(), jd(), md(), oa(), tr(), uj(), unshift(), vl() (+2 more)

### Community 152 - "._make_client"
Cohesion: 0.29
Nodes (6): _get_oauth_token(), MCP server manager — implements the ToolProvider protocol.  Manages the lifecycl, Build an unconnected client for a server config (env resolved)., Snapshot desktop-session vars present in the current environment., Get stored OAuth access token for an MCP server, if available., _session_passthrough_env()

### Community 153 - "getFullNode"
Cohesion: 0.33
Nodes (5): api, AuthStatus, AuthGate(), Markdown, LoginPage()

### Community 154 - "vg"
Cohesion: 0.25
Nodes (8): Ay(), Ey(), fb(), gb(), lb(), pb(), Ty(), Uv()

### Community 155 - "._initialize_schema"
Cohesion: 0.25
Nodes (8): build(), childNodes(), getChildState(), getFullNode(), Gm(), iterateCollection(), km(), Wm()

### Community 156 - "zy"
Cohesion: 0.25
Nodes (8): closeAllNodes(), closeNode(), endScope(), finalize(), openNode(), span(), startScope(), walk()

### Community 157 - ".connection"
Cohesion: 0.29
Nodes (7): consume(), nj(), pop(), pushMany(), px(), setCursor(), unshiftMany()

### Community 158 - "clsx"
Cohesion: 0.29
Nodes (7): firstSelectedKey(), getKeyRange(), getKeyRangeInternal(), lastSelectedKey(), ol(), Rm(), zm()

### Community 160 - "Ow"
Cohesion: 0.33
Nodes (6): Aw(), kw(), Mw(), Ow(), qw(), Ry()

### Community 161 - "zy"
Cohesion: 0.40
Nodes (6): By(), cb(), sb(), Vy(), wb(), zy()

### Community 162 - "bh"
Cohesion: 0.50
Nodes (5): bh(), Sh(), wh(), xh(), yh()

### Community 163 - "freeze"
Cohesion: 0.50
Nodes (5): freeze(), parse(), process(), processSync(), stringify()

### Community 164 - "Lm"
Cohesion: 0.50
Nodes (4): Im(), Lm(), Xv(), yv()

## Knowledge Gaps
- **137 isolated node(s):** `dax-assistant`, `install-service.sh script`, `name`, `private`, `version` (+132 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **48 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Message` connect `Agent Message Processing` to `Voice Processing Pipeline`, `Agent Tool Policy`, `Tool Dispatch Interfaces`, `Application Storage Lifecycle`, `OAuth Webhook Integration`, `Event Scheduling Runtime`, `Voice Conversation State`, `React Collection Rendering`, `Speech Synthesis Engines`, `Selection and Syntax Utilities`, `LLM Router Failover`, `WhatsApp Channel Integration`, `LLM Provider Factory`, `Gemini Provider Adapter`, `Telegram Bot Channel`, `Anthropic Provider Adapter`, `Shell Command Allowlist`, `Shared Test Fixtures`, `WebSocket Chat Server`, `OpenAI Provider Adapter`, `Mutable Collection State`, `Codex Provider Adapter`, `Application Command Entrypoint`, `Speaker Verification Embeddings`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `DaxApp` connect `Application Command Entrypoint` to `Mutable Collection State`, `MCP Lifecycle Manager`, `Agent Tool Policy`, `Application Storage Lifecycle`, `Agent Message Processing`, `OAuth Webhook Integration`, `Shell Command Parsing`, `Voice Conversation State`, `Encrypted Secret Storage`, `Shell Command Allowlist`, `Configuration Serialization Tests`, `Logging Event Buffer`, `WhatsApp Channel Integration`, `Human Approval Workflow`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `VoicePipeline` connect `Voice Conversation State` to `Mutable Collection State`, `Voice Processing Pipeline`, `Agent Message Processing`, `Application Command Entrypoint`, `Event Scheduling Runtime`, `Speech Synthesis Engines`, `Voice Activity Detection`, `Speaker Verification Embeddings`, `Wake Word Detection`, `Selection and Syntax Utilities`, `Human Approval Workflow`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `i()` (e.g. with `Ad()` and `Ao()`) actually correct?**
  _`i()` has 78 INFERRED edges - model-reasoned connections that need verification._
- **Are the 100 inferred relationships involving `n()` (e.g. with `Ad()` and `add()`) actually correct?**
  _`n()` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 102 inferred relationships involving `r()` (e.g. with `Ad()` and `ae()`) actually correct?**
  _`r()` has 102 INFERRED edges - model-reasoned connections that need verification._
- **Are the 86 inferred relationships involving `Message` (e.g. with `TelegramChannel` and `VoiceChannel`) actually correct?**
  _`Message` has 86 INFERRED edges - model-reasoned connections that need verification._