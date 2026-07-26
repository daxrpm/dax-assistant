"""Outbound capability-node daemon and persistent bundled MCP executor."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.util
import ipaddress
import json
import logging
import os
import random
import socket
import sys
import threading
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

import httpx
import numpy as np
import psutil
from websockets.asyncio.client import ClientConnection, connect

from dax.core.config import VoiceConfig
from dax.core.models import ToolCall
from dax.mcp.client import MCPClient
from dax.mcp.manager import _session_passthrough_env
from dax.mcp_servers.system.server import (
    configured_shell_allowlist,
    shell_allowlist,
    validate_command,
)

from .credentials import NodeCredentials, websocket_url
from .protocol import (
    MAX_TTS_AUDIO_BYTES,
    MAX_TTS_CHUNK_BYTES,
    MAX_TTS_CHUNKS,
    ExecuteRequest,
    SynthesizeRequest,
    hello_frame,
    local_tts_features_frame,
    parse_execute,
    parse_frame,
    parse_ready,
    parse_synthesize,
    parse_wake_policy,
    result_frame,
    synthesize_chunk_frame,
    synthesize_final_frame,
)
from .wake import WakeListener

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 20.0
MAX_IN_FLIGHT = 8
MAX_ADVERTISED_ENDPOINTS = 4
_WAKE_RESPONSES = frozenset({"wake_grant", "wake_yield", "listen_stop"})


def available_local_tts_engines() -> list[str]:
    """Advertise only local runtimes; model readiness is checked lazily."""
    engines: list[str] = []
    if importlib.util.find_spec("kokoro_onnx") is not None:
        engines.append("kokoro")
    if importlib.util.find_spec("piper") is not None:
        engines.append("piper")
    return engines


class WebSocketConnection(Protocol):
    async def send(self, message: str) -> None: ...
    def __aiter__(self) -> Any: ...
    async def close(self) -> None: ...


ConnectFactory = Callable[[str, dict[str, str]], Awaitable[WebSocketConnection]]
Sleep = Callable[[float], Awaitable[None]]


def local_endpoints(port: int) -> list[str]:
    """Private addresses this machine could be reached at on its own network.

    Only private, non-loopback IPv4. Loopback is useless to a phone, and a
    globally routable address on a laptop means it is directly exposed to the
    internet — not somewhere to invite a client to send a credential. The
    backend re-validates all of this anyway; this side simply avoids proposing
    addresses that would be thrown away.
    """
    if not 1 <= port <= 65535:
        return []
    found: list[str] = []
    try:
        interfaces = psutil.net_if_addrs()
    except Exception:  # pragma: no cover - platform dependent
        return []
    for addresses in interfaces.values():
        for address in addresses:
            if address.family != socket.AF_INET:
                continue
            try:
                parsed = ipaddress.ip_address(address.address)
            except ValueError:
                continue
            if not parsed.is_private or parsed.is_loopback or parsed.is_link_local:
                continue
            endpoint = f"{address.address}:{port}"
            if endpoint not in found:
                found.append(endpoint)
    return found[:MAX_ADVERTISED_ENDPOINTS]


def backoff_delay(attempt: int, *, random_value: float | None = None) -> float:
    """Capped full-jitter exponential reconnect delay."""
    ceiling = min(60.0, 1.0 * (2 ** min(attempt, 6)))
    value = random.random() if random_value is None else random_value
    return float(ceiling * max(0.0, min(value, 1.0)))


async def _connect(url: str, headers: dict[str, str]) -> ClientConnection:
    return await connect(
        url,
        additional_headers=headers,
        max_size=256 * 1024,
        ping_interval=HEARTBEAT_SECONDS,
        ping_timeout=HEARTBEAT_SECONDS,
    )


class SystemExecutor:
    """One persistent stdio session to the bundled dax-system MCP server."""

    def __init__(self) -> None:
        env = _session_passthrough_env()
        for key in ("DAX_SYSTEM_ROOTS",):
            if value := os.environ.get(key):
                env[key] = value
        self._shell_allow = shell_allowlist()
        # An explicitly empty allowlist is a local kill switch — "this laptop
        # runs no shell at all" — and outranks any approval. That is a different
        # statement from "these commands need no confirmation", so approval
        # cannot reopen it.
        self._shell_disabled = configured_shell_allowlist() == set()
        # The binary allowlist is enforced in `execute` below rather than as a
        # subprocess cap, because only this process knows whether the user
        # approved the call. A fixed environment variable cannot vary per call,
        # so capping here would refuse every command confirmed on screen — the
        # user clicks Allow and nothing runs. The subprocess keeps every
        # injection-safety guarantee regardless: argv-only, no shell, no
        # metacharacters. This mirrors the backend, which is likewise permissive
        # behind its own approval gate.
        env.pop("DAX_SYSTEM_SHELL_ALLOW", None)
        self._client = MCPClient(
            "dax-system",
            command=sys.executable,
            args=["-m", "dax.mcp_servers.system"],
            env=env,
        )
        self._tools: dict[str, dict[str, Any]] = {}

    async def start(self) -> list[dict[str, Any]]:
        await self._client.connect()
        tools = await self._client.list_tools()
        self._tools = {str(tool["name"]): tool for tool in tools}
        return tools

    async def stop(self) -> None:
        await self._client.disconnect()

    async def execute(self, request: ExecuteRequest) -> str:
        if request.tool_name not in self._tools:
            raise ValueError(f"Tool is not provided by bundled dax-system: {request.tool_name}")
        if request.tool_name == "shell_run":
            command = request.arguments.get("command")
            if not isinstance(command, str):
                raise ValueError("shell_run requires a string command")
            # An approved command skips the binary allowlist but keeps every
            # injection-safety check. The allowlist decides what may run
            # *without* asking; the user's confirmation is what authorises the
            # rest, and re-refusing it here would make Allow do nothing.
            if self._shell_disabled:
                raise ValueError("Shell execution is disabled on this node")
            validate_command(command, None if request.approved else self._shell_allow)
            if request.approved:
                logger.info("Running user-approved command outside the allowlist")
        result = await asyncio.wait_for(
            self._client.execute(
                ToolCall(
                    id=request.request_id,
                    server_name="dax-system",
                    tool_name=request.tool_name,
                    arguments=request.arguments,
                )
            ),
            timeout=request.timeout_seconds,
        )
        if result.is_error:
            raise RuntimeError(result.content)
        return result.content


class LocalTTSExecutor:
    """One lazy, resident local engine with strictly serialized synthesis."""

    def __init__(self, models_path: str | None = None) -> None:
        self.engines = available_local_tts_engines()
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        self._models_path = models_path or os.environ.get(
            "DAX_MODELS_PATH", str(data_home / "dax-assistant/models")
        )
        self._lock = asyncio.Semaphore(1)
        self._thread_lock = threading.Lock()
        self._engine: Any = None
        self._config_fingerprint = ""

    async def stop(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._stop_blocking)

    async def synthesize(
        self, request: SynthesizeRequest
    ) -> tuple[bytes, int, str, str | None, str]:
        if request.engine not in self.engines:
            raise RuntimeError("Requested local TTS engine is unavailable")
        await self._lock.acquire()
        loop = asyncio.get_running_loop()
        worker = loop.run_in_executor(None, self._synthesize_threadsafe, request)
        release_on_completion = False
        try:
            return await asyncio.wait_for(asyncio.shield(worker), timeout=60.0)
        except (asyncio.CancelledError, TimeoutError):
            # Python cannot kill a running inference thread. Keep admission
            # occupied until it really exits so reconnects cannot accumulate
            # overlapping model work.
            release_on_completion = True
            worker.add_done_callback(lambda _future: loop.call_soon_threadsafe(self._lock.release))
            raise
        finally:
            if not release_on_completion:
                self._lock.release()

    def _stop_blocking(self) -> None:
        with self._thread_lock:
            engine, self._engine = self._engine, None
            if engine is not None:
                engine.stop()

    def _synthesize_threadsafe(
        self, request: SynthesizeRequest
    ) -> tuple[bytes, int, str, str | None, str]:
        with self._thread_lock:
            return self._synthesize_blocking(request)

    def _synthesize_blocking(
        self, request: SynthesizeRequest
    ) -> tuple[bytes, int, str, str | None, str]:
        from dax.voice.tts import build_tts

        config_payload: dict[str, object] = {
            "tts_engine": request.engine,
            "tts_voice_es": request.config["piper_voice_es"],
            "tts_voice_en": request.config["piper_voice_en"],
        }
        if request.engine == "kokoro":
            config_payload["tts_kokoro_voice_es"] = request.config["kokoro_voice_es"]
            config_payload["tts_kokoro_voice_en"] = request.config["kokoro_voice_en"]
            config_payload["tts_kokoro_speed"] = request.config["speed"]
        config_key = hashlib.sha256(
            json.dumps(config_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self._engine is None or self._config_fingerprint != config_key:
            if self._engine is not None:
                self._engine.stop()
            self._engine = build_tts(VoiceConfig.model_validate(config_payload), self._models_path)
            self._engine.start()
            self._config_fingerprint = config_key
        audio = np.asarray(
            self._engine.synthesize(request.text, language=request.language), dtype="<i2"
        )
        pcm = audio.tobytes()
        if not pcm:
            raise RuntimeError("Local TTS returned no audio")
        if len(pcm) > MAX_TTS_AUDIO_BYTES:
            raise RuntimeError("Local TTS audio exceeds limit")
        engine = str(self._engine.engine_name)
        if engine not in {"kokoro", "piper"}:
            raise RuntimeError("Invalid local TTS executor")
        voice = self._engine.voice_name(request.language)
        fingerprint = hashlib.sha256(
            f"{config_key}:{engine}:{voice}:{self._engine.sample_rate}".encode()
        ).hexdigest()[:32]
        return pcm, int(self._engine.sample_rate), engine, voice, fingerprint


class EdgeDaemon:
    def __init__(
        self,
        credentials: NodeCredentials,
        *,
        executor: SystemExecutor | None = None,
        tts_executor: LocalTTSExecutor | None = None,
        connect_factory: ConnectFactory = _connect,
        sleep: Sleep = asyncio.sleep,
        session_port: int | None = None,
    ) -> None:
        self._credentials = credentials
        self._executor = executor or SystemExecutor()
        self._tts_executor = tts_executor or LocalTTSExecutor()
        self._connect = connect_factory
        self._sleep = sleep
        self._stop = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()
        # Only advertised once something is actually listening. Publishing an
        # address nothing answers on would send a phone to whatever else holds
        # that IP.
        self._session_port = session_port
        self._backend_public_key: str | None = None
        self._generation = 0
        # Built on the first policy that turns listening on, so a node that is
        # never asked to listen never opens its microphone at all.
        self._wake: WakeListener | None = None

    @property
    def backend_public_key(self) -> str | None:
        """The key session tickets are verified against, once the backend sends it."""
        return self._backend_public_key

    def stop(self) -> None:
        self._stop.set()

    async def _issue_token(self) -> tuple[str, int]:
        url = f"{self._credentials.endpoint}/api/auth/devices/token"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                json={
                    "device_id": self._credentials.device_id,
                    "device_secret": self._credentials.device_secret,
                },
            )
            response.raise_for_status()
            payload = response.json()
        token = payload.get("token")
        expires = payload.get("expires_in_seconds")
        if payload.get("ok") is not True or not isinstance(token, str) or not token:
            raise RuntimeError("Server did not issue a node token")
        return token, int(expires) if isinstance(expires, int) else 300

    async def run(self) -> None:
        tools = await self._executor.start()
        attempt = 0
        try:
            while not self._stop.is_set():
                connection: WebSocketConnection | None = None
                connected_at: float | None = None
                try:
                    token, expires = await self._issue_token()
                    connection = await self._connect(
                        websocket_url(self._credentials.endpoint),
                        {"Authorization": f"Bearer {token}"},
                    )
                    connected_at = asyncio.get_running_loop().time()
                    endpoints = (
                        local_endpoints(self._session_port)
                        if self._session_port is not None
                        else []
                    )
                    await connection.send(
                        json.dumps(
                            hello_frame(self._credentials.node_name, tools, endpoints)
                        )
                    )
                    await self._serve_until_stop(connection, expires)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("Capability connection failed: %s", exc.__class__.__name__)
                finally:
                    if (
                        connected_at is not None
                        and asyncio.get_running_loop().time() - connected_at >= 30.0
                    ):
                        attempt = 0
                    # The listener sends through the connection it was built
                    # with, so it cannot outlive it. The next policy push on
                    # the new socket starts it again.
                    await self._stop_wake()
                    await self._cancel_requests()
                    if connection is not None:
                        with suppress(Exception):
                            await connection.close()
                if not self._stop.is_set():
                    delay = backoff_delay(attempt)
                    attempt += 1
                    logger.info("Reconnecting capability node in %.1fs", delay)
                    await self._sleep(delay)
        finally:
            await self._stop_wake()
            await self._cancel_requests()
            await self._tts_executor.stop()
            await self._executor.stop()

    async def _stop_wake(self) -> None:
        """Shut the microphone down off the event loop — the join can block."""
        listener, self._wake = self._wake, None
        if listener is not None:
            with suppress(Exception):
                await asyncio.to_thread(listener.stop)

    def _apply_wake_policy(
        self, connection: WebSocketConnection, frame: dict[str, object]
    ) -> None:
        """Start or stop this node's own wake-word detector to match policy."""
        policy = parse_wake_policy(frame)
        if policy is None:
            # An older backend, or a policy without wake fields. Nothing over
            # there would arbitrate our claims, so stay deaf rather than answer
            # over whatever else is in the room.
            if self._wake is not None:
                self._wake.stop()
            return
        if self._wake is None:
            if not policy.enabled:
                return
            try:
                self._wake = WakeListener(
                    lambda payload: connection.send(json.dumps(payload)),
                    asyncio.get_running_loop(),
                )
            except Exception:
                logger.exception("Could not start wake word listening on this node")
                return
        self._wake.apply_policy(policy, self._generation)

    def _handle_wake_response(self, frame: dict[str, object]) -> None:
        listener = self._wake
        if listener is None:
            return
        kind = frame["type"]
        claim_id = frame.get("claim_id")
        lease_id = frame.get("lease_id")
        if kind == "wake_grant":
            if isinstance(claim_id, str) and isinstance(lease_id, str):
                listener.on_grant(claim_id, lease_id)
        elif kind == "wake_yield":
            suppress = frame.get("suppress_ms")
            if not isinstance(suppress, int) or isinstance(suppress, bool):
                suppress = 0
            if isinstance(claim_id, str):
                listener.on_yield(claim_id, suppress)
        elif kind == "listen_stop" and isinstance(lease_id, str):
            listener.on_listen_stop(lease_id)

    async def _serve_until_stop(
        self, connection: WebSocketConnection, expires: int
    ) -> None:
        serve = asyncio.create_task(
            self._serve(connection, expires), name="edge-connection"
        )
        stopping = asyncio.create_task(self._stop.wait(), name="edge-stop-wait")
        done, pending = await asyncio.wait(
            {serve, stopping}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if serve in done:
            await serve
        else:
            await connection.close()

    async def _serve(self, connection: WebSocketConnection, expires: int) -> None:
        refresh = asyncio.create_task(
            self._refresh_after(connection, max(1.0, expires - 30.0)),
            name="edge-token-refresh",
        )
        heartbeat = asyncio.create_task(
            self._heartbeat(connection), name="edge-heartbeat"
        )
        try:
            async for raw in connection:
                frame = parse_frame(raw)
                if frame["type"] == "heartbeat":
                    await connection.send(json.dumps({"type": "heartbeat"}))
                    continue
                if frame["type"] == "ready":
                    # Keep the key that signs session tickets. Without it this
                    # node cannot verify a client's ticket and must refuse
                    # direct sessions rather than serve unverified ones.
                    self._backend_public_key = parse_ready(frame)
                    if self._backend_public_key is None:
                        logger.warning(
                            "Backend did not supply a session-signing key; "
                            "direct client sessions stay disabled"
                        )
                    tts_features = local_tts_features_frame(
                        frame, self._tts_executor.engines
                    )
                    if tts_features is not None:
                        await connection.send(json.dumps(tts_features))
                    generation = frame.get("generation")
                    if isinstance(generation, int) and not isinstance(generation, bool):
                        self._generation = generation
                    continue
                if frame["type"] == "policy":
                    self._apply_wake_policy(connection, frame)
                    continue
                if frame["type"] in _WAKE_RESPONSES:
                    self._handle_wake_response(frame)
                    continue
                if frame["type"] not in {"execute", "synthesize"}:
                    continue
                try:
                    request = (
                        parse_execute(frame)
                        if frame["type"] == "execute"
                        else parse_synthesize(frame)
                    )
                except ValueError as exc:
                    logger.warning("Rejected malformed capability frame: %s", exc)
                    continue
                if len(self._tasks) >= MAX_IN_FLIGHT:
                    if isinstance(request, SynthesizeRequest):
                        busy_frame = synthesize_final_frame(
                            request, success=False, error="Node is busy"
                        )
                    else:
                        busy_frame = result_frame(
                            request, success=False, error="Node is busy"
                        )
                    await connection.send(
                        json.dumps(busy_frame)
                    )
                    continue
                if isinstance(request, ExecuteRequest):
                    coroutine = self._execute_and_send(connection, request)
                    task_name = f"edge-execute-{request.request_id}"
                else:
                    coroutine = self._synthesize_and_send(connection, request)
                    task_name = f"edge-synthesize-{request.request_id}"
                task = asyncio.create_task(coroutine, name=task_name)
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        finally:
            refresh.cancel()
            heartbeat.cancel()
            await asyncio.gather(refresh, heartbeat, return_exceptions=True)

    async def _execute_and_send(
        self, connection: WebSocketConnection, request: ExecuteRequest
    ) -> None:
        try:
            content = await self._executor.execute(request)
            frame = result_frame(request, success=True, content=content)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            frame = result_frame(request, success=False, error="Execution timed out")
        except Exception as exc:
            frame = result_frame(request, success=False, error=str(exc))
        await connection.send(json.dumps(frame))

    async def _synthesize_and_send(
        self, connection: WebSocketConnection, request: SynthesizeRequest
    ) -> None:
        try:
            pcm, sample_rate, engine, voice, fingerprint = (
                await self._tts_executor.synthesize(request)
            )
            digest = hashlib.sha256(pcm).hexdigest()
            chunks = [
                pcm[offset : offset + MAX_TTS_CHUNK_BYTES]
                for offset in range(0, len(pcm), MAX_TTS_CHUNK_BYTES)
            ]
            if len(chunks) > MAX_TTS_CHUNKS:
                raise RuntimeError("Local TTS audio exceeds chunk limit")
            for index, chunk in enumerate(chunks):
                await connection.send(
                    json.dumps(
                        synthesize_chunk_frame(
                            request, index, base64.b64encode(chunk).decode("ascii")
                        )
                    )
                )
            frame = synthesize_final_frame(
                request,
                success=True,
                chunks=len(chunks),
                size=len(pcm),
                sha256=digest,
                sample_rate=sample_rate,
                channels=1,
                sample_width=2,
                engine=engine,
                voice=voice,
                language=request.language,
                executor_fingerprint=fingerprint,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Local TTS synthesis failed", exc_info=True)
            frame = synthesize_final_frame(
                request, success=False, error="Local TTS synthesis failed"
            )
        await connection.send(json.dumps(frame))

    async def _heartbeat(self, connection: WebSocketConnection) -> None:
        while True:
            await self._sleep(HEARTBEAT_SECONDS)
            await connection.send(json.dumps({"type": "heartbeat"}))

    async def _refresh_after(
        self, connection: WebSocketConnection, delay: float
    ) -> None:
        await self._sleep(delay)
        await connection.close()

    async def _cancel_requests(self) -> None:
        tasks = list(self._tasks)
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
