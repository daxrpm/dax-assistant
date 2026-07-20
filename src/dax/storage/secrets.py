"""Encrypted secret storage backed by SQLite.

Replaces the legacy ``.env`` file as the source of truth for secrets (API
keys, integration tokens, the login password hash, the session secret).

Design
------
- Secrets live in the ``secrets`` table of the same SQLite database used for
  conversations, encrypted at rest with `Fernet`.
- The Fernet key is kept in a sibling key file (``dax.key``) with ``0600``
  permissions — readable only by the owner, never committed, never in the DB.
- At config-load time the store decrypts every secret and seeds
  ``os.environ`` (without clobbering real, externally-set env vars). This keeps
  the existing ``{env:VAR}`` resolution and the provider SDKs (which read
  ``OPENAI_API_KEY`` etc. directly) working unchanged.

The store uses the synchronous ``sqlite3`` driver so it can be read *before*
the async event loop exists (providers are built during app construction,
before ``start()``). WAL mode makes this safe alongside the async connection.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sqlite3
import stat
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken

from dax.storage.database import acquire_process_lock

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)
_KEY_FILE_LOCK = threading.Lock()
_STORE_INIT_LOCK = threading.Lock()

# Secrets that should never round-trip into os.environ as real exports (the
# password hash and session secret are read via DAX_ env names, so they DO need
# to be exported). We export everything; this set is documentation only.


class SecretStoreError(RuntimeError):
    """Encrypted secret material cannot be accessed safely."""


class SecretStore:
    """Encrypted key/value secret store on top of SQLite + a Fernet key file."""

    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._key_path = self._db_path.parent / "dax.key"
        acquire_process_lock(self._db_path)
        self._write_lock = threading.RLock()
        self._transaction_connection: sqlite3.Connection | None = None
        self._pending_env: dict[str, str | None] | None = None
        with _STORE_INIT_LOCK:
            self._fernet = Fernet(self._load_or_create_key())
            self._ensure_table()
            self._validate_existing_material()

    # -- key management --

    def _load_or_create_key(self) -> bytes:
        external_key = os.environ.get("DAX_MASTER_KEY")
        if external_key:
            return external_key.encode("ascii")
        with _KEY_FILE_LOCK:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            if self._key_path.exists():
                return self._key_path.read_bytes().strip()
            if self._has_encrypted_material():
                raise SecretStoreError(
                    f"Secret key is unavailable for existing encrypted data: {self._key_path}"
                )
            key = Fernet.generate_key()
            # O_EXCL and the process lock prevent replacement or concurrent creation.
            fd = os.open(
                self._key_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                stat.S_IRUSR | stat.S_IWUSR,
            )
            with os.fdopen(fd, "wb") as f:
                f.write(key)
            logger.info("Generated new secret key at %s", self._key_path)
            return key

    def _has_encrypted_material(self) -> bool:
        if not self._db_path.exists():
            return False
        try:
            with sqlite3.connect(self._db_path, timeout=10) as conn:
                table = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'secrets'"
                ).fetchone()
                return (
                    table is not None
                    and conn.execute("SELECT 1 FROM secrets LIMIT 1").fetchone() is not None
                )
        except sqlite3.DatabaseError as exc:
            raise SecretStoreError(f"Cannot inspect encrypted secret store: {exc}") from exc

    # -- schema --

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS secrets ("
                "  name TEXT PRIMARY KEY,"
                "  value TEXT NOT NULL,"
                "  updated_at TEXT NOT NULL DEFAULT ''"
                ")"
            )
            conn.commit()
        with contextlib.suppress(OSError):
            self._db_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def _validate_existing_material(self) -> None:
        with self._connect() as conn:
            rows = conn.execute("SELECT value FROM secrets").fetchall()
        try:
            for row in rows:
                self._fernet.decrypt(row[0].encode("ascii"))
        except (InvalidToken, UnicodeEncodeError, ValueError) as exc:
            raise SecretStoreError(
                "Encrypted secrets cannot be decrypted with the configured master key"
            ) from exc

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit a group of secret mutations and environment updates atomically."""
        with self._write_lock:
            if self._transaction_connection is not None:
                yield
                return
            conn = self._connect()
            self._transaction_connection = conn
            self._pending_env = {}
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield
                conn.commit()
                for name, value in self._pending_env.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value
            except BaseException:
                conn.rollback()
                raise
            finally:
                self._transaction_connection = None
                self._pending_env = None
                conn.close()

    # -- CRUD --

    def set(self, name: str, value: str) -> None:
        """Encrypt and persist a secret; also export it to ``os.environ``."""
        with self._write_lock:
            token = self._fernet.encrypt(value.encode("utf-8")).decode("ascii")
            if self._transaction_connection is not None:
                self._set_on_connection(self._transaction_connection, name, token)
                assert self._pending_env is not None
                self._pending_env[name] = value
                return
            with self._connect() as conn:
                self._set_on_connection(conn, name, token)
                conn.commit()
            os.environ[name] = value

    @staticmethod
    def _set_on_connection(conn: sqlite3.Connection, name: str, token: str) -> None:
        conn.execute(
            "INSERT INTO secrets (name, value, updated_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(name) DO UPDATE SET value=excluded.value, "
            "updated_at=excluded.updated_at",
            (name, token),
        )

    def get(self, name: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM secrets WHERE name = ?", (name,)).fetchone()
        if row is None:
            return None
        try:
            return self._fernet.decrypt(row[0].encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeEncodeError, ValueError) as exc:
            raise SecretStoreError(f"Encrypted secret {name!r} cannot be decrypted") from exc

    def delete(self, name: str) -> None:
        with self._write_lock:
            if self._transaction_connection is not None:
                self._transaction_connection.execute("DELETE FROM secrets WHERE name = ?", (name,))
                assert self._pending_env is not None
                self._pending_env[name] = None
                return
            with self._connect() as conn:
                conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
                conn.commit()
            os.environ.pop(name, None)

    def names(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT name FROM secrets ORDER BY name").fetchall()
        return [r[0] for r in rows]

    def all_items(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name in self.names():
            value = self.get(name)
            if value is not None:
                out[name] = value
        return out

    # -- bootstrapping --

    def load_into_env(self) -> None:
        """Seed ``os.environ`` from the store without clobbering real env vars.

        Real, externally-set environment variables keep precedence (matches the
        documented ``env > store > TOML`` order), so we use ``setdefault``.
        """
        for name, value in self.all_items().items():
            os.environ.setdefault(name, value)

    def import_dotenv(self, env_path: Path) -> int:
        """One-time migration: import ``KEY=value`` lines from a legacy .env.

        Only keys not already in the store are imported. Returns the count
        imported. The .env file is left in place but is no longer authoritative.
        """
        if not env_path.exists():
            return 0
        existing = set(self.names())
        imported = 0
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key or key in existing:
                continue
            self.set(key, value)
            imported += 1
        if imported:
            logger.info("Imported %d secret(s) from %s into the store", imported, env_path)
        return imported
