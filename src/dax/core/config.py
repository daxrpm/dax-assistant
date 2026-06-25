"""Configuration models for Dax Assistant.

Loads settings from TOML config files + environment variables.
Pydantic Settings handles the merge automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic_settings import PydanticBaseSettingsSource


class VoiceConfig(BaseModel):
    """Voice pipeline configuration."""

    enabled: bool = True
    wake_word_model: str = "models/wakeword/hey_jarvis.onnx"
    wake_word_threshold: float = 0.7
    stt_model: str = "base"
    stt_compute_type: str = "int8"
    stt_language: str = "auto"
    tts_voice_es: str = "es_ES-davefx-medium"
    tts_voice_en: str = "en_US-lessac-medium"
    vad_threshold: float = 0.5
    silence_duration_ms: int = 800


class OllamaProviderConfig(BaseModel):
    """Local Ollama provider (OpenAI-compatible API). Default provider."""

    base_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    timeout: int = 30


class AnthropicProviderConfig(BaseModel):
    """Anthropic (Claude) provider — official `anthropic` SDK."""

    model: str = "claude-opus-4-8"
    # Read from ANTHROPIC_API_KEY env var by the SDK if left blank.
    api_key: str = ""
    timeout: int = 60


class OpenAIProviderConfig(BaseModel):
    """OpenAI provider — official `openai` SDK (Chat Completions)."""

    model: str = "gpt-5.5"
    # Read from OPENAI_API_KEY env var by the SDK if left blank.
    api_key: str = ""
    # Leave blank for the OpenAI cloud; set to point at any OpenAI-compatible API.
    base_url: str = ""
    timeout: int = 60
    # Reasoning effort for gpt-5.x reasoning models: "minimal" | "low" |
    # "medium" | "high". Lower = much faster responses (big latency win for a
    # personal assistant). Ignored by OpenAI-compatible endpoints (Ollama).
    reasoning_effort: str = "low"


class GeminiProviderConfig(BaseModel):
    """Google Gemini provider — official `google-genai` SDK."""

    model: str = "gemini-3.5-flash"
    # Read from GEMINI_API_KEY / GOOGLE_API_KEY env var by the SDK if blank.
    api_key: str = ""
    timeout: int = 60


class CodexProviderConfig(BaseModel):
    """OpenAI Codex CLI provider — runs `codex exec --json` as a subprocess.

    Uses your ChatGPT plan (via ~/.codex/auth.json) or CODEX_API_KEY. Codex
    runs its own agentic loop, so this provider returns text only and does NOT
    use Dax's tool-calling pipeline. Give Codex its own MCP servers via the
    generated ~/.codex/config.toml (see the MCP section).
    """

    # Path to the codex binary (or just "codex" if on PATH).
    binary: str = "codex"
    # Model Codex should use; blank = Codex default for your account.
    model: str = ""
    timeout: int = 300


class LLMConfig(BaseModel):
    """LLM routing and provider configuration.

    The local Ollama provider is the default and is fully decoupled — any
    provider can be made the default, and `fallback_order` defines which
    providers are tried (in order) if the default fails. Cloud providers use
    their official SDKs and read API keys from the environment.
    """

    default_provider: str = "ollama"
    # Providers tried (in order) after the default fails.
    fallback_order: list[str] = Field(default_factory=lambda: ["gemini"])
    # Max tool schemas sent to the LLM per request. Keep modest: large tool
    # payloads dramatically increase prompt size and latency. The relevance
    # filter picks the best-scoring tools for the query within this budget.
    max_tools: int = 45
    ollama: OllamaProviderConfig = Field(default_factory=OllamaProviderConfig)
    anthropic: AnthropicProviderConfig = Field(default_factory=AnthropicProviderConfig)
    openai: OpenAIProviderConfig = Field(default_factory=OpenAIProviderConfig)
    gemini: GeminiProviderConfig = Field(default_factory=GeminiProviderConfig)
    codex: CodexProviderConfig = Field(default_factory=CodexProviderConfig)


class WebConfig(BaseModel):
    """Web UI and API server configuration."""

    # Bind to loopback by default — this is a personal assistant. Set
    # expose_lan=true (and configure auth) to listen on the local network.
    host: str = "127.0.0.1"
    port: int = 8420
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8420"])
    # When true, host is forced to 0.0.0.0 so other devices on the LAN can
    # reach the UI (auth is still enforced).
    expose_lan: bool = False
    # Allow the Vite dev server origin in CORS only when developing.
    dev_mode: bool = False

    @property
    def effective_host(self) -> str:
        """Resolve the bind address, honouring expose_lan."""
        return "0.0.0.0" if self.expose_lan else self.host


class SecurityConfig(BaseModel):
    """Authentication and session security.

    Secrets are supplied via environment variables, never the TOML file:
      - DAX_SECURITY__PASSWORD_HASH  (argon2 hash; see `python -m dax.web.auth`)
      - DAX_SECURITY__SESSION_SECRET (random string used to sign cookies)
    """

    auth_enabled: bool = True
    password_hash: str = ""
    session_secret: str = ""
    session_ttl_hours: int = 24
    cookie_name: str = "dax_session"
    # Mark the session cookie Secure (HTTPS only). Leave false for local http.
    cookie_secure: bool = False


class WhatsAppConfig(BaseModel):
    """WhatsApp integration via Evolution API v2."""

    enabled: bool = False
    evolution_api_url: str = "http://localhost:8080"
    evolution_api_instance: str = "dax"
    evolution_api_key: str = ""
    # Shared secret required in the inbound webhook's `apikey` header.
    # When set, requests without a matching header are rejected.
    webhook_secret: str = ""
    respond_with_audio: bool = False


class TelegramConfig(BaseModel):
    """Telegram bot integration via long-polling (aiogram).

    No public URL needed — the bot polls Telegram. Create a bot with
    @BotFather and paste its token. Restrict access with allowed_user_ids
    (numeric Telegram user IDs); empty = allow anyone who messages the bot.
    """

    enabled: bool = False
    bot_token: str = ""
    allowed_user_ids: list[int] = Field(default_factory=list)
    respond_with_audio: bool = False


class StorageConfig(BaseModel):
    """Persistence configuration."""

    database_path: str = "data/dax.db"
    models_path: str = "models/"


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server.

    Supports two transport modes:
    - stdio: Spawns a local subprocess. Requires command + args.
    - streamable_http: Connects to a remote HTTP server. Requires url.

    Environment variables in values are expanded at runtime using
    {env:VAR_NAME} syntax (e.g., {env:API_KEY} → os.environ["API_KEY"]).
    """

    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    # When true, this server is included in the generated config for the
    # respective external client (so you can pick which MCPs each tool sees).
    export_codex: bool = False
    export_claude: bool = False


class MCPConfig(BaseModel):
    """MCP server management configuration."""

    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class ToolPolicyConfig(BaseModel):
    """Allow / ask / deny policy for tool execution (fnmatch patterns).

    An empty ``ask`` list means "use the built-in destructive-action defaults".
    """

    default: str = "allow"
    allow: list[str] = Field(default_factory=list)
    ask: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class ToolsConfig(BaseModel):
    """Tool execution settings, including the confirmation gate."""

    # Seconds to wait for the user to confirm a gated action before declining.
    confirm_timeout_seconds: int = 120
    policy: ToolPolicyConfig = Field(default_factory=ToolPolicyConfig)


class DaxConfig(BaseSettings):
    """Root configuration for Dax Assistant.

    Settings are loaded in order of priority:
    1. Environment variables (highest priority)
    2. TOML config file
    3. Default values (lowest priority)
    """

    model_config = SettingsConfigDict(
        env_prefix="DAX_",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority order (highest first): environment > .env > TOML file
        # (passed as init kwargs by load_config) > defaults. This makes env
        # vars override the TOML config, matching the documented behaviour.
        return (env_settings, dotenv_settings, init_settings, file_secret_settings)

    name: str = "Dax"
    language_default: str = "es"
    log_level: str = "INFO"
    memory_path: str = "~/.dax/memory"

    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)


def load_config(config_path: Path | None = None) -> DaxConfig:
    """Load configuration from TOML file and environment variables.

    Args:
        config_path: Path to the TOML config file. If None, uses defaults only.

    Returns:
        Fully resolved DaxConfig instance.
    """
    # Load .env into the process environment so provider SDKs (which read
    # ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY directly) and the
    # DAX_* settings below all see the same secrets.
    from dotenv import load_dotenv

    load_dotenv()

    overrides: dict[str, Any] = {}

    if config_path and config_path.exists():
        import tomllib

        with open(config_path, "rb") as f:
            toml_data = tomllib.load(f)
        overrides = _flatten_toml(toml_data)

    return DaxConfig(**overrides)


def _flatten_toml(data: dict[str, Any]) -> dict[str, Any]:
    """Convert nested TOML dict to the format Pydantic Settings expects.

    Keeps nested dicts as-is since Pydantic handles nested model parsing.
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key == "general":
            # [general] section maps to top-level fields
            result.update(value)
        else:
            result[key] = value
    return result
