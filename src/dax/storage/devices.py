"""Enrolled client devices and their credentials.

A single password is the right ergonomics for a browser tab, and the wrong
security model for a phone that lives in a pocket and can reach PC-control
tools. Devices get their own long-lived secret and exchange it for
short-lived access tokens, so a lost phone can be revoked without rotating
the password every other client uses.

Two properties shape this module:

* **Only a hash of the device secret is stored.** The plaintext exists once,
  in the enrolment response, and is expected to land in the client's hardware
  keystore. A stolen database is not a set of working credentials.
* **Revocation must be enforceable synchronously.** Token validation happens
  inside a WebSocket handshake, which is not a place to await SQLite, so the
  registry keeps an in-memory mirror that the auth layer reads directly.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

if TYPE_CHECKING:
    from dax.storage.database import Database

logger = logging.getLogger(__name__)

_hasher = PasswordHasher()

# 32 bytes of entropy, URL-safe. Long enough that the argon2 verify is the
# only thing standing between an attacker and a brute force, and it never has
# to be typed by a human.
_SECRET_BYTES = 32

# Pairing codes ARE typed by a human, so they trade length for an alphabet
# with no look-alike characters. Short TTL compensates for the smaller space.
_PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_PAIRING_LENGTH = 8
CLIENT_KIND = "client"
CAPABILITY_NODE_KIND = "capability_node"
DEVICE_KINDS = frozenset({CLIENT_KIND, CAPABILITY_NODE_KIND})


def _now() -> str:
    return datetime.now(UTC).isoformat()


def generate_device_secret() -> str:
    return secrets.token_urlsafe(_SECRET_BYTES)


def generate_pairing_code() -> str:
    return "".join(secrets.choice(_PAIRING_ALPHABET) for _ in range(_PAIRING_LENGTH))


@dataclass(slots=True, frozen=True)
class Device:
    """An enrolled client. Never carries the plaintext secret."""

    id: str
    name: str
    platform: str
    created_at: str
    last_seen_at: str
    revoked_at: str
    kind: str = CLIENT_KIND

    @property
    def revoked(self) -> bool:
        return bool(self.revoked_at)

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at or None,
            "revoked_at": self.revoked_at or None,
            "revoked": self.revoked,
            "kind": self.kind,
        }


class DeviceRegistry:
    """Persists enrolled devices and answers liveness checks synchronously."""

    def __init__(self, database: Database) -> None:
        self._db = database
        # id -> (secret_hash, revoked, kind). Mirrors the table so token validation
        # never has to await inside a handshake.
        self._active: dict[str, tuple[str, bool, str]] = {}

    async def load(self) -> None:
        """Populate the in-memory mirror. Call once after the database starts."""
        async with self._db.read() as conn:
            cursor = await conn.execute(
                "SELECT id, secret_hash, revoked_at, kind FROM devices"
            )
            rows = await cursor.fetchall()
        self._active = {
            row["id"]: (row["secret_hash"], bool(row["revoked_at"]), row["kind"])
            for row in rows
        }
        logger.info("Loaded %d enrolled device(s)", len(self._active))

    # -- Synchronous checks (used during auth) --

    def is_active(self, device_id: str) -> bool:
        """True when the device exists and has not been revoked."""
        entry = self._active.get(device_id)
        return entry is not None and not entry[1]

    def kind_of(self, device_id: str) -> str | None:
        entry = self._active.get(device_id)
        return entry[2] if entry is not None else None

    def is_active_kind(self, device_id: str, kind: str) -> bool:
        entry = self._active.get(device_id)
        return entry is not None and not entry[1] and entry[2] == kind

    def verify_secret(self, device_id: str, secret: str) -> bool:
        """Constant-time-ish check of a presented device secret."""
        entry = self._active.get(device_id)
        if entry is None or entry[1]:
            return False
        try:
            return _hasher.verify(entry[0], secret)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    @property
    def count(self) -> int:
        return len(self._active)

    # -- Mutations --

    async def enroll(
        self, *, name: str, platform: str, kind: str = CLIENT_KIND
    ) -> tuple[Device, str]:
        """Create a device and return it with its one-time plaintext secret."""
        if kind not in DEVICE_KINDS:
            raise ValueError(f"Unsupported device kind: {kind}")
        device_id = secrets.token_urlsafe(16)
        secret = generate_device_secret()
        secret_hash = _hasher.hash(secret)
        created = _now()
        async with self._db.transaction() as conn:
            await conn.execute(
                "INSERT INTO devices (id, name, platform, secret_hash, created_at, kind) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, name, platform, secret_hash, created, kind),
            )
        self._active[device_id] = (secret_hash, False, kind)
        logger.info("Enrolled device %s (%s / %s)", device_id, name, platform)
        return (
            Device(
                id=device_id,
                name=name,
                platform=platform,
                created_at=created,
                last_seen_at="",
                revoked_at="",
                kind=kind,
            ),
            secret,
        )

    async def touch(self, device_id: str) -> None:
        """Record that the device just authenticated."""
        async with self._db.transaction() as conn:
            await conn.execute(
                "UPDATE devices SET last_seen_at = ? WHERE id = ?", (_now(), device_id)
            )

    async def revoke(self, device_id: str) -> bool:
        """Revoke a device. Its outstanding access tokens stop validating."""
        if device_id not in self._active:
            return False
        async with self._db.transaction() as conn:
            await conn.execute(
                "UPDATE devices SET revoked_at = ? WHERE id = ? AND revoked_at = ''",
                (_now(), device_id),
            )
        secret_hash, _, kind = self._active[device_id]
        self._active[device_id] = (secret_hash, True, kind)
        logger.info("Revoked device %s", device_id)
        return True

    async def delete(self, device_id: str) -> bool:
        if device_id not in self._active:
            return False
        async with self._db.transaction() as conn:
            await conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        self._active.pop(device_id, None)
        logger.info("Deleted device %s", device_id)
        return True

    async def list_devices(self) -> list[Device]:
        async with self._db.read() as conn:
            cursor = await conn.execute(
                "SELECT id, name, platform, created_at, last_seen_at, revoked_at, kind "
                "FROM devices ORDER BY created_at DESC LIMIT 1000"
            )
            rows = await cursor.fetchall()
        return [
            Device(
                id=row["id"],
                name=row["name"],
                platform=row["platform"],
                created_at=row["created_at"],
                last_seen_at=row["last_seen_at"],
                revoked_at=row["revoked_at"],
                kind=row["kind"],
            )
            for row in rows
        ]
