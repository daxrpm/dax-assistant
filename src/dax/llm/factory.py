"""Build the LLM router and providers from configuration.

This is the single place that knows how to turn config into concrete provider
adapters, keeping the rest of the app decoupled from any specific SDK.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dax.llm.providers import AnthropicProvider, GeminiProvider, OpenAIProvider
from dax.llm.router import LLMRouter

if TYPE_CHECKING:
    from dax.core.config import LLMConfig
    from dax.core.ports import LLMProvider

logger = logging.getLogger(__name__)


def _ollama_base_url(base_url: str) -> str:
    """Ollama's OpenAI-compatible API lives under /v1."""
    base = base_url.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def build_provider(name: str, config: LLMConfig) -> LLMProvider | None:
    """Construct a single provider by name, or None if unknown/unbuildable."""
    try:
        if name == "ollama":
            return OpenAIProvider(
                name="ollama",
                model=config.ollama.model,
                base_url=_ollama_base_url(config.ollama.base_url),
                timeout=config.ollama.timeout,
            )
        if name == "openai":
            return OpenAIProvider(
                name="openai",
                model=config.openai.model,
                api_key=config.openai.api_key,
                base_url=config.openai.base_url,
                timeout=config.openai.timeout,
            )
        if name == "anthropic":
            return AnthropicProvider(
                name="anthropic",
                model=config.anthropic.model,
                api_key=config.anthropic.api_key,
                timeout=config.anthropic.timeout,
            )
        if name == "gemini":
            return GeminiProvider(
                name="gemini",
                model=config.gemini.model,
                api_key=config.gemini.api_key,
                timeout=config.gemini.timeout,
            )
    except Exception:
        logger.exception("Failed to build LLM provider '%s'", name)
        return None

    logger.warning("Unknown LLM provider '%s' — skipping", name)
    return None


def build_router(config: LLMConfig) -> LLMRouter:
    """Build an LLMRouter: default provider first, then the fallback chain."""
    order: list[str] = [config.default_provider]
    for name in config.fallback_order:
        if name not in order:
            order.append(name)

    providers: list[LLMProvider] = []
    for name in order:
        provider = build_provider(name, config)
        if provider is not None:
            providers.append(provider)

    if not providers:
        # Last resort: a local Ollama provider so the app still starts.
        logger.warning("No LLM providers configured — defaulting to local Ollama")
        providers.append(build_provider("ollama", config))  # type: ignore[arg-type]

    logger.info("LLM router ready: %s", ", ".join(p.name for p in providers))
    return LLMRouter(providers)
