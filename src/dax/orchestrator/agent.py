"""Core agent loop — the brain of Dax Assistant.

Receives messages from the bus, sends them to the LLM with available tools,
executes any tool calls via MCP, and publishes responses back to the bus.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from dax.core.exceptions import LLMError, ToolError
from dax.core.models import ChannelType, Message, MessageRole, ToolCall, ToolResult
from dax.core.policy import Decision
from dax.core.shell_allow import shell_binary
from dax.llm.client import SYSTEM_PROMPT, build_messages_for_llm
from dax.llm.tool_mapper import mcp_tools_to_openai

if TYPE_CHECKING:
    from dax.core.models import Conversation
    from dax.core.policy import ToolPolicy
    from dax.core.ports import LLMProvider, Storage, ToolProvider
    from dax.core.shell_allow import ShellAllowlist
    from dax.mcp.registry import ToolRegistry
    from dax.orchestrator.approval import ApprovalManager
    from dax.orchestrator.bus import MessageBus

# The dax-system tool that runs shell commands — gated by the shell allowlist
# rather than the generic name-pattern policy.
_SHELL_TOOL_NAME = "shell_run"

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5

# Appended to the system prompt for voice turns: the reply is read aloud by TTS,
# so it must be plain spoken language — no markdown the synthesizer would dictate.
VOICE_STYLE_PROMPT = """

## Voice reply style (this turn is spoken aloud)
Your answer will be read by a text-to-speech voice. Reply in plain, natural \
spoken Spanish/English:
- NO markdown whatsoever — no asterisks, **bold**, _italics_, `code`, #headings, \
bullet lists, tables or emoji. They get dictated literally and sound terrible.
- Be brief and conversational, like a smart speaker. One or two short sentences \
when possible; for lists, say them as a natural sentence ("tienes tres eventos: …").
- Spell things out the way you'd say them, not write them."""

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


def _build_system_prompt(available_tools: list[dict[str, Any]]) -> str:
    """Append a concrete live tool inventory to the base system prompt.

    Grouping by server_name and listing tool names makes it unambiguous to
    the model which tools exist right now — preventing hallucinated "I don't
    have access" responses when tools are actually registered.
    """
    if not available_tools:
        return SYSTEM_PROMPT

    # Group by server
    by_server: dict[str, list[str]] = {}
    for tool in available_tools:
        server = tool.get("server_name", "unknown")
        by_server.setdefault(server, []).append(tool["name"])

    lines = ["\n\n## Active tools — available right now in this session"]
    for server, names in sorted(by_server.items()):
        tool_list = ", ".join(sorted(names))
        lines.append(f"- **{server}** ({len(names)} tools): {tool_list}")
    lines.append(
        "\nUse these tools directly. Do NOT say you lack access — "
        "if a tool is listed above you can call it."
    )

    return SYSTEM_PROMPT + "\n".join(lines)
# How many prior messages to feed back as conversation context.
MAX_HISTORY_MESSAGES = 20


class Agent:
    """The orchestrator agent that processes user messages.

    Implements the core loop:
    1. Receive message from inbound queue
    2. Build conversation context
    3. Select relevant tools for the query
    4. Call LLM with tools
    5. If LLM requests tool calls, execute them and loop back
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
        # Long-term memory: user-curated facts in <memory_path>/*.md, injected
        # into the system prompt so the assistant actually "remembers" them.
        self._memory_path = memory_path
        # When no policy/approval is wired, tools run unrestricted (used in
        # tests). In the app both are provided so destructive actions are gated.
        self._policy = policy
        self._approval = approval
        # Authoritative allowlist for the dax-system shell tool. The agent runs
        # allowlisted binaries without asking and prompts for the rest.
        self._shell_allow = shell_allow
        # Cap on tool schemas sent per LLM request — keeps prompts small and
        # responses fast. The relevance filter picks the best within this.
        self._max_tools = max_tools
        self._task: asyncio.Task[None] | None = None
        self._event_broadcaster: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None

    def _memory_block(self) -> str:
        """Read user-curated memory files and format them for the system prompt.

        Each ``<memory_path>/*.md`` file (except the MEMORY.md index) is a single
        fact with optional frontmatter (name/description/type). We surface the
        title and body so the model can use them — this is what makes the
        memories saved in the UI actually take effect in conversations.
        """
        if not self._memory_path:
            return ""
        from pathlib import Path

        mem_dir = Path(self._memory_path).expanduser()
        if not mem_dir.is_dir():
            return ""

        facts: list[str] = []
        for path in sorted(mem_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            name = path.stem.replace("-", " ")
            body = text
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    body = parts[2].strip()
                    for line in parts[1].splitlines():
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip() or name
            body = body.strip()
            if body:
                facts.append(f"- **{name}**: {body}")

        if not facts:
            return ""
        return (
            "\n\n## What you remember about the user\n"
            "These are durable facts the user saved. Treat them as true and "
            "apply them without asking again:\n" + "\n".join(facts)
        )

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

        # Gather tools BEFORE building messages so the system prompt can
        # include a concrete inventory of what is available right now.
        available_tools = await self._tools.list_tools()
        registry = self._get_registry()

        relevant: list[dict[str, Any]] = []
        openai_tools: list[dict[str, Any]] | None = None
        if available_tools:
            if registry:
                relevant = registry.get_relevant_tools(
                    _relevance_query(message.content, history),
                    max_tools=self._max_tools,
                )
            else:
                relevant = available_tools[: self._max_tools]
            openai_tools = mcp_tools_to_openai(relevant) or None

        # Build conversation context with a dynamic inventory injected into
        # the system prompt. List only the tools actually passed this turn so
        # the prompt stays small (listing all ~150 tools is slow and pointless).
        system_prompt = _build_system_prompt(relevant or available_tools)
        system_prompt += self._memory_block()
        if message.channel == ChannelType.VOICE:
            system_prompt += VOICE_STYLE_PROMPT
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
        _start_ts = time.monotonic()

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

            # If no tool calls, we have our final answer
            if not response.tool_calls:
                elapsed = round(time.monotonic() - _start_ts, 1)
                await self._emit({"type": "done", "elapsed_s": elapsed})
                return await self._finalize(
                    conversation,
                    Message(
                        role=MessageRole.ASSISTANT,
                        content=response.content,
                        channel=message.channel,
                        language=message.language,
                        metadata=dict(message.metadata),
                    ),
                )

            # Execute tool calls and feed results back to LLM
            logger.info(
                "LLM requested %d tool call(s) on iteration %d",
                len(response.tool_calls),
                iteration,
            )

            # Add assistant message with tool calls to context
            llm_messages.append(self._format_assistant_tool_calls(response))

            # Execute each tool call, emitting events so the UI can show activity
            for tool_call in response.tool_calls:
                await self._emit({
                    "type": "tool_call",
                    "tool": tool_call.tool_name,
                    "server": tool_call.server_name or "",
                    "args": dict(tool_call.arguments),
                })
                result = await self._execute_tool_safe(tool_call, registry)
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

        # If we exhausted iterations, return whatever we have
        logger.warning("Max tool iterations (%d) reached", MAX_TOOL_ITERATIONS)
        elapsed = round(time.monotonic() - _start_ts, 1)
        await self._emit({"type": "done", "elapsed_s": elapsed})
        return await self._finalize(
            conversation,
            Message(
                role=MessageRole.ASSISTANT,
                content=response.content or "I completed the requested actions.",
                channel=message.channel,
                language=message.language,
                metadata=dict(message.metadata),
            ),
        )

    async def _finalize(self, conversation: Conversation, assistant: Message) -> Message:
        """Append the assistant turn, persist the conversation, and return it."""
        conversation.add_message(assistant)
        try:
            await self._storage.save_conversation(conversation)
        except Exception:
            logger.exception("Failed to persist conversation %s", conversation.id)
        return assistant

    async def _execute_tool_safe(
        self,
        tool_call: ToolCall,
        registry: ToolRegistry | None,
    ) -> ToolResult:
        """Execute a tool call, applying the policy + confirmation gate."""
        # Resolve server name from registry
        resolved_call = tool_call
        if registry and (not tool_call.server_name or tool_call.server_name == ""):
            server = registry.get_server_for_tool(tool_call.tool_name)
            if server:
                resolved_call = ToolCall(
                    id=tool_call.id,
                    server_name=server,
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                )

        # Policy + human-in-the-loop confirmation gate.
        gate = await self._gate(resolved_call)
        if gate is not None:
            return gate

        try:
            result = await self._tools.execute(resolved_call)
            logger.info(
                "Tool '%s' executed (error=%s): %.100s",
                resolved_call.tool_name,
                result.is_error,
                result.content,
            )
            await self._audit(resolved_call, "error" if result.is_error else "executed")
            return result
        except ToolError as e:
            logger.warning("Tool execution failed: %s", e)
            await self._audit(resolved_call, "error")
            return ToolResult(
                call_id=tool_call.id,
                content=f"Error: {e}",
                is_error=True,
            )

    async def _gate(self, call: ToolCall) -> ToolResult | None:
        """Apply the policy. Returns a blocking ToolResult, or None to proceed."""
        if self._policy is None:
            return None
        decision = self._policy.decide(call.tool_name)
        if decision is Decision.DENY:
            logger.warning("Tool '%s' denied by policy", call.tool_name)
            await self._audit(call, "denied")
            return ToolResult(
                call_id=call.id,
                content=f"Error: tool '{call.tool_name}' is not permitted.",
                is_error=True,
            )
        # The shell tool is gated by the user-managed binary allowlist, not the
        # name-pattern policy: known binaries run freely, unknown ones prompt.
        if call.tool_name == _SHELL_TOOL_NAME and self._shell_allow is not None:
            return await self._gate_shell(call)
        if decision is Decision.ALLOW:
            return None
        # ASK — require confirmation.
        if self._approval is None:
            await self._audit(call, "denied")
            return ToolResult(
                call_id=call.id,
                content=(
                    f"Error: '{call.tool_name}' requires confirmation but no "
                    "approval channel is available."
                ),
                is_error=True,
            )
        result = await self._approval.request(
            tool_name=call.tool_name,
            server_name=call.server_name,
            arguments=dict(call.arguments),
        )
        approved = result != "deny"
        await self._audit(call, "approved" if approved else "declined")
        if not approved:
            return ToolResult(
                call_id=call.id,
                content=f"Error: the user declined to run '{call.tool_name}'.",
                is_error=True,
            )
        return None

    async def _gate_shell(self, call: ToolCall) -> ToolResult | None:
        """Gate a shell_run call against the user-managed command allowlist.

        Allowlisted binaries run with no prompt. Unknown ones ask the user, who
        can *approve once* (run, don't remember) or *approve & save* (run and add
        the binary to the allowlist permanently). Denials block the call.
        """
        assert self._shell_allow is not None
        command = str(call.arguments.get("command", ""))
        binary = shell_binary(command)

        if self._shell_allow.is_allowed(binary):
            await self._audit(call, "executed")
            return None

        if self._approval is None:
            await self._audit(call, "denied")
            return ToolResult(
                call_id=call.id,
                content=(
                    f"Error: command '{binary or command}' is not in the shell "
                    "allowlist and no approval channel is available to ask."
                ),
                is_error=True,
            )

        decision = await self._approval.request(
            tool_name=call.tool_name,
            server_name=call.server_name,
            arguments=dict(call.arguments),
            options=["once", "save"],
        )
        if decision == "deny":
            await self._audit(call, "declined")
            return ToolResult(
                call_id=call.id,
                content=f"Error: the user declined to run '{binary or command}'.",
                is_error=True,
            )
        if decision == "save" and binary:
            self._shell_allow.add(binary)
            logger.info("Added '%s' to the shell allowlist", binary)
        await self._audit(call, "approved")
        return None

    async def _audit(self, call: ToolCall, status: str) -> None:
        """Record a tool execution decision to the audit log, if supported."""
        logger_fn = getattr(self._storage, "log_tool_execution", None)
        if logger_fn is None:
            return
        try:
            await logger_fn(
                server_name=call.server_name,
                tool_name=call.tool_name,
                arguments=dict(call.arguments),
                status=status,
            )
        except Exception:
            logger.exception("Failed to write tool audit log")

    def _get_registry(self) -> ToolRegistry | None:
        """Get the tool registry if the tool provider is an MCPManager."""
        if hasattr(self._tools, "registry"):
            return self._tools.registry  # type: ignore[union-attr]
        return None

    def _format_assistant_tool_calls(self, response: Message) -> dict[str, Any]:
        """Format an assistant message with tool calls for the LLM context."""
        import json

        tool_calls_formatted = []
        for tc in response.tool_calls:
            tool_calls_formatted.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.tool_name,
                    "arguments": json.dumps(tc.arguments, default=str),
                },
            })

        msg: dict[str, Any] = {
            "role": "assistant",
            "content": response.content or None,
            "tool_calls": tool_calls_formatted,
        }
        return msg
