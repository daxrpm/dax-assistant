"""SQLite database initialization and connection management."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    session_key TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    channel TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'auto',
    timestamp TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id);

CREATE INDEX IF NOT EXISTS idx_conversations_channel_updated
    ON conversations(channel, updated_at DESC);

CREATE TABLE IF NOT EXISTS tool_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    server_name TEXT NOT NULL DEFAULT '',
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_audit_timestamp
    ON tool_audit(timestamp DESC);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


class Database:
    """Async SQLite database wrapper.

    Manages the connection lifecycle and schema initialization.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def start(self) -> None:
        """Open the database connection and initialize the schema."""
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self._db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await self._initialize_schema()
        logger.info("Database initialized at %s", self._db_path)

    async def stop(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    @property
    def connection(self) -> aiosqlite.Connection:
        """Return the active connection, raising if not started."""
        if self._connection is None:
            raise RuntimeError("Database not started — call start() first")
        return self._connection

    async def _initialize_schema(self) -> None:
        """Create tables if they don't exist and track schema version."""
        conn = self.connection
        await conn.executescript(SCHEMA_SQL)
        await self._migrate()

        cursor = await conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = await cursor.fetchone()
        if row is None:
            await conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
        else:
            await conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        await conn.commit()
        logger.debug("Schema version: %d", SCHEMA_VERSION)

    async def _migrate(self) -> None:
        """Apply additive migrations for databases created before this version."""
        conn = self.connection
        cursor = await conn.execute("PRAGMA table_info(conversations)")
        columns = {row["name"] for row in await cursor.fetchall()}
        if "session_key" not in columns:
            await conn.execute(
                "ALTER TABLE conversations ADD COLUMN session_key TEXT NOT NULL DEFAULT ''"
            )
            logger.info("Migrated conversations: added session_key column")
        if "title" not in columns:
            await conn.execute(
                "ALTER TABLE conversations ADD COLUMN title TEXT NOT NULL DEFAULT ''"
            )
            logger.info("Migrated conversations: added title column")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_channel_session "
            "ON conversations(channel, session_key)"
        )
        await conn.commit()
