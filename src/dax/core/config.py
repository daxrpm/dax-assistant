"""Configuration models for Dax Assistant.

Loads settings from TOML config files + environment variables.
Pydantic Settings handles the merge automatically.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic_settings import PydanticBaseSettingsSource

    from dax.storage.secrets import SecretStore


class VoiceConfig(BaseModel):
    """Voice pipeline configuration."""

    enabled: bool = True
    # OpenWakeWord built-in model name (e.g. "hey_jarvis", "alexa") or a path to
    # a custom ``.onnx`` model. The detector resolves both.
    wake_word_model: str = "hey_jarvis"
    wake_word_threshold: float = 0.7
    # Dax can listen in several places at once — the backend's own microphone
    # and every capability node allowed to listen. One "hey jarvis" spoken in a
    # room where two of them are in earshot fires both, so detections are
    # judged together and only the clearest answers. This is how long the
    # backend waits for a competing detection before deciding: long enough to
    # cover LAN jitter, short enough not to read as lag before the earcon.
    wake_arbitration_window_ms: int = 350
    # How long a microphone that lost the arbitration ignores its own detector,
    # so the rest of the same sentence cannot re-trigger it.
    wake_suppress_ms: int = 2000
    # "local" keeps audio on-device; "openai" uploads each completed utterance
    # to the Audio Transcriptions API and can fall back locally when unavailable.
    stt_backend: Literal["local", "openai"] = "local"
    # faster-whisper model. "large-v3-turbo" is near-large accuracy at a fraction
    # of the cost — the sweet spot for accurate Spanish on CPU (int8).
    stt_model: str = "large-v3-turbo"
    # "auto" picks float16 on CUDA, int8 on CPU. Explicit values still honoured.
    stt_compute_type: str = "auto"
    # "auto" uses the GPU when available, else CPU — big latency win on GPU.
    stt_device: str = "auto"
    # beam_size=2 is a good accuracy/speed balance for turbo; 1 is fastest.
    stt_beam_size: int = 2
    # ISO code ("es"/"en") to PIN the language, or "auto" to detect. Pinning the
    # language is strongly recommended: short/noisy commands otherwise get
    # mis-detected (Whisper guessing "ru"/etc.). The installer sets this.
    stt_language: str = "es"
    stt_openai_model: str = "gpt-4o-mini-transcribe"
    stt_openai_timeout_s: int = 30
    stt_openai_prompt: str = (
        "Transcribe natural Spanish accurately. Preserve names and commands such "
        "as Dax, Spotify, Nextcloud and Home Assistant."
    )
    stt_fallback_to_local: bool = True

    # -- Text-to-speech -----------------------------------------------------
    # Local engines keep audio private; OpenAI offers the most natural prosody.
    tts_engine: Literal["kokoro", "piper", "openai"] = "kokoro"
    # Piper voice names/paths (fallback engine).
    tts_voice_es: str = "es_ES-davefx-medium"
    tts_voice_en: str = "en_US-lessac-medium"
    # Kokoro voice ids (see VOICES.md). ES: ef_dora/em_alex; EN: af_heart/am_michael.
    tts_kokoro_voice_es: str = "em_alex"
    tts_kokoro_voice_en: str = "af_heart"
    tts_kokoro_speed: float = 0.95
    tts_openai_model: str = "gpt-4o-mini-tts"
    tts_openai_voice: str = "marin"
    tts_openai_instructions_es: str = (
        "Habla en español de forma cálida, natural y conversacional, con acento "
        "neutro y ritmo tranquilo. Evita sonar como un locutor o un robot."
    )
    tts_openai_instructions_en: str = (
        "Speak warmly and naturally, like a concise personal assistant."
    )
    tts_openai_timeout_s: int = 30
    tts_fallback_to_local: bool = True

    vad_threshold: float = 0.5
    silence_duration_ms: int = 800
    # Adaptive endpointing: shorten the end-of-speech pause for short commands
    # and lengthen it for longer utterances (natural pauses), Alexa-style.
    adaptive_endpointing: bool = True
    # Suppress background noise before transcription (needs the `noisereduce`
    # extra; silently skipped if unavailable).
    denoise: bool = True
    # Let the user interrupt Dax mid-reply by saying the wake word again.
    barge_in: bool = True
    # Short confirmation tone the instant the wake word fires (Alexa-style).
    earcon: bool = True
    # Seconds to keep listening for a follow-up after speaking (follow-up mode).
    conversation_timeout_s: int = 8
    # Longer window used when Dax's reply ended in a question. He has explicitly
    # invited an answer, so cutting the user off at the normal timeout — while
    # they are still working out what to say — is the wrong call.
    conversation_timeout_question_s: int = 20
    # Minutes of inactivity before a voice session expires and the next wake
    # word starts a fresh, history-free conversation. Until then consecutive
    # activations share context, so "ponla de color rojo" still resolves "la"
    # after the follow-up window has closed. Set to 0 to reset on every wake
    # word (the old behaviour).
    session_ttl_minutes: int = 10
    # Require sustained speech before opening a hands-free follow-up. A single
    # music transient or percussion hit must not create a new voice turn.
    followup_activation_ms: int = 320
    # Additional silence allowed after longer phrases so thinking pauses can
    # resume before the utterance is committed to STT.
    thinking_pause_ms: int = 900

    # -- Reliability & UX ---------------------------------------------------
    # Max seconds to wait for the assistant's reply (incl. long tool chains)
    # before giving up on a voice turn. Generous so multi-tool actions finish.
    response_timeout_s: int = 180
    # Ask for tool confirmations BY VOICE ("¿lo ejecuto? sí/no") instead of the
    # web modal, so voice-only use isn't blocked waiting for a click.
    voice_confirm: bool = True
    # Require the wake word before every turn (no hands-free follow-up). Useful
    # in noisy/shared rooms where follow-up mode picks up other people.
    require_wake_word_each_turn: bool = False

    # -- Speaker verification (Voice ID) ------------------------------------
    # When enabled AND a voice profile is enrolled, ignore commands that don't
    # match the owner's voice — so other people talking can't drive the agent.
    speaker_verification: bool = False
    # Cosine-similarity threshold (0..1) for accepting a speaker as the owner.
    speaker_threshold: float = 0.65
    # When false, enabling Voice ID without a valid profile rejects all speech.
    speaker_fail_open: bool = True


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


class DeepSeekProviderConfig(BaseModel):
    """DeepSeek provider — OpenAI-compatible API (served via the OpenAI SDK).

    Models (2026): ``deepseek-v4-flash`` (fast, cheap, 1M context — default) and
    ``deepseek-v4-pro`` (more capable). The legacy ``deepseek-chat`` /
    ``deepseek-reasoner`` aliases still work for now. Key read from
    ``DEEPSEEK_API_KEY`` if left blank.
    """

    model: str = "deepseek-v4-flash"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
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
    # How many LLM→tool round trips a single turn may take before the agent is
    # forced to answer without tools. Multi-step requests (search an artist,
    # resolve its id, then act) legitimately need several; too low a budget
    # truncates them into a useless "no pude confirmar el resultado".
    max_tool_iterations: int = 10
    ollama: OllamaProviderConfig = Field(default_factory=OllamaProviderConfig)
    anthropic: AnthropicProviderConfig = Field(default_factory=AnthropicProviderConfig)
    openai: OpenAIProviderConfig = Field(default_factory=OpenAIProviderConfig)
    gemini: GeminiProviderConfig = Field(default_factory=GeminiProviderConfig)
    deepseek: DeepSeekProviderConfig = Field(default_factory=DeepSeekProviderConfig)
    codex: CodexProviderConfig = Field(default_factory=CodexProviderConfig)


class WebConfig(BaseModel):
    """Web UI and API server configuration."""

    # Keep loopback as the explicit fallback address. LAN exposure defaults on
    # so first-party mobile clients can pair with `uv run dax` directly.
    host: str = "127.0.0.1"
    port: int = 8420
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8420"])
    # When true, host is forced to 0.0.0.0 so other devices on the LAN can
    # reach the UI (auth is still enforced).
    expose_lan: bool = True
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
    # Lifetime of a device access token. Enrolled clients (the phone) hold a
    # long-lived secret in hardware-backed storage and mint one of these on
    # demand, so it can be short: a captured token expires quickly, and
    # revoking the device kills it immediately regardless.
    device_token_ttl_minutes: int = 15
    # How long a pairing code stays redeemable. Codes are typed by hand from
    # one screen to another, so this is the window between the two.
    pairing_code_ttl_minutes: int = 5


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


def _default_shell_allow() -> list[str]:
    from dax.core.shell_allow import DEFAULT_SHELL_ALLOW

    return list(DEFAULT_SHELL_ALLOW)


class ToolsConfig(BaseModel):
    """Tool execution settings, including the confirmation gate."""

    # Seconds to wait for the user to confirm a gated action before declining.
    confirm_timeout_seconds: int = 120
    policy: ToolPolicyConfig = Field(default_factory=ToolPolicyConfig)
    # Binaries the dax-system shell tool may run on this PC. The agent runs
    # allowlisted commands without asking; unknown ones prompt for confirmation
    # and can be saved here on approval. Editable from the UI's "Commands" page.
    shell_allow: list[str] = Field(default_factory=_default_shell_allow)


class NodePolicyConfig(BaseModel):
    """What one enrolled capability node is asked to do.

    Keyed by device id in :class:`NodesConfig`. The backend owns this because
    the backend owns configuration; a node reads its own entry when it connects,
    and the desktop app running on that laptop edits it like any other setting.
    That keeps one source of truth, so revoking a node's local processing from
    the phone has the same effect as doing it on the laptop itself.
    """

    # Tool lending is independent from hosting a client session. Shell starts
    # disabled because it is the broadest capability and must be opted into.
    tools_enabled: bool = True
    shell_enabled: bool = False
    # False turns the laptop back into a plain tool lender: it still executes
    # the dax-system calls the backend routes to it, but never hosts a session.
    process_locally: bool = True
    # "auto" is the value to keep. It pins inference to the node only when the
    # model itself is local — Ollama on the node's GPU — because a cloud
    # provider is dominated by the round trip to the provider, and routing that
    # HTTPS call through a laptop adds a hop while removing none.
    inference: Literal["auto", "local", "server"] = "auto"
    # Speech is the real win. Audio is bulky and today it crosses the network
    # twice to reach a backend that may be off-LAN.
    voice: Literal["auto", "local", "server"] = "auto"
    # Commands the user has permanently approved for *this* node. Kept per node
    # rather than in `tools.shell_allow` because that list governs the backend
    # host: saving a laptop's command there would silently grant it on the
    # server too, which is a different machine with different contents.
    shell_allow: list[str] = Field(default_factory=list)
    # Whether this laptop listens for the wake word on its own microphone. On
    # by default because a laptop is usually the machine in the room with the
    # user, and a backend in a cupboard cannot hear them at all. Turn it off
    # for a node that sits somewhere it would only pick up noise.
    wake_word: bool = True


class NodesConfig(BaseModel):
    """Capability-node fleet settings."""

    enabled: bool = True
    # Whether clients should prefer a reachable node over the backend. Turning
    # this off is the fleet-wide kill switch; a single node is disabled through
    # its own ``process_locally``.
    prefer_when_available: bool = True
    policies: dict[str, NodePolicyConfig] = Field(default_factory=dict)

    def policy_for(self, node_id: str) -> NodePolicyConfig:
        """The stored policy for *node_id*, or the default one."""
        return self.policies.get(node_id, NodePolicyConfig())

    def hosts_sessions(self, node_id: str) -> bool:
        """Whether *node_id* may terminate a client session and run the turn."""
        return self.enabled and self.policy_for(node_id).process_locally

    def node_allows_command(self, node_id: str, binary: str) -> bool:
        """Whether *binary* was already approved for keeps on this node."""
        if not self.enabled or not binary:
            return False
        return binary in self.policy_for(node_id).shell_allow

    def remember_node_command(self, node_id: str, binary: str) -> None:
        """Persist a user's "always allow" for one command on one node."""
        if not binary:
            return
        policy = self.policies.setdefault(node_id, NodePolicyConfig())
        if binary not in policy.shell_allow:
            policy.shell_allow = [*policy.shell_allow, binary]

    def listens_for_wake_word(self, node_id: str) -> bool:
        """Whether *node_id* may run a wake-word detector and claim activations."""
        return self.enabled and self.policy_for(node_id).wake_word

    def lends_tool(self, node_id: str, tool_name: str) -> bool:
        """Whether the authoritative backend may route this node tool."""
        if not self.enabled:
            return False
        policy = self.policy_for(node_id)
        return policy.tools_enabled and (tool_name != "shell_run" or policy.shell_enabled)


class DaxConfig(BaseSettings):
    """Root configuration for Dax Assistant.

    Settings are loaded in order of priority:
    1. Environment variables (highest priority)
    2. Encrypted SQLite configuration
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
    # Empty selects the maintained built-in prompt. Custom values are encrypted
    # with the rest of the configuration and hot-reloaded by the live agent.
    system_prompt: str = ""

    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    nodes: NodesConfig = Field(default_factory=NodesConfig)


def load_config(config_path: Path | None = None) -> DaxConfig:
    """Load encrypted configuration, importing a legacy TOML once when present.

    Args:
        config_path: Optional legacy TOML path used only for migration/bootstrap.

    Returns:
        Fully resolved DaxConfig instance.
    """
    # Legacy: load .env if present (still supported, but the encrypted SQLite
    # secret store below is now the source of truth — see storage/secrets.py).
    from dotenv import load_dotenv

    load_dotenv()

    overrides: dict[str, Any] = {}

    if config_path and config_path.exists():
        import tomllib

        with open(config_path, "rb") as f:
            toml_data = tomllib.load(f)
        overrides = _flatten_toml(toml_data)

    store = _bootstrap_secrets(overrides, config_path)

    from dax.core.config_io import load_encrypted_config, save_encrypted_config
    from dax.core.exceptions import ConfigError

    try:
        stored = load_encrypted_config(store)
        importing_legacy = bool(overrides) and not _bootstrap_only(overrides)
        config = DaxConfig(
            **(overrides if importing_legacy else (stored if stored is not None else {}))
        )
        if stored is None or importing_legacy:
            save_encrypted_config(config, store)
    except Exception as exc:
        raise ConfigError(f"Encrypted configuration is invalid: {exc}") from exc

    if config_path is not None and config_path.exists() and importing_legacy:
        _retire_legacy_toml(config_path, config.storage.database_path)
    return config


def _bootstrap_secrets(
    overrides: dict[str, Any], config_path: Path | None
) -> SecretStore:
    """Seed os.environ from the encrypted secret store before config is built.

    Secrets (API keys, password hash, session secret) live encrypted in SQLite,
    not in .env. We decrypt them into os.environ here so pydantic-settings and
    the provider SDKs pick them up exactly as they used to from .env. A missing
    session secret is generated and stored so sessions survive restarts.
    """
    import secrets as _secrets

    from dax.storage.secrets import SecretStore

    # Resolve the DB path the same way DaxConfig will: env > TOML > default, so
    # the secret store always points at the same database the app opens.
    db_path = (
        os.environ.get("DAX_STORAGE__DATABASE_PATH")
        or (overrides.get("storage") or {}).get("database_path")
        or "data/dax.db"
    )
    store = SecretStore(db_path)

    # One-time migration of any legacy .env next to the config file.
    if config_path is not None:
        import contextlib

        env_path = config_path.parent.parent / ".env"
        with contextlib.suppress(Exception):  # best effort
            store.import_dotenv(env_path)

    store.load_into_env()

    # Auto-generate a persistent session secret on first run so logins survive
    # restarts without any manual setup.
    if not os.environ.get("DAX_SECURITY__SESSION_SECRET"):
        store.set("DAX_SECURITY__SESSION_SECRET", _secrets.token_urlsafe(48))
    return store


def _bootstrap_only(overrides: dict[str, Any]) -> bool:
    """True when the legacy file contains only the non-secret database pointer."""
    return bool(overrides) and set(overrides) == {"storage"} and set(
        overrides["storage"]
    ) == {"database_path"}


def _retire_legacy_toml(config_path: Path, database_path: str) -> None:
    """Remove migrated TOML, retaining only a custom database-path bootstrap."""
    from dax.core.exceptions import ConfigError

    try:
        if database_path == "data/dax.db":
            config_path.unlink()
            return
        import tomli_w

        config_path.write_text(
            tomli_w.dumps({"storage": {"database_path": database_path}}),
            encoding="utf-8",
        )
    except OSError as exc:
        raise ConfigError(f"Could not retire legacy config {config_path}: {exc}") from exc


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
