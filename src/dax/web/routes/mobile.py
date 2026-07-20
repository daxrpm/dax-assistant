"""Restricted configuration surface for enrolled mobile devices."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from dax.storage.devices import CAPABILITY_NODE_KIND
from dax.web.dependencies import AuthDep, ConfigDep, SecretStoreDep, persist_config
from dax.web.routes.config import (
    LLMConfigUpdate,
    VoiceConfigUpdate,
    VoiceNonSecretConfigUpdate,
    update_llm,
    update_voice,
)

router = APIRouter(prefix="/mobile/config", tags=["mobile"])


class MobileLLMConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_provider: str | None = None
    fallback_order: list[str] | None = None
    max_tools: int | None = None
    max_tool_iterations: int | None = None
    ollama_model: str | None = None
    anthropic_model: str | None = None
    openai_model: str | None = None
    gemini_model: str | None = None
    deepseek_model: str | None = None
    codex_model: str | None = None


class MobileVoiceConfigUpdate(VoiceNonSecretConfigUpdate):
    model_config = ConfigDict(extra="forbid")


class MobileNodesConfigUpdate(BaseModel):
    """The phone's share of node control.

    Only the two switches. Choosing which laptop does what stays behind a
    session, because ``devices.py`` deliberately refuses to let one enrolled
    device enumerate its siblings, and a per-node policy editor would need
    exactly that enumeration.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    prefer_when_available: bool | None = None


async def _node_summary(request: Request, config: ConfigDep, auth: AuthDep) -> dict[str, Any]:
    """Whether a node is up for this phone, without naming the fleet."""
    hub = getattr(request.app.state, "capability_hub", None)
    devices = auth.devices
    name: str | None = None
    available = 0
    if hub is not None and devices is not None:
        for device in await devices.list_devices():
            if device.kind != CAPABILITY_NODE_KIND or not hub.is_present(device.id):
                continue
            available += 1
            if name is None and config.nodes.hosts_sessions(device.id):
                name = device.name
    return {
        "enabled": config.nodes.enabled,
        "prefer_when_available": config.nodes.prefer_when_available,
        "available": available > 0,
        # Present only when that node may actually host a session, so the phone
        # never offers a laptop that would refuse the work.
        "name": name,
    }


@router.get("")
async def get_mobile_config(
    request: Request, config: ConfigDep, auth: AuthDep
) -> dict[str, Any]:
    """Return mobile-relevant settings, representing secrets only as flags."""
    return {
        "nodes": await _node_summary(request, config, auth),
        "general": {
            "name": config.name,
            "language_default": config.language_default,
            "log_level": config.log_level,
        },
        "llm": {
            "default_provider": config.llm.default_provider,
            "fallback_order": config.llm.fallback_order,
            "max_tools": config.llm.max_tools,
            "max_tool_iterations": config.llm.max_tool_iterations,
            "ollama_model": config.llm.ollama.model,
            "anthropic_model": config.llm.anthropic.model,
            "anthropic_configured": bool(config.llm.anthropic.api_key),
            "openai_model": config.llm.openai.model,
            "openai_configured": bool(config.llm.openai.api_key),
            "gemini_model": config.llm.gemini.model,
            "gemini_configured": bool(config.llm.gemini.api_key),
            "deepseek_model": config.llm.deepseek.model,
            "deepseek_configured": bool(config.llm.deepseek.api_key),
            "codex_model": config.llm.codex.model,
        },
        "voice": {
            **config.voice.model_dump(),
            "stt_openai_configured": bool(config.llm.openai.api_key),
            "tts_openai_configured": bool(config.llm.openai.api_key),
        },
    }


@router.patch("/llm")
async def update_mobile_llm(
    request: Request, body: MobileLLMConfigUpdate, config: ConfigDep
) -> dict[str, str]:
    """Apply the safe subset through the canonical live LLM updater."""
    return await update_llm(request, LLMConfigUpdate(**body.model_dump()), config)


@router.patch("/voice")
async def update_mobile_voice(
    request: Request,
    body: MobileVoiceConfigUpdate,
    config: ConfigDep,
    store: SecretStoreDep,
) -> dict[str, str]:
    """Apply non-secret voice settings through the canonical live updater."""
    return await update_voice(request, VoiceConfigUpdate(**body.model_dump()), config, store)


@router.patch("/nodes")
async def update_mobile_nodes(
    request: Request, body: MobileNodesConfigUpdate, config: ConfigDep
) -> dict[str, str]:
    """Flip the fleet switches from the phone."""
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        object.__setattr__(config.nodes, key, value)
    persist_config(request)
    if updates.get("enabled") is False:
        hub = getattr(request.app.state, "capability_hub", None)
        disconnect_all = getattr(hub, "disconnect_all", None)
        if disconnect_all is not None:
            await disconnect_all()
    return {"status": "ok"}
