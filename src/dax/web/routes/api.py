"""REST API routes — status, configuration, MCP management."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dax.core.config_io import dump_config_toml
from dax.storage.secrets import SecretStore

router = APIRouter(tags=["api"])


def _secret_store(request: Request) -> SecretStore:
    """Return the live encrypted secret store (or build one from config).

    Secrets (API keys, tokens, password hash) are persisted encrypted in
    SQLite — never in TOML and no longer in .env. The store also exports each
    value to ``os.environ`` so ``{env:VAR}`` references and provider SDKs keep
    resolving them transparently.
    """
    store = getattr(request.app.state, "secret_store", None)
    if isinstance(store, SecretStore):
        return store
    config = request.app.state.config
    return SecretStore(config.storage.database_path)


# --- Response / Request Models ---


class StatusResponse(BaseModel):
    name: str
    version: str
    status: str
    voice_listening: bool
    llm_provider: str
    mcp_servers: int
    mcp_tools: int


class ToggleRequest(BaseModel):
    enabled: bool


class ToggleResponse(BaseModel):
    voice_listening: bool


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


class ChangePasswordRequest(BaseModel):
    current_password: str = ""
    new_password: str


class TelegramConfigUpdate(BaseModel):
    enabled: bool | None = None
    bot_token: str | None = None
    allowed_user_ids: list[int] | None = None
    respond_with_audio: bool | None = None


class MCPServerCreate(BaseModel):
    name: str
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    export_codex: bool = False
    export_claude: bool = False


# --- Ollama Models ---


@router.get("/ollama/models")
async def list_ollama_models(request: Request) -> list[dict[str, Any]]:
    """List models available in the local Ollama instance."""
    config = request.app.state.config
    base_url = config.llm.ollama.base_url.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [
                {
                    "name": m["name"],
                    "size_gb": round(m.get("size", 0) / 1e9, 1),
                    "modified": m.get("modified_at", ""),
                    "family": m.get("details", {}).get("family", ""),
                    "parameters": m.get("details", {}).get(
                        "parameter_size", "",
                    ),
                    "quantization": m.get("details", {}).get(
                        "quantization_level", "",
                    ),
                }
                for m in data.get("models", [])
            ]
    except Exception:
        return []


# --- Tool audit log ---


@router.get("/tools/audit")
async def get_tool_audit(request: Request, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent tool-execution audit entries (newest first)."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        return []
    return await repo.get_tool_audit(limit=limit)


@router.get("/tools/policy")
async def get_tool_policy(request: Request) -> dict[str, Any]:
    """Expose the current tool policy so the UI can show what's gated."""
    policy = request.app.state.config.tools.policy
    return {
        "default": policy.default,
        "allow": policy.allow,
        "ask": policy.ask,
        "deny": policy.deny,
        "confirm_timeout_seconds": request.app.state.config.tools.confirm_timeout_seconds,
    }


# --- Logs ---


@router.get("/logs")
async def get_logs(request: Request, limit: int = 200) -> list[dict[str, Any]]:
    """Return recent backend log records (oldest first)."""
    buffer = getattr(request.app.state, "log_buffer", None)
    if buffer is None:
        return []
    return buffer.recent(limit=limit)


# --- MCP status ---


@router.get("/mcp/status")
async def get_mcp_status(request: Request) -> list[dict[str, Any]]:
    """Per-server MCP connection + tool status."""
    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is None:
        return []
    return manager.server_status()


# --- Status ---


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request) -> StatusResponse:
    """Get the current system status."""
    config = request.app.state.config
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    tool_count = mcp_manager.registry.tool_count if mcp_manager else 0

    return StatusResponse(
        name=config.name,
        version="0.1.0",
        status="running",
        voice_listening=request.app.state.voice_listening,
        llm_provider=config.llm.default_provider,
        mcp_servers=len(config.mcp.servers),
        mcp_tools=tool_count,
    )


# --- Voice Toggle ---


@router.post("/voice/toggle", response_model=ToggleResponse)
async def toggle_voice(
    request: Request, body: ToggleRequest,
) -> ToggleResponse:
    """Toggle voice listening on or off."""
    request.app.state.voice_listening = body.enabled
    return ToggleResponse(voice_listening=body.enabled)


# --- Full Config (read) ---


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Get the full configuration (secrets masked)."""
    config = request.app.state.config

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
            "deepseek_model": getattr(config.llm, "deepseek", None) and config.llm.deepseek.model,
            "deepseek_base_url": getattr(config.llm, "deepseek", None) and config.llm.deepseek.base_url,
            "deepseek_configured": bool(getattr(config.llm, "deepseek", None) and config.llm.deepseek.api_key),
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


# --- Config section updates ---


@router.patch("/config/general")
async def update_general(
    request: Request, body: GeneralConfigUpdate,
) -> dict[str, str]:
    """Update general settings."""
    config = request.app.state.config
    updates = body.model_dump(exclude_none=True)

    for key, value in updates.items():
        if hasattr(config, key):
            object.__setattr__(config, key, value)

    _save_config_to_toml(request)
    return {"status": "ok"}


@router.patch("/config/llm")
async def update_llm(
    request: Request, body: LLMConfigUpdate,
) -> dict[str, str]:
    """Update LLM provider settings."""
    config = request.app.state.config
    updates = body.model_dump(exclude_none=True)

    field_map = {
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

    for key, value in updates.items():
        if key in field_map:
            section, attr = field_map[key]
            obj = config
            for part in section.split("."):
                obj = getattr(obj, part)
            object.__setattr__(obj, attr, value)

    _save_config_to_toml(request)

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
                status_code=400,
                detail=f"Invalid LLM configuration: {e}",
            ) from e

    return {"status": "ok"}


@router.patch("/config/voice")
async def update_voice(
    request: Request, body: VoiceConfigUpdate,
) -> dict[str, str]:
    """Update voice pipeline settings."""
    config = request.app.state.config
    updates = body.model_dump(exclude_none=True)

    for key, value in updates.items():
        if hasattr(config.voice, key):
            object.__setattr__(config.voice, key, value)

    _save_config_to_toml(request)
    return {"status": "ok"}


@router.patch("/config/whatsapp")
async def update_whatsapp(
    request: Request, body: WhatsAppConfigUpdate,
) -> dict[str, str]:
    """Update WhatsApp integration settings."""
    config = request.app.state.config
    updates = body.model_dump(exclude_none=True)

    store = _secret_store(request)
    _WHATSAPP_SECRETS = {
        "evolution_api_key": "DAX_WHATSAPP__EVOLUTION_API_KEY",
        "webhook_secret": "DAX_WHATSAPP__WEBHOOK_SECRET",
    }

    for key, value in updates.items():
        if key in _WHATSAPP_SECRETS and isinstance(value, str) and value:
            store.set(_WHATSAPP_SECRETS[key], value)
        if hasattr(config.whatsapp, key):
            object.__setattr__(config.whatsapp, key, value)

    _save_config_to_toml(request)
    return {"status": "ok"}


@router.patch("/config/web")
async def update_web(
    request: Request, body: WebConfigUpdate,
) -> dict[str, str]:
    """Update web server settings (restart required for host/port changes)."""
    config = request.app.state.config
    updates = body.model_dump(exclude_none=True)

    for key, value in updates.items():
        if hasattr(config.web, key):
            object.__setattr__(config.web, key, value)

    _save_config_to_toml(request)
    return {"status": "ok", "note": "Restart required for host/port changes to take effect"}


@router.patch("/config/telegram")
async def update_telegram(
    request: Request, body: TelegramConfigUpdate,
) -> dict[str, str]:
    """Update Telegram bot settings. Token is stored encrypted in SQLite and
    the channel is reloaded live — no restart needed."""
    config = request.app.state.config
    updates = body.model_dump(exclude_none=True)

    store = _secret_store(request)

    for key, value in updates.items():
        if key == "bot_token" and isinstance(value, str) and value:
            store.set("DAX_TELEGRAM__BOT_TOKEN", value)
            object.__setattr__(config.telegram, "bot_token", value)
        elif hasattr(config.telegram, key):
            object.__setattr__(config.telegram, key, value)

    _save_config_to_toml(request)

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
    request: Request, body: ToolsConfigUpdate,
) -> dict[str, str]:
    """Update the tool confirmation timeout and allow/ask/deny policy."""
    config = request.app.state.config

    if body.confirm_timeout_seconds is not None:
        object.__setattr__(
            config.tools, "confirm_timeout_seconds", body.confirm_timeout_seconds
        )
    if body.policy is not None:
        policy_updates = body.policy.model_dump(exclude_none=True)
        for key, value in policy_updates.items():
            object.__setattr__(config.tools.policy, key, value)

    _save_config_to_toml(request)

    # Apply live: the agent holds the same ToolPolicy instance.
    policy_obj = getattr(request.app.state, "tool_policy", None)
    if policy_obj is not None:
        policy_obj.reload(config.tools.policy)

    return {"status": "ok"}


@router.patch("/config/security")
async def update_security(
    request: Request, body: SecurityConfigUpdate,
) -> dict[str, str]:
    """Update security settings (TTL, secure cookie, auth toggle)."""
    config = request.app.state.config
    updates = body.model_dump(exclude_none=True)

    for key, value in updates.items():
        if hasattr(config.security, key):
            object.__setattr__(config.security, key, value)

    # Sync live auth manager with the new auth_enabled flag.
    if "auth_enabled" in updates:
        auth = getattr(request.app.state, "auth", None)
        if auth is not None:
            auth._enabled = updates["auth_enabled"]

    _save_config_to_toml(request)
    return {"status": "ok"}


@router.post("/auth/change-password")
async def change_password(
    request: Request, body: ChangePasswordRequest,
) -> dict[str, str]:
    """Change the login password and persist the new hash to .env."""
    from dax.web.auth import hash_password, verify_password

    config = request.app.state.config
    auth = getattr(request.app.state, "auth", None)

    # Verify current password when auth is already configured.
    if config.security.auth_enabled and config.security.password_hash:
        if not verify_password(config.security.password_hash, body.current_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    new_hash = hash_password(body.new_password)

    _secret_store(request).set("DAX_SECURITY__PASSWORD_HASH", new_hash)

    # Update live config + auth manager so the new password takes effect immediately.
    object.__setattr__(config.security, "password_hash", new_hash)
    object.__setattr__(config.security, "auth_enabled", True)
    if auth is not None:
        auth._password_hash = new_hash
        auth._enabled = True

    _save_config_to_toml(request)
    return {"status": "ok"}


# --- MCP Server Management ---


@router.get("/config/mcp/servers")
async def list_mcp_servers(request: Request) -> dict[str, Any]:
    """List all configured MCP servers."""
    config = request.app.state.config
    return {
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
    }


@router.post("/config/mcp/servers")
async def add_mcp_server(
    request: Request, body: MCPServerCreate,
) -> dict[str, Any]:
    """Add a new MCP server, persist it, and connect to it live."""
    from dax.core.config import MCPServerConfig

    config = request.app.state.config

    if body.name in config.mcp.servers:
        raise HTTPException(
            status_code=409,
            detail=f"Server '{body.name}' already exists",
        )

    server_config = MCPServerConfig(
        command=body.command,
        args=body.args,
        env=body.env,
        transport=body.transport,
        url=body.url,
        headers=body.headers,
        enabled=body.enabled,
        export_codex=body.export_codex,
        export_claude=body.export_claude,
    )
    config.mcp.servers[body.name] = server_config
    _save_config_to_toml(request)

    # Connect live (best-effort): the server is saved either way.
    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is not None and body.enabled:
        try:
            tools = await manager.add_server(body.name, server_config)
            return {"status": "ok", "name": body.name, "tools": tools}
        except Exception as e:
            return {"status": "saved", "name": body.name, "error": str(e)}

    return {"status": "ok", "name": body.name, "tools": 0}


@router.post("/config/mcp/servers/{server_name}/reconnect")
async def reconnect_mcp_server(
    request: Request, server_name: str,
) -> dict[str, Any]:
    """Reconnect a server with current config and any stored OAuth token."""
    manager = getattr(request.app.state, "mcp_manager", None)
    if not manager:
        raise HTTPException(500, "MCP Manager not available")

    server_config = request.app.state.config.mcp.servers.get(server_name)
    if not server_config:
        raise HTTPException(404, f"Server '{server_name}' not found")

    try:
        tools = await manager.add_server(server_name, server_config)
    except Exception as e:
        raise HTTPException(500, f"Failed to connect: {e}") from e
    return {"status": "ok", "tools": tools}


class MCPServerUpdate(BaseModel):
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    export_codex: bool = False
    export_claude: bool = False


@router.patch("/config/mcp/servers/{server_name}")
async def update_mcp_server(
    request: Request, server_name: str, body: MCPServerUpdate,
) -> dict[str, Any]:
    """Update an existing MCP server config, persist, and reconnect live."""
    from dax.core.config import MCPServerConfig

    config = request.app.state.config

    if server_name not in config.mcp.servers:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    previous = config.mcp.servers[server_name]
    server_config = MCPServerConfig(
        command=body.command,
        args=body.args,
        env=body.env,
        transport=body.transport,
        url=body.url,
        headers=body.headers,
        enabled=body.enabled,
        export_codex=body.export_codex,
        export_claude=body.export_claude,
    )
    config.mcp.servers[server_name] = server_config
    _save_config_to_toml(request)

    connection_changed = any(
        getattr(previous, field) != getattr(server_config, field)
        for field in ("command", "args", "env", "transport", "url", "headers", "enabled")
    )
    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is not None and body.enabled and connection_changed:
        try:
            tools = await manager.add_server(server_name, server_config)
            return {"status": "ok", "name": server_name, "tools": tools}
        except Exception as e:
            return {"status": "saved", "name": server_name, "error": str(e)}

    return {"status": "ok", "name": server_name, "tools": 0}


@router.delete("/config/mcp/servers/{server_name}")
async def delete_mcp_server(
    request: Request, server_name: str,
) -> dict[str, str]:
    """Disconnect, drop tools, remove the server config, and persist."""
    config = request.app.state.config

    if server_name not in config.mcp.servers:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_name}' not found",
        )

    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is not None:
        await manager.remove_server(server_name)

    del config.mcp.servers[server_name]
    _save_config_to_toml(request)
    return {"status": "ok"}


# --- Shell command allowlist ---
#
# The binaries the assistant may run on this PC via the dax-system `shell_run`
# tool. This is the single source of truth: the agent runs allowlisted commands
# without asking and prompts for the rest. Editing here updates the live
# allowlist the agent consults and persists to TOML — no restart, no MCP env.


def _shell_allow_runtime(request: Request) -> Any | None:
    return getattr(request.app.state, "shell_allow", None)


@router.get("/config/system/shell-allow")
async def get_system_shell_allow(request: Request) -> dict[str, Any]:
    """Return the current shell-command allowlist and the built-in defaults."""
    from dax.core.shell_allow import DEFAULT_SHELL_ALLOW

    runtime = _shell_allow_runtime(request)
    if runtime is not None:
        commands = runtime.items()
    else:
        commands = list(getattr(request.app.state.config.tools, "shell_allow", []))
    return {"commands": commands, "default": list(DEFAULT_SHELL_ALLOW)}


class ShellAllowUpdate(BaseModel):
    commands: list[str] = Field(default_factory=list)


@router.put("/config/system/shell-allow")
async def update_system_shell_allow(
    request: Request, body: ShellAllowUpdate,
) -> dict[str, Any]:
    """Replace the shell allowlist. Applies live and persists to TOML."""
    from dax.mcp_servers.system.server import _SHELL_METACHARS

    # Normalise: trim, drop blanks, de-dupe (order preserved). Each entry must be
    # a bare binary name — no whitespace, commas or shell metacharacters.
    seen: set[str] = set()
    commands: list[str] = []
    for raw in body.commands:
        cmd = raw.strip()
        if not cmd or cmd in seen:
            continue
        if (
            "," in cmd
            or any(ch.isspace() for ch in cmd)
            or any(ch in _SHELL_METACHARS for ch in cmd)
        ):
            raise HTTPException(
                422, f"Invalid command '{cmd}': use a bare binary name (e.g. 'git')"
            )
        seen.add(cmd)
        commands.append(cmd)

    config = request.app.state.config
    object.__setattr__(config.tools, "shell_allow", commands)

    runtime = _shell_allow_runtime(request)
    if runtime is not None:
        # replace() fires the persistence hook; avoid double-writing the TOML.
        runtime.replace(commands)
    else:
        _save_config_to_toml(request)

    return {"status": "ok", "commands": commands}


# --- Config persistence ---


def _save_config_to_toml(request: Request) -> None:
    """Persist the current in-memory config to TOML (request-scoped wrapper).

    Serialization + secret extraction live in :mod:`dax.core.config_io`; this is
    only the HTTP-handler glue that resolves the live config, secret store, and
    config path from app state.
    """
    config = request.app.state.config
    config_path = getattr(
        request.app.state, "config_path", Path("config/dax.toml"),
    )
    store = _secret_store(request)
    dump_config_toml(config, store, config_path)


# --- Conversation history ---


@router.get("/conversations")
async def list_conversations(
    request: Request,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List recent web conversations for the sidebar."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        return []
    return await repo.list_conversations("web", limit=limit)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
) -> dict[str, Any]:
    """Return a conversation with its messages."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Storage not available")
    conv = await repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": conv.id,
        "session_key": conv.session_key,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role.value,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in conv.messages
            if m.role.value in ("user", "assistant")
        ],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    request: Request,
) -> None:
    """Delete a conversation and its messages."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Storage not available")
    await repo.delete_conversation(conversation_id)


# ---------------------------------------------------------------------------
# LLM Model Discovery
# ---------------------------------------------------------------------------


@router.get("/llm/models")
async def list_llm_models(request: Request, provider: str = "") -> dict[str, list[str]]:
    """Return available model IDs for each configured provider.

    Query param ``provider`` limits the response to a single provider.
    """
    import aiohttp

    config = request.app.state.config
    results: dict[str, list[str]] = {}

    async def _openai() -> list[str]:
        key = config.llm.openai.api_key or ""
        base = (config.llm.openai.base_url or "https://api.openai.com/v1").rstrip("/")
        if not key:
            return []
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return []
                data = await r.json()
        return sorted(
            {m["id"] for m in data.get("data", []) if "gpt" in m.get("id", "").lower()},
        )

    async def _anthropic() -> list[str]:
        key = config.llm.anthropic.api_key or ""
        if not key:
            return []
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return []
                data = await r.json()
        return sorted(m["id"] for m in data.get("data", []))

    async def _gemini() -> list[str]:
        key = config.llm.gemini.api_key or ""
        if not key:
            return []
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=1000",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return []
                data = await r.json()
        return sorted(
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        )

    async def _ollama() -> list[str]:
        base = (config.llm.ollama.base_url or "http://localhost:11434").rstrip("/")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    if r.status != 200:
                        return []
                    data = await r.json()
            return sorted(m["name"] for m in data.get("models", []))
        except Exception:
            return []

    async def _deepseek() -> list[str]:
        from dax.llm.factory import _resolve_env

        ds = getattr(config.llm, "deepseek", None)
        if ds is None:
            return []
        key = _resolve_env(ds.api_key) or ds.api_key
        base = (ds.base_url or "https://api.deepseek.com").rstrip("/")
        if not key:
            return []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base}/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    if r.status != 200:
                        return []
                    data = await r.json()
            return sorted(m["id"] for m in data.get("data", []))
        except Exception:
            return []

    targets = {
        "openai": _openai,
        "anthropic": _anthropic,
        "gemini": _gemini,
        "ollama": _ollama,
        "deepseek": _deepseek,
    }
    chosen = {provider: targets[provider]} if provider in targets else targets

    import asyncio as _asyncio
    fetched = await _asyncio.gather(*[fn() for fn in chosen.values()], return_exceptions=True)
    for prov, res in zip(chosen.keys(), fetched):
        results[prov] = res if isinstance(res, list) else []

    return results


# ---------------------------------------------------------------------------
# Memory management
# ---------------------------------------------------------------------------


def _memory_dir(request: Request, *, create: bool = False) -> Path:
    config = request.app.state.config
    raw = getattr(config, "memory_path", "") or "~/.dax/memory"
    p = Path(raw).expanduser()
    if create:
        p.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    if not p.is_dir():
        raise HTTPException(status_code=500, detail="memory_path is not a directory")
    return p


def _memory_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    if not slug:
        slug = "memory"
    return slug[:80]


def _memory_path(mem_dir: Path, slug: str) -> Path:
    clean = _memory_slug(slug)
    path = (mem_dir / f"{clean}.md").resolve()
    root = mem_dir.resolve()
    if root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid memory slug")
    return path


def _memory_frontmatter(
    *,
    name: str,
    description: str = "",
    mem_type: str = "user",
    body: str = "",
) -> str:
    safe_type = mem_type if mem_type in {"user", "feedback", "project", "reference"} else "user"
    return (
        "---\n"
        f"name: {name.strip() or 'Memory'}\n"
        f"description: {description.strip()}\n"
        f"type: {safe_type}\n"
        "---\n\n"
        f"{body.strip()}\n"
    )


def _refresh_memory_index(mem_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for p in sorted(mem_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        try:
            entries.append(_parse_memory_file(p))
        except Exception:
            pass
    lines = ["# Dax Memory", ""]
    if entries:
        lines.extend(
            f"- [{entry['name']}]({entry['filename']}) - {entry['description']}"
            for entry in entries
        )
    else:
        lines.append("_No memories yet._")
    (mem_dir / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_memory_file(path: Path) -> dict[str, Any]:
    """Parse a memory .md file and return structured data."""
    text = path.read_text(encoding="utf-8")
    slug = path.stem
    name = slug
    description = ""
    mem_type = "user"
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()
            for line in fm_text.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                elif "type:" in line:
                    mem_type = line.split(":", 1)[1].strip()

    return {
        "slug": slug,
        "name": name,
        "description": description,
        "type": mem_type,
        "body": body,
        "filename": path.name,
    }


@router.get("/memory")
async def list_memory(request: Request) -> list[dict[str, Any]]:
    """List all memory entries."""
    mem_dir = _memory_dir(request, create=True)
    entries = []
    for p in sorted(mem_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        try:
            entries.append(_parse_memory_file(p))
        except Exception:
            pass
    return entries


@router.get("/memory/{slug}")
async def get_memory(slug: str, request: Request) -> dict[str, Any]:
    mem_dir = _memory_dir(request, create=True)
    path = _memory_path(mem_dir, slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Memory not found")
    return _parse_memory_file(path)


class MemoryCreate(BaseModel):
    name: str
    body: str = ""
    description: str = ""
    type: str = "user"


class MemoryUpdate(BaseModel):
    name: str | None = None
    body: str | None = None
    description: str | None = None
    type: str | None = None


@router.post("/memory", status_code=201)
async def create_memory(request: Request, body: MemoryCreate) -> dict[str, Any]:
    mem_dir = _memory_dir(request, create=True)
    base_slug = _memory_slug(body.name)
    slug = base_slug
    i = 2
    while _memory_path(mem_dir, slug).exists():
        slug = f"{base_slug}-{i}"
        i += 1
    path = _memory_path(mem_dir, slug)
    path.write_text(
        _memory_frontmatter(
            name=body.name,
            description=body.description,
            mem_type=body.type,
            body=body.body,
        ),
        encoding="utf-8",
    )
    _refresh_memory_index(mem_dir)
    return _parse_memory_file(path)


@router.patch("/memory/{slug}")
async def update_memory(slug: str, request: Request, body: MemoryUpdate) -> dict[str, str]:
    mem_dir = _memory_dir(request, create=True)
    path = _memory_path(mem_dir, slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Memory not found")

    existing = _parse_memory_file(path)
    path.write_text(
        _memory_frontmatter(
            name=body.name if body.name is not None else existing["name"],
            description=(
                body.description
                if body.description is not None
                else existing["description"]
            ),
            mem_type=body.type if body.type is not None else existing["type"],
            body=body.body if body.body is not None else existing["body"],
        ),
        encoding="utf-8",
    )
    _refresh_memory_index(mem_dir)
    return {"status": "ok"}


@router.delete("/memory/{slug}", status_code=204)
async def delete_memory(slug: str, request: Request) -> None:
    mem_dir = _memory_dir(request, create=True)
    path = _memory_path(mem_dir, slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Memory not found")
    path.unlink()
    _refresh_memory_index(mem_dir)


# ---------------------------------------------------------------------------
# Codex CLI config generator
# ---------------------------------------------------------------------------


@router.get("/codex-config")
async def get_codex_config(request: Request) -> dict[str, Any]:
    """Generate ~/.codex/config.toml for MCP servers flagged export_codex."""
    config = request.app.state.config
    toml_lines = ["# Generated by Dax — paste into ~/.codex/config.toml", ""]
    count = 0

    for name, srv in config.mcp.servers.items():
        if not srv.enabled or not getattr(srv, "export_codex", False):
            continue
        count += 1
        toml_lines.append(f"[mcp_servers.{name}]")
        if srv.transport in ("http", "streamable_http", "sse") and srv.url:
            toml_lines.append(f'url = "{srv.url}"')
            static, env_hdrs = {}, {}
            for k, v in srv.headers.items():
                if v.startswith("{env:") and v.endswith("}"):
                    env_hdrs[k] = v[5:-1]
                else:
                    static[k] = v
            if env_hdrs:
                inner = ", ".join(f'"{k}" = "{var}"' for k, var in env_hdrs.items())
                toml_lines.append(f"env_http_headers = {{ {inner} }}")
            if static:
                inner = ", ".join(f'"{k}" = "{v}"' for k, v in static.items())
                toml_lines.append(f"http_headers = {{ {inner} }}")
        elif srv.command:
            toml_lines.append(f'command = "{srv.command}"')
            if srv.args:
                items = ", ".join(f'"{a}"' for a in srv.args)
                toml_lines.append(f"args = [{items}]")
            if srv.env:
                items = ", ".join(f'"{k}"' for k in srv.env)
                toml_lines.append(f"env_vars = [{items}]")
        toml_lines.append("")

    return {
        "toml": "\n".join(toml_lines),
        "server_count": count,
        "note": "Requires Codex CLI (npm i -g @openai/codex). Works with ChatGPT Pro account or OpenAI API key.",
    }


@router.get("/claude-config")
async def get_claude_config(request: Request) -> dict[str, Any]:
    """Generate Claude Desktop / Claude Code MCP config (servers flagged export_claude)."""
    config = request.app.state.config
    servers: dict[str, Any] = {}

    for name, srv in config.mcp.servers.items():
        if not srv.enabled or not getattr(srv, "export_claude", False):
            continue
        if srv.transport in ("http", "streamable_http", "sse") and srv.url:
            entry: dict[str, Any] = {"type": "http", "url": srv.url}
            if srv.headers:
                entry["headers"] = {
                    k: (f"${{{v[5:-1]}}}" if v.startswith("{env:") and v.endswith("}") else v)
                    for k, v in srv.headers.items()
                }
        else:
            entry = {"command": srv.command, "args": srv.args}
            if srv.env:
                entry["env"] = {k: f"${{{k}}}" for k in srv.env}
        servers[name] = entry

    payload = {"mcpServers": servers}
    import json as _json
    return {
        "json": _json.dumps(payload, indent=2),
        "server_count": len(servers),
        "note": "Add to claude_desktop_config.json, or run `claude mcp add-json <name> '<entry>'` for Claude Code.",
    }


# ---------------------------------------------------------------------------
# MCP Marketplace — official registry + curated presets
# ---------------------------------------------------------------------------

_MCP_REGISTRY_BASE = "https://registry.modelcontextprotocol.io"

# Curated, ready-to-use presets for the most popular MCP servers. Each maps to
# an MCPServerCreate-compatible payload the UI can install with one click.
_MCP_PRESETS: list[dict[str, Any]] = [
    {
        "id": "filesystem", "name": "Filesystem", "category": "Files",
        "description": "Read/write local files in allowed directories.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home"],
        "env": {},
    },
    {
        "id": "github", "name": "GitHub", "category": "Dev",
        "description": "Manage repos, issues, PRs and code search.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
    },
    {
        "id": "brave-search", "name": "Brave Search", "category": "Web",
        "description": "Web and local search via the Brave Search API.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": ""},
    },
    {
        "id": "puppeteer", "name": "Puppeteer", "category": "Web",
        "description": "Browse and scrape the web with a headless browser.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"], "env": {},
    },
    {
        "id": "postgres", "name": "PostgreSQL", "category": "Data",
        "description": "Read-only SQL queries against a Postgres database.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres",
                 "postgresql://localhost/mydb"], "env": {},
    },
    {
        "id": "memory", "name": "Memory (Knowledge Graph)", "category": "Productivity",
        "description": "Persistent knowledge-graph memory across sessions.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"], "env": {},
    },
    {
        "id": "slack", "name": "Slack", "category": "Productivity",
        "description": "Read and post messages in Slack channels.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env": {"SLACK_BOT_TOKEN": "", "SLACK_TEAM_ID": ""},
    },
    {
        "id": "sequential-thinking", "name": "Sequential Thinking",
        "category": "Reasoning",
        "description": "Step-by-step structured reasoning tool.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "env": {},
    },
]


@router.get("/mcp/presets")
async def mcp_presets() -> list[dict[str, Any]]:
    """Return the curated list of ready-to-install MCP server presets."""
    return _MCP_PRESETS


@router.get("/mcp/registry/search")
async def mcp_registry_search(q: str = "", limit: int = 30) -> dict[str, Any]:
    """Search the official MCP registry. Proxies registry.modelcontextprotocol.io."""
    import aiohttp

    params: dict[str, Any] = {"limit": min(limit, 100)}
    if q:
        params["search"] = q
    try:
        async with aiohttp.ClientSession() as session, session.get(
            f"{_MCP_REGISTRY_BASE}/v0/servers",
            params=params,
            timeout=aiohttp.ClientTimeout(total=12),
        ) as r:
            if r.status != 200:
                return {"servers": [], "error": f"registry returned {r.status}"}
            data = await r.json()
    except Exception as e:
        return {"servers": [], "error": str(e)}

    # The registry wraps each entry as {"server": {...}, "_meta": {...}} and may
    # return several versions of the same server — keep the latest of each name.
    results: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for entry in data.get("servers", []):
        srv = entry.get("server", entry) if isinstance(entry, dict) else {}
        meta = (entry.get("_meta") or {}).get(
            "io.modelcontextprotocol.registry/official", {}
        )
        name = srv.get("name", "")
        if not name:
            continue
        # Skip superseded versions when the registry tells us which is latest.
        if meta.get("isLatest") is False and name in seen:
            continue

        pkgs = srv.get("packages", []) or []
        remotes = srv.get("remotes", []) or []
        record = {
            "name": name,
            "description": srv.get("description", "") or srv.get("title", ""),
            "version": srv.get("version", ""),
            "packages": [
                {
                    "registry_type": p.get("registryType", p.get("registry_type", "")),
                    "identifier": p.get("identifier", ""),
                    "version": p.get("version", ""),
                }
                for p in pkgs
            ],
            "remotes": [
                {
                    "type": rm.get("type", ""),
                    "url": rm.get("url", ""),
                }
                for rm in remotes
            ],
        }
        if name in seen:
            results[seen[name]] = record
        else:
            seen[name] = len(results)
            results.append(record)

    return {"servers": results, "count": len(results)}
