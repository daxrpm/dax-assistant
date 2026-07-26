"""Authoritative capability-node protocol, lifecycle, and routing tests."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sqlite3
from typing import Any

import pytest

from dax.capabilities.hub import CapabilityHub
from dax.capabilities.protocol import (
    BUNDLED_TOOLS,
    MAX_ARGUMENT_BYTES,
    MAX_RESULT_CHARS,
    MAX_TOOLS,
    HelloFrame,
    ResultFrame,
    canonical_name,
    trusted_inventory,
)
from dax.core.config import DaxConfig, NodePolicyConfig, NodesConfig, SecurityConfig, VoiceConfig
from dax.core.exceptions import ToolNotFoundError
from dax.core.models import ToolCall, ToolResult
from dax.mcp.manager import MCPManager
from dax.mcp.registry import ToolRegistry
from dax.orchestrator.tool_gate import ToolGate
from dax.storage.database import Database
from dax.storage.devices import CAPABILITY_NODE_KIND, DeviceRegistry
from dax.web.auth import AuthManager


class FakeWebSocket:
    def __init__(self, *frames: dict[str, object]) -> None:
        self.incoming: asyncio.Queue[str | None] = asyncio.Queue()
        for frame in frames:
            self.incoming.put_nowait(json.dumps(frame))
        self.sent: list[dict[str, Any]] = []
        self.sent_event = asyncio.Event()
        self.closed = False

    async def receive_text(self) -> str:
        value = await self.incoming.get()
        if value is None:
            raise RuntimeError("closed")
        return value

    async def send_text(self, value: str) -> None:
        self.sent.append(json.loads(value))
        self.sent_event.set()

    async def close(self, code: int = 1000) -> None:
        del code
        if not self.closed:
            self.closed = True
            self.incoming.put_nowait(None)

    async def push(self, frame: dict[str, object]) -> None:
        await self.incoming.put(json.dumps(frame))

    async def wait_for_type(self, frame_type: str) -> dict[str, Any]:
        while True:
            for frame in self.sent:
                if frame["type"] == frame_type:
                    return frame
            self.sent_event.clear()
            await asyncio.wait_for(self.sent_event.wait(), timeout=1)


class StalledCloseWebSocket(FakeWebSocket):
    def __init__(self, *frames: dict[str, object]) -> None:
        super().__init__(*frames)
        self.close_started = asyncio.Event()
        self.release_close = asyncio.Event()

    async def close(self, code: int = 1000) -> None:
        self.close_started.set()
        await self.release_close.wait()
        await super().close(code)


def _hello(*names: str) -> dict[str, object]:
    return {
        "type": "hello",
        "version": 1,
        "tools": [
            {"name": name, "input_schema": BUNDLED_TOOLS[name][1]}
            for name in names
        ],
    }


def _tts_hello(*engines: str) -> dict[str, object]:
    hello = _hello()
    hello["features"] = {"local_tts": {"engines": list(engines)}}
    return hello


@pytest.fixture
async def capability_env(tmp_path):
    database = Database(str(tmp_path / "dax.db"))
    await database.start()
    devices = DeviceRegistry(database)
    await devices.load()
    node, _ = await devices.enroll(
        name="laptop", platform="linux", kind=CAPABILITY_NODE_KIND
    )
    manager = MCPManager(DaxConfig().mcp)
    hub = CapabilityHub(manager, devices, voice=VoiceConfig())
    yield hub, manager, devices, node.id
    await hub.stop()
    await database.stop()


async def _connect(hub: CapabilityHub, node_id: str, *tools: str):
    socket = FakeWebSocket(_hello(*tools))
    task = asyncio.create_task(hub.handle(socket, node_id))
    ready = await socket.wait_for_type("ready")
    return socket, task, ready


class TestCapabilityAuth:
    async def test_node_and_client_token_scopes_are_isolated(self, tmp_path):
        database = Database(str(tmp_path / "dax.db"))
        await database.start()
        devices = DeviceRegistry(database)
        await devices.load()
        client, _ = await devices.enroll(name="phone", platform="android")
        node, _ = await devices.enroll(
            name="laptop", platform="linux", kind=CAPABILITY_NODE_KIND
        )
        auth = AuthManager(SecurityConfig(auth_enabled=True, session_secret="secret"))
        auth.attach_devices(devices)

        client_token = auth.issue_device_token(client.id)
        node_token = auth.issue_capability_token(node.id)

        assert auth.device_from_token(client_token) == client.id
        assert auth.capability_node_from_token(client_token) is None
        assert auth.capability_node_from_token(node_token) == node.id
        assert auth.validate_token(node_token) is False
        assert auth.device_from_token(node_token) is None
        await database.stop()


class TestCapabilityProtocol:
    def test_android_inventory_is_bounded_and_server_owned(self):
        names = (
            "app_open",
            "app_deeplink",
            "media_status",
            "media_control",
            "notifications_read",
            "call_dial",
            "call_place",
            "sms_compose",
        )
        hello = HelloFrame.model_validate(_hello(*names))

        inventory = trusted_inventory("phone", hello)

        assert len(inventory) == len(names) <= MAX_TOOLS
        assert {str(tool["name"]).rsplit("__", 1)[-1] for tool in inventory} == set(names)
        assert all(tool["server_name"] == "capability-node:phone" for tool in inventory)

    def test_rejects_unknown_schema_and_tool_count_limit(self):
        bad = HelloFrame.model_validate(_hello("shell_run"))
        bad.tools[0].input_schema = {"type": "object"}
        with pytest.raises(ValueError, match="Untrusted schema"):
            trusted_inventory("node", bad)

        payload = _hello(*(["system_info"] * (MAX_TOOLS + 1)))
        with pytest.raises(ValueError):
            HelloFrame.model_validate(payload)

    def test_result_payload_limit_is_strict(self):
        with pytest.raises(ValueError):
            ResultFrame.model_validate(
                {
                    "type": "result",
                    "generation": 1,
                    "request_id": "call",
                    "content": "x" * (MAX_RESULT_CHARS + 1),
                    "success": True,
                    "error": None,
                }
            )

    def test_local_tts_feature_rejects_unknown_duplicate_and_extra_values(self):
        for engines in (["openai"], ["kokoro", "kokoro"]):
            with pytest.raises(ValueError):
                HelloFrame.model_validate(
                    {**_hello(), "features": {"local_tts": {"engines": engines}}}
                )
        with pytest.raises(ValueError):
            HelloFrame.model_validate(
                {
                    **_hello(),
                    "features": {
                        "local_tts": {"engines": ["piper"], "token": "secret"}
                    },
                }
            )

    async def test_argument_limit_is_enforced_before_send(self, capability_env):
        hub, manager, _devices, node_id = capability_env
        socket, task, _ = await _connect(hub, node_id, "fs_write")
        result = await manager.execute(
            ToolCall(
                id="large",
                server_name="",
                tool_name=canonical_name(node_id, "fs_write"),
                arguments={"path": "x", "content": "x" * (MAX_ARGUMENT_BYTES + 1)},
            )
        )
        assert result.is_error is True
        assert "exceed" in result.content
        assert not any(frame["type"] == "execute" for frame in socket.sent)
        await hub.disconnect_node(node_id)
        await task


class TestCapabilityLifecycle:
    async def test_shell_is_not_advertised_until_explicitly_enabled(self, capability_env):
        hub, manager, _devices, node_id = capability_env
        _socket, task, _ = await _connect(hub, node_id, "shell_run")
        assert manager.get_server_for_tool(canonical_name(node_id, "shell_run")) is None
        await hub.disconnect_node(node_id)
        await task

        hub.nodes.policies[node_id] = NodePolicyConfig(shell_enabled=True)
        _socket, task, _ = await _connect(hub, node_id, "shell_run")
        assert manager.get_server_for_tool(canonical_name(node_id, "shell_run")) is not None
        await hub.disconnect_node(node_id)
        await task

    async def test_fleet_kill_switch_rejects_new_connections(self, capability_env):
        hub, manager, _devices, node_id = capability_env
        hub.nodes.enabled = False
        socket = FakeWebSocket(_hello("system_info"))
        await hub.handle(socket, node_id)
        assert socket.closed is True
        assert manager.get_server_for_tool(canonical_name(node_id, "system_info")) is None

    async def test_execution_routes_result_and_disconnect_removes_tools(
        self, capability_env
    ):
        hub, manager, _devices, node_id = capability_env
        socket, task, ready = await _connect(hub, node_id, "system_info")
        name = canonical_name(node_id, "system_info")
        execution = asyncio.create_task(
            manager.execute(ToolCall("outer", "", name, {}))
        )
        call = await socket.wait_for_type("execute")
        await socket.push(
            {
                "type": "result",
                "generation": ready["generation"],
                "request_id": call["request_id"],
                "content": "linux",
                "success": True,
                "error": None,
            }
        )
        assert await execution == ToolResult("outer", "linux", False)

        await hub.disconnect_node(node_id)
        await task
        assert manager.get_server_for_tool(name) is None

    async def test_replacement_fences_stale_results(self, capability_env):
        hub, manager, _devices, node_id = capability_env
        old, old_task, old_ready = await _connect(hub, node_id, "system_info")
        new, new_task, new_ready = await _connect(hub, node_id, "system_info")
        assert old.closed is True
        await old_task

        execution = asyncio.create_task(
            manager.execute(
                ToolCall("outer", "", canonical_name(node_id, "system_info"), {})
            )
        )
        call = await new.wait_for_type("execute")
        await new.push(
            {
                "type": "result",
                "generation": old_ready["generation"],
                "request_id": call["request_id"],
                "content": "stale",
                "success": True,
                "error": None,
            }
        )
        await asyncio.sleep(0)
        assert not execution.done()
        await new.push(
            {
                "type": "result",
                "generation": new_ready["generation"],
                "request_id": call["request_id"],
                "content": "current",
                "success": True,
                "error": None,
            }
        )
        assert (await execution).content == "current"
        await hub.disconnect_node(node_id)
        await new_task

    async def test_replacement_with_reduced_inventory_rejects_approved_call(
        self, capability_env
    ):
        hub, manager, _devices, node_id = capability_env
        _old, old_task, _ = await _connect(
            hub, node_id, "system_info", "fs_read"
        )
        removed_name = canonical_name(node_id, "fs_read")
        approved_call = ToolCall(
            "approved", f"capability-node:{node_id}", removed_name, {"path": "/tmp/x"}
        )

        new, new_task, _ = await _connect(hub, node_id, "system_info")
        await old_task
        with pytest.raises(ToolNotFoundError, match="no longer provided"):
            await manager.execute(approved_call)
        assert not any(frame["type"] == "execute" for frame in new.sent)

        connection = hub._connections[node_id]
        result = await connection.execute(approved_call)
        assert result.is_error is True
        assert "inventory" in result.content
        await hub.disconnect_node(node_id)
        await new_task

    async def test_stalled_replacement_close_does_not_hold_lifecycle_lock(
        self, capability_env
    ):
        hub, manager, _devices, node_id = capability_env
        old = StalledCloseWebSocket(_hello("system_info"))
        old_task = asyncio.create_task(hub.handle(old, node_id))
        await old.wait_for_type("ready")

        new = FakeWebSocket(_hello("system_info"))
        replacement = asyncio.create_task(hub.handle(new, node_id))
        await asyncio.wait_for(old.close_started.wait(), timeout=1)

        await asyncio.wait_for(hub.disconnect_node(node_id), timeout=0.2)
        assert manager.get_server_for_tool(
            canonical_name(node_id, "system_info")
        ) is None
        assert new.closed is True

        old.release_close.set()
        await replacement
        await old_task
        assert not any(frame["type"] == "ready" for frame in new.sent)

    async def test_revocation_rejects_execution_immediately(self, capability_env):
        hub, manager, devices, node_id = capability_env
        socket, task, _ = await _connect(hub, node_id, "system_info")
        await devices.revoke(node_id)
        result = await manager.execute(
            ToolCall("revoked", "", canonical_name(node_id, "system_info"), {})
        )
        assert result.is_error is True
        assert "revoked" in result.content
        assert not any(frame["type"] == "execute" for frame in socket.sent)
        await hub.disconnect_node(node_id)
        await task


class TestCapabilityTTS:
    async def test_offline_explicit_local_policy_never_falls_back(self, capability_env):
        hub, _manager, _devices, node_id = capability_env
        hub.nodes.policies[node_id] = NodePolicyConfig(voice="local")
        with pytest.raises(RuntimeError, match="Node-local TTS"):
            await hub.synthesize_tts("Private text", "en", VoiceConfig(tts_engine="openai"))

    async def test_tts_features_are_negotiated_after_v1_hello(self, capability_env):
        hub, _manager, _devices, node_id = capability_env
        socket = FakeWebSocket(_hello())
        task = asyncio.create_task(hub.handle(socket, node_id))
        ready = await socket.wait_for_type("ready")
        assert ready["features"] == {"local_tts": 1}
        await socket.push(
            {
                "type": "features",
                "generation": ready["generation"],
                "local_tts": {"engines": ["piper"]},
            }
        )
        for _ in range(20):
            if hub._connections[node_id].tts_engines:
                break
            await asyncio.sleep(0.01)
        assert hub._connections[node_id].tts_engines == frozenset({"piper"})
        await hub.disconnect_node(node_id)
        await task

    async def test_auto_cloud_server_policy_and_fleet_switches_do_not_route(
        self, capability_env
    ):
        hub, _manager, _devices, node_id = capability_env
        socket = FakeWebSocket(_tts_hello("kokoro", "piper"))
        task = asyncio.create_task(hub.handle(socket, node_id))
        await socket.wait_for_type("ready")

        assert (
            await hub.synthesize_tts("Hello", "en", VoiceConfig(tts_engine="openai"))
            is None
        )
        hub.nodes.policies[node_id] = NodePolicyConfig(voice="server")
        assert (
            await hub.synthesize_tts("Hello", "en", VoiceConfig(tts_engine="piper"))
            is None
        )
        hub.nodes.policies[node_id] = NodePolicyConfig(voice="local")
        hub.nodes.prefer_when_available = False
        with pytest.raises(RuntimeError, match="Node-local TTS"):
            await hub.synthesize_tts("Hello", "en", VoiceConfig(tts_engine="piper"))
        assert not any(frame["type"] == "synthesize" for frame in socket.sent)
        await hub.disconnect_node(node_id)
        await task

    async def test_routes_complete_validated_pcm_and_records_executor(self, capability_env):
        hub, _manager, _devices, node_id = capability_env
        socket = FakeWebSocket(_tts_hello("kokoro"))
        task = asyncio.create_task(hub.handle(socket, node_id))
        ready = await socket.wait_for_type("ready")

        synthesis = asyncio.create_task(
            hub.synthesize_tts("Hola", "es", VoiceConfig(tts_engine="kokoro"))
        )
        request = await socket.wait_for_type("synthesize")
        pcm = b"\x00\x00\x01\x00"
        await socket.push(
            {
                "type": "synthesize_chunk",
                "generation": ready["generation"],
                "request_id": request["request_id"],
                "index": 0,
                "data": base64.b64encode(pcm).decode(),
            }
        )
        await socket.push(
            {
                "type": "synthesize_final",
                "generation": ready["generation"],
                "request_id": request["request_id"],
                "success": True,
                "chunks": 1,
                "size": len(pcm),
                "sha256": hashlib.sha256(pcm).hexdigest(),
                "sample_rate": 24_000,
                "channels": 1,
                "sample_width": 2,
                "engine": "kokoro",
                "voice": "em_alex",
                "language": "es",
                "executor_fingerprint": "actual-engine",
                "error": None,
            }
        )

        result = await synthesis
        assert result is not None
        assert result.pcm == pcm
        expected = hashlib.sha256(
            f"node:{node_id}:{ready['generation']}:actual-engine".encode()
        ).hexdigest()[:32]
        assert result.executor_fingerprint == expected
        await hub.disconnect_node(node_id)
        await task

    async def test_wake_reply_targets_and_plays_on_its_exact_node(self, capability_env):
        hub, _manager, _devices, node_id = capability_env
        socket = FakeWebSocket(_tts_hello("kokoro"))
        task = asyncio.create_task(hub.handle(socket, node_id))
        ready = await socket.wait_for_type("ready")

        speaking = asyncio.create_task(
            hub._speak_on_wake_node(node_id, "Hola", "es")
        )
        request = await socket.wait_for_type("synthesize")
        assert request["playback"] is True
        pcm = b"\x00\x00\x01\x00"
        await socket.push(
            {
                "type": "synthesize_chunk",
                "generation": ready["generation"],
                "request_id": request["request_id"],
                "index": 0,
                "data": base64.b64encode(pcm).decode(),
            }
        )
        await socket.push(
            {
                "type": "synthesize_final",
                "generation": ready["generation"],
                "request_id": request["request_id"],
                "success": True,
                "chunks": 1,
                "size": len(pcm),
                "sha256": hashlib.sha256(pcm).hexdigest(),
                "sample_rate": 24_000,
                "channels": 1,
                "sample_width": 2,
                "engine": "kokoro",
                "voice": "em_alex",
                "language": "es",
                "executor_fingerprint": "actual-engine",
                "error": None,
            }
        )

        await speaking
        await hub.disconnect_node(node_id)
        await task

    async def test_noncontiguous_chunks_close_connection_and_fail_pending(
        self, capability_env
    ):
        hub, _manager, _devices, node_id = capability_env
        socket = FakeWebSocket(_tts_hello("piper"))
        task = asyncio.create_task(hub.handle(socket, node_id))
        ready = await socket.wait_for_type("ready")
        synthesis = asyncio.create_task(
            hub.synthesize_tts("Hello", "en", VoiceConfig(tts_engine="piper"))
        )
        request = await socket.wait_for_type("synthesize")
        await socket.push(
            {
                "type": "synthesize_chunk",
                "generation": ready["generation"],
                "request_id": request["request_id"],
                "index": 1,
                "data": base64.b64encode(b"\x00\x00").decode(),
            }
        )

        with pytest.raises(RuntimeError, match="disconnected"):
            await synthesis
        await task
        assert socket.closed is True

    @pytest.mark.parametrize(
        "invalid",
        [
            {"sha256": "0" * 64},
            {"size": 4},
            {"sample_rate": 7999},
            {"channels": 2},
            {"sample_width": 4},
        ],
    )
    async def test_rejects_invalid_audio_integrity_metadata(
        self, capability_env, invalid: dict[str, object]
    ):
        hub, _manager, _devices, node_id = capability_env
        socket = FakeWebSocket(_tts_hello("piper"))
        task = asyncio.create_task(hub.handle(socket, node_id))
        ready = await socket.wait_for_type("ready")
        synthesis = asyncio.create_task(
            hub.synthesize_tts("Hello", "en", VoiceConfig(tts_engine="piper"))
        )
        request = await socket.wait_for_type("synthesize")
        pcm = b"\x00\x00"
        await socket.push(
            {
                "type": "synthesize_chunk",
                "generation": ready["generation"],
                "request_id": request["request_id"],
                "index": 0,
                "data": base64.b64encode(pcm).decode(),
            }
        )
        final: dict[str, object] = {
            "type": "synthesize_final",
            "generation": ready["generation"],
            "request_id": request["request_id"],
            "success": True,
            "chunks": 1,
            "size": len(pcm),
            "sha256": hashlib.sha256(pcm).hexdigest(),
            "sample_rate": 22_050,
            "channels": 1,
            "sample_width": 2,
            "engine": "piper",
            "voice": "voice",
            "language": "en",
            "executor_fingerprint": "actual",
            "error": None,
        }
        final.update(invalid)
        await socket.push(final)

        with pytest.raises(RuntimeError, match="disconnected"):
            await synthesis
        await task
        assert socket.closed is True

    async def test_replacement_fails_pending_synthesis(self, capability_env):
        hub, _manager, _devices, node_id = capability_env
        old = FakeWebSocket(_tts_hello("kokoro"))
        old_task = asyncio.create_task(hub.handle(old, node_id))
        await old.wait_for_type("ready")
        synthesis = asyncio.create_task(
            hub.synthesize_tts("Hola", "es", VoiceConfig(tts_engine="kokoro"))
        )
        await old.wait_for_type("synthesize")

        new = FakeWebSocket(_tts_hello("kokoro"))
        new_task = asyncio.create_task(hub.handle(new, node_id))
        await new.wait_for_type("ready")
        with pytest.raises(RuntimeError, match=r"Node-local|replaced"):
            await synthesis

        await old_task
        await hub.disconnect_node(node_id)
        await new_task

    async def test_policy_selection_is_deterministic_and_respects_modes(self, tmp_path):
        database = Database(str(tmp_path / "dax.db"))
        await database.start()
        devices = DeviceRegistry(database)
        await devices.load()
        first, _ = await devices.enroll(
            name="first", platform="linux", kind=CAPABILITY_NODE_KIND
        )
        second, _ = await devices.enroll(
            name="second", platform="linux", kind=CAPABILITY_NODE_KIND
        )
        nodes = NodesConfig(
            policies={
                first.id: NodePolicyConfig(voice="server"),
                second.id: NodePolicyConfig(voice="local"),
            }
        )
        hub = CapabilityHub(MCPManager(DaxConfig().mcp), devices, nodes)
        sockets: dict[str, FakeWebSocket] = {}
        tasks = []
        for node_id in sorted((first.id, second.id), reverse=True):
            socket = FakeWebSocket(_tts_hello("piper"))
            sockets[node_id] = socket
            tasks.append(asyncio.create_task(hub.handle(socket, node_id)))
            await socket.wait_for_type("ready")

        synthesis = asyncio.create_task(
            hub.synthesize_tts("Hello", "en", VoiceConfig(tts_engine="openai"))
        )
        request = await sockets[second.id].wait_for_type("synthesize")
        assert request["engine"] == "piper"
        assert not any(
            frame["type"] == "synthesize" for frame in sockets[first.id].sent
        )
        await hub.disconnect_node(second.id)
        with pytest.raises(RuntimeError, match="Node-local"):
            await synthesis
        await hub.stop()
        await asyncio.gather(*tasks)
        await database.stop()


def test_dynamic_inventory_collision_is_atomic():
    registry = ToolRegistry()
    registry.register(
        [{"name": "taken", "server_name": "static", "inputSchema": {}}]
    )
    with pytest.raises(ValueError, match="collision"):
        registry.replace_server(
            "capability-node:x",
            [{"name": "taken", "server_name": "capability-node:x"}],
            reject_collisions=True,
        )
    assert registry.get_server_for_tool("taken") == "static"


def test_shell_special_treatment_requires_a_trusted_owner():
    class Provider:
        def __init__(self, owner: str) -> None:
            self.owner = owner

        def get_server_for_tool(self, _name: str) -> str:
            return self.owner

    node_name = canonical_name("node", "shell_run")
    trusted = ToolGate(Provider("capability-node:node"))  # type: ignore[arg-type]
    arbitrary = ToolGate(Provider("third-party"))  # type: ignore[arg-type]

    assert trusted._is_trusted_shell(
        ToolCall("call", "capability-node:node", node_name, {})
    )
    assert not arbitrary._is_trusted_shell(
        ToolCall("call", "third-party", node_name, {})
    )
    assert not arbitrary._is_trusted_shell(
        ToolCall("call", "third-party", "shell_run", {})
    )


async def test_schema_v5_migrates_existing_devices_to_client(tmp_path):
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO schema_version VALUES (5);
        CREATE TABLE devices (
            id TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT '', secret_hash TEXT NOT NULL,
            created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL DEFAULT '',
            revoked_at TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO devices VALUES ('old', 'phone', 'android', 'hash', 'now', '', '');
        """
    )
    connection.commit()
    connection.close()

    database = Database(str(path))
    await database.start()
    row = await (await database.connection.execute(
        "SELECT kind FROM devices WHERE id = 'old'"
    )).fetchone()
    version = await (await database.connection.execute(
        "SELECT version FROM schema_version"
    )).fetchone()
    assert row["kind"] == "client"
    assert version["version"] == 6
    await database.stop()
