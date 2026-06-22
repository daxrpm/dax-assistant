"""LLM router — local-first fallback across decoupled providers.

Holds an ordered list of providers (the first is the default) and tries them in
turn. The default gets one retry before falling back. Implements the
LLMProvider port so the orchestrator only ever sees a single provider.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from dax.core.exceptions import LLMError, LLMProviderUnavailableError

if TYPE_CHECKING:
    from dax.core.models import Message
    from dax.core.ports import LLMProvider

logger = logging.getLogger(__name__)


class LLMRouter:
    """Routes completion requests across an ordered list of providers."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("LLMRouter requires at least one provider")
        self._providers = providers

    def set_providers(self, providers: list[LLMProvider]) -> None:
        """Swap the provider list in place (e.g. after a config change).

        Mutates this router so existing holders (the agent) pick up the new
        providers without being re-wired.
        """
        if not providers:
            raise ValueError("LLMRouter requires at least one provider")
        self._providers = providers
        logger.info("LLM router updated: %s", ", ".join(p.name for p in providers))

    @property
    def name(self) -> str:
        return self._providers[0].name

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Message:
        last_error: Exception | None = None
        for index, provider in enumerate(self._providers):
            # The default provider gets one retry; fallbacks get a single try.
            attempts = 2 if index == 0 else 1
            for attempt in range(attempts):
                try:
                    return await provider.complete(
                        messages, tools, temperature=temperature, max_tokens=max_tokens
                    )
                except LLMError as e:
                    last_error = e
                    logger.warning(
                        "Provider '%s' failed (attempt %d/%d): %s",
                        provider.name, attempt + 1, attempts, e,
                    )
        raise LLMProviderUnavailableError(
            f"All LLM providers failed ({', '.join(self.provider_names)})"
        ) from last_error

    async def is_available(self) -> bool:
        for provider in self._providers:
            try:
                if await provider.is_available():
                    return True
            except Exception:
                continue
        return False
