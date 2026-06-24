"""OpenAI provider adapter — official `openai` SDK (Chat Completions).

Also serves any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio, OpenRouter,
…) by setting ``base_url``. This is how the local AI layer stays decoupled: the
default Ollama provider is just this adapter pointed at ``localhost:11434/v1``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from dax.core.exceptions import LLMError, LLMTimeoutError
from dax.core.models import Message, MessageRole, ToolCall

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """Implements the LLMProvider port over the OpenAI Chat Completions API."""

    def __init__(
        self,
        *,
        name: str,
        model: str,
        api_key: str = "",
        base_url: str = "",
        timeout: int = 60,
        reasoning_effort: str = "",
    ) -> None:
        self._name = name
        self._model = model
        self._reasoning_effort = reasoning_effort
        # base_url set => an OpenAI-compatible endpoint (e.g. Ollama). When
        # talking to a local endpoint a key isn't needed, but the SDK requires
        # a non-empty value, so fall back to a placeholder.
        self._is_compatible = bool(base_url)
        client_kwargs: dict[str, Any] = {"timeout": timeout}
        if base_url:
            client_kwargs["base_url"] = base_url
            client_kwargs["api_key"] = api_key or "not-needed"
        elif api_key:
            client_kwargs["api_key"] = api_key
        self._client = AsyncOpenAI(**client_kwargs)

    @property
    def name(self) -> str:
        return self._name

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Message:
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        # Compatible endpoints (Ollama et al.) use the classic params; OpenAI's
        # newer reasoning models restrict temperature and use
        # max_completion_tokens, so only send sampling params downstream.
        if self._is_compatible:
            kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
        else:
            if max_tokens is not None:
                kwargs["max_completion_tokens"] = max_tokens
            # Lower reasoning effort = faster responses on gpt-5.x. BUT OpenAI
            # rejects reasoning_effort alongside function tools on
            # /v1/chat/completions, so only send it for tool-less turns.
            if self._reasoning_effort and not tools:
                kwargs["reasoning_effort"] = self._reasoning_effort

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            if "timeout" in str(e).lower():
                raise LLMTimeoutError(f"{self._name} timed out: {e}") from e
            raise LLMError(f"{self._name} error: {e}") from e

        return self._parse(response)

    async def is_available(self) -> bool:
        try:
            await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False

    def _parse(self, response: Any) -> Message:
        choice = response.choices[0]
        msg = choice.message
        content = msg.content or ""

        tool_calls: tuple[ToolCall, ...] = ()
        if getattr(msg, "tool_calls", None):
            parsed: list[ToolCall] = []
            for tc in msg.tool_calls:
                raw = tc.function.arguments
                try:
                    args = json.loads(raw) if isinstance(raw, str) else (raw or {})
                except json.JSONDecodeError:
                    args = {}
                parsed.append(
                    ToolCall(
                        id=tc.id or "",
                        server_name="",  # resolved by the agent via the registry
                        tool_name=tc.function.name or "",
                        arguments=args,
                    )
                )
            tool_calls = tuple(parsed)

        return Message(role=MessageRole.ASSISTANT, content=content, tool_calls=tool_calls)
