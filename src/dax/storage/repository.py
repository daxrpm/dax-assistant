"""Conversation repository — implements the Storage protocol for SQLite."""

from __future__ import annotations

import json
import logging
from datetime import UTC
from typing import TYPE_CHECKING

from dax.core.models import (
    ChannelType,
    Conversation,
    Language,
    Message,
    MessageRole,
)

if TYPE_CHECKING:
    from datetime import datetime

    from dax.storage.database import Database

logger = logging.getLogger(__name__)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO format datetime string."""
    from datetime import datetime

    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


class ConversationRepository:
    """SQLite-backed conversation storage.

    Implements the Storage protocol defined in core/ports.py.
    """

    def __init__(self, database: Database) -> None:
        self._db = database

    async def start(self) -> None:
        """No-op — database lifecycle is managed separately."""

    async def stop(self) -> None:
        """No-op — database lifecycle is managed separately."""

    async def save_conversation(self, conversation: Conversation) -> None:
        """Persist a conversation and all its messages."""
        conn = self._db.connection

        await conn.execute(
            """
            INSERT OR REPLACE INTO conversations
                (id, channel, session_key, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                conversation.id,
                conversation.channel.value,
                conversation.session_key,
                conversation.created_at.isoformat(),
                conversation.updated_at.isoformat(),
            ),
        )

        for msg in conversation.messages:
            await conn.execute(
                """
                INSERT OR REPLACE INTO messages
                    (id, conversation_id, role, content, channel, language, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg.id,
                    conversation.id,
                    msg.role.value,
                    msg.content,
                    msg.channel.value,
                    msg.language.value,
                    msg.timestamp.isoformat(),
                    json.dumps(msg.metadata, default=str),
                ),
            )

        await conn.commit()
        logger.debug(
            "Saved conversation %s with %d messages",
            conversation.id,
            len(conversation.messages),
        )

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Retrieve a conversation by ID, including all messages."""
        conn = self._db.connection

        cursor = await conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        conversation = Conversation(
            id=row["id"],
            channel=ChannelType(row["channel"]),
            session_key=row["session_key"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

        msg_cursor = await conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (conversation_id,),
        )
        rows = await msg_cursor.fetchall()

        for msg_row in rows:
            message = Message(
                id=msg_row["id"],
                role=MessageRole(msg_row["role"]),
                content=msg_row["content"],
                channel=ChannelType(msg_row["channel"]),
                language=Language(msg_row["language"]),
                timestamp=_parse_datetime(msg_row["timestamp"]),
                metadata=json.loads(msg_row["metadata"]),
            )
            conversation.messages.append(message)

        return conversation

    async def get_or_create_conversation(
        self,
        channel: ChannelType,
        session_key: str,
    ) -> Conversation:
        """Return the existing conversation for (channel, session_key), or a new one.

        A new conversation is NOT persisted until the next ``save_conversation``
        — callers append messages and save once per turn.
        """
        conn = self._db.connection
        cursor = await conn.execute(
            """
            SELECT id FROM conversations
            WHERE channel = ? AND session_key = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (channel.value, session_key),
        )
        row = await cursor.fetchone()
        if row is not None:
            existing = await self.get_conversation(row["id"])
            if existing is not None:
                return existing

        return Conversation(channel=channel, session_key=session_key)

    async def log_tool_execution(
        self,
        *,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
        status: str,
    ) -> None:
        """Append a tool-execution record to the audit log."""
        from datetime import datetime

        conn = self._db.connection
        await conn.execute(
            """
            INSERT INTO tool_audit (timestamp, server_name, tool_name, arguments, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                server_name,
                tool_name,
                json.dumps(arguments, default=str),
                status,
            ),
        )
        await conn.commit()

    async def get_tool_audit(self, limit: int = 50) -> list[dict[str, object]]:
        """Return the most recent tool-audit entries (newest first)."""
        conn = self._db.connection
        cursor = await conn.execute(
            """
            SELECT timestamp, server_name, tool_name, arguments, status
            FROM tool_audit ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "timestamp": r["timestamp"],
                "server_name": r["server_name"],
                "tool_name": r["tool_name"],
                "arguments": json.loads(r["arguments"]),
                "status": r["status"],
            }
            for r in rows
        ]

    async def get_recent_conversations(
        self,
        channel: str,
        limit: int = 5,
    ) -> list[Conversation]:
        """Retrieve the most recent conversations for a channel."""
        conn = self._db.connection

        cursor = await conn.execute(
            """
            SELECT id FROM conversations
            WHERE channel = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (channel, limit),
        )
        rows = await cursor.fetchall()

        conversations: list[Conversation] = []
        for row in rows:
            conv = await self.get_conversation(row["id"])
            if conv is not None:
                conversations.append(conv)

        return conversations
