"""Tests for the REST API endpoints."""

from __future__ import annotations

import io
import wave
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from dax.channels.web_channel import WebChannel
from dax.core.config import DaxConfig
from dax.core.models import ChannelType, Message, MessageRole
from dax.orchestrator.bus import MessageBus
from dax.voice.pipeline import PipelineState
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
def app(bus: MessageBus, tmp_path: Path) -> FastAPI:
    # These tests exercise the endpoints themselves; auth is covered separately
    # in test_auth.py, so disable it here.
    config = DaxConfig(
        security={"auth_enabled": False},
        storage={"database_path": str(tmp_path / "dax.db")},
    )
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
            "name",
            "version",
            "status",
            "voice_listening",
            "llm_provider",
            "mcp_servers",
            "mcp_tools",
        }
        assert required_fields.issubset(data.keys())

    async def test_host_metrics_are_aggregate(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr("dax.web.routes.system.psutil.cpu_percent", lambda **_: 12.5)
        monkeypatch.setattr("dax.web.routes.system.psutil.cpu_count", lambda: 8)
        monkeypatch.setattr(
            "dax.web.routes.system.psutil.virtual_memory",
            lambda: SimpleNamespace(total=1000, used=600, available=400, percent=60.0),
        )
        monkeypatch.setattr(
            "dax.web.routes.system.psutil.disk_usage",
            lambda _path: SimpleNamespace(total=2000, used=500, free=1500, percent=25.0),
        )
        monkeypatch.setattr("dax.web.routes.system.psutil.boot_time", lambda: 100.0)
        monkeypatch.setattr("dax.web.routes.system.time.time", lambda: 223.5)

        response = await client.get("/api/system/metrics")

        assert response.status_code == 200
        assert response.json() == {
            "cpu_percent": 12.5,
            "cpu_count": 8,
            "memory": {
                "total_bytes": 1000,
                "used_bytes": 600,
                "available_bytes": 400,
                "percent": 60.0,
            },
            "disk": {
                "total_bytes": 2000,
                "used_bytes": 500,
                "available_bytes": 1500,
                "percent": 25.0,
            },
            "uptime_seconds": 123.5,
        }


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


class TestPushToTalkAPI:
    async def test_press_and_release_reach_local_pipeline(self, client: AsyncClient):
        app = client._transport.app  # type: ignore[union-attr]
        pipeline = SimpleNamespace(
            push_to_talk_press=MagicMock(return_value=PipelineState.LISTENING),
            push_to_talk_release=MagicMock(return_value=PipelineState.PROCESSING),
        )
        app.state.voice_pipeline = pipeline

        pressed = await client.post("/api/voice/push-to-talk/press")
        released = await client.post("/api/voice/push-to-talk/release")

        assert pressed.json() == {"status": "ok", "state": "listening"}
        assert released.json() == {"status": "ok", "state": "processing"}
        pipeline.push_to_talk_press.assert_called_once_with()
        pipeline.push_to_talk_release.assert_called_once_with()

    async def test_unavailable_voice_degrades_with_clear_503(self, client: AsyncClient):
        response = await client.post("/api/voice/push-to-talk/press")

        assert response.status_code == 503
        assert "Local voice input is unavailable" in response.json()["detail"]


def _wav_recording(sample_rate: int = 16_000, seconds: int = 2) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        tone = np.full(sample_rate * seconds, 1200, dtype="<i2")
        wav.writeframes(tone.tobytes())
    return output.getvalue()


class TestVoiceStudio:
    async def test_enrolls_three_wav_samples_and_reloads(
        self,
        client: AsyncClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        app = client._transport.app  # type: ignore[union-attr]
        object.__setattr__(app.state.config.storage, "models_path", str(tmp_path))
        app.state.dax_app = SimpleNamespace(reload_voice=AsyncMock())
        verifier = MagicMock()
        verifier.encoder_ready = True
        verifier.enroll.return_value = True
        monkeypatch.setattr(
            "dax.web.routes.voice.SpeakerVerifier", MagicMock(return_value=verifier)
        )
        recording = _wav_recording()

        response = await client.post(
            "/api/voice/enroll",
            files=[
                ("samples", (f"sample-{index}.wav", recording, "audio/wav")) for index in range(3)
            ],
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "enrolled": True, "samples": 3}
        assert verifier.enroll.call_count == 1
        app.state.dax_app.reload_voice.assert_awaited_once()

    async def test_rejects_wrong_enrollment_sample_rate(self, client: AsyncClient):
        recording = _wav_recording(sample_rate=44_100)
        response = await client.post(
            "/api/voice/enroll",
            files=[
                ("samples", (f"sample-{index}.wav", recording, "audio/wav")) for index in range(3)
            ],
        )

        assert response.status_code == 422
        assert "16 kHz" in response.json()["detail"]

    async def test_profile_status_and_delete(
        self,
        client: AsyncClient,
        tmp_path: Path,
    ):
        app = client._transport.app  # type: ignore[union-attr]
        object.__setattr__(app.state.config.storage, "models_path", str(tmp_path))
        profile = tmp_path / "voice_profile.npy"
        profile.write_bytes(b"profile")

        assert (await client.get("/api/voice/profile")).json()["enrolled"] is True
        response = await client.delete("/api/voice/profile")

        assert response.status_code == 200
        assert response.json()["enrolled"] is False
        assert not profile.exists()

    async def test_returns_wav_voice_preview(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        engine = MagicMock()
        engine.sample_rate = 24_000
        engine.synthesize.return_value = np.arange(240, dtype=np.int16)
        monkeypatch.setattr("dax.web.routes.voice._build_preview_engine", lambda *_: engine)

        response = await client.post(
            "/api/voice/preview",
            json={"engine": "kokoro", "voice": "em_alex"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert response.content.startswith(b"RIFF")
        engine.start.assert_called_once()
        engine.stop.assert_called_once()


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
        assert data["voice"]["stt_backend"] == "local"
        assert data["voice"]["stt_openai_model"] == "gpt-4o-mini-transcribe"
        assert isinstance(data["voice"]["stt_openai_configured"], bool)
        assert data["general"]["system_prompt"]
        assert data["general"]["system_prompt_custom"] is False

    async def test_config_hides_secrets(self, client: AsyncClient):
        app = client._transport.app  # type: ignore[union-attr]
        object.__setattr__(app.state.config.llm.openai, "api_key", "sk-private")
        object.__setattr__(app.state.config.whatsapp, "evolution_api_key", "wa-private")
        response = await client.get("/api/config")
        data = response.json()

        config_str = str(data)
        assert "sk-private" not in config_str
        assert "wa-private" not in config_str
        assert data["llm"]["openai_api_key"] == "********"
        assert data["whatsapp"]["evolution_api_key"] == "********"
        assert data["llm"]["gemini_configured"] is False
        assert data["whatsapp"]["has_api_key"] is True


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

    async def test_system_prompt_updates_live_and_resets(self, client: AsyncClient):
        app = client._transport.app  # type: ignore[union-attr]
        dax_app = SimpleNamespace(set_system_prompt=MagicMock())
        app.state.dax_app = dax_app

        response = await client.patch(
            "/api/config/general", json={"system_prompt": "Be concise and precise."}
        )

        assert response.status_code == 200
        assert app.state.config.system_prompt == "Be concise and precise."
        dax_app.set_system_prompt.assert_called_once_with("Be concise and precise.")

        reset = await client.post("/api/config/general/system-prompt/reset")
        assert reset.status_code == 200
        assert reset.json()["system_prompt"]
        assert app.state.config.system_prompt == ""
        dax_app.set_system_prompt.assert_called_with("")

    async def test_system_prompt_rejects_blank(self, client: AsyncClient):
        response = await client.patch("/api/config/general", json={"system_prompt": "   "})
        assert response.status_code == 422

    async def test_update_llm(self, client: AsyncClient, tmp_path: Path):
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]

        response = await client.patch(
            "/api/config/llm",
            json={"ollama_model": "qwen3.5:4b"},
        )
        assert response.status_code == 200

        cfg = await client.get("/api/config")
        assert cfg.json()["llm"]["ollama_model"] == "qwen3.5:4b"

    async def test_update_registry_config_fields(self, client: AsyncClient):
        voice = await client.patch(
            "/api/config/voice",
            json={"conversation_timeout_question_s": 35, "session_ttl_minutes": 15},
        )
        llm = await client.patch(
            "/api/config/llm",
            json={"max_tool_iterations": 12, "openai_timeout": 90},
        )
        web = await client.patch("/api/config/web", json={"dev_mode": True})

        assert voice.status_code == llm.status_code == web.status_code == 200
        data = (await client.get("/api/config")).json()
        assert data["voice"]["conversation_timeout_question_s"] == 35
        assert data["voice"]["session_ttl_minutes"] == 15
        assert data["llm"]["max_tool_iterations"] == 12
        assert data["llm"]["openai_timeout"] == 90
        assert data["web"]["dev_mode"] is True
        assert "database_path" in data["storage"]

    @pytest.mark.parametrize("submitted", ["", "********"])
    async def test_masked_secret_patch_preserves_key(
        self, client: AsyncClient, submitted: str
    ):
        app = client._transport.app  # type: ignore[union-attr]
        object.__setattr__(app.state.config.llm.openai, "api_key", "sk-existing")

        response = await client.patch(
            "/api/config/llm", json={"openai_api_key": submitted}
        )

        assert response.status_code == 200
        assert app.state.config.llm.openai.api_key == "sk-existing"

    async def test_update_llm_rebuilds_router(
        self,
        client: AsyncClient,
        tmp_path: Path,
    ):
        from dax.llm.factory import build_router

        app = client._transport.app  # type: ignore[union-attr]
        app.state.config_path = tmp_path / "dax.toml"
        router = build_router(app.state.config.llm)
        app.state.llm_router = router
        assert router.name == "ollama"

        # Switching the provider in the web UI must take effect on the live
        # router (held by the agent) without a restart.
        response = await client.patch(
            "/api/config/llm",
            json={
                "default_provider": "openai",
                "openai_api_key": "sk-test",
                "fallback_order": [],
            },
        )
        assert response.status_code == 200
        assert router.name == "openai"
        assert "ollama" not in router.provider_names

    async def test_update_hosted_voice_config_and_encrypt_key(
        self,
        client: AsyncClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = client._transport.app  # type: ignore[union-attr]
        app.state.config_path = tmp_path / "dax.toml"
        object.__setattr__(app.state.config.storage, "database_path", str(tmp_path / "dax.db"))

        response = await client.patch(
            "/api/config/voice",
            json={
                "stt_backend": "openai",
                "stt_openai_model": "whisper-1",
                "stt_openai_api_key": "sk-voice-test",
                "stt_fallback_to_local": True,
            },
        )

        assert response.status_code == 200
        config = (await client.get("/api/config")).json()
        assert config["voice"]["stt_backend"] == "openai"
        assert config["voice"]["stt_openai_model"] == "whisper-1"
        assert config["voice"]["stt_openai_configured"] is True
        from dax.storage.secrets import SecretStore

        store = SecretStore(str(tmp_path / "dax.db"))
        assert store.get("OPENAI_API_KEY") == "sk-voice-test"
        assert not (tmp_path / "dax.toml").exists()

    async def test_rejects_unknown_voice_backend(self, client: AsyncClient):
        response = await client.patch("/api/config/voice", json={"stt_backend": "unknown"})
        assert response.status_code == 422

    async def test_identical_voice_patch_does_not_reload(self, client: AsyncClient):
        app = client._transport.app  # type: ignore[union-attr]
        dax_app = SimpleNamespace(reload_voice=AsyncMock())
        app.state.dax_app = dax_app

        response = await client.patch("/api/config/voice", json={"stt_backend": "local"})

        assert response.status_code == 200
        assert response.json()["note"] == "Voice configuration unchanged"
        dax_app.reload_voice.assert_not_awaited()

    async def test_voice_patch_reloads_live_pipeline(
        self,
        client: AsyncClient,
        tmp_path: Path,
    ):
        from dax.storage.secrets import SecretStore

        app = client._transport.app  # type: ignore[union-attr]
        app.state.config_path = tmp_path / "dax.toml"
        app.state.secret_store = SecretStore(str(tmp_path / "dax.db"))
        dax_app = SimpleNamespace(reload_voice=AsyncMock())
        app.state.dax_app = dax_app

        response = await client.patch(
            "/api/config/voice",
            json={
                "tts_engine": "piper",
                "tts_voice_es": "es_ES-sharvard-medium",
                "speaker_threshold": 0.72,
            },
        )

        assert response.status_code == 200
        assert response.json()["note"] == "Voice pipeline reloaded"
        dax_app.reload_voice.assert_awaited_once()
        voice = (await client.get("/api/config")).json()["voice"]
        assert voice["tts_engine"] == "piper"
        assert voice["tts_voice_es"] == "es_ES-sharvard-medium"
        assert voice["speaker_threshold"] == 0.72

    async def test_failed_voice_reload_rolls_back_config(
        self,
        client: AsyncClient,
        tmp_path: Path,
    ):
        from dax.storage.secrets import SecretStore

        app = client._transport.app  # type: ignore[union-attr]
        app.state.config_path = tmp_path / "dax.toml"
        app.state.secret_store = SecretStore(str(tmp_path / "dax.db"))
        app.state.dax_app = SimpleNamespace(
            reload_voice=AsyncMock(side_effect=RuntimeError("audio busy"))
        )

        response = await client.patch("/api/config/voice", json={"stt_language": "en"})

        assert response.status_code == 400
        voice = (await client.get("/api/config")).json()["voice"]
        assert voice["stt_language"] == "es"


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
        self,
        client: AsyncClient,
        tmp_path: Path,
    ):
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]

        body = {"name": "test", "command": "echo"}
        await client.post("/api/config/mcp/servers", json=body)
        response = await client.post("/api/config/mcp/servers", json=body)
        assert response.status_code == 409

    async def test_delete_server(
        self,
        client: AsyncClient,
        tmp_path: Path,
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

    async def test_mcp_secrets_are_masked_and_preserved(
        self,
        client: AsyncClient,
    ):
        await client.post(
            "/api/config/mcp/servers",
            json={
                "name": "private",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "env": {"API_TOKEN": "env-secret"},
                "headers": {"Authorization": "Bearer header-secret"},
            },
        )

        listed = (await client.get("/api/config/mcp/servers")).json()["private"]
        assert listed["env"] == {"API_TOKEN": "********"}
        assert listed["headers"] == {"Authorization": "********"}

        listed["enabled"] = False
        response = await client.patch("/api/config/mcp/servers/private", json=listed)

        assert response.status_code == 200
        app = client._transport.app  # type: ignore[union-attr]
        server = app.state.config.mcp.servers["private"]
        assert server.env["API_TOKEN"] == "env-secret"
        assert server.headers["Authorization"] == "Bearer header-secret"


class TestNewEndpoints:
    async def test_config_includes_security_and_tools(self, client: AsyncClient):
        data = (await client.get("/api/config")).json()
        assert "security" in data
        assert data["security"]["auth_enabled"] is False  # test fixture disables auth
        assert "tools" in data
        assert "policy" in data["tools"]
        assert data["tools"]["policy"]["default"] == "allow"

    async def test_logs_empty_without_buffer(self, client: AsyncClient):
        assert (await client.get("/api/logs")).json() == []

    async def test_mcp_status_empty_without_manager(self, client: AsyncClient):
        assert (await client.get("/api/mcp/status")).json() == []

    async def test_update_tools_policy(self, client: AsyncClient, tmp_path: Path):
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]
        resp = await client.patch(
            "/api/config/tools",
            json={
                "confirm_timeout_seconds": 90,
                "policy": {"default": "ask", "deny": ["*format*"]},
            },
        )
        assert resp.status_code == 200
        cfg = (await client.get("/api/config")).json()
        assert cfg["tools"]["confirm_timeout_seconds"] == 90
        assert cfg["tools"]["policy"]["default"] == "ask"
        assert cfg["tools"]["policy"]["deny"] == ["*format*"]

    async def test_update_security(self, client: AsyncClient, tmp_path: Path):
        client._transport.app.state.config_path = tmp_path / "dax.toml"  # type: ignore[union-attr]
        resp = await client.patch(
            "/api/config/security",
            json={
                "session_ttl_hours": 48,
                "cookie_secure": True,
                "cookie_name": "custom_session",
            },
        )
        assert resp.status_code == 200
        cfg = (await client.get("/api/config")).json()
        assert cfg["security"]["session_ttl_hours"] == 48
        assert cfg["security"]["cookie_secure"] is True
        assert cfg["security"]["cookie_name"] == "custom_session"
        app = client._transport.app  # type: ignore[union-attr]
        assert app.state.auth._ttl_seconds == 48 * 3600
        assert app.state.auth.cookie_name == "custom_session"
        assert app.state.auth.cookie_secure is True


async def test_web_channel_correlates_response_frame(monkeypatch):
    # Replies dispatch by session so they reach the client that asked, rather
    # than every attached client.
    dispatch = AsyncMock()
    monkeypatch.setattr(
        "dax.channels.web_channel.ws_manager",
        SimpleNamespace(connection_count=1, dispatch=dispatch),
    )
    message = Message(
        role=MessageRole.ASSISTANT,
        content="respuesta",
        channel=ChannelType.WEB,
        metadata={"session_id": "client-session"},
    )

    await WebChannel().send(message)

    frame = dispatch.await_args.args[0]
    assert frame["session_id"] == "client-session"
