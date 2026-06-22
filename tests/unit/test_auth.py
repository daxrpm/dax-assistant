"""Tests for single-user web authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
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
