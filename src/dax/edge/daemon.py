"""Outbound capability-node daemon and persistent bundled MCP executor."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import random
import socket
import sys
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol

import httpx
import psutil
from websockets.asyncio.client import ClientConnection, connect

from dax.core.models import ToolCall
from dax.mcp.client import MCPClient
from dax.mcp.manager import _session_passthrough_env
from dax.mcp_servers.system.server import validate_command

from .credentials import NodeCredentials, websocket_url
from .protocol import (
    ExecuteRequest,
    hello_frame,
    parse_execute,
    parse_frame,
    parse_ready,
    result_frame,
)

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 20.0
MAX_IN_FLIGHT = 8
MAX_ADVERTISED_ENDPOINTS = 4


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
            validate_command(command)
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


class EdgeDaemon:
    def __init__(
        self,
        credentials: NodeCredentials,
        *,
        executor: SystemExecutor | None = None,
        connect_factory: ConnectFactory = _connect,
        sleep: Sleep = asyncio.sleep,
        session_port: int | None = None,
    ) -> None:
        self._credentials = credentials
        self._executor = executor or SystemExecutor()
        self._connect = connect_factory
        self._sleep = sleep
        self._stop = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()
        # Only advertised once something is actually listening. Publishing an
        # address nothing answers on would send a phone to whatever else holds
        # that IP.
        self._session_port = session_port
        self._backend_public_key: str | None = None

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
            await self._cancel_requests()
            await self._executor.stop()

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
                    continue
                if frame["type"] != "execute":
                    continue
                try:
                    request = parse_execute(frame)
                except ValueError as exc:
                    logger.warning("Rejected malformed execute frame: %s", exc)
                    continue
                if len(self._tasks) >= MAX_IN_FLIGHT:
                    await connection.send(
                        json.dumps(
                            result_frame(request, success=False, error="Node is busy")
                        )
                    )
                    continue
                task = asyncio.create_task(
                    self._execute_and_send(connection, request),
                    name=f"edge-execute-{request.request_id}",
                )
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
