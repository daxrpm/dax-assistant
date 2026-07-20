"""Restricted configuration surface for enrolled mobile devices."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from dax.web.dependencies import ConfigDep, SecretStoreDep
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


@router.get("")
async def get_mobile_config(config: ConfigDep) -> dict[str, Any]:
    """Return mobile-relevant settings, representing secrets only as flags."""
    return {
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
