"""Tests for the multi-provider LLM layer: adapters, router and factory."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from dax.core.config import LLMConfig
from dax.core.exceptions import LLMError, LLMProviderUnavailableError
from dax.core.models import Message, MessageRole
from dax.llm.factory import build_provider, build_router
from dax.llm.providers import AnthropicProvider, GeminiProvider, OpenAIProvider
from dax.llm.router import LLMRouter

# A conversation in OpenAI chat format with a full tool round-trip.
SAMPLE_MESSAGES = [
    {"role": "system", "content": "You are Dax."},
    {"role": "user", "content": "list my files"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "fs_list", "arguments": '{"path": "/home"}'},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": "a.txt\nb.txt"},
]

SAMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fs_list",
            "description": "List files",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
        },
    }
]


class TestOpenAIProvider:
    def test_parse_text(self):
        p = OpenAIProvider(name="openai", model="gpt-5.5", api_key="x")
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi", tool_calls=None))]
        )
        msg = p._parse(resp)
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "hi"
        assert msg.tool_calls == ()

    def test_parse_tool_calls(self):
        p = OpenAIProvider(name="openai", model="gpt-5.5", api_key="x")
        tc = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="fs_list", arguments='{"path": "/home"}'),
        )
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tc]))]
        )
        msg = p._parse(resp)
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].tool_name == "fs_list"
        assert msg.tool_calls[0].arguments == {"path": "/home"}

    def test_ollama_uses_compatible_params(self):
        p = OpenAIProvider(name="ollama", model="llama3.1", base_url="http://x/v1")
        assert p._is_compatible is True


class TestAnthropicProvider:
    def test_translate_messages(self):
        p = AnthropicProvider(api_key="x")
        system, msgs = p._translate_messages(SAMPLE_MESSAGES)
        assert system == "You are Dax."
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"][0]["type"] == "tool_use"
        assert msgs[1]["content"][0]["name"] == "fs_list"
        assert msgs[2]["content"][0]["type"] == "tool_result"
        assert msgs[2]["content"][0]["tool_use_id"] == "call_1"

    def test_translate_tools(self):
        p = AnthropicProvider(api_key="x")
        tools = p._translate_tools(SAMPLE_TOOLS)
        assert tools[0]["name"] == "fs_list"
        assert "input_schema" in tools[0]

    def test_parse(self):
        p = AnthropicProvider(api_key="x")
        resp = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="done"),
                SimpleNamespace(type="tool_use", id="tu1", name="fs_list", input={"path": "/"}),
            ]
        )
        msg = p._parse(resp)
        assert msg.content == "done"
        assert msg.tool_calls[0].tool_name == "fs_list"
        assert msg.tool_calls[0].arguments == {"path": "/"}


class TestGeminiProvider:
    def test_translate_messages(self):
        p = GeminiProvider(api_key="x")
        system, contents = p._translate_messages(SAMPLE_MESSAGES)
        assert system == "You are Dax."
        assert contents[0].role == "user"
        assert contents[1].role == "model"  # assistant -> model
        assert contents[-1].role == "user"  # function response

    def test_translate_tools(self):
        p = GeminiProvider(api_key="x")
        tools = p._translate_tools(SAMPLE_TOOLS)
        assert tools[0].function_declarations[0].name == "fs_list"

    def test_parse(self):
        p = GeminiProvider(api_key="x")
        fc = SimpleNamespace(name="fs_list", args={"path": "/"})
        part_text = SimpleNamespace(text="ok", function_call=None)
        part_fc = SimpleNamespace(text=None, function_call=fc)
        cand = SimpleNamespace(content=SimpleNamespace(parts=[part_text, part_fc]))
        resp = SimpleNamespace(candidates=[cand])
        msg = p._parse(resp)
        assert msg.content == "ok"
        assert msg.tool_calls[0].tool_name == "fs_list"
        assert msg.tool_calls[0].arguments == {"path": "/"}


class _FakeProvider:
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self._name = name
        self._fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def complete(self, messages: Any, tools: Any = None, **kwargs: Any) -> Message:
        self.calls += 1
        if self._fail:
            raise LLMError(f"{self._name} boom")
        return Message(role=MessageRole.ASSISTANT, content=f"from {self._name}")

    async def is_available(self) -> bool:
        return not self._fail


class TestLLMRouter:
    async def test_uses_primary(self):
        primary = _FakeProvider("primary")
        router = LLMRouter([primary, _FakeProvider("fallback")])
        msg = await router.complete([{"role": "user", "content": "hi"}])
        assert msg.content == "from primary"
        assert router.name == "primary"

    async def test_falls_back(self):
        primary = _FakeProvider("primary", fail=True)
        fallback = _FakeProvider("fallback")
        router = LLMRouter([primary, fallback])
        msg = await router.complete([{"role": "user", "content": "hi"}])
        assert msg.content == "from fallback"
        assert primary.calls == 2  # retried once before falling back
        assert fallback.calls == 1

    async def test_all_fail_raises(self):
        router = LLMRouter([_FakeProvider("a", fail=True), _FakeProvider("b", fail=True)])
        with pytest.raises(LLMProviderUnavailableError):
            await router.complete([{"role": "user", "content": "hi"}])

    def test_requires_a_provider(self):
        with pytest.raises(ValueError, match="at least one"):
            LLMRouter([])


class TestFactory:
    def test_build_ollama_provider(self):
        provider = build_provider("ollama", LLMConfig())
        assert provider is not None
        assert provider.name == "ollama"

    def test_unknown_provider_returns_none(self):
        assert build_provider("does-not-exist", LLMConfig()) is None

    def test_router_order_default_then_fallback(self):
        cfg = LLMConfig(
            default_provider="ollama",
            fallback_order=["gemini"],
            gemini={"api_key": "x"},
        )
        router = build_router(cfg)
        assert router.provider_names[0] == "ollama"
        assert "gemini" in router.provider_names

    def test_unconfigured_fallback_is_skipped(self):
        # Gemini in the fallback chain with no API key must be skipped cleanly
        # (no crash, no traceback), leaving a working router.
        cfg = LLMConfig(default_provider="ollama", fallback_order=["gemini"])
        router = build_router(cfg)
        assert router.provider_names == ["ollama"]
