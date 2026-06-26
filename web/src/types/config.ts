export interface StatusResponse {
  name: string;
  version: string;
  status: string;
  voice_listening: boolean;
  llm_provider: string;
  mcp_servers: number;
  mcp_tools: number;
}

export interface GeneralConfig {
  name: string;
  language_default: string;
  log_level: string;
  memory_path: string;
}

export interface VoiceConfig {
  enabled: boolean;
  wake_word_threshold: number;
  stt_model: string;
  stt_compute_type: string;
  stt_device: string;
  stt_beam_size: number;
  stt_language: string;
  tts_voice_es: string;
  tts_voice_en: string;
  vad_threshold: number;
  silence_duration_ms: number;
  adaptive_endpointing: boolean;
  denoise: boolean;
  barge_in: boolean;
  earcon: boolean;
  conversation_timeout_s: number;
}

export interface LLMConfig {
  default_provider: string;
  fallback_order: string[];
  max_tools: number;
  ollama_model: string;
  ollama_base_url: string;
  ollama_timeout: number;
  anthropic_model: string;
  anthropic_configured: boolean;
  openai_model: string;
  openai_base_url: string;
  openai_configured: boolean;
  openai_reasoning_effort: string;
  gemini_model: string;
  gemini_configured: boolean;
  deepseek_model: string;
  deepseek_base_url: string;
  deepseek_configured: boolean;
  codex_binary: string;
  codex_model: string;
}

export interface WebConfig {
  host: string;
  port: number;
  cors_origins: string[];
  expose_lan: boolean;
}

export interface WhatsAppConfig {
  enabled: boolean;
  evolution_api_url: string;
  evolution_api_instance: string;
  respond_with_audio: boolean;
  has_api_key: boolean;
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
}

export interface LogEntry {
  ts: string;
  level: string;
  logger: string;
  message: string;
}
