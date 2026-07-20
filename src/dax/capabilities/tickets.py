"""Server-vouched session tickets for direct client-to-node connections.

A phone that finds a laptop on the WiFi has learned nothing about who that
laptop is. Discovery is a hint; it is never evidence. So the backend — the one
party both sides already trust — vouches: the phone asks it for a ticket naming
a specific node, and the node verifies that ticket before serving anyone.

Three properties do the work, and each closes a concrete attack:

* **Ed25519, not HMAC.** The existing session and device tokens are signed with
  a shared secret through ``itsdangerous``. A node holding that secret could
  mint device tokens and session cookies for the backend itself. With a
  signature scheme the node verifies but cannot produce, a compromised laptop
  can impersonate nobody.
* **Bound to a node and a device.** A ticket issued for one laptop is refused by
  another, so a hostile node on the LAN cannot collect tickets and replay them
  against the real one.
* **Short-lived, with a nonce.** The window is a couple of minutes, and the
  nonce lets a node reject a ticket it has already honoured inside that window.

There is deliberately no algorithm field in the payload. Negotiable algorithms
are where JWT implementations get broken — an attacker flips ``alg`` to ``none``
or to a symmetric algorithm and the verifier obliges. Here the algorithm is a
property of the code, not of the message.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)

SIGNING_KEY_SECRET = "DAX_NODE_SESSION_SIGNING_KEY"
TICKET_VERSION = 1
DEFAULT_TTL_SECONDS = 120
MAX_TTL_SECONDS = 600
MAX_TICKET_BYTES = 2048
# Phones and laptops drift. Half a minute is enough for that without meaningfully
# widening the replay window.
CLOCK_SKEW_SECONDS = 30


@dataclass(frozen=True, slots=True)
class TicketClaims:
    """What a verified ticket asserts."""

    node_id: str
    device_id: str
    expires_at: int
    nonce: str


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class KeyStore(Protocol):
    """The slice of the secret store this module needs.

    Structural rather than a concrete import, so signing stays independent of
    how secrets happen to be persisted.
    """

    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...


def signing_key(store: KeyStore) -> str:
    """The backend's private key, generated on first use.

    Lazily rather than at startup, so an install that never enrols a node never
    grows a key it has no use for. Losing it invalidates outstanding tickets and
    nothing else — clients simply ask for another.
    """
    existing = store.get(SIGNING_KEY_SECRET)
    if existing:
        return existing
    created = generate_signing_key()
    store.set(SIGNING_KEY_SECRET, created)
    logger.info("Generated a node-session signing key")
    return created


def generate_signing_key() -> str:
    """A fresh Ed25519 private key, base64url-encoded for the secret store."""
    return _b64(Ed25519PrivateKey.generate().private_bytes_raw())


def public_key_for(private_key: str) -> str:
    """The public half, which is what nodes and clients are given."""
    key = Ed25519PrivateKey.from_private_bytes(_unb64(private_key))
    return _b64(key.public_key().public_bytes_raw())


def issue_ticket(
    private_key: str,
    *,
    node_id: str,
    device_id: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    """Sign a ticket letting *device_id* open a session on *node_id*."""
    if not node_id or not device_id:
        raise ValueError("A ticket must name both a node and a device")
    ttl = max(1, min(int(ttl_seconds), MAX_TTL_SECONDS))
    body = json.dumps(
        {
            "v": TICKET_VERSION,
            "node": node_id,
            "device": device_id,
            "exp": int(time.time()) + ttl,
            "nonce": secrets.token_hex(16),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    key = Ed25519PrivateKey.from_private_bytes(_unb64(private_key))
    return f"{_b64(body)}.{_b64(key.sign(body))}"


def verify_ticket(
    ticket: str,
    public_key: str,
    *,
    node_id: str,
    now: float | None = None,
) -> TicketClaims | None:
    """Verify *ticket* for *node_id*, or return None.

    Returns None for every failure rather than raising or distinguishing between
    them: a caller that can tell "bad signature" from "expired" from "wrong
    node" hands an attacker an oracle, and there is nothing a node would do
    differently for one over another.
    """
    if not ticket or len(ticket.encode()) > MAX_TICKET_BYTES:
        return None
    encoded_body, _, encoded_signature = ticket.partition(".")
    if not encoded_body or not encoded_signature:
        return None

    try:
        body = _unb64(encoded_body)
        signature = _unb64(encoded_signature)
        verifier = Ed25519PublicKey.from_public_bytes(_unb64(public_key))
    except (ValueError, TypeError):
        return None

    # Authenticate before parsing. Nothing below this line touches attacker-
    # controlled structure until the bytes are known to be ours.
    try:
        verifier.verify(signature, body)
    except (InvalidSignature, ValueError, TypeError):
        return None

    try:
        payload = json.loads(body)
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("v") != TICKET_VERSION:
        return None

    claimed_node = payload.get("node")
    device_id = payload.get("device")
    expires_at = payload.get("exp")
    nonce = payload.get("nonce")
    if not isinstance(claimed_node, str) or not isinstance(device_id, str):
        return None
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        return None
    if not isinstance(nonce, str) or not nonce or not device_id:
        return None

    # A ticket for another laptop is not a ticket for this one, however valid
    # its signature.
    if claimed_node != node_id:
        return None

    moment = time.time() if now is None else now
    if moment > expires_at + CLOCK_SKEW_SECONDS:
        return None

    return TicketClaims(
        node_id=claimed_node,
        device_id=device_id,
        expires_at=expires_at,
        nonce=nonce,
    )


class SeenNonces:
    """Rejects a ticket the node has already honoured.

    Bounded on purpose: entries are dropped once they cannot possibly still
    verify, so a node cannot be pushed into unbounded memory by being handed a
    stream of valid tickets.
    """

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def claim(self, claims: TicketClaims, *, now: float | None = None) -> bool:
        """Record *claims*; False if this nonce was already used."""
        moment = int(time.time() if now is None else now)
        self._prune(moment)
        if claims.nonce in self._seen:
            return False
        self._seen[claims.nonce] = claims.expires_at + CLOCK_SKEW_SECONDS
        return True

    def _prune(self, moment: int) -> None:
        expired = [nonce for nonce, until in self._seen.items() if until < moment]
        for nonce in expired:
            del self._seen[nonce]

    def __len__(self) -> int:
        return len(self._seen)
