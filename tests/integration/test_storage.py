"""Integration tests for SQLite storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dax.core.models import (
    ChannelType,
    Conversation,
    Language,
    Message,
    MessageRole,
)
from dax.storage.repository import ConversationRepository

if TYPE_CHECKING:
    from dax.storage.database import Database


class TestConversationMemory:
    async def test_get_or_create_returns_new_then_resumes(self, database: Database):
        repo = ConversationRepository(database)

        # First call: brand-new conversation for this (channel, session).
        conv = await repo.get_or_create_conversation(ChannelType.WHATSAPP, "user@jid")
        assert conv.session_key == "user@jid"
        assert conv.message_count == 0

        conv.add_message(Message(role=MessageRole.USER, content="remember 42"))
        conv.add_message(Message(role=MessageRole.ASSISTANT, content="ok, 42"))
        await repo.save_conversation(conv)

        # Second call with the same key: resumes the SAME conversation + history.
        resumed = await repo.get_or_create_conversation(ChannelType.WHATSAPP, "user@jid")
        assert resumed.id == conv.id
        assert resumed.session_key == "user@jid"
        assert [m.content for m in resumed.messages] == ["remember 42", "ok, 42"]

    async def test_different_session_keys_are_isolated(self, database: Database):
        repo = ConversationRepository(database)
        a = await repo.get_or_create_conversation(ChannelType.WEB, "web")
        a.add_message(Message(role=MessageRole.USER, content="A"))
        await repo.save_conversation(a)

        b = await repo.get_or_create_conversation(ChannelType.WHATSAPP, "phone")
        assert b.id != a.id
        assert b.message_count == 0


class TestToolAudit:
    async def test_log_and_read(self, database: Database):
        repo = ConversationRepository(database)
        await repo.log_tool_execution(
            server_name="dax-system",
            tool_name="fs_write",
            arguments={"path": "/tmp/x"},
            status="approved",
        )
        await repo.log_tool_execution(
            server_name="dax-system",
            tool_name="fs_read",
            arguments={"path": "/tmp/x"},
            status="executed",
        )
        entries = await repo.get_tool_audit(limit=10)
        assert len(entries) == 2
        # Newest first
        assert entries[0]["tool_name"] == "fs_read"
        assert entries[1]["status"] == "approved"
        assert entries[1]["arguments"] == {"path": "/tmp/x"}


class TestConversationRepository:
    async def test_save_and_retrieve(self, database: Database):
        repo = ConversationRepository(database)
        conv = Conversation(channel=ChannelType.WEB)
        conv.add_message(
            Message(
                role=MessageRole.USER,
                content="Hello",
                channel=ChannelType.WEB,
                language=Language.ENGLISH,
            )
        )
        conv.add_message(
            Message(
                role=MessageRole.ASSISTANT,
                content="Hi there!",
                channel=ChannelType.WEB,
                language=Language.ENGLISH,
            )
        )

        await repo.save_conversation(conv)

        retrieved = await repo.get_conversation(conv.id)
        assert retrieved is not None
        assert retrieved.id == conv.id
        assert retrieved.channel == ChannelType.WEB
        assert len(retrieved.messages) == 2
        assert retrieved.messages[0].content == "Hello"
        assert retrieved.messages[1].content == "Hi there!"

    async def test_get_nonexistent_returns_none(self, database: Database):
        repo = ConversationRepository(database)
        result = await repo.get_conversation("nonexistent-id")
        assert result is None

    async def test_get_recent_conversations(self, database: Database):
        repo = ConversationRepository(database)

        for i in range(3):
            conv = Conversation(channel=ChannelType.VOICE)
            conv.add_message(
                Message(content=f"Voice message {i}", channel=ChannelType.VOICE)
            )
            await repo.save_conversation(conv)

        # Also save a web conversation
        web_conv = Conversation(channel=ChannelType.WEB)
        web_conv.add_message(Message(content="Web message", channel=ChannelType.WEB))
        await repo.save_conversation(web_conv)

        voice_convs = await repo.get_recent_conversations("voice", limit=10)
        assert len(voice_convs) == 3

        web_convs = await repo.get_recent_conversations("web", limit=10)
        assert len(web_convs) == 1

    async def test_save_overwrites_existing(self, database: Database):
        repo = ConversationRepository(database)
        conv = Conversation(channel=ChannelType.WEB)
        conv.add_message(Message(content="First", channel=ChannelType.WEB))
        await repo.save_conversation(conv)

        conv.add_message(Message(content="Second", channel=ChannelType.WEB))
        await repo.save_conversation(conv)

        retrieved = await repo.get_conversation(conv.id)
        assert retrieved is not None
        assert len(retrieved.messages) == 2


class TestSchemaMigration:
    async def test_migrates_legacy_conversations_table(self, tmp_path):
        """A v1 DB (no session_key) must migrate without errors."""
        import aiosqlite

        from dax.storage.database import Database

        db_path = str(tmp_path / "legacy.db")
        # Create the old schema by hand.
        conn = await aiosqlite.connect(db_path)
        await conn.execute(
            "CREATE TABLE conversations (id TEXT PRIMARY KEY, channel TEXT NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        await conn.commit()
        await conn.close()

        # Starting the real Database should add the column + index and work.
        db = Database(db_path)
        await db.start()
        try:
            repo = ConversationRepository(db)
            conv = await repo.get_or_create_conversation(ChannelType.WEB, "web")
            conv.add_message(Message(role=MessageRole.USER, content="hi"))
            await repo.save_conversation(conv)
            resumed = await repo.get_or_create_conversation(ChannelType.WEB, "web")
            assert resumed.id == conv.id
        finally:
            await db.stop()


class TestDatabase:
    async def test_schema_version(self, database: Database):
        cursor = await database.connection.execute(
            "SELECT version FROM schema_version"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["version"] == 3

    async def test_wal_mode(self, database: Database):
        cursor = await database.connection.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row[0] == "wal"

    async def test_foreign_keys_enabled(self, database: Database):
        cursor = await database.connection.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row[0] == 1
