"""Authoritative capability-node protocol, lifecycle, and routing tests."""

from __future__ import annotations

import asyncio
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
from dax.core.config import DaxConfig, SecurityConfig
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
    hub = CapabilityHub(manager, devices)
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
