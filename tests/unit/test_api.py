"""Tests for the REST API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from dax.core.config import DaxConfig
from dax.orchestrator.bus import MessageBus
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
def app(bus: MessageBus) -> FastAPI:
    # These tests exercise the endpoints themselves; auth is covered separately
    # in test_auth.py, so disable it here.
    config = DaxConfig(security={"auth_enabled": False})
    fastapi_app = create_app(config=config, bus=bus)
    # Manually set state since ASGITransport skips lifespan
    fastapi_app.state.config = config
    fastapi_app.state.bus = bus
    fastapi_app.state.voice_listening = config.voice.enabled
    return fastapi_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


class TestStatusEndpoint:
    async def test_get_status(self, client: AsyncClient):
        response = await client.get("/api/status")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Dax"
        assert data["version"] == "0.1.0"
        assert data["status"] == "running"
        assert isinstance(data["voice_listening"], bool)
        assert data["llm_provider"] == "ollama"

    async def test_status_fields(self, client: AsyncClient):
        response = await client.get("/api/status")
        data = response.json()
        required_fields = {
            "name", "version", "status", "voice_listening",
            "llm_provider", "mcp_servers", "mcp_tools",
        }
        assert required_fields.issubset(data.keys())


class TestVoiceToggle:
    async def test_toggle_on(self, client: AsyncClient):
        response = await client.post(
            "/api/voice/toggle",
            json={"enabled": True},
        )
        assert response.status_code == 200
        assert response.json()["voice_listening"] is True

    async def test_toggle_off(self, client: AsyncClient):
        response = await client.post(
            "/api/voice/toggle",
            json={"enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["voice_listening"] is False

    async def test_toggle_invalid_body(self, client: AsyncClient):
        response = await client.post(
            "/api/voice/toggle",
            json={"wrong_field": True},
        )
        assert response.status_code == 422


class TestConfigEndpoint:
    async def test_get_config(self, client: AsyncClient):
        response = await client.get("/api/config")
        assert response.status_code == 200

        data = response.json()
        assert data["general"]["name"] == "Dax"
        assert "voice" in data
        assert "llm" in data
        assert "web" in data
        assert "whatsapp" in data
        assert "mcp" in data

    async def test_config_hides_secrets(self, client: AsyncClient):
        response = await client.get("/api/config")
        data = response.json()

        # Raw API key values should NOT be in the response
        config_str = str(data)
        assert "evolution_api_key" not in config_str
        # gemini_configured and has_api_key are booleans, not key values
        assert data["llm"]["gemini_configured"] is False
        assert data["whatsapp"]["has_api_key"] is False


class TestConfigUpdate:
    async def test_update_general(self, client: AsyncClient, tmp_path: Path):
        # Set config path so save doesn't fail
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]

        response = await client.patch(
            "/api/config/general",
            json={"name": "TestBot", "log_level": "DEBUG"},
        )
        assert response.status_code == 200

        # Verify config was updated in memory
        cfg_response = await client.get("/api/config")
        assert cfg_response.json()["general"]["name"] == "TestBot"
        assert cfg_response.json()["general"]["log_level"] == "DEBUG"

    async def test_update_llm(self, client: AsyncClient, tmp_path: Path):
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]

        response = await client.patch(
            "/api/config/llm",
            json={"ollama_model": "qwen3.5:4b"},
        )
        assert response.status_code == 200

        cfg = await client.get("/api/config")
        assert cfg.json()["llm"]["ollama_model"] == "qwen3.5:4b"


class TestMCPServers:
    async def test_list_empty(self, client: AsyncClient):
        response = await client.get("/api/config/mcp/servers")
        assert response.status_code == 200
        assert response.json() == {}

    async def test_add_server(self, client: AsyncClient, tmp_path: Path):
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]

        response = await client.post(
            "/api/config/mcp/servers",
            json={
                "name": "shell",
                "command": "uvx",
                "args": ["mcp-shell-server"],
                "env": {"ALLOWED_COMMANDS": "ls,date"},
            },
        )
        assert response.status_code == 200
        assert response.json()["name"] == "shell"

        # Verify it appears in the list
        servers = await client.get("/api/config/mcp/servers")
        assert "shell" in servers.json()

    async def test_add_duplicate_server(
        self, client: AsyncClient, tmp_path: Path,
    ):
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]

        body = {"name": "test", "command": "echo"}
        await client.post("/api/config/mcp/servers", json=body)
        response = await client.post("/api/config/mcp/servers", json=body)
        assert response.status_code == 409

    async def test_delete_server(
        self, client: AsyncClient, tmp_path: Path,
    ):
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]

        await client.post(
            "/api/config/mcp/servers",
            json={"name": "to_delete", "command": "echo"},
        )

        response = await client.delete(
            "/api/config/mcp/servers/to_delete",
        )
        assert response.status_code == 200

        servers = await client.get("/api/config/mcp/servers")
        assert "to_delete" not in servers.json()

    async def test_delete_nonexistent(self, client: AsyncClient):
        response = await client.delete(
            "/api/config/mcp/servers/nonexistent",
        )
        assert response.status_code == 404
