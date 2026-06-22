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
}

export interface VoiceConfig {
  enabled: boolean;
  wake_word_threshold: number;
  stt_model: string;
  stt_compute_type: string;
  stt_language: string;
  tts_voice_es: string;
  tts_voice_en: string;
  vad_threshold: number;
  silence_duration_ms: number;
}

export interface LLMConfig {
  default_provider: string;
  fallback_order: string[];
  ollama_model: string;
  ollama_base_url: string;
  ollama_timeout: number;
  anthropic_model: string;
  anthropic_configured: boolean;
  openai_model: string;
  openai_base_url: string;
  openai_configured: boolean;
  gemini_model: string;
  gemini_configured: boolean;
}

export interface WebConfig {
  host: string;
  port: number;
  cors_origins: string[];
}

export interface WhatsAppConfig {
  enabled: boolean;
  evolution_api_url: string;
  evolution_api_instance: string;
  respond_with_audio: boolean;
  has_api_key: boolean;
}

export interface MCPServerConfig {
  command: string;
  args: string[];
  env: Record<string, string>;
  transport: string;
  url: string;
  headers: Record<string, string>;
  enabled: boolean;
}

export interface FullConfig {
  general: GeneralConfig;
  voice: VoiceConfig;
  llm: LLMConfig;
  web: WebConfig;
  whatsapp: WhatsAppConfig;
  mcp: {
    servers: Record<string, MCPServerConfig>;
  };
}
