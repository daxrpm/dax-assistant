"""Build the LLM router and providers from configuration.

This is the single place that knows how to turn config into concrete provider
adapters, keeping the rest of the app decoupled from any specific SDK.
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

from dax.llm.providers import AnthropicProvider, GeminiProvider, OpenAIProvider
from dax.llm.router import LLMRouter

if TYPE_CHECKING:
    from dax.core.config import LLMConfig
    from dax.core.ports import LLMProvider

logger = logging.getLogger(__name__)

_ENV_REF = re.compile(r"^\{env:([^}]+)\}$")


def _resolve_env(value: str) -> str:
    """Resolve a ``{env:VAR}`` reference to its environment value.

    API keys are stored in TOML as ``{env:OPENAI_API_KEY}`` (the secret itself
    lives in .env). Provider SDKs need the real value, so resolve it here. A
    plain value is returned unchanged; an unset env var resolves to "" so the
    SDK can fall back to its own env lookup.
    """
    if not value:
        return value
    match = _ENV_REF.match(value.strip())
    if match:
        return os.environ.get(match.group(1), "")
    return value


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
                api_key=_resolve_env(config.openai.api_key),
                base_url=_resolve_env(config.openai.base_url),
                timeout=config.openai.timeout,
                reasoning_effort=config.openai.reasoning_effort,
            )
        if name == "codex":
            from dax.llm.providers.codex_provider import CodexProvider

            return CodexProvider(
                name="codex",
                binary=config.codex.binary,
                model=config.codex.model,
                timeout=config.codex.timeout,
            )
        if name == "anthropic":
            return AnthropicProvider(
                name="anthropic",
                model=config.anthropic.model,
                api_key=_resolve_env(config.anthropic.api_key),
                timeout=config.anthropic.timeout,
            )
        if name == "gemini":
            return GeminiProvider(
                name="gemini",
                model=config.gemini.model,
                api_key=_resolve_env(config.gemini.api_key),
                timeout=config.gemini.timeout,
            )
    except Exception as e:
        # A missing API key is an expected, recoverable condition (e.g. a cloud
        # provider listed in the fallback chain without a key) — log it plainly
        # instead of dumping a traceback, and skip the provider.
        logger.warning("Skipping LLM provider '%s': %s", name, e)
        return None

    logger.warning("Unknown LLM provider '%s' — skipping", name)
    return None


def build_providers(config: LLMConfig) -> list[LLMProvider]:
    """Build the ordered provider list: default first, then the fallback chain.

    Providers that can't be built (e.g. a cloud provider with no API key) are
    skipped. Always returns at least one provider so the router stays usable.
    """
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
        ollama = build_provider("ollama", config)
        if ollama is not None:
            providers.append(ollama)

    return providers


def build_router(config: LLMConfig) -> LLMRouter:
    """Build an LLMRouter from configuration."""
    providers = build_providers(config)
    logger.info("LLM router ready: %s", ", ".join(p.name for p in providers))
    return LLMRouter(providers)
