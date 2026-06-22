"""End-to-end web flow: login → protected endpoints → tool audit.

Exercises the real FastAPI app, auth, and the API↔repository wiring together
(without external services), mirroring how the browser drives the backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from dax.core.config import DaxConfig
from dax.orchestrator.bus import MessageBus
from dax.storage.repository import ConversationRepository
from dax.web.auth import hash_password
from dax.web.server import create_app

if TYPE_CHECKING:
    from fastapi import FastAPI

    from dax.storage.database import Database

PASSWORD = "e2e-password"


@pytest.fixture
def app(database: Database) -> FastAPI:
    bus = MessageBus()
    bus.start()
    config = DaxConfig(
        security={
            "auth_enabled": True,
            "password_hash": hash_password(PASSWORD),
            "session_secret": "e2e-secret-" + "z" * 32,
        }
    )
    fastapi_app = create_app(config=config, bus=bus)
    fastapi_app.state.config = config
    fastapi_app.state.bus = bus
    fastapi_app.state.voice_listening = config.voice.enabled
    # Wire the repository the way DaxApp.start() does, over the temp DB.
    fastapi_app.state.repository = ConversationRepository(database)
    return fastapi_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


async def test_full_web_flow(client: AsyncClient, database: Database):
    # 1. Unauthenticated: protected endpoints are blocked.
    assert (await client.get("/api/status")).status_code == 401
    assert (await client.get("/api/tools/audit")).status_code == 401

    # 2. Auth status is public and reports an unauthenticated, configured app.
    status = (await client.get("/api/auth/status")).json()
    assert status["auth_enabled"] is True
    assert status["configured"] is True
    assert status["authenticated"] is False

    # 3. Log in — the session cookie is stored in the client jar.
    login = await client.post("/api/auth/login", json={"password": PASSWORD})
    assert login.status_code == 200 and login.json()["ok"] is True

    # 4. Protected endpoints now work.
    assert (await client.get("/api/status")).status_code == 200
    policy = (await client.get("/api/tools/policy")).json()
    assert policy["default"] == "allow"

    # 5. Audit starts empty, reflects a logged execution.
    assert (await client.get("/api/tools/audit")).json() == []
    repo = ConversationRepository(database)
    await repo.log_tool_execution(
        server_name="dax-system",
        tool_name="fs_write",
        arguments={"path": "/tmp/e2e"},
        status="approved",
    )
    audit = (await client.get("/api/tools/audit")).json()
    assert len(audit) == 1
    assert audit[0]["tool_name"] == "fs_write"
    assert audit[0]["status"] == "approved"

    # 6. Logout invalidates the session.
    await client.post("/api/auth/logout")
    assert (await client.get("/api/status")).status_code == 401
