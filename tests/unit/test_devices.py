"""Device enrolment, short-lived tokens, and revocation."""

from __future__ import annotations

import time

import pytest

from dax.core.config import SecurityConfig
from dax.storage.database import Database
from dax.storage.devices import DeviceRegistry, generate_pairing_code
from dax.web.auth import AuthManager
from dax.web.routes.devices import _PairingCodes


@pytest.fixture
async def registry(tmp_path):
    db = Database(str(tmp_path / "dax.db"))
    await db.start()
    reg = DeviceRegistry(db)
    await reg.load()
    yield reg
    await db.stop()


def _auth(**overrides) -> AuthManager:
    return AuthManager(
        SecurityConfig(
            auth_enabled=True,
            password_hash="x",
            session_secret="test-secret-not-a-real-one",
            **overrides,
        )
    )


class TestDeviceRegistry:
    async def test_enroll_returns_secret_once_and_stores_only_a_hash(self, registry):
        device, secret = await registry.enroll(name="Redmi Note 13", platform="android")

        assert secret
        assert registry.is_active(device.id) is True
        assert registry.verify_secret(device.id, secret) is True

        # The plaintext must not be recoverable from the persisted row.
        cursor = await registry._db.connection.execute(
            "SELECT secret_hash FROM devices WHERE id = ?", (device.id,)
        )
        row = await cursor.fetchone()
        assert secret not in row["secret_hash"]
        assert row["secret_hash"].startswith("$argon2")

    async def test_wrong_secret_is_rejected(self, registry):
        device, _ = await registry.enroll(name="phone", platform="android")
        assert registry.verify_secret(device.id, "not-the-secret") is False

    async def test_unknown_device_is_rejected(self, registry):
        assert registry.verify_secret("nope", "whatever") is False
        assert registry.is_active("nope") is False

    async def test_revoke_stops_verification(self, registry):
        device, secret = await registry.enroll(name="phone", platform="android")
        assert await registry.revoke(device.id) is True

        assert registry.is_active(device.id) is False
        assert registry.verify_secret(device.id, secret) is False

    async def test_revoke_survives_reload(self, registry):
        device, secret = await registry.enroll(name="phone", platform="android")
        await registry.revoke(device.id)

        await registry.load()

        assert registry.is_active(device.id) is False
        assert registry.verify_secret(device.id, secret) is False

    async def test_delete_removes_the_device(self, registry):
        device, _ = await registry.enroll(name="phone", platform="android")
        assert await registry.delete(device.id) is True
        assert registry.is_active(device.id) is False
        assert await registry.delete(device.id) is False

    async def test_listing_never_exposes_a_secret(self, registry):
        _, secret = await registry.enroll(name="phone", platform="android")
        listed = [d.to_json() for d in await registry.list_devices()]

        assert len(listed) == 1
        assert secret not in repr(listed)
        assert "secret" not in " ".join(listed[0].keys())

    async def test_secrets_are_unique_per_device(self, registry):
        _, first = await registry.enroll(name="a", platform="android")
        _, second = await registry.enroll(name="b", platform="android")
        assert first != second


class TestDeviceTokens:
    async def test_device_token_validates_and_resolves(self, registry):
        auth = _auth()
        auth.attach_devices(registry)
        device, _ = await registry.enroll(name="phone", platform="android")

        token = auth.issue_device_token(device.id)

        assert auth.validate_token(token) is True
        assert auth.device_from_token(token) == device.id

    async def test_revoked_device_token_stops_working_immediately(self, registry):
        auth = _auth()
        auth.attach_devices(registry)
        device, _ = await registry.enroll(name="phone", platform="android")
        token = auth.issue_device_token(device.id)
        assert auth.validate_token(token) is True

        await registry.revoke(device.id)

        assert auth.device_from_token(token) is None
        assert auth.validate_token(token) is False

    async def test_device_token_expires(self, registry, monkeypatch):
        auth = _auth(device_token_ttl_minutes=1)
        auth.attach_devices(registry)
        device, _ = await registry.enroll(name="phone", platform="android")
        token = auth.issue_device_token(device.id)
        assert auth.device_from_token(token) == device.id

        # itsdangerous stamps wall-clock time into the token, so advancing the
        # clock past the TTL is what expiry actually looks like.
        real_time = time.time
        monkeypatch.setattr(time, "time", lambda: real_time() + 3600)

        assert auth.device_from_token(token) is None
        assert auth.validate_token(token) is False

    async def test_session_token_is_not_a_device_token(self, registry):
        """Salt separation: a browser session must not authenticate as a device."""
        auth = _auth()
        auth.attach_devices(registry)

        session_token = auth.issue_token()

        assert auth.validate_token(session_token) is True
        assert auth.device_from_token(session_token) is None

    async def test_device_token_is_not_a_session_token(self, registry):
        auth = _auth()
        auth.attach_devices(registry)
        device, _ = await registry.enroll(name="phone", platform="android")
        device_token = auth.issue_device_token(device.id)

        # Valid overall, but not decodable under the session salt.
        assert auth.validate_token(device_token) is True
        auth_without_devices = _auth()
        assert auth_without_devices.validate_token(device_token) is False

    async def test_device_tokens_rejected_when_no_registry_attached(self, registry):
        auth = _auth()
        device, _ = await registry.enroll(name="phone", platform="android")
        token = auth.issue_device_token(device.id)

        assert auth.device_from_token(token) is None
        assert auth.validate_token(token) is False

    async def test_tampered_token_is_rejected(self, registry):
        auth = _auth()
        auth.attach_devices(registry)
        device, _ = await registry.enroll(name="phone", platform="android")
        token = auth.issue_device_token(device.id)

        tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")

        assert auth.device_from_token(tampered) is None

    async def test_token_signed_with_a_different_secret_is_rejected(self, registry):
        issuer = _auth()
        issuer.attach_devices(registry)
        device, _ = await registry.enroll(name="phone", platform="android")
        token = issuer.issue_device_token(device.id)

        other = AuthManager(
            SecurityConfig(
                auth_enabled=True, password_hash="x", session_secret="a-different-secret"
            )
        )
        other.attach_devices(registry)

        assert other.device_from_token(token) is None


class TestPairingCodes:
    def test_code_redeems_exactly_once(self):
        codes = _PairingCodes()
        entry = codes.issue(300)

        assert codes.redeem(entry.code) is True
        assert codes.redeem(entry.code) is False

    def test_code_is_case_insensitive_and_trimmed(self):
        codes = _PairingCodes()
        entry = codes.issue(300)

        assert codes.redeem(f"  {entry.code.lower()}  ") is True

    def test_expired_code_is_rejected(self):
        codes = _PairingCodes()
        entry = codes.issue(0)

        assert codes.redeem(entry.code) is False
        assert codes.outstanding == 0

    def test_wrong_code_is_rejected(self):
        codes = _PairingCodes()
        codes.issue(300)

        assert codes.redeem("XXXXXXXX") is False
        assert codes.outstanding == 1

    def test_outstanding_codes_are_bounded(self):
        codes = _PairingCodes()
        for _ in range(50):
            codes.issue(300)

        assert codes.outstanding <= 8

    def test_generated_codes_avoid_lookalike_characters(self):
        for _ in range(50):
            assert not set(generate_pairing_code()) & set("O0I1")
