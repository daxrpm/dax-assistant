"""End-to-end device enrolment over the HTTP API.

Covers the gating each endpoint relies on: pairing needs a session, enrolment
needs a live one-time code, token exchange needs the device secret, and
listing/revocation need a session so a compromised device cannot unenroll its
siblings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from dax.core.config import DaxConfig
from dax.orchestrator.bus import MessageBus
from dax.storage.database import Database
from dax.storage.devices import DeviceRegistry
from dax.web.server import create_app

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import FastAPI


@pytest.fixture
def bus() -> MessageBus:
    b = MessageBus()
    b.start()
    return b


@pytest.fixture
async def app(bus: MessageBus, tmp_path: Path):
    """An app with auth OFF but a live device registry attached.

    Auth-off keeps the session-gated endpoints reachable without a login
    round-trip; the device-secret and pairing-code checks under test are
    enforced independently of `auth_enabled`.
    """
    config = DaxConfig(
        security={"auth_enabled": False, "session_secret": "test-secret"},
        storage={"database_path": str(tmp_path / "dax.db")},
    )
    fastapi_app = create_app(config=config, bus=bus)
    fastapi_app.state.config = config
    fastapi_app.state.bus = bus
    fastapi_app.state.voice_listening = config.voice.enabled

    database = Database(str(tmp_path / "dax.db"))
    await database.start()
    registry = DeviceRegistry(database)
    await registry.load()
    fastapi_app.state.auth.attach_devices(registry)
    fastapi_app.state.devices = registry
    yield fastapi_app
    await database.stop()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


async def _enroll(client: AsyncClient) -> tuple[str, str]:
    code = (await client.post("/api/auth/devices/pair")).json()["code"]
    body = (
        await client.post(
            "/api/auth/devices/enroll",
            json={"code": code, "name": "Redmi Note 13", "platform": "android"},
        )
    ).json()
    return body["device_id"], body["device_secret"]


class TestEnrolmentFlow:
    async def test_pair_enroll_token_round_trip(self, client: AsyncClient, app: FastAPI):
        pair = await client.post("/api/auth/devices/pair")
        assert pair.status_code == 200
        code = pair.json()["code"]
        assert pair.json()["expires_in_seconds"] > 0
        assert pair.json()["backend_url"] == "http://test"
        parsed = urlparse(pair.json()["pairing_uri"])
        assert (parsed.scheme, parsed.netloc) == ("dax", "pair")
        assert parse_qs(parsed.query) == {"url": ["http://test"], "code": [code]}

        enroll = await client.post(
            "/api/auth/devices/enroll",
            json={"code": code, "name": "Redmi Note 13", "platform": "android"},
        )
        assert enroll.status_code == 200
        device_id = enroll.json()["device_id"]
        secret = enroll.json()["device_secret"]
        assert device_id and secret

        token = await client.post(
            "/api/auth/devices/token",
            json={"device_id": device_id, "device_secret": secret},
        )
        assert token.status_code == 200
        assert token.json()["ok"] is True
        assert app.state.auth.device_from_token(token.json()["token"]) == device_id

    async def test_pairing_code_cannot_be_reused(self, client: AsyncClient):
        code = (await client.post("/api/auth/devices/pair")).json()["code"]
        first = await client.post("/api/auth/devices/enroll", json={"code": code})
        assert first.status_code == 200

        second = await client.post("/api/auth/devices/enroll", json={"code": code})
        assert second.status_code == 401
        assert second.json()["ok"] is False

    async def test_capability_node_kind_is_bound_to_pairing_code(
        self, client: AsyncClient, app: FastAPI
    ):
        pair = await client.post(
            "/api/auth/devices/pair", json={"kind": "capability_node"}
        )
        enrolled = await client.post(
            "/api/auth/devices/enroll",
            json={
                "code": pair.json()["code"],
                "name": "Laptop",
                "platform": "linux",
            },
        )
        credentials = enrolled.json()
        token = (
            await client.post(
                "/api/auth/devices/token",
                json={
                    "device_id": credentials["device_id"],
                    "device_secret": credentials["device_secret"],
                },
            )
        ).json()["token"]

        listed = (await client.get("/api/auth/devices")).json()["devices"][0]
        assert pair.json()["kind"] == "capability_node"
        assert listed["kind"] == "capability_node"
        assert app.state.auth.capability_node_from_token(token) == listed["id"]
        assert app.state.auth.validate_token(token) is False

    async def test_bad_pairing_code_is_rejected(self, client: AsyncClient):
        response = await client.post("/api/auth/devices/enroll", json={"code": "ZZZZZZZZ"})
        assert response.status_code == 401
        assert response.json()["device_secret"] is None

    async def test_wrong_device_secret_gets_no_token(self, client: AsyncClient):
        device_id, _ = await _enroll(client)

        response = await client.post(
            "/api/auth/devices/token",
            json={"device_id": device_id, "device_secret": "wrong"},
        )

        assert response.status_code == 401
        assert response.json()["token"] is None

    async def test_unknown_device_gets_no_token(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/devices/token",
            json={"device_id": "made-up", "device_secret": "whatever"},
        )
        assert response.status_code == 401


class TestDeviceManagement:
    async def test_listing_shows_the_device_without_its_secret(self, client: AsyncClient):
        device_id, secret = await _enroll(client)

        response = await client.get("/api/auth/devices")

        assert response.status_code == 200
        listed = response.json()["devices"]
        assert [d["id"] for d in listed] == [device_id]
        assert listed[0]["name"] == "Redmi Note 13"
        assert listed[0]["platform"] == "android"
        assert secret not in response.text

    async def test_token_exchange_records_last_seen(self, client: AsyncClient):
        device_id, secret = await _enroll(client)
        assert (await client.get("/api/auth/devices")).json()["devices"][0]["last_seen_at"] is None

        await client.post(
            "/api/auth/devices/token",
            json={"device_id": device_id, "device_secret": secret},
        )

        listed = (await client.get("/api/auth/devices")).json()["devices"][0]
        assert listed["last_seen_at"] is not None

    async def test_revoked_device_cannot_get_a_new_token(self, client: AsyncClient):
        device_id, secret = await _enroll(client)

        revoke = await client.post(f"/api/auth/devices/{device_id}/revoke")
        assert revoke.status_code == 200

        response = await client.post(
            "/api/auth/devices/token",
            json={"device_id": device_id, "device_secret": secret},
        )
        assert response.status_code == 401

    async def test_revocation_invalidates_an_existing_token(self, client: AsyncClient):
        device_id, secret = await _enroll(client)
        token = (
            await client.post(
                "/api/auth/devices/token",
                json={"device_id": device_id, "device_secret": secret},
            )
        ).json()["token"]
        assert client._transport.app.state.auth.validate_token(token) is True  # type: ignore[union-attr]

        assert (await client.post(f"/api/auth/devices/{device_id}/revoke")).status_code == 200

        assert client._transport.app.state.auth.validate_token(token) is False  # type: ignore[union-attr]

    async def test_device_secret_verification_runs_off_event_loop(
        self, client: AsyncClient, app: FastAPI, monkeypatch
    ):
        import threading

        event_loop_thread = threading.get_ident()
        verification_thread = None

        def verify_secret(_device_id: str, _secret: str) -> bool:
            nonlocal verification_thread
            verification_thread = threading.get_ident()
            return False

        monkeypatch.setattr(app.state.auth.devices, "verify_secret", verify_secret)
        response = await client.post(
            "/api/auth/devices/token",
            json={"device_id": "device", "device_secret": "secret"},
        )

        assert response.status_code == 401
        assert verification_thread is not None
        assert verification_thread != event_loop_thread

    async def test_revoked_device_is_still_listed_as_revoked(self, client: AsyncClient):
        device_id, _ = await _enroll(client)
        await client.post(f"/api/auth/devices/{device_id}/revoke")

        listed = (await client.get("/api/auth/devices")).json()["devices"][0]

        assert listed["revoked"] is True
        assert listed["revoked_at"] is not None

    async def test_deleting_a_device_removes_it(self, client: AsyncClient):
        device_id, secret = await _enroll(client)

        assert (await client.delete(f"/api/auth/devices/{device_id}")).status_code == 200

        assert (await client.get("/api/auth/devices")).json()["devices"] == []
        response = await client.post(
            "/api/auth/devices/token",
            json={"device_id": device_id, "device_secret": secret},
        )
        assert response.status_code == 401

    async def test_revoking_an_unknown_device_is_404(self, client: AsyncClient):
        assert (await client.post("/api/auth/devices/nope/revoke")).status_code == 404
        assert (await client.delete("/api/auth/devices/nope")).status_code == 404


class TestAuthGating:
    """With auth on, only a session may pair or manage devices."""

    @pytest.fixture
    async def secured(self, bus: MessageBus, tmp_path: Path):
        from dax.web.auth import hash_password

        config = DaxConfig(
            security={
                "auth_enabled": True,
                "password_hash": hash_password("correct-horse"),
                "session_secret": "test-secret",
            },
            storage={"database_path": str(tmp_path / "dax.db")},
        )
        app = create_app(config=config, bus=bus)
        app.state.config = config
        app.state.bus = bus
        app.state.voice_listening = config.voice.enabled
        database = Database(str(tmp_path / "dax.db"))
        await database.start()
        registry = DeviceRegistry(database)
        await registry.load()
        app.state.auth.attach_devices(registry)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
        await database.stop()

    async def test_pairing_requires_a_session(self, secured: AsyncClient):
        assert (await secured.post("/api/auth/devices/pair")).status_code == 401

    async def test_listing_requires_a_session(self, secured: AsyncClient):
        assert (await secured.get("/api/auth/devices")).status_code == 401

    async def test_revocation_requires_a_session(self, secured: AsyncClient):
        assert (await secured.post("/api/auth/devices/x/revoke")).status_code == 401
        assert (await secured.delete("/api/auth/devices/x")).status_code == 401

    async def test_device_token_authenticates_the_api(self, secured: AsyncClient):
        """The whole point: a device token is a first-class credential."""
        login = await secured.post("/api/auth/login", json={"password": "correct-horse"})
        session = login.json()["token"]
        headers = {"Authorization": f"Bearer {session}"}

        code = (await secured.post("/api/auth/devices/pair", headers=headers)).json()["code"]
        enrolled = (
            await secured.post(
                "/api/auth/devices/enroll",
                json={"code": code, "name": "phone", "platform": "android"},
            )
        ).json()
        token = (
            await secured.post(
                "/api/auth/devices/token",
                json={
                    "device_id": enrolled["device_id"],
                    "device_secret": enrolled["device_secret"],
                },
            )
        ).json()["token"]

        response = await secured.get("/api/status", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    async def test_revoked_existing_token_cannot_authenticate_again(self, secured: AsyncClient):
        login = await secured.post("/api/auth/login", json={"password": "correct-horse"})
        session_headers = {"Authorization": f"Bearer {login.json()['token']}"}
        code = (
            await secured.post("/api/auth/devices/pair", headers=session_headers)
        ).json()["code"]
        enrolled = (
            await secured.post(
                "/api/auth/devices/enroll",
                json={"code": code, "name": "phone", "platform": "android"},
            )
        ).json()
        device_token = (
            await secured.post(
                "/api/auth/devices/token",
                json={
                    "device_id": enrolled["device_id"],
                    "device_secret": enrolled["device_secret"],
                },
            )
        ).json()["token"]
        device_headers = {"Authorization": f"Bearer {device_token}"}
        secured.cookies.clear()
        assert (await secured.get("/api/status", headers=device_headers)).status_code == 200

        revoke = await secured.post(
            f"/api/auth/devices/{enrolled['device_id']}/revoke", headers=session_headers
        )

        assert revoke.status_code == 200
        assert (await secured.get("/api/status", headers=device_headers)).status_code == 401

    async def _device_headers(self, secured: AsyncClient) -> dict[str, str]:
        login = await secured.post("/api/auth/login", json={"password": "correct-horse"})
        session_headers = {"Authorization": f"Bearer {login.json()['token']}"}
        code = (
            await secured.post("/api/auth/devices/pair", headers=session_headers)
        ).json()["code"]
        enrolled = (
            await secured.post(
                "/api/auth/devices/enroll",
                json={"code": code, "name": "phone", "platform": "android"},
            )
        ).json()
        token = (
            await secured.post(
                "/api/auth/devices/token",
                json={
                    "device_id": enrolled["device_id"],
                    "device_secret": enrolled["device_secret"],
                },
            )
        ).json()["token"]
        secured.cookies.clear()
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", "/api/auth/devices/pair"),
            ("GET", "/api/auth/devices"),
            ("GET", "/api/config"),
            ("GET", "/api/config/mcp/servers"),
            ("GET", "/api/memory"),
        ],
    )
    async def test_device_token_is_rejected_from_session_only_routes(
        self, secured: AsyncClient, method: str, path: str
    ):
        headers = await self._device_headers(secured)

        response = await secured.request(method, path, headers=headers)

        assert response.status_code == 401

    async def test_device_token_can_read_status_and_mobile_config(self, secured: AsyncClient):
        headers = await self._device_headers(secured)
        app = secured._transport.app  # type: ignore[union-attr]
        object.__setattr__(app.state.config.llm.openai, "api_key", "sk-never-return")

        status_response = await secured.get("/api/status", headers=headers)
        config_response = await secured.get("/api/mobile/config", headers=headers)

        assert status_response.status_code == 200
        assert config_response.status_code == 200
        payload = config_response.json()
        assert set(payload) == {"general", "llm", "voice"}
        assert payload["llm"]["openai_configured"] is True
        assert payload["voice"]["stt_openai_configured"] is True
        assert "sk-never-return" not in config_response.text
        assert "api_key" not in config_response.text
        assert "base_url" not in config_response.text
        assert "binary" not in config_response.text

    async def test_device_token_can_patch_safe_mobile_settings(self, secured: AsyncClient):
        headers = await self._device_headers(secured)
        app = secured._transport.app  # type: ignore[union-attr]

        llm = await secured.patch(
            "/api/mobile/config/llm",
            headers=headers,
            json={"ollama_model": "qwen3.5:4b", "max_tool_iterations": 12},
        )
        voice = await secured.patch(
            "/api/mobile/config/voice",
            headers=headers,
            json={"stt_language": "en", "vad_threshold": 0.6},
        )

        assert llm.status_code == voice.status_code == 200
        assert app.state.config.llm.ollama.model == "qwen3.5:4b"
        assert app.state.config.llm.max_tool_iterations == 12
        assert app.state.config.voice.stt_language == "en"
        assert app.state.config.voice.vad_threshold == 0.6

    @pytest.mark.parametrize(
        ("path", "body"),
        [
            ("/api/mobile/config/llm", {"openai_api_key": "sk-nope"}),
            ("/api/mobile/config/llm", {"ollama_base_url": "http://evil"}),
            ("/api/mobile/config/llm", {"codex_binary": "/tmp/codex"}),
            ("/api/mobile/config/voice", {"stt_openai_api_key": "sk-nope"}),
        ],
    )
    async def test_mobile_patches_reject_sensitive_fields(
        self, secured: AsyncClient, path: str, body: dict[str, str]
    ):
        headers = await self._device_headers(secured)

        response = await secured.patch(path, headers=headers, json=body)

        assert response.status_code == 422

    async def test_enrolment_still_needs_a_code_even_with_a_session(
        self, secured: AsyncClient
    ):
        login = await secured.post("/api/auth/login", json={"password": "correct-horse"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        response = await secured.post(
            "/api/auth/devices/enroll", json={"code": "BOGUS123"}, headers=headers
        )

        assert response.status_code == 401


class TestWithoutRegistry:
    """A server that never wired a registry must fail closed, not crash."""

    async def test_enrolment_reports_unavailable(self, bus: MessageBus, tmp_path: Path):
        config = DaxConfig(
            security={"auth_enabled": False},
            storage={"database_path": str(tmp_path / "dax.db")},
        )
        app = create_app(config=config, bus=bus)
        app.state.config = config
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            code = (await client.post("/api/auth/devices/pair")).json()["code"]
            enroll = await client.post("/api/auth/devices/enroll", json={"code": code})
            assert enroll.status_code == 503

            token = await client.post(
                "/api/auth/devices/token",
                json={"device_id": "x", "device_secret": "y"},
            )
            assert token.status_code == 503

            assert (await client.get("/api/auth/devices")).json()["devices"] == []
