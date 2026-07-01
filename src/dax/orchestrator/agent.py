"""Core agent loop — the brain of Dax Assistant.

Receives messages from the bus, sends them to the LLM with available tools,
executes any tool calls via the tool gate, and publishes responses back.

The agent stays focused on orchestration; two collaborators own the cross-cutting
concerns it used to carry inline:
- :class:`~dax.orchestrator.tool_gate.ToolGate` — policy, confirmation, audit,
  and the actual tool execution.
- :class:`~dax.orchestrator.prompting.SystemPromptBuilder` — system-prompt
  assembly (tool inventory, user memory, voice style).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from dax.core.exceptions import LLMError
from dax.core.models import Message, MessageRole
from dax.llm.client import build_messages_for_llm
from dax.llm.tool_mapper import mcp_tools_to_openai
from dax.orchestrator.prompting import SystemPromptBuilder
from dax.orchestrator.tool_gate import ToolGate

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Sequence

    from dax.core.models import Conversation, ToolCall
    from dax.core.policy import ToolPolicy
    from dax.core.ports import LLMProvider, Storage, ToolProvider
    from dax.core.shell_allow import ShellAllowlist
    from dax.orchestrator.approval import ApprovalManager
    from dax.orchestrator.bus import MessageBus

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5

# How many prior messages to feed back as conversation context.
MAX_HISTORY_MESSAGES = 20

# How many recent user turns to fold into the tool-relevance query so that
# follow-ups ("ponla", "play it") still surface the right server's tools even
# when the latest message names no keywords.
_RELEVANCE_CONTEXT_TURNS = 3


def _relevance_query(content: str, history: list[Message]) -> str:
    """Build the query used to pick relevant tools, with recent context.

    The relevance filter scores tools against this string. Using only the
    latest message means a context-free follow-up (e.g. "ponla") loses the
    server it referred to a turn ago (e.g. Spotify) and its tools drop out of
    the budget. Prepending the last few user turns keeps that intent in scope.
    """
    recent = [
        m.content
        for m in history
        if m.role is MessageRole.USER and m.content
    ][-_RELEVANCE_CONTEXT_TURNS:]
    return " ".join([*recent, content])


class Agent:
    """The orchestrator agent that processes user messages.

    Implements the core loop:
    1. Receive message from inbound queue
    2. Build conversation context
    3. Select relevant tools for the query
    4. Call LLM with tools
    5. If LLM requests tool calls, execute them (via the gate) and loop back
    6. Publish final text response to outbound queue
    """

    def __init__(
        self,
        bus: MessageBus,
        llm: LLMProvider,
        tools: ToolProvider,
        storage: Storage,
        policy: ToolPolicy | None = None,
        approval: ApprovalManager | None = None,
        shell_allow: ShellAllowlist | None = None,
        max_tools: int = 45,
        memory_path: str | None = None,
    ) -> None:
        self._bus = bus
        self._llm = llm
        self._tools = tools
        self._storage = storage
        # Cap on tool schemas sent per LLM request — keeps prompts small and
        # responses fast. The relevance filter picks the best within this.
        self._max_tools = max_tools
        # Collaborators: prompt assembly and the policy/confirmation/exec gate.
        self._prompt = SystemPromptBuilder(memory_path)
        self._gate = ToolGate(
            tools,
            policy=policy,
            approval=approval,
            shell_allow=shell_allow,
            storage=storage,
        )
        self._task: asyncio.Task[None] | None = None
        self._event_broadcaster: (
            Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None
        ) = None

    def set_event_broadcaster(
        self,
        broadcaster: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Wire a callback that receives real-time agent events (tool calls, etc.)."""
        self._event_broadcaster = broadcaster

    async def _emit(self, event: dict[str, Any]) -> None:
        """Fire an agent event to the broadcaster, silently ignoring errors."""
        if self._event_broadcaster is not None:
            with contextlib.suppress(Exception):
                await self._event_broadcaster(event)

    async def start(self) -> None:
        """Begin the agent processing loop."""
        self._task = asyncio.create_task(self._process_loop(), name="agent")
        logger.info("Agent started")

    async def stop(self) -> None:
        """Cancel the agent loop."""
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Agent stopped")

    async def _process_loop(self) -> None:
        """Main loop: consume inbound, process, publish outbound."""
        while True:
            message = await self._bus.consume_inbound()
            try:
                response = await self._handle_message(message)
                await self._bus.publish_outbound(response)
            except Exception:
                logger.exception("Failed to process message: %.50s", message.content)
                error_response = Message(
                    role=MessageRole.ASSISTANT,
                    content="I'm sorry, something went wrong processing your request.",
                    channel=message.channel,
                    language=message.language,
                )
                await self._bus.publish_outbound(error_response)

    @staticmethod
    def _session_key(message: Message) -> str:
        """Stable per-session key so conversations resume correctly.

        WhatsApp groups by sender; web/voice use a single rolling session
        (this is a single-user assistant). An explicit ``session_id`` in the
        message metadata always wins.
        """
        explicit = message.metadata.get("session_id")
        if isinstance(explicit, str) and explicit:
            return explicit
        sender = message.metadata.get("sender_jid")
        if isinstance(sender, str) and sender:
            return sender
        return message.channel.value

    async def _handle_message(self, message: Message) -> Message:
        """Process a single user message through the LLM + tool pipeline."""
        logger.info(
            "Processing message from %s: %.80s",
            message.channel,
            message.content,
        )

        # Load (or start) the conversation for this session and feed recent
        # history back to the model so it has memory across turns.
        session_key = self._session_key(message)
        conversation = await self._storage.get_or_create_conversation(
            message.channel, session_key
        )
        history = conversation.messages[-MAX_HISTORY_MESSAGES:]

        # Record the user turn in the conversation we'll persist below.
        conversation.add_message(message)

        # Gather + select tools BEFORE building messages so the system prompt
        # can list a concrete inventory of what is available right now. List
        # only the tools actually passed this turn (listing all ~150 is slow).
        available_tools = await self._tools.list_tools()
        relevant: list[dict[str, Any]] = []
        openai_tools: list[dict[str, Any]] | None = None
        if available_tools:
            relevant = self._tools.get_relevant_tools(
                _relevance_query(message.content, history),
                max_tools=self._max_tools,
            )
            openai_tools = mcp_tools_to_openai(relevant) or None

        system_prompt = self._prompt.build(
            relevant or available_tools, channel=message.channel
        )
        llm_messages = build_messages_for_llm(
            message, conversation_history=history, system_prompt=system_prompt
        )

        logger.debug(
            "Passing %d tools to LLM for query '%.60s': %s",
            len(relevant),
            message.content,
            [t["name"] for t in relevant[:15]],
        )

        await self._emit({"type": "thinking"})
        start_ts = time.monotonic()

        # LLM call + tool execution loop
        for iteration in range(MAX_TOOL_ITERATIONS):
            try:
                response = await self._llm.complete(
                    messages=llm_messages,
                    tools=openai_tools,
                )
            except LLMError:
                logger.exception("LLM call failed on iteration %d", iteration)
                raise

            # If no tool calls, we have our final answer.
            if not response.tool_calls:
                await self._emit_done(start_ts)
                return await self._finalize(
                    conversation, self._assistant_reply(message, response.content)
                )

            logger.info(
                "LLM requested %d tool call(s) on iteration %d",
                len(response.tool_calls),
                iteration,
            )
            llm_messages.append(self._format_assistant_tool_calls(response))
            await self._run_tool_calls(
                response.tool_calls, llm_messages, channel=message.channel.value
            )

        # If we exhausted iterations, return whatever we have.
        logger.warning("Max tool iterations (%d) reached", MAX_TOOL_ITERATIONS)
        await self._emit_done(start_ts)
        return await self._finalize(
            conversation,
            self._assistant_reply(
                message, response.content or "I completed the requested actions."
            ),
        )

    async def _run_tool_calls(
        self,
        tool_calls: Sequence[ToolCall],
        llm_messages: list[dict[str, Any]],
        *,
        channel: str | None = None,
    ) -> None:
        """Execute each tool call via the gate, emitting UI events + feeding
        results back into the LLM message list."""
        for tool_call in tool_calls:
            await self._emit({
                "type": "tool_call",
                "tool": tool_call.tool_name,
                "server": tool_call.server_name or "",
                "args": dict(tool_call.arguments),
            })
            result = await self._gate.execute(tool_call, channel=channel)
            await self._emit({
                "type": "tool_result",
                "tool": tool_call.tool_name,
                "preview": result.content[:300] if result.content else "",
                "error": result.is_error,
            })
            llm_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result.content,
            })

    def _assistant_reply(self, source: Message, content: str) -> Message:
        """Build an assistant Message mirroring the source's channel/metadata."""
        return Message(
            role=MessageRole.ASSISTANT,
            content=content,
            channel=source.channel,
            language=source.language,
            metadata=dict(source.metadata),
        )

    async def _emit_done(self, start_ts: float) -> None:
        await self._emit({"type": "done", "elapsed_s": round(time.monotonic() - start_ts, 1)})

    async def _finalize(self, conversation: Conversation, assistant: Message) -> Message:
        """Append the assistant turn, persist the conversation, and return it."""
        conversation.add_message(assistant)
        try:
            await self._storage.save_conversation(conversation)
        except Exception:
            logger.exception("Failed to persist conversation %s", conversation.id)
        return assistant

    def _format_assistant_tool_calls(self, response: Message) -> dict[str, Any]:
        """Format an assistant message with tool calls for the LLM context."""
        tool_calls_formatted = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.tool_name,
                    "arguments": json.dumps(tc.arguments, default=str),
                },
            }
            for tc in response.tool_calls
        ]
        return {
            "role": "assistant",
            "content": response.content or None,
            "tool_calls": tool_calls_formatted,
        }
