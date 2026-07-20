"""SQLite database initialization and connection management."""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import IO

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 6

_PROCESS_LOCKS: dict[Path, tuple[int, IO[bytes]]] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


class DatabaseLockedError(RuntimeError):
    """Raised when another process owns a database's persistence files."""


def acquire_process_lock(db_path: str | Path) -> None:
    """Hold an exclusive advisory lock for this database until process exit."""
    if str(db_path) == ":memory:":
        return
    path = Path(db_path).expanduser().resolve()
    with _PROCESS_LOCKS_GUARD:
        existing = _PROCESS_LOCKS.get(path)
        if existing is not None and existing[0] == os.getpid():
            return
        if existing is not None:
            existing[1].close()
            _PROCESS_LOCKS.pop(path, None)

        path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = path.with_name(f"{path.name}.lock").open("a+b")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.close()
            raise DatabaseLockedError(
                f"Persistence database is already in use by another process: {path}"
            ) from exc
        _PROCESS_LOCKS[path] = (os.getpid(), lock_file)


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

-- Encrypted secret store (values encrypted at rest; see storage/secrets.py).
CREATE TABLE IF NOT EXISTS secrets (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT ''
);

-- Enrolled clients (phone, desktop). Only an argon2 hash of the device secret
-- is stored: the plaintext is shown once at enrolment and never again, so a
-- database copy cannot be replayed as a device. See storage/devices.py.
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT '',
    secret_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL DEFAULT '',
    revoked_at TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'client'
);
"""


class Database:
    """Async SQLite database wrapper.

    Manages the connection lifecycle and schema initialization.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None
        self._transaction_lock = asyncio.Lock()

    async def start(self) -> None:
        """Open the database connection and initialize the schema."""
        if self._connection is not None:
            raise RuntimeError("Database already started")
        acquire_process_lock(self._db_path)
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        connection = await aiosqlite.connect(self._db_path, timeout=10)
        self._connection = connection
        connection.row_factory = aiosqlite.Row
        try:
            await connection.execute("PRAGMA journal_mode=WAL")
            await connection.execute("PRAGMA foreign_keys=ON")
            await connection.execute("PRAGMA busy_timeout=10000")
            await self._initialize_schema()
        except BaseException:
            await connection.close()
            self._connection = None
            raise
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

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Serialize a write transaction and roll it back on any failure."""
        async with self._transaction_lock:
            conn = self.connection
            await conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                await conn.rollback()
                raise
            else:
                await conn.commit()

    @contextlib.asynccontextmanager
    async def read(self) -> AsyncIterator[aiosqlite.Connection]:
        """Run one or more reads against a consistent, serialized snapshot."""
        async with self._transaction_lock:
            conn = self.connection
            await conn.execute("BEGIN")
            try:
                yield conn
            finally:
                await conn.rollback()

    async def _initialize_schema(self) -> None:
        """Create tables if they don't exist and track schema version."""
        conn = self.connection
        try:
            await conn.executescript(f"BEGIN IMMEDIATE;\n{SCHEMA_SQL}")
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
        except BaseException:
            await conn.rollback()
            raise
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
        cursor = await conn.execute("PRAGMA table_info(devices)")
        device_columns = {row["name"] for row in await cursor.fetchall()}
        if "kind" not in device_columns:
            await conn.execute(
                "ALTER TABLE devices ADD COLUMN kind TEXT NOT NULL DEFAULT 'client'"
            )
            logger.info("Migrated devices: added kind column")
