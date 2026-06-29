"""Tests for the orchestrator agent with LLM + tool calling."""

from __future__ import annotations

import asyncio
from typing import Any

from dax.core.models import (
    ChannelType,
    Conversation,
    Language,
    Message,
    MessageRole,
    ToolCall,
    ToolResult,
)
from dax.orchestrator.agent import Agent
from dax.orchestrator.bus import MessageBus


class _MockLLM:
    """Mock LLM that returns configurable responses."""

    def __init__(self, responses: list[Message] | None = None) -> None:
        self._responses = list(responses) if responses else []
        self._call_count = 0
        self.last_messages: list[dict[str, Any]] = []
        self.last_tools: list[dict[str, Any]] | None = None

    @property
    def name(self) -> str:
        return "mock"

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Message:
        self.last_messages = messages
        self.last_tools = tools
        if self._responses:
            response = self._responses[min(self._call_count, len(self._responses) - 1)]
        else:
            response = Message(
                role=MessageRole.ASSISTANT,
                content="Mock response",
            )
        self._call_count += 1
        return response

    async def is_available(self) -> bool:
        return True


class _MockTools:
    """Mock tool provider that returns configurable results."""

    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        results: dict[str, ToolResult] | None = None,
    ) -> None:
        self._tools = tools or []
        self._results = results or {}
        self.executed_calls: list[ToolCall] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def list_tools(self) -> list[dict[str, Any]]:
        return self._tools

    def get_relevant_tools(
        self, query: str, max_tools: int
    ) -> list[dict[str, Any]]:
        return self._tools[:max_tools]

    def get_server_for_tool(self, tool_name: str) -> str | None:
        return next(
            (t.get("server_name") for t in self._tools if t.get("name") == tool_name),
            None,
        )

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        self.executed_calls.append(tool_call)
        if tool_call.tool_name in self._results:
            return self._results[tool_call.tool_name]
        return ToolResult(call_id=tool_call.id, content="OK")


class _MockStorage:
    def __init__(self) -> None:
        self.saved: list[Conversation] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def save_conversation(self, conversation: Conversation) -> None:
        self.saved.append(conversation)

    async def get_conversation(self, conversation_id: str) -> None:
        return None

    async def get_or_create_conversation(
        self, channel: ChannelType, session_key: str
    ) -> Conversation:
        return Conversation(channel=channel, session_key=session_key)

    async def get_recent_conversations(
        self, channel: str, limit: int = 5
    ) -> list[object]:
        return []


class TestAgentSimpleResponse:
    async def test_text_response_no_tools(self):
        """Agent returns LLM text response when no tools are called."""
        bus = MessageBus()
        bus.start()

        llm = _MockLLM(responses=[
            Message(role=MessageRole.ASSISTANT, content="Hello! I'm Dax."),
        ])

        agent = Agent(
            bus=bus,
            llm=llm,  # type: ignore[arg-type]
            tools=_MockTools(),  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
        )
        await agent.start()

        await bus.publish_inbound(
            Message(content="Hello", channel=ChannelType.WEB, language=Language.ENGLISH)
        )

        response = await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert response.role == MessageRole.ASSISTANT
        assert response.content == "Hello! I'm Dax."
        assert response.channel == ChannelType.WEB
        assert response.language == Language.ENGLISH

        await agent.stop()

    async def test_preserves_channel_and_language(self):
        bus = MessageBus()
        bus.start()

        llm = _MockLLM(responses=[
            Message(role=MessageRole.ASSISTANT, content="Hola!"),
        ])

        agent = Agent(
            bus=bus,
            llm=llm,  # type: ignore[arg-type]
            tools=_MockTools(),  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
        )
        await agent.start()

        await bus.publish_inbound(
            Message(content="Hola", channel=ChannelType.WHATSAPP, language=Language.SPANISH)
        )

        response = await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert response.channel == ChannelType.WHATSAPP
        assert response.language == Language.SPANISH

        await agent.stop()


class TestAgentToolCalling:
    async def test_single_tool_call(self):
        """Agent executes a tool call and returns the final response."""
        bus = MessageBus()
        bus.start()

        # LLM first returns a tool call, then the final answer
        llm = _MockLLM(responses=[
            Message(
                role=MessageRole.ASSISTANT,
                content="",
                tool_calls=(
                    ToolCall(
                        id="call_1",
                        server_name="shell",
                        tool_name="execute",
                        arguments={"command": "date"},
                    ),
                ),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="The current date is March 19, 2026.",
            ),
        ])

        mock_tools = _MockTools(
            results={"execute": ToolResult(call_id="call_1", content="Thu Mar 19 2026")}
        )

        agent = Agent(
            bus=bus,
            llm=llm,  # type: ignore[arg-type]
            tools=mock_tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
        )
        await agent.start()

        await bus.publish_inbound(Message(content="What's the date?"))

        response = await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert response.content == "The current date is March 19, 2026."
        assert len(mock_tools.executed_calls) == 1
        assert mock_tools.executed_calls[0].tool_name == "execute"

        await agent.stop()

    async def test_tool_error_returns_error_to_llm(self):
        """When a tool fails, the error is fed back to the LLM."""
        bus = MessageBus()
        bus.start()

        llm = _MockLLM(responses=[
            Message(
                role=MessageRole.ASSISTANT,
                content="",
                tool_calls=(
                    ToolCall(
                        id="call_1",
                        server_name="shell",
                        tool_name="bad_tool",
                        arguments={},
                    ),
                ),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="Sorry, that tool failed.",
            ),
        ])

        mock_tools = _MockTools(
            results={
                "bad_tool": ToolResult(
                    call_id="call_1",
                    content="Permission denied",
                    is_error=True,
                ),
            }
        )

        agent = Agent(
            bus=bus,
            llm=llm,  # type: ignore[arg-type]
            tools=mock_tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
        )
        await agent.start()

        await bus.publish_inbound(Message(content="Do bad thing"))

        response = await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert response.content == "Sorry, that tool failed."

        await agent.stop()


class _StatefulStorage:
    """In-memory storage that actually resumes conversations by session key."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], Conversation] = {}

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def get_or_create_conversation(
        self, channel: ChannelType, session_key: str
    ) -> Conversation:
        return self._by_key.get(
            (channel.value, session_key),
            Conversation(channel=channel, session_key=session_key),
        )

    async def save_conversation(self, conversation: Conversation) -> None:
        self._by_key[(conversation.channel.value, conversation.session_key)] = conversation

    async def get_conversation(self, conversation_id: str) -> None:
        return None

    async def get_recent_conversations(self, channel: str, limit: int = 5) -> list[object]:
        return []


class TestAgentMemory:
    async def test_remembers_previous_turn(self):
        bus = MessageBus()
        bus.start()
        storage = _StatefulStorage()
        llm = _MockLLM(responses=[
            Message(role=MessageRole.ASSISTANT, content="Nice to meet you, Dax."),
            Message(role=MessageRole.ASSISTANT, content="Your name is Dax."),
        ])
        agent = Agent(
            bus=bus,
            llm=llm,  # type: ignore[arg-type]
            tools=_MockTools(),  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
        )
        await agent.start()

        await bus.publish_inbound(Message(content="My name is Dax", channel=ChannelType.WEB))
        await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)

        await bus.publish_inbound(Message(content="What is my name?", channel=ChannelType.WEB))
        await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)

        # On the 2nd turn the LLM must have received the prior turns as history.
        contents = [m.get("content") for m in llm.last_messages]
        assert "My name is Dax" in contents
        assert "Nice to meet you, Dax." in contents

        await agent.stop()


def _tool_then_text(tool_name: str) -> _MockLLM:
    return _MockLLM(responses=[
        Message(
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=(
                ToolCall(id="c1", server_name="dax-system", tool_name=tool_name, arguments={}),
            ),
        ),
        Message(role=MessageRole.ASSISTANT, content="all done"),
    ])


class TestAgentPolicyGate:
    async def test_denied_tool_not_executed(self):
        from dax.core.policy import Decision, ToolPolicy

        bus = MessageBus()
        bus.start()
        tools = _MockTools()
        agent = Agent(
            bus=bus,
            llm=_tool_then_text("fs_write"),  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
            policy=ToolPolicy(default=Decision.ALLOW, deny=["fs_write"]),
        )
        await agent.start()
        await bus.publish_inbound(Message(content="write a file"))
        resp = await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert resp.content == "all done"
        assert tools.executed_calls == []  # blocked by policy
        await agent.stop()

    async def test_ask_approved_runs(self):
        from dax.core.policy import ToolPolicy
        from dax.orchestrator.approval import ApprovalManager

        bus = MessageBus()
        bus.start()
        approval = ApprovalManager(timeout_seconds=5)

        async def auto_approve(payload: dict[str, Any]) -> None:
            approval.resolve(payload["approval_id"], "approve")

        approval.set_notifier(auto_approve)
        tools = _MockTools()
        agent = Agent(
            bus=bus,
            llm=_tool_then_text("fs_write"),  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
            policy=ToolPolicy(ask=["fs_write"]),
            approval=approval,
        )
        await agent.start()
        await bus.publish_inbound(Message(content="write a file"))
        await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert len(tools.executed_calls) == 1
        await agent.stop()

    async def test_ask_denied_blocks(self):
        from dax.core.policy import ToolPolicy
        from dax.orchestrator.approval import ApprovalManager

        bus = MessageBus()
        bus.start()
        approval = ApprovalManager(timeout_seconds=5)

        async def auto_deny(payload: dict[str, Any]) -> None:
            approval.resolve(payload["approval_id"], "deny")

        approval.set_notifier(auto_deny)
        tools = _MockTools()
        agent = Agent(
            bus=bus,
            llm=_tool_then_text("fs_write"),  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
            policy=ToolPolicy(ask=["fs_write"]),
            approval=approval,
        )
        await agent.start()
        await bus.publish_inbound(Message(content="write a file"))
        await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert tools.executed_calls == []  # user declined
        await agent.stop()


def _shell_then_text(command: str) -> _MockLLM:
    return _MockLLM(responses=[
        Message(
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=(
                ToolCall(
                    id="c1",
                    server_name="dax-system",
                    tool_name="shell_run",
                    arguments={"command": command},
                ),
            ),
        ),
        Message(role=MessageRole.ASSISTANT, content="all done"),
    ])


class TestAgentShellGate:
    async def test_allowlisted_runs_without_asking(self):
        from dax.core.policy import ToolPolicy
        from dax.core.shell_allow import ShellAllowlist
        from dax.orchestrator.approval import ApprovalManager

        bus = MessageBus()
        bus.start()
        approval = ApprovalManager(timeout_seconds=5)
        asked = False

        async def notifier(payload: dict[str, Any]) -> None:
            nonlocal asked
            asked = True
            approval.resolve(payload["approval_id"], "deny")

        approval.set_notifier(notifier)
        tools = _MockTools()
        agent = Agent(
            bus=bus,
            llm=_shell_then_text("git status"),  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
            policy=ToolPolicy(),
            approval=approval,
            shell_allow=ShellAllowlist(["git"]),
        )
        await agent.start()
        await bus.publish_inbound(Message(content="run git"))
        await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert asked is False  # never prompted
        assert len(tools.executed_calls) == 1
        await agent.stop()

    async def test_unknown_approve_once_runs_without_saving(self):
        from dax.core.policy import ToolPolicy
        from dax.core.shell_allow import ShellAllowlist
        from dax.orchestrator.approval import ApprovalManager

        bus = MessageBus()
        bus.start()
        approval = ApprovalManager(timeout_seconds=5)

        async def notifier(payload: dict[str, Any]) -> None:
            assert payload["options"] == ["once", "save"]
            approval.resolve(payload["approval_id"], "once")

        approval.set_notifier(notifier)
        tools = _MockTools()
        allow = ShellAllowlist(["git"])
        agent = Agent(
            bus=bus,
            llm=_shell_then_text("flatpak run spotify"),  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
            policy=ToolPolicy(),
            approval=approval,
            shell_allow=allow,
        )
        await agent.start()
        await bus.publish_inbound(Message(content="open spotify"))
        await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert len(tools.executed_calls) == 1
        assert "flatpak" not in allow.items()  # ran but not remembered
        await agent.stop()

    async def test_unknown_approve_save_persists(self):
        from dax.core.policy import ToolPolicy
        from dax.core.shell_allow import ShellAllowlist
        from dax.orchestrator.approval import ApprovalManager

        bus = MessageBus()
        bus.start()
        approval = ApprovalManager(timeout_seconds=5)
        saved: list[str] = []

        async def notifier(payload: dict[str, Any]) -> None:
            approval.resolve(payload["approval_id"], "save")

        approval.set_notifier(notifier)
        tools = _MockTools()
        allow = ShellAllowlist(["git"], on_change=lambda cmds: saved.append(cmds[-1]))
        agent = Agent(
            bus=bus,
            llm=_shell_then_text("flatpak run spotify"),  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
            policy=ToolPolicy(),
            approval=approval,
            shell_allow=allow,
        )
        await agent.start()
        await bus.publish_inbound(Message(content="open spotify"))
        await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert len(tools.executed_calls) == 1
        assert "flatpak" in allow.items()  # remembered
        assert saved == ["flatpak"]  # persistence hook fired
        await agent.stop()

    async def test_unknown_denied_blocks(self):
        from dax.core.policy import ToolPolicy
        from dax.core.shell_allow import ShellAllowlist
        from dax.orchestrator.approval import ApprovalManager

        bus = MessageBus()
        bus.start()
        approval = ApprovalManager(timeout_seconds=5)

        async def notifier(payload: dict[str, Any]) -> None:
            approval.resolve(payload["approval_id"], "deny")

        approval.set_notifier(notifier)
        tools = _MockTools()
        allow = ShellAllowlist(["git"])
        agent = Agent(
            bus=bus,
            llm=_shell_then_text("rm -rf /"),  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
            policy=ToolPolicy(),
            approval=approval,
            shell_allow=allow,
        )
        await agent.start()
        await bus.publish_inbound(Message(content="delete everything"))
        await asyncio.wait_for(bus.consume_outbound(), timeout=2.0)
        assert tools.executed_calls == []  # blocked
        assert "rm" not in allow.items()
        await agent.stop()


class TestAgentStartStop:
    async def test_start_and_stop_cleanly(self):
        bus = MessageBus()
        bus.start()

        agent = Agent(
            bus=bus,
            llm=_MockLLM(),  # type: ignore[arg-type]
            tools=_MockTools(),  # type: ignore[arg-type]
            storage=_MockStorage(),  # type: ignore[arg-type]
        )
        await agent.start()
        await agent.stop()
