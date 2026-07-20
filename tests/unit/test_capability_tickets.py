"""Session tickets: what they prove, and every way they must refuse."""

from __future__ import annotations

import base64
import json
import time

import pytest

from dax.capabilities.tickets import (
    CLOCK_SKEW_SECONDS,
    MAX_TICKET_BYTES,
    MAX_TTL_SECONDS,
    SeenNonces,
    generate_signing_key,
    issue_ticket,
    public_key_for,
    verify_ticket,
)


@pytest.fixture
def keypair() -> tuple[str, str]:
    private = generate_signing_key()
    return private, public_key_for(private)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class TestRoundTrip:
    def test_a_ticket_verifies_for_the_node_it_names(self, keypair) -> None:
        private, public = keypair

        ticket = issue_ticket(private, node_id="laptop", device_id="phone")
        claims = verify_ticket(ticket, public, node_id="laptop")

        assert claims is not None
        assert claims.node_id == "laptop"
        assert claims.device_id == "phone"

    def test_every_ticket_carries_a_distinct_nonce(self, keypair) -> None:
        private, public = keypair

        first = verify_ticket(
            issue_ticket(private, node_id="laptop", device_id="phone"),
            public,
            node_id="laptop",
        )
        second = verify_ticket(
            issue_ticket(private, node_id="laptop", device_id="phone"),
            public,
            node_id="laptop",
        )

        assert first is not None and second is not None
        assert first.nonce != second.nonce

    def test_ttl_is_capped(self, keypair) -> None:
        private, public = keypair

        ticket = issue_ticket(
            private, node_id="laptop", device_id="phone", ttl_seconds=99_999
        )

        claims = verify_ticket(ticket, public, node_id="laptop")
        assert claims is not None
        assert claims.expires_at <= int(time.time()) + MAX_TTL_SECONDS

    def test_a_ticket_stays_well_under_the_size_bound(self, keypair) -> None:
        private, _ = keypair

        ticket = issue_ticket(private, node_id="laptop", device_id="phone")

        assert len(ticket.encode()) < MAX_TICKET_BYTES

    def test_a_ticket_must_name_both_parties(self, keypair) -> None:
        private, _ = keypair

        with pytest.raises(ValueError):
            issue_ticket(private, node_id="", device_id="phone")
        with pytest.raises(ValueError):
            issue_ticket(private, node_id="laptop", device_id="")


class TestRefusal:
    """Each of these is an attack, not an edge case."""

    def test_a_ticket_for_another_node_is_refused(self, keypair) -> None:
        """A hostile laptop cannot collect tickets and replay them elsewhere."""
        private, public = keypair

        ticket = issue_ticket(private, node_id="other-laptop", device_id="phone")

        assert verify_ticket(ticket, public, node_id="laptop") is None

    def test_a_ticket_signed_by_another_key_is_refused(self, keypair) -> None:
        """The node cannot be talked into trusting a key that is not the backend's."""
        _, public = keypair
        attacker = generate_signing_key()

        ticket = issue_ticket(attacker, node_id="laptop", device_id="phone")

        assert verify_ticket(ticket, public, node_id="laptop") is None

    def test_an_expired_ticket_is_refused(self, keypair) -> None:
        private, public = keypair

        ticket = issue_ticket(private, node_id="laptop", device_id="phone", ttl_seconds=1)

        later = time.time() + 1 + CLOCK_SKEW_SECONDS + 1
        assert verify_ticket(ticket, public, node_id="laptop", now=later) is None

    def test_a_ticket_within_clock_skew_still_verifies(self, keypair) -> None:
        private, public = keypair

        ticket = issue_ticket(private, node_id="laptop", device_id="phone", ttl_seconds=1)

        just_after = time.time() + 1 + (CLOCK_SKEW_SECONDS - 5)
        assert verify_ticket(ticket, public, node_id="laptop", now=just_after) is not None

    def test_a_tampered_payload_is_refused(self, keypair) -> None:
        """Editing the device the ticket names invalidates the signature."""
        private, public = keypair
        ticket = issue_ticket(private, node_id="laptop", device_id="phone")
        body, _, signature = ticket.partition(".")
        payload = json.loads(_unb64(body))
        payload["device"] = "attacker"
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        forged = f"{_b64(body)}.{signature}"

        assert verify_ticket(forged, public, node_id="laptop") is None

    def test_an_extended_expiry_is_refused(self, keypair) -> None:
        private, public = keypair
        ticket = issue_ticket(private, node_id="laptop", device_id="phone", ttl_seconds=1)
        body, _, signature = ticket.partition(".")
        payload = json.loads(_unb64(body))
        payload["exp"] = int(time.time()) + 100_000
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        forged = f"{_b64(body)}.{signature}"

        assert verify_ticket(forged, public, node_id="laptop") is None

    def test_an_unsigned_ticket_is_refused(self, keypair) -> None:
        """There is no algorithm field to downgrade, but try the shape anyway."""
        _, public = keypair
        body = json.dumps(
            {
                "v": 1,
                "node": "laptop",
                "device": "phone",
                "exp": int(time.time()) + 60,
                "nonce": "abc",
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

        assert verify_ticket(f"{_b64(body)}.", public, node_id="laptop") is None
        assert verify_ticket(_b64(body), public, node_id="laptop") is None

    def test_a_wrong_version_is_refused(self, keypair) -> None:
        private, public = keypair
        key_bytes = _unb64(private)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        signer = Ed25519PrivateKey.from_private_bytes(key_bytes)
        body = json.dumps(
            {
                "v": 99,
                "node": "laptop",
                "device": "phone",
                "exp": int(time.time()) + 60,
                "nonce": "abc",
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        ticket = f"{_b64(body)}.{_b64(signer.sign(body))}"

        assert verify_ticket(ticket, public, node_id="laptop") is None

    def test_garbage_is_refused_without_raising(self, keypair) -> None:
        _, public = keypair

        for junk in ["", ".", "..", "not-a-ticket", "a.b", "@@@.@@@", "x" * 5000]:
            assert verify_ticket(junk, public, node_id="laptop") is None

    def test_an_oversized_ticket_is_refused_before_parsing(self, keypair) -> None:
        _, public = keypair

        assert verify_ticket("x" * (MAX_TICKET_BYTES + 1), public, node_id="laptop") is None

    def test_a_malformed_public_key_refuses_rather_than_raises(self) -> None:
        private = generate_signing_key()
        ticket = issue_ticket(private, node_id="laptop", device_id="phone")

        assert verify_ticket(ticket, "not-a-key", node_id="laptop") is None


class TestSeenNonces:
    def test_a_nonce_is_accepted_once(self, keypair) -> None:
        private, public = keypair
        claims = verify_ticket(
            issue_ticket(private, node_id="laptop", device_id="phone"),
            public,
            node_id="laptop",
        )
        assert claims is not None
        seen = SeenNonces()

        assert seen.claim(claims) is True
        assert seen.claim(claims) is False

    def test_distinct_tickets_both_pass(self, keypair) -> None:
        private, public = keypair
        seen = SeenNonces()
        for _ in range(3):
            claims = verify_ticket(
                issue_ticket(private, node_id="laptop", device_id="phone"),
                public,
                node_id="laptop",
            )
            assert claims is not None
            assert seen.claim(claims) is True

    def test_entries_are_dropped_once_they_can_no_longer_verify(self, keypair) -> None:
        """Otherwise a stream of valid tickets is an unbounded memory leak."""
        private, public = keypair
        seen = SeenNonces()
        claims = verify_ticket(
            issue_ticket(private, node_id="laptop", device_id="phone", ttl_seconds=1),
            public,
            node_id="laptop",
        )
        assert claims is not None
        seen.claim(claims)
        assert len(seen) == 1

        # A later claim prunes what can no longer be replayed anyway.
        fresh = verify_ticket(
            issue_ticket(private, node_id="laptop", device_id="phone"),
            public,
            node_id="laptop",
        )
        assert fresh is not None
        seen.claim(fresh, now=time.time() + CLOCK_SKEW_SECONDS + 10)

        assert len(seen) == 1
