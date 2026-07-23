/**
 * Backend response shapes.
 *
 * Mirrored from `web/src/api/client.ts` and `web/src/types/config.ts` rather
 * than imported — PLAN.md 3.9 defers unifying the two build systems to M5.
 * Kept in the same order as the source files so drift is easy to spot.
 */

export interface AuthStatus {
  auth_enabled: boolean;
  configured: boolean;
  authenticated: boolean;
}

/**
 * `token` is the desktop-relevant addition: the backend now returns the signed
 * session token alongside the Set-Cookie header so a native client can use
 * `Authorization: Bearer` instead of relying on cookie replay.
 */
export interface LoginResponse {
  ok: boolean;
  token?: string | null;
  /** Why a refusal happened, when it is something the operator can act on. */
  detail?: string | null;
}

export interface HealthResponse {
  status: string;
  instance_id: string;
  role: string;
  api_protocol: string;
  api_version: number;
  liveness: boolean;
  readiness: boolean;
}

export interface StatusResponse {
  name: string;
  version: string;
  status: string;
  voice_listening: boolean;
  llm_provider: string;
  mcp_servers: number;
  mcp_tools: number;
}

export interface MCPServerStatus {
  name: string;
  connected: boolean;
  transport: string;
  enabled: boolean;
  tool_count: number;
  tools: string[];
}

/**
 * `GET /api/logs` returns `timestamp`; the `/ws/logs` stream returns `ts`.
 * Both are optional here and normalized at the edge — see `hooks/useLogStream`.
 */
export interface LogEntry {
  ts?: string;
  timestamp?: string;
  level: string;
  logger: string;
  message: string;
}

export interface ToolAuditEntry {
  timestamp: string;
  server_name: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: string;
}

export interface ToolPolicyResponse {
  default: string;
  allow: string[];
  ask: string[];
  deny: string[];
  confirm_timeout_seconds: number;
}

/* ---------------- conversations ---------------- */

export interface ConversationSummary {
  id: string;
  session_key: string;
  title: string;
  preview: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  timestamp: string;
}

export interface ConversationDetail {
  id: string;
  session_key: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

/* ---------------- memory ---------------- */

export type MemoryType = "user" | "feedback" | "project" | "reference";

export interface MemoryEntry {
  slug: string;
  name: string;
  description: string;
  type: MemoryType;
  body: string;
  filename: string;
}

/* ---------------- MCP ---------------- */

export interface MCPPreset {
  id: string;
  name: string;
  category: string;
  description: string;
  transport: string;
  command: string;
  args: string[];
  env: Record<string, string>;
}

export interface RegistryServer {
  name: string;
  description: string;
  version: string;
  packages: { registry_type: string; identifier: string; version: string }[];
  remotes: { type: string; url: string }[];
}

export interface RegistrySearchResponse {
  servers: RegistryServer[];
  count?: number;
  error?: string;
}

export interface ShellAllowResponse {
  commands: string[];
  default: string[];
}

export interface MCPAuthStatus {
  authenticated: boolean;
  expired?: boolean;
}

/* ---------------- voice ---------------- */

export interface VoiceProfileResponse {
  status?: string;
  enrolled: boolean;
  samples?: number;
}

export interface VoicePreviewOptions {
  engine: "kokoro" | "piper" | "openai";
  voice: string;
  language?: "es" | "en";
  text?: string;
  speed?: number;
  model?: string;
  instructions?: string;
  timeout_s?: number;
}

export interface OllamaModel {
  name: string;
  size_gb: number;
  modified: string;
  family: string;
  parameters: string;
  quantization: string;
}

/* ---------------- config ---------------- */

export interface GeneralConfig {
  name: string;
  language_default: string;
  log_level: string;
  memory_path: string;
  system_prompt: string;
  system_prompt_custom: boolean;
}

export interface VoiceConfig {
  enabled: boolean;
  wake_word_model: string;
  wake_word_threshold: number;
  stt_backend: "local" | "openai";
  stt_model: string;
  stt_compute_type: string;
  stt_device: string;
  stt_beam_size: number;
  stt_language: string;
  stt_openai_model: string;
  stt_openai_timeout_s: number;
  stt_openai_prompt: string;
  stt_openai_configured: boolean;
  stt_fallback_to_local: boolean;
  tts_engine: string;
  tts_voice_es: string;
  tts_voice_en: string;
  tts_kokoro_voice_es: string;
  tts_kokoro_voice_en: string;
  tts_kokoro_speed: number;
  tts_openai_model: string;
  tts_openai_voice: string;
  tts_openai_instructions_es: string;
  tts_openai_instructions_en: string;
  tts_openai_timeout_s: number;
  tts_fallback_to_local: boolean;
  vad_threshold: number;
  silence_duration_ms: number;
  adaptive_endpointing: boolean;
  denoise: boolean;
  barge_in: boolean;
  earcon: boolean;
  conversation_timeout_s: number;
  conversation_timeout_question_s: number;
  session_ttl_minutes: number;
  followup_activation_ms: number;
  thinking_pause_ms: number;
  response_timeout_s: number;
  voice_confirm: boolean;
  require_wake_word_each_turn: boolean;
  speaker_verification: boolean;
  speaker_threshold: number;
  speaker_fail_open: boolean;
  speaker_profile_enrolled: boolean;
}

export interface LLMConfig {
  default_provider: string;
  fallback_order: string[];
  max_tools: number;
  max_tool_iterations: number;
  ollama_model: string;
  ollama_base_url: string;
  ollama_timeout: number;
  anthropic_model: string;
  anthropic_configured: boolean;
  anthropic_timeout: number;
  openai_model: string;
  openai_base_url: string;
  openai_configured: boolean;
  openai_reasoning_effort: string;
  openai_timeout: number;
  gemini_model: string;
  gemini_configured: boolean;
  gemini_timeout: number;
  deepseek_model: string;
  deepseek_base_url: string;
  deepseek_configured: boolean;
  deepseek_timeout: number;
  codex_binary: string;
  codex_model: string;
  codex_timeout: number;
}

export interface WebConfig {
  host: string;
  port: number;
  cors_origins: string[];
  expose_lan: boolean;
  dev_mode: boolean;
}

export interface WhatsAppConfig {
  enabled: boolean;
  evolution_api_url: string;
  evolution_api_instance: string;
  respond_with_audio: boolean;
  has_api_key: boolean;
  has_webhook_secret: boolean;
  webhook_secret: string;
}

export interface TelegramConfig {
  enabled: boolean;
  allowed_user_ids: number[];
  respond_with_audio: boolean;
  has_token: boolean;
}

export interface MCPServerConfig {
  command: string;
  args: string[];
  env: Record<string, string>;
  transport: string;
  url: string;
  headers: Record<string, string>;
  enabled: boolean;
  export_codex: boolean;
  export_claude: boolean;
}

export interface SecurityConfig {
  auth_enabled: boolean;
  configured: boolean;
  session_ttl_hours: number;
  cookie_secure: boolean;
  cookie_name: string;
}

export interface ToolsConfig {
  confirm_timeout_seconds: number;
  policy: {
    default: string;
    allow: string[];
    ask: string[];
    deny: string[];
  };
}

/** What one laptop is asked to do when it is up. */
export interface NodePolicy {
  tools_enabled: boolean;
  shell_enabled: boolean;
  /** False leaves it lending tools without ever hosting a session. */
  process_locally: boolean;
  /**
   * Keep this on "auto". It pins inference to the node only when the model is
   * itself local; a cloud provider is dominated by the round trip to the
   * provider, so routing that call through a laptop adds a hop and removes none.
   */
  inference: "auto" | "local" | "server";
  voice: "auto" | "local" | "server";
}

export interface NodesConfig {
  enabled: boolean;
  prefer_when_available: boolean;
  policies: Record<string, NodePolicy>;
}

/** A capability node as listed by `/api/nodes`, with live presence. */
export interface CapabilityNode {
  id: string;
  name: string;
  platform: string;
  last_seen_at: string | null;
  revoked: boolean;
  connected: boolean;
  policy: NodePolicy;
}

export interface NodeFleet {
  enabled: boolean;
  prefer_when_available: boolean;
  nodes: CapabilityNode[];
}

export interface FullConfig {
  general: GeneralConfig;
  voice: VoiceConfig;
  llm: LLMConfig;
  web: WebConfig;
  whatsapp: WhatsAppConfig;
  telegram: TelegramConfig;
  security: SecurityConfig;
  tools: ToolsConfig;
  mcp: {
    servers: Record<string, MCPServerConfig>;
  };
  nodes: NodesConfig;
  storage: {
    database_path: string;
    models_path: string;
  };
}

/** A one-time code the phone redeems to enrol. Never persisted server-side. */
export interface PairCodeResponse {
  code: string;
  expires_in_seconds: number;
  backend_url: string;
  pairing_uri: string;
  kind: DeviceKind;
}

export type DeviceKind = "client" | "capability_node";

/**
 * An enrolled client.
 *
 * `connected` is live socket presence, not a stored flag — it is true only
 * while the device actually has a chat socket open, which is what makes the
 * deck tile meaningful rather than decorative. `last_seen_at` is the weaker
 * signal: when it last asked for a token.
 */
export interface PairedDevice {
  id: string;
  name: string;
  platform: string;
  created_at: string;
  last_seen_at: string | null;
  revoked_at: string | null;
  revoked: boolean;
  connected: boolean;
  kind: DeviceKind;
}
