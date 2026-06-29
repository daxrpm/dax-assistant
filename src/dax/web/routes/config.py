"""Configuration endpoints — read the full config and patch it section by section.

Every mutation updates the live config object in place and persists via
``persist_config`` (secrets extracted to the encrypted store). Some sections also
apply live: LLM rebuilds the router, tools reloads the policy, telegram restarts
the channel, security/auth syncs the auth manager — all without a restart.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from dax.web.dependencies import ConfigDep, SecretStoreDep, persist_config

router = APIRouter(tags=["config"])

# Secret fields that, when present in a patch, are written to the encrypted
# store under these env names (kept out of the TOML by config_io too).
_WHATSAPP_SECRETS = {
    "evolution_api_key": "DAX_WHATSAPP__EVOLUTION_API_KEY",
    "webhook_secret": "DAX_WHATSAPP__WEBHOOK_SECRET",
}

# LLM patch field → (dotted config section, attribute).
_LLM_FIELD_MAP: dict[str, tuple[str, str]] = {
    "default_provider": ("llm", "default_provider"),
    "fallback_order": ("llm", "fallback_order"),
    "max_tools": ("llm", "max_tools"),
    "ollama_model": ("llm.ollama", "model"),
    "ollama_base_url": ("llm.ollama", "base_url"),
    "ollama_timeout": ("llm.ollama", "timeout"),
    "anthropic_model": ("llm.anthropic", "model"),
    "anthropic_api_key": ("llm.anthropic", "api_key"),
    "openai_model": ("llm.openai", "model"),
    "openai_base_url": ("llm.openai", "base_url"),
    "openai_api_key": ("llm.openai", "api_key"),
    "openai_reasoning_effort": ("llm.openai", "reasoning_effort"),
    "gemini_model": ("llm.gemini", "model"),
    "gemini_api_key": ("llm.gemini", "api_key"),
    "deepseek_model": ("llm.deepseek", "model"),
    "deepseek_api_key": ("llm.deepseek", "api_key"),
    "deepseek_base_url": ("llm.deepseek", "base_url"),
    "codex_binary": ("llm.codex", "binary"),
    "codex_model": ("llm.codex", "model"),
}


class GeneralConfigUpdate(BaseModel):
    name: str | None = None
    language_default: str | None = None
    log_level: str | None = None
    memory_path: str | None = None


class LLMConfigUpdate(BaseModel):
    default_provider: str | None = None
    fallback_order: list[str] | None = None
    max_tools: int | None = None
    ollama_model: str | None = None
    ollama_base_url: str | None = None
    ollama_timeout: int | None = None
    anthropic_model: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    openai_reasoning_effort: str | None = None
    gemini_model: str | None = None
    gemini_api_key: str | None = None
    deepseek_model: str | None = None
    deepseek_api_key: str | None = None
    deepseek_base_url: str | None = None
    codex_binary: str | None = None
    codex_model: str | None = None


class VoiceConfigUpdate(BaseModel):
    enabled: bool | None = None
    wake_word_threshold: float | None = None
    stt_model: str | None = None
    stt_compute_type: str | None = None
    stt_device: str | None = None
    stt_beam_size: int | None = None
    stt_language: str | None = None
    tts_voice_es: str | None = None
    tts_voice_en: str | None = None
    vad_threshold: float | None = None
    silence_duration_ms: int | None = None
    adaptive_endpointing: bool | None = None
    denoise: bool | None = None
    barge_in: bool | None = None
    earcon: bool | None = None
    conversation_timeout_s: int | None = None


class WhatsAppConfigUpdate(BaseModel):
    enabled: bool | None = None
    evolution_api_url: str | None = None
    evolution_api_instance: str | None = None
    evolution_api_key: str | None = None
    respond_with_audio: bool | None = None


class ToolPolicyUpdate(BaseModel):
    default: str | None = None
    allow: list[str] | None = None
    ask: list[str] | None = None
    deny: list[str] | None = None


class ToolsConfigUpdate(BaseModel):
    confirm_timeout_seconds: int | None = None
    policy: ToolPolicyUpdate | None = None


class SecurityConfigUpdate(BaseModel):
    auth_enabled: bool | None = None
    session_ttl_hours: int | None = None
    cookie_secure: bool | None = None


class WebConfigUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    cors_origins: list[str] | None = None
    expose_lan: bool | None = None


class TelegramConfigUpdate(BaseModel):
    enabled: bool | None = None
    bot_token: str | None = None
    allowed_user_ids: list[int] | None = None
    respond_with_audio: bool | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = ""
    new_password: str


@router.get("/config")
async def get_config(config: ConfigDep) -> dict[str, Any]:
    """Get the full configuration (secrets masked)."""
    return {
        "general": {
            "name": config.name,
            "language_default": config.language_default,
            "log_level": config.log_level,
            "memory_path": getattr(config, "memory_path", ""),
        },
        "voice": {
            "enabled": config.voice.enabled,
            "wake_word_threshold": config.voice.wake_word_threshold,
            "stt_model": config.voice.stt_model,
            "stt_compute_type": config.voice.stt_compute_type,
            "stt_device": getattr(config.voice, "stt_device", "auto"),
            "stt_beam_size": getattr(config.voice, "stt_beam_size", 1),
            "stt_language": config.voice.stt_language,
            "tts_voice_es": config.voice.tts_voice_es,
            "tts_voice_en": config.voice.tts_voice_en,
            "vad_threshold": config.voice.vad_threshold,
            "silence_duration_ms": config.voice.silence_duration_ms,
            "adaptive_endpointing": getattr(config.voice, "adaptive_endpointing", True),
            "denoise": getattr(config.voice, "denoise", True),
            "barge_in": getattr(config.voice, "barge_in", True),
            "earcon": getattr(config.voice, "earcon", True),
            "conversation_timeout_s": getattr(config.voice, "conversation_timeout_s", 8),
        },
        "llm": {
            "default_provider": config.llm.default_provider,
            "fallback_order": config.llm.fallback_order,
            "max_tools": getattr(config.llm, "max_tools", 45),
            "ollama_model": config.llm.ollama.model,
            "ollama_base_url": config.llm.ollama.base_url,
            "ollama_timeout": config.llm.ollama.timeout,
            "anthropic_model": config.llm.anthropic.model,
            "anthropic_configured": bool(config.llm.anthropic.api_key),
            "openai_model": config.llm.openai.model,
            "openai_base_url": config.llm.openai.base_url,
            "openai_configured": bool(config.llm.openai.api_key),
            "openai_reasoning_effort": getattr(
                config.llm.openai, "reasoning_effort", "low"
            ),
            "gemini_model": config.llm.gemini.model,
            "gemini_configured": bool(config.llm.gemini.api_key),
            "deepseek_model": getattr(config.llm, "deepseek", None)
            and config.llm.deepseek.model,
            "deepseek_base_url": getattr(config.llm, "deepseek", None)
            and config.llm.deepseek.base_url,
            "deepseek_configured": bool(
                getattr(config.llm, "deepseek", None) and config.llm.deepseek.api_key
            ),
            "codex_binary": getattr(config.llm.codex, "binary", "codex"),
            "codex_model": getattr(config.llm.codex, "model", ""),
        },
        "web": {
            "host": config.web.host,
            "port": config.web.port,
            "cors_origins": config.web.cors_origins,
            "expose_lan": getattr(config.web, "expose_lan", False),
        },
        "whatsapp": {
            "enabled": config.whatsapp.enabled,
            "evolution_api_url": config.whatsapp.evolution_api_url,
            "evolution_api_instance": config.whatsapp.evolution_api_instance,
            "respond_with_audio": config.whatsapp.respond_with_audio,
            "has_api_key": bool(config.whatsapp.evolution_api_key),
        },
        "telegram": {
            "enabled": config.telegram.enabled,
            "allowed_user_ids": config.telegram.allowed_user_ids,
            "respond_with_audio": config.telegram.respond_with_audio,
            "has_token": bool(config.telegram.bot_token),
        },
        "security": {
            "auth_enabled": config.security.auth_enabled,
            "configured": bool(config.security.password_hash),
            "session_ttl_hours": config.security.session_ttl_hours,
            "cookie_secure": config.security.cookie_secure,
        },
        "tools": {
            "confirm_timeout_seconds": config.tools.confirm_timeout_seconds,
            "shell_allow": getattr(config.tools, "shell_allow", []),
            "policy": {
                "default": config.tools.policy.default,
                "allow": config.tools.policy.allow,
                "ask": config.tools.policy.ask,
                "deny": config.tools.policy.deny,
            },
        },
        "mcp": {
            "servers": {
                name: {
                    "command": srv.command,
                    "args": srv.args,
                    "env": srv.env,
                    "transport": srv.transport,
                    "url": srv.url,
                    "headers": srv.headers,
                    "enabled": srv.enabled,
                    "export_codex": getattr(srv, "export_codex", False),
                    "export_claude": getattr(srv, "export_claude", False),
                }
                for name, srv in config.mcp.servers.items()
            },
        },
    }


@router.patch("/config/general")
async def update_general(
    request: Request, body: GeneralConfigUpdate, config: ConfigDep
) -> dict[str, str]:
    """Update general settings."""
    for key, value in body.model_dump(exclude_none=True).items():
        if hasattr(config, key):
            object.__setattr__(config, key, value)
    persist_config(request)
    return {"status": "ok"}


@router.patch("/config/llm")
async def update_llm(
    request: Request, body: LLMConfigUpdate, config: ConfigDep
) -> dict[str, str]:
    """Update LLM provider settings and rebuild the live router."""
    for key, value in body.model_dump(exclude_none=True).items():
        if key not in _LLM_FIELD_MAP:
            continue
        section, attr = _LLM_FIELD_MAP[key]
        obj: Any = config
        for part in section.split("."):
            obj = getattr(obj, part)
        object.__setattr__(obj, attr, value)

    persist_config(request)

    # Rebuild the live router so the change takes effect immediately — no
    # restart. The agent holds the same router instance, so it picks up the
    # new default/fallback providers on its next request.
    router_obj = getattr(request.app.state, "llm_router", None)
    if router_obj is not None:
        from dax.llm.factory import build_providers

        try:
            router_obj.set_providers(build_providers(config.llm))
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid LLM configuration: {e}"
            ) from e

    return {"status": "ok"}


@router.patch("/config/voice")
async def update_voice(
    request: Request, body: VoiceConfigUpdate, config: ConfigDep
) -> dict[str, str]:
    """Update voice pipeline settings."""
    for key, value in body.model_dump(exclude_none=True).items():
        if hasattr(config.voice, key):
            object.__setattr__(config.voice, key, value)
    persist_config(request)
    return {"status": "ok"}


@router.patch("/config/whatsapp")
async def update_whatsapp(
    request: Request, body: WhatsAppConfigUpdate, config: ConfigDep, store: SecretStoreDep
) -> dict[str, str]:
    """Update WhatsApp integration settings."""
    for key, value in body.model_dump(exclude_none=True).items():
        if key in _WHATSAPP_SECRETS and isinstance(value, str) and value:
            store.set(_WHATSAPP_SECRETS[key], value)
        if hasattr(config.whatsapp, key):
            object.__setattr__(config.whatsapp, key, value)
    persist_config(request)
    return {"status": "ok"}


@router.patch("/config/web")
async def update_web(
    request: Request, body: WebConfigUpdate, config: ConfigDep
) -> dict[str, str]:
    """Update web server settings (restart required for host/port changes)."""
    for key, value in body.model_dump(exclude_none=True).items():
        if hasattr(config.web, key):
            object.__setattr__(config.web, key, value)
    persist_config(request)
    return {"status": "ok", "note": "Restart required for host/port changes to take effect"}


@router.patch("/config/telegram")
async def update_telegram(
    request: Request, body: TelegramConfigUpdate, config: ConfigDep, store: SecretStoreDep
) -> dict[str, str]:
    """Update Telegram bot settings. Token is stored encrypted in SQLite and
    the channel is reloaded live — no restart needed."""
    for key, value in body.model_dump(exclude_none=True).items():
        if key == "bot_token" and isinstance(value, str) and value:
            store.set("DAX_TELEGRAM__BOT_TOKEN", value)
            object.__setattr__(config.telegram, "bot_token", value)
        elif hasattr(config.telegram, key):
            object.__setattr__(config.telegram, key, value)

    persist_config(request)

    # Apply live: restart the Telegram channel with the new settings.
    dax_app = getattr(request.app.state, "dax_app", None)
    if dax_app is not None:
        try:
            await dax_app.reload_telegram()
        except Exception as e:
            return {"status": "saved", "note": f"Saved, but reload failed: {e}"}

    return {"status": "ok"}


@router.patch("/config/tools")
async def update_tools(
    request: Request, body: ToolsConfigUpdate, config: ConfigDep
) -> dict[str, str]:
    """Update the tool confirmation timeout and allow/ask/deny policy."""
    if body.confirm_timeout_seconds is not None:
        object.__setattr__(
            config.tools, "confirm_timeout_seconds", body.confirm_timeout_seconds
        )
    if body.policy is not None:
        for key, value in body.policy.model_dump(exclude_none=True).items():
            object.__setattr__(config.tools.policy, key, value)

    persist_config(request)

    # Apply live: the agent holds the same ToolPolicy instance.
    policy_obj = getattr(request.app.state, "tool_policy", None)
    if policy_obj is not None:
        policy_obj.reload(config.tools.policy)

    return {"status": "ok"}


@router.patch("/config/security")
async def update_security(
    request: Request, body: SecurityConfigUpdate, config: ConfigDep
) -> dict[str, str]:
    """Update security settings (TTL, secure cookie, auth toggle)."""
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        if hasattr(config.security, key):
            object.__setattr__(config.security, key, value)

    # Sync live auth manager with the new auth_enabled flag.
    if "auth_enabled" in updates:
        auth = getattr(request.app.state, "auth", None)
        if auth is not None:
            auth._enabled = updates["auth_enabled"]

    persist_config(request)
    return {"status": "ok"}


@router.post("/auth/change-password")
async def change_password(
    request: Request, body: ChangePasswordRequest, config: ConfigDep, store: SecretStoreDep
) -> dict[str, str]:
    """Change the login password and persist the new hash to the secret store."""
    from dax.web.auth import hash_password, verify_password

    auth = getattr(request.app.state, "auth", None)

    # Verify current password when auth is already configured.
    if (
        config.security.auth_enabled
        and config.security.password_hash
        and not verify_password(config.security.password_hash, body.current_password)
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    new_hash = hash_password(body.new_password)
    store.set("DAX_SECURITY__PASSWORD_HASH", new_hash)

    # Update live config + auth manager so the new password takes effect now.
    object.__setattr__(config.security, "password_hash", new_hash)
    object.__setattr__(config.security, "auth_enabled", True)
    if auth is not None:
        auth._password_hash = new_hash
        auth._enabled = True

    persist_config(request)
    return {"status": "ok"}
