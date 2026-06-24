"""Domain models for Dax Assistant.

Pure dataclasses with no external dependencies. These represent the core
vocabulary of the system — messages, conversations, and tool interactions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ChannelType(StrEnum):
    """Supported communication channels."""

    VOICE = "voice"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    WEB = "web"


class MessageRole(StrEnum):
    """Role of a message participant."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Language(StrEnum):
    """Supported languages for voice interaction."""

    SPANISH = "es"
    ENGLISH = "en"
    AUTO = "auto"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request to execute an MCP tool."""

    id: str
    server_name: str
    tool_name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The result of an MCP tool execution."""

    call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class Message:
    """A single message in a conversation.

    Immutable value object. All messages flow through the system bus
    as Message instances regardless of their source channel.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    role: MessageRole = MessageRole.USER
    content: str = ""
    channel: ChannelType = ChannelType.WEB
    language: Language = Language.AUTO
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class Conversation:
    """An ordered sequence of messages within a channel session.

    Mutable — messages are appended as the conversation progresses.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    channel: ChannelType = ChannelType.WEB
    # Stable key identifying the conversation session within a channel
    # (e.g. a WhatsApp sender JID, or "web"/"voice"). Lets the agent resume
    # the right conversation across messages.
    session_key: str = ""
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_message(self, message: Message) -> None:
        """Append a message and update the timestamp."""
        self.messages.append(message)
        self.updated_at = datetime.now(UTC)

    @property
    def last_message(self) -> Message | None:
        """Return the most recent message, or None if empty."""
        return self.messages[-1] if self.messages else None

    @property
    def message_count(self) -> int:
        return len(self.messages)
