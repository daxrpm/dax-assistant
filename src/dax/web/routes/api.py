"""REST API routes — status, configuration, MCP management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["api"])


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


class LLMConfigUpdate(BaseModel):
    default_provider: str | None = None
    fallback_order: list[str] | None = None
    ollama_model: str | None = None
    ollama_base_url: str | None = None
    ollama_timeout: int | None = None
    anthropic_model: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    gemini_model: str | None = None
    gemini_api_key: str | None = None


class VoiceConfigUpdate(BaseModel):
    enabled: bool | None = None
    wake_word_threshold: float | None = None
    stt_model: str | None = None
    stt_compute_type: str | None = None
    stt_language: str | None = None
    tts_voice_es: str | None = None
    tts_voice_en: str | None = None
    vad_threshold: float | None = None
    silence_duration_ms: int | None = None


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
    session_ttl_hours: int | None = None
    cookie_secure: bool | None = None


class MCPServerCreate(BaseModel):
    name: str
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


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
        },
        "voice": {
            "enabled": config.voice.enabled,
            "wake_word_threshold": config.voice.wake_word_threshold,
            "stt_model": config.voice.stt_model,
            "stt_compute_type": config.voice.stt_compute_type,
            "stt_language": config.voice.stt_language,
            "tts_voice_es": config.voice.tts_voice_es,
            "tts_voice_en": config.voice.tts_voice_en,
            "vad_threshold": config.voice.vad_threshold,
            "silence_duration_ms": config.voice.silence_duration_ms,
        },
        "llm": {
            "default_provider": config.llm.default_provider,
            "fallback_order": config.llm.fallback_order,
            "ollama_model": config.llm.ollama.model,
            "ollama_base_url": config.llm.ollama.base_url,
            "ollama_timeout": config.llm.ollama.timeout,
            "anthropic_model": config.llm.anthropic.model,
            "anthropic_configured": bool(config.llm.anthropic.api_key),
            "openai_model": config.llm.openai.model,
            "openai_base_url": config.llm.openai.base_url,
            "openai_configured": bool(config.llm.openai.api_key),
            "gemini_model": config.llm.gemini.model,
            "gemini_configured": bool(config.llm.gemini.api_key),
        },
        "web": {
            "host": config.web.host,
            "port": config.web.port,
            "cors_origins": config.web.cors_origins,
        },
        "whatsapp": {
            "enabled": config.whatsapp.enabled,
            "evolution_api_url": config.whatsapp.evolution_api_url,
            "evolution_api_instance": config.whatsapp.evolution_api_instance,
            "respond_with_audio": config.whatsapp.respond_with_audio,
            "has_api_key": bool(config.whatsapp.evolution_api_key),
        },
        "security": {
            "auth_enabled": config.security.auth_enabled,
            "configured": bool(config.security.password_hash),
            "session_ttl_hours": config.security.session_ttl_hours,
            "cookie_secure": config.security.cookie_secure,
        },
        "tools": {
            "confirm_timeout_seconds": config.tools.confirm_timeout_seconds,
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
                    "enabled": srv.enabled,
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
        "ollama_model": ("llm.ollama", "model"),
        "ollama_base_url": ("llm.ollama", "base_url"),
        "ollama_timeout": ("llm.ollama", "timeout"),
        "anthropic_model": ("llm.anthropic", "model"),
        "anthropic_api_key": ("llm.anthropic", "api_key"),
        "openai_model": ("llm.openai", "model"),
        "openai_base_url": ("llm.openai", "base_url"),
        "openai_api_key": ("llm.openai", "api_key"),
        "gemini_model": ("llm.gemini", "model"),
        "gemini_api_key": ("llm.gemini", "api_key"),
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

    for key, value in updates.items():
        if hasattr(config.whatsapp, key):
            object.__setattr__(config.whatsapp, key, value)

    _save_config_to_toml(request)
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
    """Update non-secret security settings (TTL, secure cookie)."""
    config = request.app.state.config
    updates = body.model_dump(exclude_none=True)

    for key, value in updates.items():
        if hasattr(config.security, key):
            object.__setattr__(config.security, key, value)

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


# --- Config persistence ---


def _save_config_to_toml(request: Request) -> None:
    """Write the current config state back to the TOML file.

    Reconstructs the TOML structure from the in-memory config
    and writes it to the config file path.
    """
    config = request.app.state.config
    config_path = getattr(
        request.app.state, "config_path", Path("config/dax.toml"),
    )

    lines: list[str] = []

    # [general]
    lines.append("[general]")
    lines.append(f'name = "{config.name}"')
    lines.append(f'language_default = "{config.language_default}"')
    lines.append(f'log_level = "{config.log_level}"')
    lines.append("")

    # [voice]
    lines.append("[voice]")
    lines.append(f"enabled = {_toml_bool(config.voice.enabled)}")
    lines.append(
        f"wake_word_threshold = {config.voice.wake_word_threshold}"
    )
    lines.append(f'stt_model = "{config.voice.stt_model}"')
    lines.append(f'stt_compute_type = "{config.voice.stt_compute_type}"')
    lines.append(f'stt_language = "{config.voice.stt_language}"')
    lines.append(f'tts_voice_es = "{config.voice.tts_voice_es}"')
    lines.append(f'tts_voice_en = "{config.voice.tts_voice_en}"')
    lines.append(f"vad_threshold = {config.voice.vad_threshold}")
    lines.append(
        f"silence_duration_ms = {config.voice.silence_duration_ms}"
    )
    lines.append("")

    # [llm]
    lines.append("[llm]")
    lines.append(f'default_provider = "{config.llm.default_provider}"')
    fallback = ", ".join(f'"{p}"' for p in config.llm.fallback_order)
    lines.append(f"fallback_order = [{fallback}]")
    lines.append("")
    lines.append("[llm.ollama]")
    lines.append(f'base_url = "{config.llm.ollama.base_url}"')
    lines.append(f'model = "{config.llm.ollama.model}"')
    lines.append(f"timeout = {config.llm.ollama.timeout}")
    lines.append("")
    lines.append("[llm.anthropic]")
    lines.append(f'model = "{config.llm.anthropic.model}"')
    if config.llm.anthropic.api_key:
        lines.append(f'api_key = "{config.llm.anthropic.api_key}"')
    lines.append("")
    lines.append("[llm.openai]")
    lines.append(f'model = "{config.llm.openai.model}"')
    if config.llm.openai.base_url:
        lines.append(f'base_url = "{config.llm.openai.base_url}"')
    if config.llm.openai.api_key:
        lines.append(f'api_key = "{config.llm.openai.api_key}"')
    lines.append("")
    lines.append("[llm.gemini]")
    lines.append(f'model = "{config.llm.gemini.model}"')
    if config.llm.gemini.api_key:
        lines.append(f'api_key = "{config.llm.gemini.api_key}"')
    lines.append("")

    # [web]
    lines.append("[web]")
    lines.append(f'host = "{config.web.host}"')
    lines.append(f"port = {config.web.port}")
    origins = ", ".join(f'"{o}"' for o in config.web.cors_origins)
    lines.append(f"cors_origins = [{origins}]")
    lines.append("")

    # [whatsapp]
    lines.append("[whatsapp]")
    lines.append(
        f"enabled = {_toml_bool(config.whatsapp.enabled)}"
    )
    lines.append(
        f'evolution_api_url = "{config.whatsapp.evolution_api_url}"'
    )
    lines.append(
        f'evolution_api_instance = '
        f'"{config.whatsapp.evolution_api_instance}"'
    )
    lines.append(
        f"respond_with_audio = "
        f"{_toml_bool(config.whatsapp.respond_with_audio)}"
    )
    lines.append("")

    # [security] — secrets (password_hash, session_secret) stay in env only.
    lines.append("[security]")
    lines.append(f"auth_enabled = {_toml_bool(config.security.auth_enabled)}")
    lines.append(f"session_ttl_hours = {config.security.session_ttl_hours}")
    lines.append(f"cookie_secure = {_toml_bool(config.security.cookie_secure)}")
    lines.append("")

    # [tools] + [tools.policy]
    lines.append("[tools]")
    lines.append(
        f"confirm_timeout_seconds = {config.tools.confirm_timeout_seconds}"
    )
    lines.append("")
    lines.append("[tools.policy]")
    lines.append(f'default = "{config.tools.policy.default}"')
    allow = ", ".join(f'"{p}"' for p in config.tools.policy.allow)
    ask = ", ".join(f'"{p}"' for p in config.tools.policy.ask)
    deny = ", ".join(f'"{p}"' for p in config.tools.policy.deny)
    lines.append(f"allow = [{allow}]")
    lines.append(f"ask = [{ask}]")
    lines.append(f"deny = [{deny}]")
    lines.append("")

    # [storage]
    lines.append("[storage]")
    lines.append(f'database_path = "{config.storage.database_path}"')
    lines.append(f'models_path = "{config.storage.models_path}"')
    lines.append("")

    # [mcp.servers.*]
    for name, srv in config.mcp.servers.items():
        lines.append(f"[mcp.servers.{name}]")
        lines.append(f'command = "{srv.command}"')
        args_str = ", ".join(f'"{a}"' for a in srv.args)
        lines.append(f"args = [{args_str}]")
        if srv.env:
            env_pairs = ", ".join(
                f'{k} = "{v}"' for k, v in srv.env.items()
            )
            lines.append(f"env = {{ {env_pairs} }}")
        lines.append(f'transport = "{srv.transport}"')
        if srv.url:
            lines.append(f'url = "{srv.url}"')
        lines.append(
            f"enabled = {_toml_bool(srv.enabled)}"
        )
        lines.append("")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(lines))


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"
