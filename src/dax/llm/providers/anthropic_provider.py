"""Anthropic (Claude) provider adapter — official `anthropic` SDK.

Translates the OpenAI chat format used internally into Anthropic's Messages API
shape (system prompt extracted, tool_use / tool_result blocks) and back into a
domain ``Message``. Defaults to Claude Opus 4.8 with adaptive thinking.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from dax.core.exceptions import LLMError, LLMTimeoutError
from dax.core.models import Message, MessageRole, ToolCall

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider:
    """Implements the LLMProvider port over the Anthropic Messages API."""

    def __init__(
        self,
        *,
        name: str = "anthropic",
        model: str = "claude-opus-4-8",
        api_key: str = "",
        timeout: int = 60,
    ) -> None:
        self._name = name
        self._model = model
        kwargs: dict[str, Any] = {"timeout": timeout}
        if api_key:
            kwargs["api_key"] = api_key  # else SDK reads ANTHROPIC_API_KEY
        self._client = AsyncAnthropic(**kwargs)

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
        system, anthropic_messages = self._translate_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens or _DEFAULT_MAX_TOKENS,
            "messages": anthropic_messages,
            "thinking": {"type": "adaptive"},
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._translate_tools(tools)

        try:
            response = await self._client.messages.create(**kwargs)
        except Exception as e:
            if "timeout" in str(e).lower():
                raise LLMTimeoutError(f"{self._name} timed out: {e}") from e
            raise LLMError(f"{self._name} error: {e}") from e

        return self._parse(response)

    async def is_available(self) -> bool:
        try:
            await self._client.messages.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False

    # -- translation --

    @staticmethod
    def _translate_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for t in tools:
            fn = t.get("function", t)
            out.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters")
                    or {"type": "object", "properties": {}},
                }
            )
        return out

    @staticmethod
    def _translate_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        out: list[dict[str, Any]] = []

        for m in messages:
            role = m.get("role")
            if role == "system":
                if m.get("content"):
                    system_parts.append(str(m["content"]))
                continue

            if role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.get("tool_call_id", ""),
                                "content": str(m.get("content", "")),
                            }
                        ],
                    }
                )
                continue

            if role == "assistant" and m.get("tool_calls"):
                blocks: list[dict[str, Any]] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": str(m["content"])})
                for tc in m["tool_calls"]:
                    fn = tc["function"]
                    raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(raw) if isinstance(raw, str) else (raw or {})
                    except json.JSONDecodeError:
                        args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": fn.get("name", ""),
                            "input": args,
                        }
                    )
                out.append({"role": "assistant", "content": blocks})
                continue

            # Plain user/assistant text turn.
            out.append({"role": role, "content": str(m.get("content", "") or "")})

        return "\n\n".join(system_parts), out

    def _parse(self, response: Any) -> Message:
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                content_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        server_name="",
                        tool_name=block.name,
                        arguments=dict(block.input or {}),
                    )
                )
        return Message(
            role=MessageRole.ASSISTANT,
            content="".join(content_parts),
            tool_calls=tuple(tool_calls),
        )
