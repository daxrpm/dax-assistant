"""Authoritative lifecycle and execution hub for laptop capability nodes."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import TypeAdapter, ValidationError

from dax.capabilities.protocol import (
    MAX_ARGUMENT_BYTES,
    MAX_FRAME_BYTES,
    HeartbeatFrame,
    HelloFrame,
    InboundFrame,
    ResultFrame,
    canonical_prefix,
    trusted_inventory,
)
from dax.core.models import ToolCall, ToolResult

if TYPE_CHECKING:
    from fastapi import WebSocket

    from dax.mcp.manager import MCPManager
    from dax.storage.devices import DeviceRegistry

logger = logging.getLogger(__name__)
_INBOUND: TypeAdapter[InboundFrame] = TypeAdapter(InboundFrame)
_HELLO_TIMEOUT = 10.0
_IDLE_TIMEOUT = 30.0
_PONG_TIMEOUT = 10.0
_CALL_TIMEOUT = 60.0
_CLOSE_TIMEOUT = 5.0
_MAX_CONCURRENT_CALLS = 4


@dataclass(slots=True)
class _Connection:
    hub: CapabilityHub
    node_id: str
    websocket: WebSocket
    generation: int
    inventory: frozenset[str]
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    calls: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(_MAX_CONCURRENT_CALLS)
    )
    pending: dict[str, asyncio.Future[ToolResult]] = field(default_factory=dict)
    closed: bool = False

    async def send(self, frame: dict[str, object]) -> None:
        payload = json.dumps(frame, separators=(",", ":"))
        if len(payload.encode()) > MAX_FRAME_BYTES:
            raise ValueError("Capability frame exceeds limit")
        async with self.send_lock:
            await asyncio.wait_for(self.websocket.send_text(payload), timeout=10)

    async def execute(self, call: ToolCall) -> ToolResult:
        async with self.calls:
            if not self.hub.is_current(self) or not self.hub.devices.is_active(self.node_id):
                return _failure(call.id, "Capability node is disconnected or revoked")
            prefix = canonical_prefix(self.node_id)
            if call.tool_name not in self.inventory:
                return _failure(
                    call.id, "Capability tool is not in this connection inventory"
                )
            arguments = json.dumps(call.arguments, separators=(",", ":"))
            if len(arguments.encode()) > MAX_ARGUMENT_BYTES:
                return _failure(call.id, "Capability arguments exceed limit")
            wire_id = uuid.uuid4().hex
            future = asyncio.get_running_loop().create_future()
            self.pending[wire_id] = future
            try:
                await self.send(
                    {
                        "type": "execute",
                        "generation": self.generation,
                        "request_id": wire_id,
                        "tool_name": call.tool_name.removeprefix(prefix),
                        "arguments": call.arguments,
                        "timeout_seconds": _CALL_TIMEOUT,
                    }
                )
                result = await asyncio.wait_for(future, timeout=_CALL_TIMEOUT)
                return ToolResult(
                    call_id=call.id,
                    content=result.content,
                    is_error=result.is_error,
                )
            except TimeoutError:
                return _failure(call.id, "Capability call timed out")
            except Exception:
                logger.exception("Capability call transport failed for %s", self.node_id)
                return _failure(call.id, "Capability node disconnected")
            finally:
                self.pending.pop(wire_id, None)

    def fail_pending(self, reason: str) -> None:
        for future in self.pending.values():
            if not future.done():
                future.set_result(_failure("", reason))


def _failure(call_id: str, reason: str) -> ToolResult:
    return ToolResult(call_id=call_id, content=f"Error: {reason}", is_error=True)


class CapabilityHub:
    """Owns ephemeral inventories and one generation-fenced socket per node."""

    def __init__(self, manager: MCPManager, devices: DeviceRegistry) -> None:
        self.manager = manager
        self.devices = devices
        self._connections: dict[str, _Connection] = {}
        self._generations: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._stopping = False

    def is_present(self, node_id: str) -> bool:
        connection = self._connections.get(node_id)
        return connection is not None and not connection.closed

    def is_current(self, connection: _Connection) -> bool:
        return self._connections.get(connection.node_id) is connection and not connection.closed

    async def handle(self, websocket: WebSocket, node_id: str) -> None:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=_HELLO_TIMEOUT)
            if len(raw.encode()) > MAX_FRAME_BYTES:
                raise ValueError("Hello frame exceeds limit")
            hello = HelloFrame.model_validate_json(raw)
            tools = trusted_inventory(node_id, hello)
        except (TimeoutError, ValueError, ValidationError):
            await self._close_socket(websocket, code=1008)
            return

        old: _Connection | None = None
        reject_code: int | None = None
        async with self._lock:
            if self._stopping:
                reject_code = 1012
            else:
                old = self._connections.get(node_id)
                generation = self._generations.get(node_id, 0) + 1
                connection = _Connection(
                    self,
                    node_id,
                    websocket,
                    generation,
                    frozenset(str(tool["name"]) for tool in tools),
                )
                try:
                    self.manager.register_dynamic_provider(
                        f"capability-node:{node_id}", tools, connection.execute
                    )
                except ValueError:
                    reject_code = 1008
                else:
                    self._generations[node_id] = generation
                    self._connections[node_id] = connection
                    if old is not None:
                        # The new registry, executor, and generation are visible
                        # before the old transport can be closed or reused.
                        self._detach_locked(old, "Capability node replaced")

        if reject_code is not None:
            await self._close_socket(websocket, code=reject_code)
            return
        if old is not None:
            await self._close_socket(old.websocket, code=1008)

        try:
            if not self.is_current(connection):
                return
            await connection.send(
                {"type": "ready", "version": 1, "generation": generation}
            )
            await self._receive_loop(connection)
        finally:
            close = False
            async with self._lock:
                if self._connections.get(node_id) is connection:
                    self._detach_locked(connection, "Capability node disconnected")
                    close = True
            if close:
                await self._close_socket(connection.websocket, code=1008)

    async def _receive_loop(self, connection: _Connection) -> None:
        awaiting_pong = False
        while self.is_current(connection):
            timeout = _PONG_TIMEOUT if awaiting_pong else _IDLE_TIMEOUT
            try:
                raw = await asyncio.wait_for(
                    connection.websocket.receive_text(), timeout=timeout
                )
            except TimeoutError:
                if awaiting_pong:
                    return
                await connection.send(
                    {"type": "heartbeat"}
                )
                awaiting_pong = True
                continue
            except Exception:
                return
            if len(raw.encode()) > MAX_FRAME_BYTES:
                await self._close_socket(connection.websocket, code=1009)
                return
            try:
                frame = _INBOUND.validate_json(raw)
            except ValidationError:
                await self._close_socket(connection.websocket, code=1008)
                return
            if isinstance(frame, HeartbeatFrame):
                awaiting_pong = False
                continue
            if frame.generation != connection.generation:
                continue
            if isinstance(frame, ResultFrame):
                if len(frame.content.encode()) > 64 * 1024 or (
                    frame.error is not None and len(frame.error.encode()) > 64 * 1024
                ):
                    await self._close_socket(connection.websocket, code=1009)
                    return
                future = connection.pending.get(frame.request_id)
                if future is not None and not future.done():
                    future.set_result(
                        ToolResult(
                            call_id=frame.request_id,
                            content=(
                                frame.content
                                if frame.success
                                else f"Error: {frame.error or frame.content}"
                            ),
                            is_error=not frame.success,
                        )
                    )

    async def disconnect_node(self, node_id: str) -> None:
        connection: _Connection | None = None
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is not None:
                self._detach_locked(connection, "Capability node revoked")
        if connection is not None:
            await self._close_socket(connection.websocket, code=1008)

    def _detach_locked(self, connection: _Connection, reason: str) -> None:
        connection.closed = True
        if self._connections.get(connection.node_id) is connection:
            self._connections.pop(connection.node_id, None)
            self.manager.unregister_dynamic_provider(
                f"capability-node:{connection.node_id}"
            )
        connection.fail_pending(reason)

    async def _close_socket(self, websocket: WebSocket, *, code: int) -> None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(websocket.close(code=code), timeout=_CLOSE_TIMEOUT)

    async def stop(self) -> None:
        connections: list[_Connection]
        async with self._lock:
            self._stopping = True
            connections = list(self._connections.values())
            for connection in connections:
                self._detach_locked(connection, "Capability hub stopped")
        await asyncio.gather(
            *(
                self._close_socket(connection.websocket, code=1008)
                for connection in connections
            )
        )
