"""Protocol interfaces (ports) for the hexagonal architecture.

All adapters implement these protocols. The orchestrator depends ONLY
on these — never on concrete implementations. This enables swapping
any adapter (channel, LLM provider, storage) without touching the core.

Uses Python Protocols (structural typing) instead of ABCs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from dax.core.models import (
        ChannelType,
        Conversation,
        Message,
        ToolCall,
        ToolResult,
    )


@runtime_checkable
class Channel(Protocol):
    """Input/output channel for user interaction.

    Channels receive messages from users and deliver assistant responses.
    Each channel (voice, WhatsApp, web) implements this protocol.
    """

    @property
    def name(self) -> str:
        """Unique channel identifier (e.g., 'voice', 'whatsapp', 'web')."""
        ...

    async def start(self) -> None:
        """Initialize and begin listening for messages."""
        ...

    async def stop(self) -> None:
        """Gracefully shut down the channel."""
        ...

    async def receive(self) -> AsyncIterator[Message]:
        """Yield incoming messages from this channel."""
        ...

    async def send(self, message: Message) -> None:
        """Deliver a response message through this channel."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """LLM inference provider.

    Abstracts the model backend (Ollama, Gemini, etc.) behind a
    unified interface for the orchestrator.
    """

    @property
    def name(self) -> str:
        """Provider identifier (e.g., 'ollama', 'gemini')."""
        ...

    async def complete(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Message:
        """Send a completion request and return the assistant's response.

        Args:
            messages: Conversation history in OpenAI-compatible format.
            tools: Available tool schemas in OpenAI function-calling format.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            The assistant's response as a Message (may contain tool_calls).
        """
        ...

    async def is_available(self) -> bool:
        """Check if this provider is reachable and ready."""
        ...


@runtime_checkable
class ToolProvider(Protocol):
    """MCP tool execution provider.

    Manages connections to MCP servers and executes tool calls.
    """

    async def start(self) -> None:
        """Launch and connect to all configured MCP servers."""
        ...

    async def stop(self) -> None:
        """Shut down all MCP server connections."""
        ...

    async def list_tools(self) -> list[dict[str, object]]:
        """Return all available tool schemas across all servers."""
        ...

    def get_relevant_tools(
        self, query: str, max_tools: int
    ) -> list[dict[str, object]]:
        """Return the tool schemas most relevant to ``query``, capped at
        ``max_tools``. Lets the core trim the tool budget without knowing how
        relevance is scored or which server owns what."""
        ...

    def get_server_for_tool(self, tool_name: str) -> str | None:
        """Return the server that owns ``tool_name``, or None if unknown."""
        ...

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call on the appropriate MCP server."""
        ...


@runtime_checkable
class Storage(Protocol):
    """Persistence layer for conversations and messages."""

    async def start(self) -> None:
        """Initialize the storage backend (create tables, run migrations)."""
        ...

    async def stop(self) -> None:
        """Close storage connections."""
        ...

    async def save_conversation(self, conversation: Conversation) -> None:
        """Persist a conversation and its messages."""
        ...

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Retrieve a conversation by ID, or None if not found."""
        ...

    async def get_or_create_conversation(
        self,
        channel: ChannelType,
        session_key: str,
    ) -> Conversation:
        """Return the conversation for (channel, session_key), creating one if needed."""
        ...

    async def get_recent_conversations(
        self,
        channel: str,
        limit: int = 5,
    ) -> list[Conversation]:
        """Retrieve the most recent conversations for a channel."""
        ...
