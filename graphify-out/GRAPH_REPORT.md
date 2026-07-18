# Graph Report - dax-assistant  (2026-07-18)

## Corpus Check
- 148 files · ~93,084 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2847 nodes · 8070 edges · 188 communities (129 shown, 59 thin omitted)
- Extraction: 75% EXTRACTED · 25% INFERRED · 0% AMBIGUOUS · INFERRED: 2024 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4b525c20`
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
- constructor
- Badge
- ._make_client
- getFullNode
- Mp
- ._initialize_schema
- xl
- TestYesNoParser
- clsx
- .get_server_for_tool
- freeze
- create_app
- ww
- datetime
- sx
- react
- MemoryTab.tsx
- oauth.py
- oauth_callback
- Any
- ai
- datetime
- app
- ._initialize_schema
- Pw
- ds
- .delete_conversation
- .connection
- .stop
- .get_recent_conversations
- .get_tool_audit
- .list_conversations
- .log_tool_execution
- .start
- ak
- by
- ym
- wg

## God Nodes (most connected - your core abstractions)
1. `i()` - 174 edges
2. `n()` - 170 edges
3. `t()` - 149 edges
4. `r()` - 145 edges
5. `Message` - 140 edges
6. `a()` - 112 edges
7. `MessageBus` - 99 edges
8. `push()` - 93 edges
9. `s()` - 88 edges
10. `l()` - 67 edges

## Surprising Connections (you probably didn't know these)
- `ModelSelector()` --indirect_call--> `m()`  [INFERRED]
  web/src/pages/Chat.tsx → src/dax/web/static/assets/index-Dvu6q04l.js
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

## Communities (188 total, 59 thin omitted)

### Community 0 - "Bundle Collection Utilities"
Cohesion: 0.02
Nodes (29): an(), basename(), clear(), componentDidCatch(), continuePropagation(), Dj(), Ej(), Fg() (+21 more)

### Community 1 - "Voice Processing Pipeline"
Cohesion: 0.09
Nodes (18): CallbackFlags, AudioCapture, AudioPlayer, ndarray, Audio I/O — microphone capture and speaker playback.  Uses sounddevice for cross, sounddevice callback — runs on the audio thread., Play audio through the default output device., Play a full audio buffer and block until playback finishes.          Args: (+10 more)

### Community 2 - "Frontend Runtime Internals"
Cohesion: 0.08
Nodes (124): a(), Ad(), ae(), aj(), Am(), ar(), b(), be() (+116 more)

### Community 3 - "Agent Tool Policy"
Cohesion: 0.10
Nodes (13): _MockLLM, _MockStorage, _MockTools, Any, Tests for the orchestrator agent with LLM + tool calling., Agent returns LLM text response when no tools are called., Mock LLM that returns configurable responses., Mock tool provider that returns configurable results. (+5 more)

### Community 4 - "Tree Collection Traversal"
Cohesion: 0.06
Nodes (97): __(), aa(), ac(), add(), Ag(), ao(), Ap(), bc() (+89 more)

### Community 5 - "Tool Dispatch Interfaces"
Cohesion: 0.08
Nodes (20): LLMProvider, Protocol, Protocol interfaces (ports) for the hexagonal architecture.  All adapters implem, Launch and connect to all configured MCP servers., Shut down all MCP server connections., Return all available tool schemas across all servers., Return the tool schemas most relevant to ``query``, capped at         ``max_tool, Return the server that owns ``tool_name``, or None if unknown. (+12 more)

### Community 6 - "DOM Collection Mutation"
Cohesion: 0.07
Nodes (72): al(), announce(), appendChild(), at(), bf(), bl(), bt(), cf() (+64 more)

### Community 7 - "Application Storage Lifecycle"
Cohesion: 0.14
Nodes (13): Database, SQLite database initialization and connection management., Async SQLite database wrapper.      Manages the connection lifecycle and schema, ConversationRepository, SQLite-backed conversation storage.      Implements the Storage protocol defined, Persist a conversation and all its messages., Integration tests for SQLite storage., A v1 DB (no session_key) must migrate without errors. (+5 more)

### Community 8 - "Agent Message Processing"
Cohesion: 0.09
Nodes (39): bp(), dp(), firstChild(), firstSelectedKey(), fp(), Ft(), gt(), hp() (+31 more)

### Community 9 - "OAuth Webhook Integration"
Cohesion: 0.14
Nodes (14): BusDep, Encrypted secret storage backed by SQLite.  Replaces the legacy ``.env`` file as, _extract_text(), Any, BaseModel, ConfigDep, Request, Response (+6 more)

### Community 10 - "MCP Tool Registry"
Cohesion: 0.05
Nodes (26): filter_tools_by_relevance(), mcp_tools_to_openai(), parse_tool_calls_from_response(), Any, Maps MCP tool schemas to OpenAI function-calling format.  We use the OpenAI tool, Convert a list of MCP tool schemas to OpenAI function-calling format.      MCP f, Filter tools based on keyword relevance to the user's query.      Always include, Parse tool calls from a litellm response into our internal format.      Args: (+18 more)

### Community 11 - "Collection Cursor Operations"
Cohesion: 0.09
Nodes (68): addChild(), addEventListener(), addTreeNode(), Au(), Bd(), bu(), Ca(), cd() (+60 more)

### Community 12 - "Event Scheduling Runtime"
Cohesion: 0.08
Nodes (23): Speech-to-text transcription failed., STTError, build_stt(), FallbackSpeechToText, OpenAISpeechToText, ndarray, VoiceConfig, Speech-to-Text via faster-whisper.  Wraps the CTranslate2-based Whisper model fo (+15 more)

### Community 13 - "Voice Conversation State"
Cohesion: 0.06
Nodes (27): ndarray, Full voice pipeline: wake -> listen -> transcribe -> respond -> converse.      R, Start all voice components and launch the pipeline thread., Stop the pipeline thread and all components., State-machine loop in the voice-pipeline thread., IDLE — listen for wake word activation., LISTENING — buffer audio and detect end-of-speech.          With adaptive endpoi, Track speech/silence on *float_chunk*; return True at end-of-speech.          En (+19 more)

### Community 14 - "React Collection Rendering"
Cohesion: 0.08
Nodes (23): build_messages_for_llm(), Any, Shared LLM helpers: the system prompt and the message builder.  The conversation, Build the OpenAI-format message list for an LLM call.      Converts our Message, Remove provider control markup that must never reach users or TTS., sanitize_assistant_text(), Agent, Any (+15 more)

### Community 15 - "Conversation Data Models"
Cohesion: 0.07
Nodes (51): bj(), bv(), canSelectItemIn(), clearSelection(), Em(), Er(), findKey(), findNextNonDisabled() (+43 more)

### Community 16 - "Speech Synthesis Engines"
Cohesion: 0.05
Nodes (38): PiperVoice, Voice pipeline configuration., VoiceConfig, Text-to-speech synthesis failed., TTSError, _build_local_tts(), _build_piper(), build_tts() (+30 more)

### Community 17 - "Shared Web UI Components"
Cohesion: 0.13
Nodes (32): index(), api, COLORS, ICONS, Badge(), BadgeColor, Field(), PanelHeader() (+24 more)

### Community 18 - "Configuration API Routes"
Cohesion: 0.11
Nodes (38): persist_config(), Serialize the live config to TOML (secrets extracted to the store).      The sin, change_password(), ChangePasswordRequest, GeneralConfigUpdate, get_config(), LLMConfigUpdate, Any (+30 more)

### Community 19 - "MCP Configuration Routes"
Cohesion: 0.07
Nodes (50): __addSublanguage(), af(), Ba(), bs(), bx(), cn(), consume(), currentNode() (+42 more)

### Community 20 - "System API Tests"
Cohesion: 0.09
Nodes (16): app(), bus(), client(), AsyncClient, FastAPI, MonkeyPatch, Path, Tests for the REST API endpoints. (+8 more)

### Community 21 - "Webhook API Tests"
Cohesion: 0.07
Nodes (31): MessageBus, Async message bus for inter-component communication.  Decouples channels from th, Async message bus using asyncio queues.      Thread-safe for posting from voice, Initialize the queues. Must be called from an async context., Number of messages waiting to be processed., Number of responses waiting to be dispatched., Tests for the async message bus., TestMessageBus (+23 more)

### Community 22 - "System MCP Server"
Cohesion: 0.09
Nodes (17): FastMCP, main(), Run the dax-system MCP server over stdio: python -m dax.mcp_servers.system, allowed_roots(), build_server(), Path, `dax-system` — a local MCP server exposing safe, typed PC-control tools.  Runs a, Construct the FastMCP server with all dax-system tools registered. (+9 more)

### Community 23 - "Selection and Syntax Utilities"
Cohesion: 0.12
Nodes (34): MCPServerConfig, Configuration for a single MCP server.      Supports two transport modes:     -, add_mcp_server(), delete_mcp_server(), get_claude_config(), get_codex_config(), get_system_shell_allow(), list_mcp_servers() (+26 more)

### Community 24 - "Core Configuration Models"
Cohesion: 0.09
Nodes (27): AnthropicProviderConfig, CodexProviderConfig, DeepSeekProviderConfig, GeminiProviderConfig, MCPConfig, OllamaProviderConfig, OpenAIProviderConfig, BaseModel (+19 more)

### Community 25 - "Dashboard API Client"
Cohesion: 0.18
Nodes (11): FullConfig, GeneralConfig, LLMConfig, MCPServerConfig, SecurityConfig, StatusResponse, TelegramConfig, ToolsConfig (+3 more)

### Community 26 - "LLM Router Failover"
Cohesion: 0.12
Nodes (11): LLMProviderUnavailableError, No LLM provider is available to handle the request., LLMRouter, Any, LLM router — local-first fallback across decoupled providers.  Holds an ordered, Routes completion requests across an ordered list of providers., Swap the provider list in place (e.g. after a config change).          Mutates t, _FakeProvider (+3 more)

### Community 27 - "Logging Event Buffer"
Cohesion: 0.16
Nodes (9): LogRecord, Queue, LogBuffer, AbstractEventLoop, Any, Stdlib log handler that retains recent records and fans them out live., Register the event loop used to deliver live records to subscribers., Return the most recent records (oldest first), capped at ``limit``. (+1 more)

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
Cohesion: 0.20
Nodes (17): File, _build_preview_engine(), _decode_enrollment_wav(), delete_voice_profile(), _encode_wav(), enroll_voice(), get_voice_profile(), preview_voice() (+9 more)

### Community 34 - "MCP Lifecycle Manager"
Cohesion: 0.18
Nodes (8): MCPManager, Launch and connect to all enabled MCP servers., Connect to a server and register its tools live. Returns tool count.          Re, Disconnect a server (if connected) and drop its tools., Disconnect a server from the MCP lifecycle worker task., Disconnect from all MCP servers., Return which server owns ``tool_name`` (ToolProvider port)., Manages multiple MCP server connections.      Implements the ToolProvider protoc

### Community 35 - "Secure Configuration Serialization"
Cohesion: 0.14
Nodes (22): _del_path(), dump_config_toml(), _env_var_for_header(), _extract_secrets(), _get_path(), _is_sensitive_header(), Any, Path (+14 more)

### Community 36 - "Realtime Chat Interface"
Cohesion: 0.11
Nodes (16): ConversationSummary, Markdown, Modal(), AgentEvent, ChatMessage, ConfirmationRequest, nextId(), Status (+8 more)

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
Cohesion: 0.31
Nodes (7): Select(), useLogStream(), wsUrl(), LEVEL_COLOR, LEVELS, LogsPage(), LogEntry

### Community 45 - "Gemini Provider Adapter"
Cohesion: 0.16
Nodes (7): Content, GeminiProvider, Any, Google Gemini provider adapter — official `google-genai` SDK.  Translates the Op, Implements the LLMProvider port over the Gemini generateContent API., TestGeminiProvider, Tool

### Community 46 - "Telegram Bot Channel"
Cohesion: 0.08
Nodes (13): Conversation, Return the most recent message, or None if empty., An ordered sequence of messages within a channel session.      Mutable — message, Append a message and update the timestamp., Persist a conversation and its messages., Retrieve a conversation by ID, or None if not found., Return the conversation for (channel, session_key), creating one if needed., Retrieve the most recent conversations for a channel. (+5 more)

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
Cohesion: 0.11
Nodes (23): bo(), cs(), es(), Fo(), fs(), G(), gs(), Ho() (+15 more)

### Community 51 - "Voice Activity Detection"
Cohesion: 0.08
Nodes (25): Exception, ConfigError, DaxError, Domain exception hierarchy for Dax Assistant., MCP tool execution failed., Requested tool does not exist in the registry., Tool was found but execution failed., Database or persistence operation failed. (+17 more)

### Community 52 - "Audio Capture Playback"
Cohesion: 0.08
Nodes (14): Initialize all components in dependency order., Restart the voice channel and pipeline with the live configuration., Voice channel adapter — bridges the dispatcher to the voice pipeline.  The voice, Voice channel adapter for the dispatcher.      Inbound messages are published by, No-op — the voice pipeline manages its own lifecycle., No-op — the voice pipeline manages its own lifecycle., Enqueue an outbound message for the voice pipeline to consume.          Called b, Discard any queued responses left over from a previous turn.          The pipeli (+6 more)

### Community 53 - "Shared Test Fixtures"
Cohesion: 0.13
Nodes (15): config_from_file(), database(), default_config(), isolate_config_env(), message_bus(), MonkeyPatch, Path, Shared test fixtures for Dax Assistant. (+7 more)

### Community 54 - "Configuration Loading Tests"
Cohesion: 0.18
Nodes (11): _bootstrap_secrets(), _flatten_toml(), load_config(), Any, Path, Load configuration from TOML file and environment variables.      Args:, Seed os.environ from the encrypted secret store before config is built.      Sec, Convert nested TOML dict to the format Pydantic Settings expects.      Keeps nes (+3 more)

### Community 55 - "Wake Word Detection"
Cohesion: 0.14
Nodes (10): Wake word detection failed., WakeWordError, ndarray, Wake word detection via OpenWakeWord.  Wraps the OpenWakeWord inference model be, Reset the model's internal state between activations., Detect wake words in streaming audio chunks.      Args:         model_names: Lis, Download models (if needed) and initialise the detector., Release the model resources. (+2 more)

### Community 56 - "WebSocket Chat Server"
Cohesion: 0.18
Nodes (10): approval_from_app(), Any, WebSocket, WebSocket chat endpoint for the web UI.  Handles inbound messages from browser c, Manages active WebSocket connections.      For a single-user assistant, we typic, Send data to a specific WebSocket connection., Send data to all connected WebSocket clients., WebSocket endpoint for real-time chat with Dax.      Protocol:         Client se (+2 more)

### Community 57 - "Collection Selection Management"
Cohesion: 0.09
Nodes (19): A request to execute an MCP tool., The result of an MCP tool execution., ToolCall, ToolResult, Execute a tool call on the appropriate MCP server., Execute a tool call on this server., Execute a tool call on the appropriate MCP server., Apply the policy. Returns a blocking ToolResult, or None to proceed. (+11 more)

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
Cohesion: 0.14
Nodes (12): Allow / ask / deny policy for tool execution (fnmatch patterns).      An empty `, ToolPolicyConfig, Decision, StrEnum, Tool execution policy — allow / ask / deny per tool name.  The agent consults th, Resolves an allow/ask/deny decision for a tool name., Update rules in place so the agent picks them up without a restart., ToolPolicy (+4 more)

### Community 62 - "Voice Model Downloads"
Cohesion: 0.21
Nodes (13): _download(), download_kokoro(), download_piper_voices(), download_wake_word(), download_whisper(), main(), Path, Download voice models for Dax Assistant.  Fetches everything the voice pipeline (+5 more)

### Community 63 - "OpenAI Provider Adapter"
Cohesion: 0.19
Nodes (5): OpenAIProvider, Any, OpenAI provider adapter — official `openai` SDK (Chat Completions).  Also serves, Implements the LLMProvider port over the OpenAI Chat Completions API., TestOpenAIProvider

### Community 64 - "Mutable Collection State"
Cohesion: 0.09
Nodes (13): Channel, Input/output channel for user interaction.      Channels receive messages from u, Unique channel identifier (e.g., 'voice', 'whatsapp', 'web')., Initialize and begin listening for messages., Gracefully shut down the channel., Yield incoming messages from this channel., Deliver a response message through this channel., Dispatcher (+5 more)

### Community 65 - "Web Application Entrypoint"
Cohesion: 0.13
Nodes (14): fail(), info(), message(), MCPServerStatus, ToolAuditEntry, ToastProvider(), Panel(), useConfig() (+6 more)

### Community 66 - "Codex Provider Adapter"
Cohesion: 0.16
Nodes (10): LLMError, LLMTimeoutError, LLM provider communication failed., LLM request timed out., CodexProvider, Any, OpenAI Codex CLI provider.  Runs ``codex exec --json`` as a subprocess to use th, Parse the JSONL event stream and return the final agent message. (+2 more)

### Community 67 - "MCP Environment Resolution"
Cohesion: 0.21
Nodes (6): Replace {env:VAR_NAME} patterns with environment variable values., Resolve env vars in all values of a dict., _resolve_env_dict(), _resolve_env_vars(), Tests for MCP manager env var resolution and transport selection., TestEnvVarResolution

### Community 68 - "MCP Marketplace Interface"
Cohesion: 0.29
Nodes (9): toHTML(), value(), envToText(), FormMode, headersToText(), McpTab(), parseEnv(), parseHeaders() (+1 more)

### Community 69 - "Project Architecture Overview"
Cohesion: 0.15
Nodes (11): Architecture, Channels (`channels/`), Commands, Config & secrets (`core/config.py`, `web/routes/api.py`), LLM layer (`llm/`) — fully decoupled behind the `LLMProvider` port, MCP (`mcp/`) and the bundled server, Message flow (the spine), Safety model (+3 more)

### Community 70 - "End-to-End Web Tests"
Cohesion: 0.14
Nodes (8): Message, A single message in a conversation.      Immutable value object. All messages fl, Send a completion request and return the assistant's response.          Args:, Publish a message from a channel to the orchestrator., Wait for and return the next inbound message., Publish a response from the orchestrator to a channel., Wait for and return the next outbound message., TestMessage

### Community 71 - "Collection Selection Queries"
Cohesion: 0.29
Nodes (7): Cg(), Ch(), Dh(), Eh(), kg(), qg(), wh()

### Community 72 - "Application Shell Theming"
Cohesion: 0.24
Nodes (9): AppShell(), NAV, NavItem, TITLES, ThemeToggle(), apply(), resolveInitial(), Theme (+1 more)

### Community 73 - "Streaming Speech Synthesis"
Cohesion: 0.18
Nodes (16): ab(), bb(), cb(), db(), fb(), gb(), ib(), kb() (+8 more)

### Community 74 - "Application Command Entrypoint"
Cohesion: 0.10
Nodes (10): Runtime allowlist of shell binaries the assistant may run on this PC.  This is t, Extract the bare binary name from a command string (``/bin/ls -l`` → ``ls``)., Mutable, observable set of allowed shell binaries (order preserved)., Append a binary if new. Returns True if it was actually added., Replace the whole list (de-duped, order preserved) and persist., shell_binary(), ShellAllowlist, Tests for the shell-command allowlist. (+2 more)

### Community 75 - "Shell Command Parsing"
Cohesion: 0.13
Nodes (10): DaxApp, Mirror the live shell allowlist into config and rewrite the TOML., Expose FastAPI app for testing., Restart the Telegram channel to apply config changes without a full         app, Serialize live voice reloads so repeated UI saves remain safe., Shut down all components in reverse order., Run the application with embedded uvicorn server., Run shutdown to completion even if uvicorn/request cancellation leaks. (+2 more)

### Community 78 - "Single Page Middleware"
Cohesion: 0.24
Nodes (7): Scope, Response, SPA-aware static file serving.  Subclasses Starlette's StaticFiles to return ind, StaticFiles that falls back to index.html for SPA routing.      For any path tha, Serve index.html as fallback., SPAStaticFiles, StaticFiles

### Community 79 - "Conversation API Routes"
Cohesion: 0.27
Nodes (9): delete_conversation(), get_conversation(), list_conversations(), Any, Request, Conversation history endpoints — list, fetch, delete web chats., List recent web conversations for the sidebar., Return a conversation with its messages. (+1 more)

### Community 80 - "WebSocket Channel Adapter"
Cohesion: 0.18
Nodes (8): _configure_logging(), Path, Application bootstrap and lifecycle management.  Wires all components together v, Create a DaxApp instance from a config file path., Set up structlog with console rendering., main(), Entry point for running Dax Assistant: python -m dax, Parse arguments and run the application.

### Community 81 - "Web Authentication Interface"
Cohesion: 0.22
Nodes (4): Web channel — delegates to WebSocket manager.  The actual WebSocket handling is, Web UI channel adapter.      Bridges between the dispatcher and the WebSocket ma, Broadcast a message to all connected WebSocket clients., WebChannel

### Community 84 - "Speaker Verification Embeddings"
Cohesion: 0.08
Nodes (17): main(), ndarray, Enroll the owner's voice for speaker verification (Voice ID).  Records a few sho, _record(), ndarray, Speaker verification (Voice ID) via Resemblyzer.  Optional, Alexa-style "only re, Compute a voice embedding for *audio* (float32, 16 kHz mono)., Return True if *audio* matches the owner (or if verification is off).          A (+9 more)

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
Cohesion: 0.27
Nodes (11): _discover_auth(), _fetch_as_metadata(), _parse_www_authenticate(), AsyncClient, Discover OAuth endpoints for a remote MCP server.      Follows the MCP authoriza, Parse WWW-Authenticate header and discover auth endpoints., Fetch Authorization Server metadata via well-known endpoints., Try to find OAuth metadata via well-known URL patterns. (+3 more)

### Community 96 - "Frontend Package Metadata"
Cohesion: 0.40
Nodes (4): name, private, type, version

### Community 98 - "Production Favicon Graphics"
Cohesion: 0.50
Nodes (4): Favicon Graphic, Lightning Bolt Symbol, Purple Angular Mark, Soft Glow Highlights

### Community 102 - "React Runtime Dependency"
Cohesion: 0.20
Nodes (16): build(), canSelectItem(), childNodes(), extendSelection(), getChildState(), getFullNode(), getKey(), getKeyRange() (+8 more)

### Community 150 - "constructor"
Cohesion: 0.18
Nodes (13): addNode(), getCollection(), getMutableCollection(), getMutableNode(), kf(), op(), removeNode(), resetAfterSSR() (+5 more)

### Community 151 - "Badge"
Cohesion: 0.22
Nodes (9): addText(), closeAllNodes(), closeNode(), endScope(), finalize(), openNode(), span(), startScope() (+1 more)

### Community 152 - "._make_client"
Cohesion: 0.33
Nodes (5): _get_oauth_token(), MCP server manager — implements the ToolProvider protocol.  Manages the lifecycl, Snapshot desktop-session vars present in the current environment., Get stored OAuth access token for an MCP server, if available., _session_passthrough_env()

### Community 153 - "getFullNode"
Cohesion: 0.11
Nodes (16): ApiError, AuthStatus, ConversationDetail, ConversationMessage, MCPPreset, OllamaModel, RegistryServer, requestBlob() (+8 more)

### Community 154 - "Mp"
Cohesion: 0.22
Nodes (9): addDescendants(), CollectionBranch(), CollectionRoot(), commit(), filter(), Fm(), getChildren(), vp() (+1 more)

### Community 155 - "._initialize_schema"
Cohesion: 0.25
Nodes (8): ay(), hb(), jy(), transform(), vb(), vy(), yb(), Yv()

### Community 156 - "xl"
Cohesion: 1.00
Nodes (3): Gy(), Ky(), qy()

### Community 157 - "TestYesNoParser"
Cohesion: 0.08
Nodes (24): Enum, ChannelType, Language, MessageRole, StrEnum, Domain models for Dax Assistant.  Pure dataclasses with no external dependencies, Supported communication channels., Role of a message participant. (+16 more)

### Community 158 - "clsx"
Cohesion: 0.20
Nodes (11): _load_all_clients(), _load_client_info(), ConfigDep, Register as an OAuth client via Dynamic Client Registration., Store registered client credentials to disk., Start the OAuth flow for a remote MCP server.      1. Hits the MCP server to get, Load stored client credentials for a server., Load all stored client credentials from disk. (+3 more)

### Community 159 - ".get_server_for_tool"
Cohesion: 0.24
Nodes (5): Any, Build an unconnected client for a server config (env resolved)., Per-configured-server connection + tool status for the web UI., Return all available tool schemas across all servers., Return the tools most relevant to ``query`` (ToolProvider port).          Delega

### Community 160 - "freeze"
Cohesion: 0.33
Nodes (7): freeze(), parse(), process(), processSync(), run(), runSync(), stringify()

### Community 161 - "create_app"
Cohesion: 0.50
Nodes (4): create_app(), FastAPI, FastAPI application factory.  Creates the web server with lifespan management, C, Create and configure the FastAPI application.

### Community 162 - "ww"
Cohesion: 0.50
Nodes (4): Cw(), Sw(), ww(), xw()

### Community 163 - "datetime"
Cohesion: 0.50
Nodes (4): ex(), Go(), ks(), ox()

### Community 164 - "sx"
Cohesion: 0.67
Nodes (3): dx(), Jb(), sx()

### Community 166 - "MemoryTab.tsx"
Cohesion: 0.18
Nodes (8): copy(), data(), MemoryEntry, EMPTY_DRAFT, MEMORY_TYPES, MemoryDraft, MemoryTab(), TYPE_COLOR

### Community 167 - "oauth.py"
Cohesion: 0.22
Nodes (9): auth_logout(), _AuthStartResponse, _delete_tokens(), get_access_token(), MCP OAuth 2.1 authentication endpoints.  Implements the MCP Authorization spec (, Clear stored OAuth tokens for a server., Delete stored tokens for a server., Get the current access token for a server (used by MCP client). (+1 more)

### Community 168 - "oauth_callback"
Cohesion: 0.25
Nodes (8): HTMLResponse, _callback_html(), oauth_callback(), Request, Handle the OAuth redirect callback from the auth provider., Reconnect an MCP server so a freshly stored token takes effect., Generate the callback page HTML., _reconnect_mcp_server()

### Community 169 - "Any"
Cohesion: 0.31
Nodes (9): auth_status(), _load_all_tokens(), _load_tokens(), Any, Check if a server has stored OAuth tokens., Store OAuth tokens to disk (owner-read-only permissions)., Load stored tokens for a specific server., Load all stored tokens from disk. (+1 more)

### Community 170 - "ai"
Cohesion: 0.36
Nodes (8): ai(), as(), ii(), li(), ni(), Rd(), ti(), va()

### Community 171 - "datetime"
Cohesion: 0.33
Nodes (5): datetime, In-memory log buffer + live fan-out for the web Logs viewer.  A single :class:`L, _parse_datetime(), Conversation repository — implements the Storage protocol for SQLite., Parse an ISO format datetime string.

### Community 172 - "app"
Cohesion: 0.43
Nodes (6): app(), client(), AsyncClient, FastAPI, End-to-end web flow: login → protected endpoints → tool audit.  Exercises the re, test_full_web_flow()

### Community 173 - "._initialize_schema"
Cohesion: 0.33
Nodes (3): Create tables if they don't exist and track schema version., Apply additive migrations for databases created before this version., Open the database connection and initialize the schema.

### Community 174 - "Pw"
Cohesion: 0.40
Nodes (5): Bw(), Fw(), Pw(), Rw(), Wy()

### Community 175 - "ds"
Cohesion: 0.40
Nodes (5): ds(), et(), Ha(), ps(), us()

## Knowledge Gaps
- **142 isolated node(s):** `dax-assistant`, `install-service.sh script`, `name`, `private`, `version` (+137 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **59 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Message` connect `End-to-End Web Tests` to `Voice Processing Pipeline`, `Agent Tool Policy`, `Tool Dispatch Interfaces`, `Application Storage Lifecycle`, `OAuth Webhook Integration`, `Event Scheduling Runtime`, `Voice Conversation State`, `React Collection Rendering`, `Speech Synthesis Engines`, `Webhook API Tests`, `LLM Router Failover`, `WhatsApp Channel Integration`, `TestYesNoParser`, `LLM Provider Factory`, `Gemini Provider Adapter`, `Telegram Bot Channel`, `Anthropic Provider Adapter`, `Audio Capture Playback`, `Shared Test Fixtures`, `WebSocket Chat Server`, `Collection Selection Management`, `Application Settings Models`, `OpenAI Provider Adapter`, `Mutable Collection State`, `Codex Provider Adapter`, `Web Authentication Interface`, `Speaker Verification Embeddings`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `MessageBus` connect `Webhook API Tests` to `Voice Processing Pipeline`, `Agent Tool Policy`, `Tool Dispatch Interfaces`, `Event Scheduling Runtime`, `Voice Conversation State`, `React Collection Rendering`, `Speech Synthesis Engines`, `System API Tests`, `WhatsApp Channel Integration`, `TestYesNoParser`, `Web Dependency Injection`, `create_app`, `app`, `Telegram Bot Channel`, `Audio Capture Playback`, `Shared Test Fixtures`, `Collection Selection Management`, `Password Authentication Tests`, `Application Settings Models`, `Mutable Collection State`, `End-to-End Web Tests`, `Shell Command Parsing`, `WebSocket Channel Adapter`, `Speaker Verification Embeddings`, `Authentication Flow Tests`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `DaxApp` connect `Shell Command Parsing` to `Mutable Collection State`, `MCP Lifecycle Manager`, `Application Storage Lifecycle`, `oauth_callback`, `Application Command Entrypoint`, `Voice Conversation State`, `React Collection Rendering`, `WebSocket Channel Adapter`, `Web Authentication Interface`, `Encrypted Secret Storage`, `Audio Capture Playback`, `Webhook API Tests`, `Configuration Serialization Tests`, `Logging Event Buffer`, `WhatsApp Channel Integration`, `Application Settings Models`, `Human Approval Workflow`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 83 inferred relationships involving `i()` (e.g. with `__()` and `ac()`) actually correct?**
  _`i()` has 83 INFERRED edges - model-reasoned connections that need verification._
- **Are the 107 inferred relationships involving `n()` (e.g. with `__()` and `index-Dvu6q04l.js`) actually correct?**
  _`n()` has 107 INFERRED edges - model-reasoned connections that need verification._
- **Are the 90 inferred relationships involving `t()` (e.g. with `__()` and `a()`) actually correct?**
  _`t()` has 90 INFERRED edges - model-reasoned connections that need verification._
- **Are the 105 inferred relationships involving `r()` (e.g. with `__()` and `index-Dvu6q04l.js`) actually correct?**
  _`r()` has 105 INFERRED edges - model-reasoned connections that need verification._