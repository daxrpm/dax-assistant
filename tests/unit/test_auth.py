"""Tests for single-user web authentication."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from dax.core.config import DaxConfig
from dax.orchestrator.bus import MessageBus
from dax.web.auth import AttemptLimiter, AuthManager, hash_password, verify_password
from dax.web.server import create_app

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import FastAPI

PASSWORD = "correct horse battery staple"


def test_hash_and_verify_password():
    h = hash_password(PASSWORD)
    assert h != PASSWORD
    assert verify_password(h, PASSWORD)
    assert not verify_password(h, "wrong")
    assert not verify_password("", PASSWORD)


def test_token_roundtrip():
    cfg = DaxConfig(
        security={"password_hash": hash_password(PASSWORD), "session_secret": "x" * 40}
    )
    mgr = AuthManager(cfg.security)
    token = mgr.issue_token()
    assert mgr.validate_token(token)
    assert not mgr.validate_token("garbage")
    assert not mgr.validate_token(None)
    assert mgr.is_session_token(token)


def test_attempt_limiter_is_bounded_global_and_expires():
    now = 100.0
    limiter = AttemptLimiter(max_client_keys=2, clock=lambda: now)

    assert limiter.check("login", "one", client_limit=2, global_limit=3) is None
    assert limiter.check("login", "two", client_limit=2, global_limit=3) is None
    assert limiter.check("login", "three", client_limit=2, global_limit=3) is None
    assert limiter.client_key_count == 2
    assert limiter.check("login", "rotated", client_limit=2, global_limit=3) == 60

    now += 61
    assert limiter.check("login", "rotated", client_limit=2, global_limit=3) is None


@pytest.fixture
def auth_app() -> FastAPI:
    bus = MessageBus()
    bus.start()
    config = DaxConfig(
        security={
            "auth_enabled": True,
            "password_hash": hash_password(PASSWORD),
            "session_secret": "test-secret-" + "y" * 32,
        }
    )
    app = create_app(config=config, bus=bus)
    app.state.config = config
    app.state.bus = bus
    app.state.voice_listening = config.voice.enabled
    return app


@pytest.fixture
async def auth_client(auth_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


class TestAuthFlow:
    async def test_health_endpoint_is_public(self, auth_client: AsyncClient):
        response = await auth_client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_protected_route_requires_auth(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/status")
        assert resp.status_code == 401

    async def test_host_metrics_require_auth(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/system/metrics")
        assert resp.status_code == 401

    async def test_push_to_talk_requires_auth(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/voice/push-to-talk/press")
        assert resp.status_code == 401

    async def test_status_endpoint_is_public(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_enabled"] is True
        assert data["configured"] is True
        assert data["authenticated"] is False

    async def test_wrong_password_rejected(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/auth/login", json={"password": "nope"})
        assert resp.status_code == 401
        assert resp.json()["ok"] is False

    async def test_login_verification_runs_off_event_loop(
        self, auth_client: AsyncClient, auth_app: FastAPI, monkeypatch
    ):
        import threading

        event_loop_thread = threading.get_ident()
        verification_thread = None

        def verify_login(_password: str) -> bool:
            nonlocal verification_thread
            verification_thread = threading.get_ident()
            return False

        monkeypatch.setattr(auth_app.state.auth, "verify_login", verify_login)
        await auth_client.post("/api/auth/login", json={"password": "wrong"})

        assert verification_thread is not None
        assert verification_thread != event_loop_thread

    async def test_login_password_size_is_limited(self, auth_client: AsyncClient):
        response = await auth_client.post("/api/auth/login", json={"password": "x" * 1025})
        assert response.status_code == 422

    async def test_login_then_access(self, auth_client: AsyncClient):
        login = await auth_client.post("/api/auth/login", json={"password": PASSWORD})
        assert login.status_code == 200
        assert login.json()["ok"] is True
        # Cookie jar now carries the session — protected route works.
        resp = await auth_client.get("/api/status")
        assert resp.status_code == 200

    async def test_logout_clears_session(self, auth_client: AsyncClient):
        await auth_client.post("/api/auth/login", json={"password": PASSWORD})
        assert (await auth_client.get("/api/status")).status_code == 200
        await auth_client.post("/api/auth/logout")
        assert (await auth_client.get("/api/status")).status_code == 401


class TestInitialSetup:
    @staticmethod
    def _app(tmp_path: Path) -> FastAPI:
        bus = MessageBus()
        bus.start()
        config = DaxConfig(
            security={"auth_enabled": True, "session_secret": "setup-secret"},
            storage={"database_path": str(tmp_path / "setup.db")},
        )
        app = create_app(config=config, bus=bus)
        app.state.config = config
        app.state.bus = bus
        return app

    async def test_remote_request_cannot_claim_initial_setup(self, tmp_path: Path):
        app = self._app(tmp_path)
        transport = ASGITransport(app=app, client=("203.0.113.10", 1234))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/setup", json={"password": PASSWORD})

        assert response.status_code == 403
        assert app.state.auth.configured is False

    async def test_only_one_concurrent_setup_request_can_win(self, tmp_path: Path):
        app = self._app(tmp_path)
        transport = ASGITransport(app=app, client=("127.0.0.1", 1234))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first, second = await asyncio.gather(
                client.post("/api/auth/setup", json={"password": PASSWORD}),
                client.post(
                    "/api/auth/setup",
                    json={"password": "another sufficiently long password"},
                ),
            )

        assert sorted((first.status_code, second.status_code)) == [200, 409]
        assert sum(response.json()["ok"] for response in (first, second)) == 1

    async def test_unknown_client_cannot_claim_initial_setup(self, tmp_path: Path):
        app = self._app(tmp_path)
        transport = ASGITransport(app=app, client=None)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/setup", json={"password": PASSWORD})

        assert response.status_code == 403
        assert app.state.auth.configured is False

    async def test_loopback_setup_hashes_off_event_loop(
        self, tmp_path: Path, monkeypatch
    ):
        import threading

        app = self._app(tmp_path)
        event_loop_thread = threading.get_ident()
        hashing_thread = None

        def fake_hash(_password: str) -> str:
            nonlocal hashing_thread
            hashing_thread = threading.get_ident()
            return "test-password-hash"

        monkeypatch.setattr("dax.web.routes.auth.hash_password", fake_hash)
        transport = ASGITransport(app=app, client=("127.0.0.1", 1234))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/setup", json={"password": PASSWORD})

        assert response.status_code == 200
        assert response.json()["token"]
        assert app.state.auth.configured is True
        assert hashing_thread is not None
        assert hashing_thread != event_loop_thread

class TestBearerToken:
    """The desktop client can't rely on a SameSite=lax cookie from a webview
    custom-protocol origin, so login hands back the token for bearer use."""

    async def test_login_returns_token(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/auth/login", json={"password": PASSWORD})
        assert resp.status_code == 200
        token = resp.json()["token"]
        assert isinstance(token, str) and token

    async def test_failed_login_returns_no_token(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/auth/login", json={"password": "nope"})
        assert resp.status_code == 401
        assert resp.json()["token"] is None

    async def test_bearer_token_authenticates_without_cookie(self, auth_app: FastAPI) -> None:
        transport = ASGITransport(app=auth_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login = await ac.post("/api/auth/login", json={"password": PASSWORD})
            token = login.json()["token"]

        # A brand-new client — no cookie jar at all, only the bearer header.
        async with AsyncClient(transport=transport, base_url="http://test") as bare:
            assert (await bare.get("/api/status")).status_code == 401
            resp = await bare.get("/api/status", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200

    async def test_bearer_authenticates_push_to_talk(self, auth_app: FastAPI) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        transport = ASGITransport(app=auth_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            token = (await ac.post("/api/auth/login", json={"password": PASSWORD})).json()["token"]
        auth_app.state.voice_pipeline = SimpleNamespace(
            push_to_talk_press=MagicMock(return_value="listening")
        )

        async with AsyncClient(transport=transport, base_url="http://test") as bare:
            response = await bare.post(
                "/api/voice/push-to-talk/press",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        assert response.json()["state"] == "listening"

    async def test_bearer_reported_in_auth_status(self, auth_app: FastAPI) -> None:
        transport = ASGITransport(app=auth_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            token = (await ac.post("/api/auth/login", json={"password": PASSWORD})).json()["token"]
        async with AsyncClient(transport=transport, base_url="http://test") as bare:
            data = (
                await bare.get("/api/auth/status", headers={"Authorization": f"Bearer {token}"})
            ).json()
            assert data["authenticated"] is True

    async def test_garbage_bearer_rejected(self, auth_client: AsyncClient):
        for header in ("Bearer garbage", "Bearer ", "Basic abc", "garbage"):
            resp = await auth_client.get("/api/status", headers={"Authorization": header})
            assert resp.status_code == 401, header

    async def test_valid_bearer_survives_a_stale_cookie(self, auth_app: FastAPI) -> None:
        """A cookie left over from a previous session must not shadow a good
        bearer token — auth accepts if *any* offered credential validates."""
        transport = ASGITransport(app=auth_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            token = (await ac.post("/api/auth/login", json={"password": PASSWORD})).json()["token"]

        auth: AuthManager = auth_app.state.auth
        async with AsyncClient(transport=transport, base_url="http://test") as bare:
            bare.cookies.set(auth.cookie_name, "stale-and-invalid")
            assert (await bare.get("/api/status")).status_code == 401
            resp = await bare.get("/api/status", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200

    async def test_cookie_still_works_when_bearer_is_junk(self, auth_client: AsyncClient) -> None:
        """Regression guard: the existing web UI must keep working."""
        await auth_client.post("/api/auth/login", json={"password": PASSWORD})
        resp = await auth_client.get("/api/status", headers={"Authorization": "Bearer nonsense"})
        assert resp.status_code == 200


class TestWebSocketAuthCredentials:
    """`authenticate_websocket` accepts cookie, ?token=, or bearer header."""

    @staticmethod
    def _manager() -> AuthManager:
        cfg = DaxConfig(
            security={
                "auth_enabled": True,
                "password_hash": hash_password(PASSWORD),
                "session_secret": "ws-secret-" + "z" * 32,
            }
        )
        return AuthManager(cfg.security)

    def _fake_ws(self, *, cookies=None, query=None, headers=None):
        from types import SimpleNamespace

        return SimpleNamespace(
            cookies=cookies or {},
            query_params=query or {},
            headers=headers or {},
        )

    def test_query_param_token_accepted(self):
        mgr = self._manager()
        token = mgr.issue_token()
        ws = self._fake_ws(query={"token": token})
        assert mgr.authenticate_websocket(ws)  # type: ignore[arg-type]

    def test_bearer_header_accepted(self):
        mgr = self._manager()
        token = mgr.issue_token()
        ws = self._fake_ws(headers={"authorization": f"Bearer {token}"})
        assert mgr.authenticate_websocket(ws)  # type: ignore[arg-type]

    def test_cookie_accepted(self):
        mgr = self._manager()
        token = mgr.issue_token()
        ws = self._fake_ws(cookies={mgr.cookie_name: token})
        assert mgr.authenticate_websocket(ws)  # type: ignore[arg-type]

    def test_stale_cookie_does_not_shadow_query_token(self):
        mgr = self._manager()
        token = mgr.issue_token()
        ws = self._fake_ws(cookies={mgr.cookie_name: "stale"}, query={"token": token})
        assert mgr.authenticate_websocket(ws)  # type: ignore[arg-type]

    def test_no_credentials_rejected(self):
        mgr = self._manager()
        assert not mgr.authenticate_websocket(self._fake_ws())  # type: ignore[arg-type]

    def test_auth_disabled_allows_everything(self):
        cfg = DaxConfig(security={"auth_enabled": False})
        mgr = AuthManager(cfg.security)
        assert mgr.authenticate_websocket(self._fake_ws())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "origin",
    [
        "tauri://localhost",
        "http://localhost:5273",
        "http://127.0.0.1:5273",
    ],
)
def test_desktop_webview_origin_is_allowed_by_default(origin: str):
    """A fresh install must serve the desktop app without config changes.

    The webview's origin is not configurable on the client side, so leaving it
    to `web.cors_origins` made a clean install fail every request with 400
    "Disallowed CORS origin" — and any settings save from the running app
    rewrites the whole config document, silently reverting a manual entry.
    """
    bus = MessageBus()
    bus.start()
    config = DaxConfig(
        security={"password_hash": hash_password(PASSWORD), "session_secret": "x" * 40}
    )
    # Deliberately does NOT list any desktop origin.
    assert "tauri://localhost" not in config.web.cors_origins

    app = create_app(config=config, bus=bus)
    client = TestClient(app)

    response = client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
