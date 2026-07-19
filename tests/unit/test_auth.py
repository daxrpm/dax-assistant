"""Tests for single-user web authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from dax.core.config import DaxConfig
from dax.orchestrator.bus import MessageBus
from dax.web.auth import AuthManager, hash_password, verify_password
from dax.web.server import create_app

if TYPE_CHECKING:
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

    async def test_bearer_token_authenticates_without_cookie(
        self, auth_app: FastAPI
    ) -> None:
        transport = ASGITransport(app=auth_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login = await ac.post("/api/auth/login", json={"password": PASSWORD})
            token = login.json()["token"]

        # A brand-new client — no cookie jar at all, only the bearer header.
        async with AsyncClient(transport=transport, base_url="http://test") as bare:
            assert (await bare.get("/api/status")).status_code == 401
            resp = await bare.get(
                "/api/status", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 200

    async def test_bearer_reported_in_auth_status(self, auth_app: FastAPI) -> None:
        transport = ASGITransport(app=auth_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            token = (
                await ac.post("/api/auth/login", json={"password": PASSWORD})
            ).json()["token"]
        async with AsyncClient(transport=transport, base_url="http://test") as bare:
            data = (
                await bare.get(
                    "/api/auth/status", headers={"Authorization": f"Bearer {token}"}
                )
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
            token = (
                await ac.post("/api/auth/login", json={"password": PASSWORD})
            ).json()["token"]

        auth: AuthManager = auth_app.state.auth
        async with AsyncClient(transport=transport, base_url="http://test") as bare:
            bare.cookies.set(auth.cookie_name, "stale-and-invalid")
            assert (await bare.get("/api/status")).status_code == 401
            resp = await bare.get(
                "/api/status", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 200

    async def test_cookie_still_works_when_bearer_is_junk(
        self, auth_client: AsyncClient
    ) -> None:
        """Regression guard: the existing web UI must keep working."""
        await auth_client.post("/api/auth/login", json={"password": PASSWORD})
        resp = await auth_client.get(
            "/api/status", headers={"Authorization": "Bearer nonsense"}
        )
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


def test_desktop_webview_origin_is_allowed_by_default():
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
            "Origin": "tauri://localhost",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "tauri://localhost"
