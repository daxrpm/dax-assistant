"""Google Gemini provider adapter — official `google-genai` SDK.

Translates the OpenAI chat format into Gemini ``Content``/``Part`` objects and
function declarations, and parses function calls back into domain ``ToolCall``s.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from google import genai
from google.genai import types

from dax.core.exceptions import LLMError, LLMTimeoutError
from dax.core.models import Message, MessageRole, ToolCall

logger = logging.getLogger(__name__)


class GeminiProvider:
    """Implements the LLMProvider port over the Gemini generateContent API."""

    def __init__(
        self,
        *,
        name: str = "gemini",
        model: str = "gemini-3.5-flash",
        api_key: str = "",
        timeout: int = 60,
    ) -> None:
        self._name = name
        self._model = model
        # api_key blank => SDK reads GEMINI_API_KEY / GOOGLE_API_KEY.
        self._client = genai.Client(api_key=api_key) if api_key else genai.Client()

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
        system, contents = self._translate_messages(messages)
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if system:
            config_kwargs["system_instruction"] = system
        if max_tokens is not None:
            config_kwargs["max_output_tokens"] = max_tokens
        if tools:
            config_kwargs["tools"] = self._translate_tools(tools)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as e:
            if "timeout" in str(e).lower() or "deadline" in str(e).lower():
                raise LLMTimeoutError(f"{self._name} timed out: {e}") from e
            raise LLMError(f"{self._name} error: {e}") from e

        return self._parse(response)

    async def is_available(self) -> bool:
        try:
            await self._client.aio.models.generate_content(
                model=self._model,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=1),
            )
            return True
        except Exception:
            return False

    # -- translation --

    @staticmethod
    def _translate_tools(tools: list[dict[str, Any]]) -> list[types.Tool]:
        declarations: list[types.FunctionDeclaration] = []
        for t in tools:
            fn = t.get("function", t)
            declarations.append(
                types.FunctionDeclaration(
                    name=fn.get("name", ""),
                    description=fn.get("description", ""),
                    parameters=fn.get("parameters") or {"type": "object", "properties": {}},
                )
            )
        return [types.Tool(function_declarations=declarations)]

    @staticmethod
    def _translate_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[str, list[types.Content]]:
        system_parts: list[str] = []
        contents: list[types.Content] = []
        # Map tool_call_id -> function name so tool results can be paired.
        call_names: dict[str, str] = {}

        for m in messages:
            role = m.get("role")
            if role == "system":
                if m.get("content"):
                    system_parts.append(str(m["content"]))
                continue

            if role == "tool":
                call_id = m.get("tool_call_id", "")
                fn_name = call_names.get(call_id, call_id)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=fn_name,
                                response={"result": str(m.get("content", ""))},
                            )
                        ],
                    )
                )
                continue

            if role == "assistant" and m.get("tool_calls"):
                parts: list[types.Part] = []
                if m.get("content"):
                    parts.append(types.Part(text=str(m["content"])))
                for tc in m["tool_calls"]:
                    fn = tc["function"]
                    raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(raw) if isinstance(raw, str) else (raw or {})
                    except json.JSONDecodeError:
                        args = {}
                    call_names[tc.get("id", "")] = fn.get("name", "")
                    parts.append(
                        types.Part.from_function_call(name=fn.get("name", ""), args=args)
                    )
                contents.append(types.Content(role="model", parts=parts))
                continue

            gemini_role = "model" if role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part(text=str(m.get("content", "") or ""))],
                )
            )

        return "\n\n".join(system_parts), contents

    def _parse(self, response: Any) -> Message:
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            parts = getattr(getattr(cand, "content", None), "parts", None) or []
            for part in parts:
                if getattr(part, "text", None):
                    content_parts.append(part.text)
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    tool_calls.append(
                        ToolCall(
                            id=getattr(fc, "id", None) or uuid.uuid4().hex,
                            server_name="",
                            tool_name=fc.name or "",
                            arguments=dict(fc.args or {}),
                        )
                    )

        return Message(
            role=MessageRole.ASSISTANT,
            content="".join(content_parts),
            tool_calls=tuple(tool_calls),
        )
