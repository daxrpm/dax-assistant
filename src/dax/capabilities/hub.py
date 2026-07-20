"""Authoritative lifecycle and execution hub for laptop capability nodes."""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import TypeAdapter, ValidationError

from dax.capabilities.protocol import (
    MAX_ARGUMENT_BYTES,
    MAX_FRAME_BYTES,
    MAX_TTS_AUDIO_BYTES,
    MAX_TTS_CHUNK_BYTES,
    MAX_TTS_CHUNKS,
    FeaturesFrame,
    HeartbeatFrame,
    HelloFrame,
    InboundFrame,
    ResultFrame,
    SynthesizeChunkFrame,
    SynthesizeFinalFrame,
    canonical_prefix,
    trusted_endpoints,
    trusted_inventory,
)
from dax.core.config import NodesConfig
from dax.core.models import ToolCall, ToolResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import WebSocket

    from dax.core.config import VoiceConfig
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


class CapabilityTTSTransportError(RuntimeError):
    """A selected node failed to return a valid synthesis."""


class LocalTTSRequiredError(RuntimeError):
    """An explicit node-local voice policy could not be fulfilled."""


@dataclass(frozen=True, slots=True)
class CapabilitySynthesis:
    pcm: bytes
    sample_rate: int
    engine: str
    voice: str | None
    language: str
    executor_fingerprint: str


@dataclass(slots=True)
class _PendingSynthesis:
    future: asyncio.Future[CapabilitySynthesis]
    language: str
    chunks: list[bytes] = field(default_factory=list)
    size: int = 0


@dataclass(slots=True)
class _Connection:
    hub: CapabilityHub
    node_id: str
    websocket: WebSocket
    generation: int
    inventory: frozenset[str]
    tts_engines: frozenset[str] = frozenset()
    # Validated by `trusted_endpoints`, never taken as advertised.
    endpoints: tuple[str, ...] = ()
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    calls: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(_MAX_CONCURRENT_CALLS)
    )
    pending: dict[str, asyncio.Future[ToolResult]] = field(default_factory=dict)
    tts_pending: dict[str, _PendingSynthesis] = field(default_factory=dict)
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
            local_name = call.tool_name.removeprefix(prefix)
            if not self.hub.nodes.lends_tool(self.node_id, local_name):
                return _failure(call.id, "Capability tool is disabled by node policy")
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
                        "tool_name": local_name,
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
        for pending in self.tts_pending.values():
            if not pending.future.done():
                pending.future.set_exception(CapabilityTTSTransportError(reason))

    async def synthesize(
        self,
        text: str,
        language: str,
        engine: str,
        config: dict[str, object],
    ) -> CapabilitySynthesis:
        if not self.hub.is_current(self) or not self.hub.devices.is_active(self.node_id):
            raise CapabilityTTSTransportError("Capability node is disconnected or revoked")
        wire_id = uuid.uuid4().hex
        future: asyncio.Future[CapabilitySynthesis] = (
            asyncio.get_running_loop().create_future()
        )
        self.tts_pending[wire_id] = _PendingSynthesis(future, language)
        try:
            await self.send(
                {
                    "type": "synthesize",
                    "generation": self.generation,
                    "request_id": wire_id,
                    "text": text,
                    "language": language,
                    "engine": engine,
                    "config": config,
                }
            )
            return await asyncio.wait_for(future, timeout=_CALL_TIMEOUT)
        except TimeoutError as exc:
            raise CapabilityTTSTransportError("Capability synthesis timed out") from exc
        except CapabilityTTSTransportError:
            raise
        except Exception as exc:
            logger.exception("Capability TTS transport failed for %s", self.node_id)
            raise CapabilityTTSTransportError("Capability node disconnected") from exc
        finally:
            self.tts_pending.pop(wire_id, None)


def _failure(call_id: str, reason: str) -> ToolResult:
    return ToolResult(call_id=call_id, content=f"Error: {reason}", is_error=True)


class CapabilityHub:
    """Owns ephemeral inventories and one generation-fenced socket per node."""

    def __init__(
        self,
        manager: MCPManager,
        devices: DeviceRegistry,
        nodes: NodesConfig | None = None,
        public_key: Callable[[], str] | None = None,
    ) -> None:
        self.manager = manager
        self.devices = devices
        # A callable rather than the key itself: it is generated on first use,
        # and a node that connects before anything has needed it should still
        # get the key that eventually signs its tickets.
        self._public_key = public_key
        # Held live rather than copied: settings edits mutate the config object
        # in place, so a node's next policy push reflects them without a reload.
        self.nodes = nodes if nodes is not None else NodesConfig()
        self._connections: dict[str, _Connection] = {}
        self._generations: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._stopping = False

    async def send_policy(self, node_id: str) -> None:
        """Push *node_id*'s current policy to it, if it is connected.

        Best effort by design: a node that misses the push re-reads the policy
        on its next connect, and the backend never depends on the node having
        obeyed. Nothing here is a security control — the backend still refuses
        to route work a policy forbids.
        """
        connection = self._connections.get(node_id)
        if connection is None or connection.closed:
            return
        policy = self.nodes.policy_for(node_id)
        with contextlib.suppress(Exception):
            await connection.send(
                {
                    "type": "policy",
                    "generation": connection.generation,
                    "process_locally": self.nodes.hosts_sessions(node_id),
                    "inference": policy.inference,
                    "voice": policy.voice,
                }
            )

    def is_present(self, node_id: str) -> bool:
        connection = self._connections.get(node_id)
        return connection is not None and not connection.closed

    def endpoints_for(self, node_id: str) -> list[str]:
        """Validated LAN addresses this node is currently reachable at.

        Empty when the node is gone, which is what a client should see: an
        address for a laptop that is not connected is an invitation to talk to
        whatever now holds that IP.
        """
        connection = self._connections.get(node_id)
        if connection is None or connection.closed:
            return []
        return list(connection.endpoints)

    def is_current(self, connection: _Connection) -> bool:
        return self._connections.get(connection.node_id) is connection and not connection.closed

    async def handle(self, websocket: WebSocket, node_id: str) -> None:
        if not self.nodes.enabled:
            await self._close_socket(websocket, code=1008)
            return
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=_HELLO_TIMEOUT)
            if len(raw.encode()) > MAX_FRAME_BYTES:
                raise ValueError("Hello frame exceeds limit")
            hello = HelloFrame.model_validate_json(raw)
            tools = trusted_inventory(node_id, hello)
            prefix = canonical_prefix(node_id)
            tools = [
                tool
                for tool in tools
                if self.nodes.lends_tool(
                    node_id, str(tool["name"]).removeprefix(prefix)
                )
            ]
            endpoints = tuple(trusted_endpoints(hello))
            tts_engines = frozenset(
                hello.features.local_tts.engines
                if hello.features.local_tts is not None
                else []
            )
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
                    tts_engines,
                    endpoints,
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
            ready: dict[str, object] = {
                "type": "ready",
                "version": 1,
                "generation": generation,
                # Feature negotiation happens after the v1 hello so a new node
                # can still connect to an older strict-v1 backend.
                "features": {"local_tts": 1},
            }
            # The node needs this to verify session tickets on its own, without
            # asking the backend on every connection a phone makes.
            if self._public_key is not None:
                with contextlib.suppress(Exception):
                    ready["public_key"] = self._public_key()
            await connection.send(ready)
            await self.send_policy(node_id)
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
            if isinstance(frame, FeaturesFrame):
                if connection.tts_engines:
                    await self._close_socket(connection.websocket, code=1008)
                    return
                connection.tts_engines = frozenset(frame.local_tts.engines)
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
                continue
            if isinstance(frame, SynthesizeChunkFrame):
                if not self._accept_tts_chunk(connection, frame):
                    await self._close_socket(connection.websocket, code=1008)
                    return
                continue
            if isinstance(frame, SynthesizeFinalFrame) and not self._accept_tts_final(
                connection, frame
            ):
                await self._close_socket(connection.websocket, code=1008)
                return

    def _accept_tts_chunk(
        self, connection: _Connection, frame: SynthesizeChunkFrame
    ) -> bool:
        pending = connection.tts_pending.get(frame.request_id)
        if pending is None:
            return True
        if frame.index != len(pending.chunks) or len(pending.chunks) >= MAX_TTS_CHUNKS:
            return False
        try:
            chunk = base64.b64decode(frame.data, validate=True)
        except (binascii.Error, ValueError):
            return False
        if not chunk or len(chunk) > MAX_TTS_CHUNK_BYTES:
            return False
        pending.size += len(chunk)
        if pending.size > MAX_TTS_AUDIO_BYTES:
            return False
        pending.chunks.append(chunk)
        return True

    def _accept_tts_final(
        self, connection: _Connection, frame: SynthesizeFinalFrame
    ) -> bool:
        pending = connection.tts_pending.get(frame.request_id)
        if pending is None:
            return True
        if not frame.success:
            if (
                pending.chunks
                or frame.chunks
                or frame.size
                or frame.sha256
                or frame.sample_rate
                or frame.channels != 1
                or frame.sample_width != 2
                or frame.engine is not None
                or frame.voice is not None
                or frame.language is not None
                or frame.executor_fingerprint
                or not frame.error
            ):
                return False
            if not pending.future.done():
                pending.future.set_exception(
                    CapabilityTTSTransportError("Capability node could not synthesize speech")
                )
            return True
        pcm = b"".join(pending.chunks)
        valid = (
            frame.chunks == len(pending.chunks)
            and frame.size == len(pcm)
            and frame.size > 0
            and frame.size % 2 == 0
            and frame.sha256 == hashlib.sha256(pcm).hexdigest()
            and 8_000 <= frame.sample_rate <= 96_000
            and frame.channels == 1
            and frame.sample_width == 2
            and frame.engine in connection.tts_engines
            and frame.language == pending.language
            and bool(frame.executor_fingerprint)
            and frame.error is None
        )
        if not valid:
            return False
        assert frame.engine is not None
        assert frame.language is not None
        if not pending.future.done():
            pending.future.set_result(
                CapabilitySynthesis(
                    pcm=pcm,
                    sample_rate=frame.sample_rate,
                    engine=frame.engine,
                    voice=frame.voice,
                    language=frame.language,
                    executor_fingerprint=hashlib.sha256(
                        (
                            f"node:{connection.node_id}:{connection.generation}:"
                            f"{frame.executor_fingerprint}"
                        ).encode()
                    ).hexdigest()[:32],
                )
            )
        return True

    async def synthesize_tts(
        self, text: str, language: str, config: VoiceConfig
    ) -> CapabilitySynthesis | None:
        """Route mobile TTS to one policy-eligible node, if available."""
        local_node_ids = sorted(
            node_id
            for node_id, policy in self.nodes.policies.items()
            if policy.voice == "local" and self.devices.is_active(node_id)
        )
        if not self.nodes.enabled or not self.nodes.prefer_when_available:
            if local_node_ids:
                raise LocalTTSRequiredError("Node-local TTS is disabled or unavailable")
            return None
        selected: tuple[_Connection, str, str] | None = None
        candidates = local_node_ids or sorted(self._connections)
        for node_id in candidates:
            policy = self.nodes.policy_for(node_id).voice
            if policy == "server" or (local_node_ids and policy != "local"):
                continue
            connection = self._connections.get(node_id)
            if connection is None:
                continue
            if (
                not self.is_current(connection)
                or not self.devices.is_active(node_id)
            ):
                continue
            if not connection.tts_engines:
                continue
            if policy == "auto":
                if (
                    config.tts_engine in {"kokoro", "piper"}
                    and config.tts_engine in connection.tts_engines
                ):
                    selected = (connection, config.tts_engine, policy)
                    break
                continue
            engine = next(
                (name for name in ("kokoro", "piper") if name in connection.tts_engines),
                None,
            )
            if engine is None:
                continue
            selected = (connection, engine, policy)
            break
        if selected is None:
            if local_node_ids:
                raise LocalTTSRequiredError("Node-local TTS is unavailable")
            return None
        connection, engine, selected_policy = selected
        wire_config = _tts_config(config, engine)
        try:
            return await connection.synthesize(text, language, engine, wire_config)
        except CapabilityTTSTransportError as exc:
            if selected_policy == "local":
                raise LocalTTSRequiredError("Node-local TTS failed") from exc
            raise

    async def disconnect_node(self, node_id: str) -> None:
        connection: _Connection | None = None
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is not None:
                self._detach_locked(connection, "Capability node revoked")
        if connection is not None:
            await self._close_socket(connection.websocket, code=1008)

    async def disconnect_all(self) -> None:
        """Remove every live inventory when the fleet kill switch is disabled."""
        for node_id in list(self._connections):
            await self.disconnect_node(node_id)

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


def _tts_config(config: VoiceConfig, engine: str) -> dict[str, object]:
    if engine == "kokoro":
        return {
            "kokoro_voice_es": config.tts_kokoro_voice_es,
            "kokoro_voice_en": config.tts_kokoro_voice_en,
            "piper_voice_es": config.tts_voice_es,
            "piper_voice_en": config.tts_voice_en,
            "speed": config.tts_kokoro_speed,
        }
    return {
        "piper_voice_es": config.tts_voice_es,
        "piper_voice_en": config.tts_voice_en,
    }
