# Graph Report - dax-assistant  (2026-07-18)

## Corpus Check
- 150 files · ~96,395 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2872 nodes · 8257 edges · 152 communities (107 shown, 45 thin omitted)
- Extraction: 74% EXTRACTED · 26% INFERRED · 0% AMBIGUOUS · INFERRED: 2113 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fcc17437`
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
- TestPipelineEnabled
- mcp_tools_to_openai
- create_app
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
- getFullNode

## God Nodes (most connected - your core abstractions)
1. `i()` - 172 edges
2. `n()` - 164 edges
3. `t()` - 155 edges
4. `Message` - 143 edges
5. `r()` - 143 edges
6. `a()` - 111 edges
7. `MessageBus` - 100 edges
8. `s()` - 100 edges
9. `push()` - 95 edges
10. `l()` - 82 edges

## Surprising Connections (you probably didn't know these)
- `ModelSelector()` --indirect_call--> `m()`  [INFERRED]
  web/src/pages/Chat.tsx → src/dax/web/static/assets/index-CtpIuQcu.js
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

## Communities (152 total, 45 thin omitted)

### Community 0 - "Bundle Collection Utilities"
Cohesion: 0.01
Nodes (140): ab(), addChild(), addDescendants(), addNode(), addText(), addTreeNode(), Ag(), ak() (+132 more)

### Community 1 - "Voice Processing Pipeline"
Cohesion: 0.07
Nodes (24): CallbackFlags, AudioCapture, AudioPlayer, ndarray, Audio I/O — microphone capture and speaker playback.  Uses sounddevice for cross, sounddevice callback — runs on the audio thread., Play audio through the default output device., Play a full audio buffer and block until playback finishes.          Args: (+16 more)

### Community 2 - "Frontend Runtime Internals"
Cohesion: 0.08
Nodes (53): aa(), ac(), ae(), Ba(), Bi(), cc(), de(), Do() (+45 more)

### Community 3 - "Agent Tool Policy"
Cohesion: 0.09
Nodes (30): A request to execute an MCP tool., ToolCall, Agent, The orchestrator agent that processes user messages.      Implements the core lo, Apply a new base prompt without restarting the agent., Cancel the agent loop., MessageBus, Async message bus for inter-component communication.  Decouples channels from th (+22 more)

### Community 4 - "Tree Collection Traversal"
Cohesion: 0.10
Nodes (100): _(), a(), aj(), ar(), b(), be(), bn(), br() (+92 more)

### Community 5 - "Tool Dispatch Interfaces"
Cohesion: 0.05
Nodes (32): The result of an MCP tool execution., ToolResult, LLMProvider, Protocol, Protocol interfaces (ports) for the hexagonal architecture.  All adapters implem, Launch and connect to all configured MCP servers., Shut down all MCP server connections., Return all available tool schemas across all servers. (+24 more)

### Community 6 - "DOM Collection Mutation"
Cohesion: 0.08
Nodes (83): Ad(), add(), addEventListener(), Au(), bf(), bu(), ca(), cd() (+75 more)

### Community 7 - "Application Storage Lifecycle"
Cohesion: 0.05
Nodes (44): ChannelType, Language, MessageRole, StrEnum, Domain models for Dax Assistant.  Pure dataclasses with no external dependencies, Supported communication channels., Role of a message participant., Supported languages for voice interaction. (+36 more)

### Community 8 - "Agent Message Processing"
Cohesion: 0.09
Nodes (30): announce(), at(), bd(), bj(), Bv(), cf(), Dt(), Ef() (+22 more)

### Community 9 - "OAuth Webhook Integration"
Cohesion: 0.05
Nodes (66): BusDep, HTMLResponse, Encrypted secret storage backed by SQLite.  Replaces the legacy ``.env`` file as, auth_logout(), auth_status(), _AuthStartResponse, _callback_html(), configure_oauth_store() (+58 more)

### Community 10 - "MCP Tool Registry"
Cohesion: 0.12
Nodes (10): Tool registry — aggregates tools from all MCP servers.  Provides lookup by tool, Aggregates tool schemas from multiple MCP servers.      Maintains a mapping of t, Remove all tools belonging to a server (e.g. on disconnect)., Remove all registered tools., Return the tool_name → server_name mapping., Look up which server owns a tool., ToolRegistry, _make_tools() (+2 more)

### Community 11 - "Collection Cursor Operations"
Cohesion: 0.05
Nodes (79): __addSublanguage(), ai(), ao(), bs(), Bw(), bx(), clear(), componentDidCatch() (+71 more)

### Community 12 - "Event Scheduling Runtime"
Cohesion: 0.08
Nodes (22): Speech-to-text transcription failed., STTError, build_stt(), FallbackSpeechToText, OpenAISpeechToText, ndarray, VoiceConfig, Speech-to-Text via faster-whisper.  Wraps the CTranslate2-based Whisper model fo (+14 more)

### Community 13 - "Voice Conversation State"
Cohesion: 0.06
Nodes (32): _clean_for_speech(), ndarray, Voice pipeline — wake word, listen, transcribe, respond.  Runs in a dedicated th, Full voice pipeline: wake -> listen -> transcribe -> respond -> converse.      R, Start all voice components and launch the pipeline thread., Stop the pipeline thread and all components., State-machine loop in the voice-pipeline thread., IDLE — listen for wake word activation. (+24 more)

### Community 14 - "React Collection Rendering"
Cohesion: 0.07
Nodes (22): datetime, In-memory log buffer + live fan-out for the web Logs viewer.  A single :class:`L, build_messages_for_llm(), Any, Shared LLM helpers: the system prompt and the message builder.  The conversation, Build the OpenAI-format message list for an LLM call.      Converts our Message, Remove provider control markup that must never reach users or TTS., sanitize_assistant_text() (+14 more)

### Community 15 - "Conversation Data Models"
Cohesion: 0.08
Nodes (51): bg(), canSelectItem(), canSelectItemIn(), clearSelection(), Cm(), Dm(), Eg(), extendSelection() (+43 more)

### Community 16 - "Speech Synthesis Engines"
Cohesion: 0.05
Nodes (38): PiperVoice, Voice pipeline configuration., VoiceConfig, Text-to-speech synthesis failed., TTSError, _build_local_tts(), _build_piper(), build_tts() (+30 more)

### Community 17 - "Shared Web UI Components"
Cohesion: 0.12
Nodes (31): index(), COLORS, ICONS, Badge(), BadgeColor, Field(), PanelHeader(), Tabs() (+23 more)

### Community 18 - "Configuration API Routes"
Cohesion: 0.05
Nodes (76): MCPServerConfig, Configuration for a single MCP server.      Supports two transport modes:     -, persist_config(), Persist the live configuration as an encrypted SQLite document.      The single, change_password(), ChangePasswordRequest, GeneralConfigUpdate, get_config() (+68 more)

### Community 19 - "MCP Configuration Routes"
Cohesion: 0.08
Nodes (53): af(), ah(), appendChild(), bc(), bt(), ci(), co(), consume() (+45 more)

### Community 20 - "System API Tests"
Cohesion: 0.08
Nodes (16): app(), bus(), client(), AsyncClient, FastAPI, MonkeyPatch, Path, Tests for the REST API endpoints. (+8 more)

### Community 21 - "Webhook API Tests"
Cohesion: 0.15
Nodes (12): _make_text_webhook(), AsyncClient, Text messages should be published to the inbound bus., Extended text messages (with URL preview) should extract text., Audio messages should be queued with metadata., Messages sent by us (fromMe=True) should be ignored., Non-message events should be acknowledged but not processed., Unsupported message types (sticker, location, etc.) should be ignored. (+4 more)

### Community 22 - "System MCP Server"
Cohesion: 0.09
Nodes (17): FastMCP, main(), Run the dax-system MCP server over stdio: python -m dax.mcp_servers.system, allowed_roots(), build_server(), Path, `dax-system` — a local MCP server exposing safe, typed PC-control tools.  Runs a, Construct the FastMCP server with all dax-system tools registered. (+9 more)

### Community 23 - "Selection and Syntax Utilities"
Cohesion: 0.08
Nodes (48): ap(), Bp(), cn(), CollectionBranch(), CollectionRoot(), Ct(), dn(), dp() (+40 more)

### Community 24 - "Core Configuration Models"
Cohesion: 0.11
Nodes (29): AnthropicProviderConfig, CodexProviderConfig, DeepSeekProviderConfig, GeminiProviderConfig, MCPConfig, OllamaProviderConfig, OpenAIProviderConfig, BaseModel (+21 more)

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
Cohesion: 0.11
Nodes (16): Any, WhatsApp channel — sends responses via Evolution API v2.  Incoming messages are, Send a voice note via Evolution API v2.          POST /message/sendWhatsAppAudio, WhatsApp outbound channel via Evolution API v2.      Sends text (and optionally, Initialize the HTTP client for Evolution API calls., Close the HTTP client., Send a response message to a WhatsApp contact.          The recipient JID is ext, Send a text message via Evolution API v2.          POST /message/sendText/{insta (+8 more)

### Community 29 - "TypeScript Compiler Configuration"
Cohesion: 0.08
Nodes (25): DOM, DOM.Iterable, ES2023, src, vite/client, compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly (+17 more)

### Community 30 - "Web Dependency Injection"
Cohesion: 0.25
Nodes (15): get_approval(), get_auth(), get_bus(), get_config(), get_llm_router(), get_mcp_manager(), get_repository(), get_secret_store() (+7 more)

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
Cohesion: 0.11
Nodes (13): MCPManager, Any, Build an unconnected client for a server config (env resolved)., Launch and connect to all enabled MCP servers., Connect to a server and register its tools live. Returns tool count.          Re, Disconnect a server (if connected) and drop its tools., Disconnect a server from the MCP lifecycle worker task., Disconnect from all MCP servers. (+5 more)

### Community 35 - "Secure Configuration Serialization"
Cohesion: 0.12
Nodes (27): Enum, _del_path(), dump_config_toml(), _env_var_for_header(), _env_var_for_mcp_env(), _extract_secrets(), _get_path(), _is_sensitive_header() (+19 more)

### Community 36 - "Realtime Chat Interface"
Cohesion: 0.13
Nodes (15): ConversationSummary, Modal(), AgentEvent, ChatMessage, ConfirmationRequest, nextId(), Status, useChatSocket() (+7 more)

### Community 37 - "Frontend Runtime Dependencies"
Cohesion: 0.17
Nodes (9): filter_tools_by_relevance(), parse_tool_calls_from_response(), Any, Maps MCP tool schemas to OpenAI function-calling format.  We use the OpenAI tool, Filter tools based on keyword relevance to the user's query.      Always include, Parse tool calls from a litellm response into our internal format.      Args:, Tests for MCP → OpenAI tool schema mapping and relevance filtering., TestFilterToolsByRelevance (+1 more)

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
Cohesion: 0.12
Nodes (18): Any, System-prompt assembly for the agent.  Builds the per-turn system prompt from th, Append a concrete live tool inventory to the base system prompt.      Grouping b, Assembles the per-turn system prompt (tools + memory + voice style)., Replace the editable base prompt for subsequent turns., Return the full system prompt for this turn., Read user-curated memory files and format them for the system prompt.          E, SystemPromptBuilder (+10 more)

### Community 43 - "Frontend Development Dependencies"
Cohesion: 0.17
Nodes (15): _bootstrap_only(), _bootstrap_secrets(), _flatten_toml(), load_config(), Any, Path, Load encrypted configuration, importing a legacy TOML once when present.      Ar, Seed os.environ from the encrypted secret store before config is built.      Sec (+7 more)

### Community 44 - "Logs and Configuration Types"
Cohesion: 0.31
Nodes (7): Select(), useLogStream(), wsUrl(), LEVEL_COLOR, LEVELS, LogsPage(), LogEntry

### Community 45 - "Gemini Provider Adapter"
Cohesion: 0.16
Nodes (7): Content, GeminiProvider, Any, Google Gemini provider adapter — official `google-genai` SDK.  Translates the Op, Implements the LLMProvider port over the Gemini generateContent API., TestGeminiProvider, Tool

### Community 46 - "Telegram Bot Channel"
Cohesion: 0.12
Nodes (12): Wake word detection failed., WakeWordError, AbstractEventLoop, VoiceConfig, ndarray, Wake word detection via OpenWakeWord.  Wraps the OpenWakeWord inference model be, Reset the model's internal state between activations., Detect wake words in streaming audio chunks.      Args:         model_names: Lis (+4 more)

### Community 47 - "Anthropic Provider Adapter"
Cohesion: 0.19
Nodes (5): AnthropicProvider, Any, Anthropic (Claude) provider adapter — official `anthropic` SDK.  Translates the, Implements the LLMProvider port over the Anthropic Messages API., TestAnthropicProvider

### Community 48 - "Encrypted Secret Storage"
Cohesion: 0.13
Nodes (13): Mirror the live shell allowlist into encrypted configuration., load_encrypted_config(), Persist the complete validated configuration as encrypted JSON., Load and decode the encrypted configuration document, if initialized., save_encrypted_config(), Connection, Path, Seed ``os.environ`` from the store without clobbering real env vars.          Re (+5 more)

### Community 49 - "Authentication API Routes"
Cohesion: 0.19
Nodes (19): AuthDep, auth_status(), AuthStatus, health(), HealthResponse, login(), LoginRequest, LoginResponse (+11 more)

### Community 50 - "Shell Command Allowlist"
Cohesion: 0.10
Nodes (44): al(), Av(), bl(), continuePropagation(), Dv(), Em(), Fj(), fl() (+36 more)

### Community 51 - "Voice Activity Detection"
Cohesion: 0.08
Nodes (23): Exception, DaxError, Domain exception hierarchy for Dax Assistant., MCP tool execution failed., Requested tool does not exist in the registry., Tool was found but execution failed., Database or persistence operation failed., Voice pipeline component failed. (+15 more)

### Community 52 - "Audio Capture Playback"
Cohesion: 0.29
Nodes (4): Any, Register tools from an MCP server.          Each tool dict must include a 'serve, Return all registered tool schemas., Return the most relevant tools for a given query.          Uses keyword matching

### Community 53 - "Shared Test Fixtures"
Cohesion: 0.13
Nodes (15): config_from_file(), database(), default_config(), isolate_config_env(), message_bus(), MonkeyPatch, Path, Shared test fixtures for Dax Assistant. (+7 more)

### Community 55 - "Wake Word Detection"
Cohesion: 0.06
Nodes (16): Conversation, Return the most recent message, or None if empty., An ordered sequence of messages within a channel session.      Mutable — message, Append a message and update the timestamp., Persist a conversation and its messages., Retrieve a conversation by ID, or None if not found., Return the conversation for (channel, session_key), creating one if needed., Retrieve the most recent conversations for a channel. (+8 more)

### Community 56 - "WebSocket Chat Server"
Cohesion: 0.19
Nodes (9): Any, WebSocket, WebSocket chat endpoint for the web UI.  Handles inbound messages from browser c, Manages active WebSocket connections.      For a single-user assistant, we typic, Send data to a specific WebSocket connection., Send data to all connected WebSocket clients., WebSocket endpoint for real-time chat with Dax.      Protocol:         Client se, websocket_chat() (+1 more)

### Community 57 - "Collection Selection Management"
Cohesion: 0.07
Nodes (15): Message, A single message in a conversation.      Immutable value object. All messages fl, Send a completion request and return the assistant's response.          Args:, Core agent loop — the brain of Dax Assistant.  Receives messages from the bus, s, Build the query used to pick relevant tools, with recent context.      The relev, _relevance_query(), _respond_in_spanish(), _tool_budget_fallback() (+7 more)

### Community 58 - "Configuration Serialization Tests"
Cohesion: 0.10
Nodes (21): BaseSettings, PydanticBaseSettingsSource, DaxConfig, Root configuration for Dax Assistant.      Settings are loaded in order of prior, Path, Tests for TOML config serialization + secret extraction (config_io)., A field already holding an {env:…} ref is kept verbatim, not re-stored., Authorization-style headers move to the store as {env:…} refs. (+13 more)

### Community 59 - "Domain Error Hierarchy"
Cohesion: 0.12
Nodes (16): Audio troubleshooting, Choosing / adding LLM providers, Configuration, Dax Assistant, Development, Development quick start, Highlights, Layout (+8 more)

### Community 60 - "Password Authentication Tests"
Cohesion: 0.19
Nodes (12): hash_password(), _main(), Single-user authentication for the web UI and API.  Dax is a personal assistant:, Return an argon2id hash of ``password``., Check ``password`` against a stored argon2 hash., verify_password(), auth_app(), auth_client() (+4 more)

### Community 61 - "Application Settings Models"
Cohesion: 0.15
Nodes (10): Allow / ask / deny policy for tool execution (fnmatch patterns).      An empty `, ToolPolicyConfig, Decision, StrEnum, Tool execution policy — allow / ask / deny per tool name.  The agent consults th, Resolves an allow/ask/deny decision for a tool name., Update rules in place so the agent picks them up without a restart., ToolPolicy (+2 more)

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
Cohesion: 0.12
Nodes (15): fail(), info(), message(), MCPServerStatus, ToolAuditEntry, AuthGate(), ToastProvider(), Panel() (+7 more)

### Community 66 - "Codex Provider Adapter"
Cohesion: 0.16
Nodes (10): LLMError, LLMTimeoutError, LLM provider communication failed., LLM request timed out., CodexProvider, Any, OpenAI Codex CLI provider.  Runs ``codex exec --json`` as a subprocess to use th, Parse the JSONL event stream and return the final agent message. (+2 more)

### Community 67 - "MCP Environment Resolution"
Cohesion: 0.14
Nodes (11): _get_oauth_token(), MCP server manager — implements the ToolProvider protocol.  Manages the lifecycl, Replace {env:VAR_NAME} patterns with environment variable values., Resolve env vars in all values of a dict., Snapshot desktop-session vars present in the current environment., Get stored OAuth access token for an MCP server, if available., _resolve_env_dict(), _resolve_env_vars() (+3 more)

### Community 68 - "MCP Marketplace Interface"
Cohesion: 0.29
Nodes (9): toHTML(), value(), envToText(), FormMode, headersToText(), McpTab(), parseEnv(), parseHeaders() (+1 more)

### Community 69 - "Project Architecture Overview"
Cohesion: 0.15
Nodes (11): Architecture, Channels (`channels/`), Commands, Config & secrets (`core/config.py`, `core/config_io.py`), LLM layer (`llm/`) — fully decoupled behind the `LLMProvider` port, MCP (`mcp/`) and the bundled server, Message flow (the spine), Safety model (+3 more)

### Community 70 - "End-to-End Web Tests"
Cohesion: 0.40
Nodes (4): MonkeyPatch, Path, Encrypted secret-store tests., test_external_master_key_avoids_local_key_file()

### Community 71 - "Collection Selection Queries"
Cohesion: 0.12
Nodes (9): Voice channel adapter — bridges the dispatcher to the voice pipeline.  The voice, Voice channel adapter for the dispatcher.      Inbound messages are published by, No-op — the voice pipeline manages its own lifecycle., No-op — the voice pipeline manages its own lifecycle., Enqueue an outbound message for the voice pipeline to consume.          Called b, Discard any queued responses left over from a previous turn.          The pipeli, Wait for the next outbound message from the dispatcher.          Called by the v, VoiceChannel (+1 more)

### Community 72 - "Application Shell Theming"
Cohesion: 0.24
Nodes (9): AppShell(), NAV, NavItem, TITLES, ThemeToggle(), apply(), resolveInitial(), Theme (+1 more)

### Community 73 - "Streaming Speech Synthesis"
Cohesion: 0.40
Nodes (3): Path, Smoke tests for the portable Linux installer., test_installer_dry_run_uses_xdg_layout()

### Community 74 - "Application Command Entrypoint"
Cohesion: 0.17
Nodes (5): Mutable, observable set of allowed shell binaries (order preserved)., Append a binary if new. Returns True if it was actually added., Replace the whole list (de-duped, order preserved) and persist., ShellAllowlist, TestShellAllowlist

### Community 75 - "Shell Command Parsing"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 78 - "Single Page Middleware"
Cohesion: 0.24
Nodes (7): Scope, Response, SPA-aware static file serving.  Subclasses Starlette's StaticFiles to return ind, StaticFiles that falls back to index.html for SPA routing.      For any path tha, Serve index.html as fallback., SPAStaticFiles, StaticFiles

### Community 79 - "Conversation API Routes"
Cohesion: 0.27
Nodes (9): delete_conversation(), get_conversation(), list_conversations(), Any, Request, Conversation history endpoints — list, fetch, delete web chats., List recent web conversations for the sidebar., Return a conversation with its messages. (+1 more)

### Community 80 - "WebSocket Channel Adapter"
Cohesion: 0.20
Nodes (8): _configure_logging(), Path, Application bootstrap and lifecycle management.  Wires all components together v, Create a DaxApp instance from a config file path., Set up structlog with console rendering., main(), Entry point for running Dax Assistant: python -m dax, Parse arguments and run the application.

### Community 81 - "Web Authentication Interface"
Cohesion: 0.06
Nodes (25): DaxApp, Apply the configured prompt to the live agent for its next turn., Expose FastAPI app for testing., Initialize all components in dependency order., Restart the Telegram channel to apply config changes without a full         app, Serialize live voice reloads so repeated UI saves remain safe., Restart the voice channel and pipeline with the live configuration., Shut down all components in reverse order. (+17 more)

### Community 84 - "Speaker Verification Embeddings"
Cohesion: 0.08
Nodes (17): main(), ndarray, Enroll the owner's voice for speaker verification (Voice ID).  Records a few sho, _record(), ndarray, Speaker verification (Voice ID) via Resemblyzer.  Optional, Alexa-style "only re, Compute a voice embedding for *audio* (float32, 16 kHz mono)., Return True if *audio* matches the owner (or if verification is off).          A (+9 more)

### Community 86 - "Production Social Icons"
Cohesion: 0.48
Nodes (7): Bluesky Icon, Discord Icon, Documentation and Code Icon, GitHub Icon, Social Profile Icon, Web Icon Sprite, X Social Platform Icon

### Community 88 - "test_webhooks.py"
Cohesion: 0.23
Nodes (11): app(), bus(), client(), _make_audio_webhook(), _make_extended_text_webhook(), FastAPI, Tests for Evolution API v2 webhook receiver., Build a webhook with extendedTextMessage type. (+3 more)

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
Cohesion: 0.24
Nodes (5): Runtime allowlist of shell binaries the assistant may run on this PC.  This is t, Extract the bare binary name from a command string (``/bin/ls -l`` → ``ls``)., shell_binary(), Tests for the shell-command allowlist., TestShellBinary

### Community 96 - "MemoryTab.tsx"
Cohesion: 0.18
Nodes (8): copy(), data(), MemoryEntry, EMPTY_DRAFT, MEMORY_TYPES, MemoryDraft, MemoryTab(), TYPE_COLOR

### Community 98 - "Production Favicon Graphics"
Cohesion: 0.50
Nodes (4): Favicon Graphic, Lightning Bolt Symbol, Purple Angular Mark, Soft Glow Highlights

### Community 102 - "auth_from_app"
Cohesion: 0.22
Nodes (9): approval_from_app(), auth_from_app(), bus_from_app(), log_buffer_from_app(), WebSocket, WebSocket endpoint that streams live backend logs to the web UI., Stream log records as JSON. Authenticated like the chat socket., websocket_logs() (+1 more)

### Community 111 - "mcp_tools_to_openai"
Cohesion: 0.43
Nodes (3): mcp_tools_to_openai(), Convert a list of MCP tool schemas to OpenAI function-calling format.      MCP f, TestMCPToolsToOpenAI

### Community 112 - "create_app"
Cohesion: 0.50
Nodes (4): create_app(), FastAPI, FastAPI application factory.  Creates the web server with lifespan management, C, Create and configure the FastAPI application.

### Community 150 - "test_legacy_oauth_files_migrate_encrypted"
Cohesion: 0.50
Nodes (3): Path, Encrypted persistence tests for MCP OAuth credentials., test_legacy_oauth_files_migrate_encrypted()

### Community 153 - "getFullNode"
Cohesion: 0.11
Nodes (17): api, ApiError, AuthStatus, ConversationDetail, ConversationMessage, MCPPreset, OllamaModel, RegistryServer (+9 more)

## Knowledge Gaps
- **113 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `dax-assistant`, `install-service.sh script`, `ConversationMessage` (+108 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **45 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MessageBus` connect `Agent Tool Policy` to `Voice Processing Pipeline`, `Tool Dispatch Interfaces`, `Application Storage Lifecycle`, `Event Scheduling Runtime`, `Voice Conversation State`, `Speech Synthesis Engines`, `System API Tests`, `Webhook API Tests`, `Web Dependency Injection`, `Telegram Bot Channel`, `Shared Test Fixtures`, `Configuration Loading Tests`, `Wake Word Detection`, `Collection Selection Management`, `Password Authentication Tests`, `Mutable Collection State`, `Collection Selection Queries`, `Web Authentication Interface`, `Speaker Verification Embeddings`, `Authentication Flow Tests`, `test_webhooks.py`, `auth_from_app`, `TestPipelineEnabled`, `create_app`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `Message` connect `Collection Selection Management` to `Voice Processing Pipeline`, `Agent Tool Policy`, `Tool Dispatch Interfaces`, `Application Storage Lifecycle`, `OAuth Webhook Integration`, `Event Scheduling Runtime`, `Voice Conversation State`, `React Collection Rendering`, `Speech Synthesis Engines`, `LLM Router Failover`, `WhatsApp Channel Integration`, `LLM Provider Factory`, `Gemini Provider Adapter`, `Anthropic Provider Adapter`, `Shared Test Fixtures`, `Configuration Loading Tests`, `Wake Word Detection`, `WebSocket Chat Server`, `OpenAI Provider Adapter`, `Mutable Collection State`, `Codex Provider Adapter`, `Collection Selection Queries`, `Web Authentication Interface`, `Speaker Verification Embeddings`, `TestPipelineEnabled`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `DaxApp` connect `Web Authentication Interface` to `Mutable Collection State`, `MCP Lifecycle Manager`, `Agent Tool Policy`, `Collection Selection Queries`, `Application Storage Lifecycle`, `OAuth Webhook Integration`, `Application Command Entrypoint`, `Voice Conversation State`, `WebSocket Channel Adapter`, `Encrypted Secret Storage`, `Configuration Serialization Tests`, `Logging Event Buffer`, `WhatsApp Channel Integration`, `Application Settings Models`, `Human Approval Workflow`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 85 inferred relationships involving `i()` (e.g. with `index-CtpIuQcu.js` and `ac()`) actually correct?**
  _`i()` has 85 INFERRED edges - model-reasoned connections that need verification._
- **Are the 106 inferred relationships involving `n()` (e.g. with `index-CtpIuQcu.js` and `ab()`) actually correct?**
  _`n()` has 106 INFERRED edges - model-reasoned connections that need verification._
- **Are the 95 inferred relationships involving `t()` (e.g. with `a()` and `ab()`) actually correct?**
  _`t()` has 95 INFERRED edges - model-reasoned connections that need verification._
- **Are the 86 inferred relationships involving `Message` (e.g. with `TelegramChannel` and `VoiceChannel`) actually correct?**
  _`Message` has 86 INFERRED edges - model-reasoned connections that need verification._