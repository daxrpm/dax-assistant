"""MCP server manager — implements the ToolProvider protocol.

Manages the lifecycle of multiple MCP server connections (both local
stdio and remote HTTP), aggregates tools, and routes execution.

Supports environment variable substitution in config values using
{env:VAR_NAME} syntax for secure credential management.
"""

from __future__ import annotations

import logging
import os
import re
import asyncio
from typing import TYPE_CHECKING, Any

from dax.core.exceptions import ToolNotFoundError
from dax.core.models import ToolCall, ToolResult
from dax.mcp.client import MCPClient
from dax.mcp.registry import ToolRegistry

if TYPE_CHECKING:
    from dax.core.config import MCPConfig

logger = logging.getLogger(__name__)

# Pattern for {env:VAR_NAME} substitution
_ENV_PATTERN = re.compile(r"\{env:(\w+)\}")


def _resolve_env_vars(value: str) -> str:
    """Replace {env:VAR_NAME} patterns with environment variable values."""
    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name, "")
        if not env_value:
            logger.warning("Environment variable '%s' not set", var_name)
        return env_value

    return _ENV_PATTERN.sub(_replace, value)


def _resolve_env_dict(d: dict[str, str]) -> dict[str, str]:
    """Resolve env vars in all values of a dict."""
    return {k: _resolve_env_vars(v) for k, v in d.items()}


def _get_oauth_token(server_name: str) -> str | None:
    """Get stored OAuth access token for an MCP server, if available."""
    try:
        from dax.web.routes.oauth import get_access_token
        return get_access_token(server_name)
    except Exception:
        return None


class MCPManager:
    """Manages multiple MCP server connections.

    Implements the ToolProvider protocol. Supports:
    - **stdio** transport: spawns local subprocess (npx, uvx, etc.)
    - **streamable_http** transport: connects to remote HTTP MCP server

    Config values support {env:VAR_NAME} for secure credential injection.
    """

    def __init__(self, config: MCPConfig) -> None:
        self._config = config
        self._clients: dict[str, MCPClient] = {}
        self._registry = ToolRegistry()
        self._lock = asyncio.Lock()
        self._stopping = False
        self._ops: asyncio.Queue[
            tuple[str, str | None, Any, asyncio.Future[Any]]
        ] | None = None
        self._worker: asyncio.Task[None] | None = None

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def _make_client(self, name: str, server_config: Any) -> MCPClient | None:
        """Build an unconnected client for a server config (env resolved)."""
        transport = server_config.transport

        if transport == "stdio":
            if not server_config.command:
                logger.warning("MCP server '%s' (stdio) has no command, skipping", name)
                return None
            return MCPClient(
                server_name=name,
                command=server_config.command,
                args=server_config.args,
                env=_resolve_env_dict(server_config.env),
            )

        if transport in ("streamable_http", "sse", "http"):
            if not server_config.url:
                logger.warning(
                    "MCP server '%s' (%s) has no URL, skipping", name, transport
                )
                return None
            headers = _resolve_env_dict(server_config.headers)
            oauth_token = _get_oauth_token(name)
            if oauth_token:
                headers["Authorization"] = f"Bearer {oauth_token}"
            return MCPClient(
                server_name=name,
                transport="http",
                url=_resolve_env_vars(server_config.url),
                headers=headers,
            )

        logger.warning(
            "MCP server '%s' has unknown transport '%s', skipping", name, transport
        )
        return None

    async def start(self) -> None:
        """Launch and connect to all enabled MCP servers."""
        self._stopping = False
        self._ensure_worker()
        for name, server_config in self._config.servers.items():
            if not server_config.enabled:
                logger.info("MCP server '%s' is disabled, skipping", name)
                continue
            try:
                await self.add_server(name, server_config)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException:
                # BaseException (not just Exception) because anyio/MCP SDK can
                # propagate CancelledError (a BaseException in Python 3.11)
                # when HTTP transport connection fails.
                logger.exception("Failed to start MCP server '%s'", name)

        logger.info(
            "MCP Manager started: %d servers, %d total tools",
            len(self._clients),
            self._registry.tool_count,
        )

    async def add_server(self, name: str, server_config: Any) -> int:
        """Connect to a server and register its tools live. Returns tool count.

        Reconnects cleanly if the server was already connected. Raises on
        connection failure so callers can surface the error.
        """
        return await self._submit("add", name, server_config)

    async def _add_server_now(self, name: str, server_config: Any) -> int:
        if self._stopping:
            raise RuntimeError("MCP manager is stopping")

        await self._remove_server_now(name)

        # Best-effort: refresh an expired OAuth token before (re)connecting an
        # HTTP server so the new Bearer header carries a valid token.
        if getattr(server_config, "transport", "stdio") in (
            "streamable_http", "sse", "http"
        ):
            try:
                from dax.web.routes.oauth import refresh_access_token

                await refresh_access_token(name)
            except Exception:
                logger.debug("Token refresh skipped for '%s'", name, exc_info=True)

        client = self._make_client(name, server_config)
        if client is None:
            raise ValueError(f"MCP server '{name}' has an invalid configuration")

        try:
            await client.connect()
            tools = await client.list_tools()
        except BaseException:
            await client.disconnect()
            raise

        self._clients[name] = client
        self._registry.register(tools)
        logger.info(
            "MCP server '%s' (%s) ready with %d tools",
            name, server_config.transport, len(tools),
        )
        return len(tools)

    async def remove_server(self, name: str) -> None:
        """Disconnect a server (if connected) and drop its tools."""
        await self._submit("remove", name, None)

    async def _remove_server_now(self, name: str) -> None:
        """Disconnect a server from the MCP lifecycle worker task."""
        client = self._clients.pop(name, None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                logger.exception("Error disconnecting MCP server '%s'", name)
        self._registry.unregister_server(name)

    async def stop(self) -> None:
        """Disconnect from all MCP servers."""
        self._stopping = True
        if self._worker is not None and not self._worker.done():
            await self._submit("stop", None, None)
            await self._worker
            self._worker = None
            self._ops = None
            return

        await self._stop_now()

    async def _stop_now(self) -> None:
        clients = list(self._clients.items())
        self._clients.clear()
        self._registry.clear()

        for name, client in clients:
            try:
                await client.disconnect()
            except Exception:
                logger.exception("Error disconnecting MCP server '%s'", name)

        logger.info("MCP Manager stopped")

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._ops = asyncio.Queue()
            self._worker = asyncio.create_task(
                self._run_lifecycle_worker(),
                name="mcp-lifecycle-worker",
            )

    async def _submit(self, op: str, name: str | None, payload: Any) -> Any:
        self._ensure_worker()
        assert self._ops is not None
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        await self._ops.put((op, name, payload, future))
        return await future

    async def _run_lifecycle_worker(self) -> None:
        assert self._ops is not None
        while True:
            op, name, payload, future = await self._ops.get()
            try:
                if op == "add":
                    assert name is not None
                    result = await self._add_server_now(name, payload)
                elif op == "remove":
                    assert name is not None
                    result = await self._remove_server_now(name)
                elif op == "stop":
                    result = await self._stop_now()
                    if not future.done():
                        future.set_result(result)
                    break
                else:
                    raise RuntimeError(f"Unknown MCP lifecycle op: {op}")
            except BaseException as exc:
                if not future.done():
                    future.set_exception(exc)
            else:
                if not future.done():
                    future.set_result(result)

    def server_status(self) -> list[dict[str, Any]]:
        """Per-configured-server connection + tool status for the web UI."""
        lookup = self._registry.server_lookup
        statuses: list[dict[str, Any]] = []
        for name, cfg in self._config.servers.items():
            client = self._clients.get(name)
            tools = sorted(t for t, s in lookup.items() if s == name)
            statuses.append(
                {
                    "name": name,
                    "connected": client is not None and client.is_connected,
                    "transport": cfg.transport,
                    "enabled": cfg.enabled,
                    "tool_count": len(tools),
                    "tools": tools,
                }
            )
        return statuses

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return all available tool schemas across all servers."""
        return self._registry.all_tools

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call on the appropriate MCP server."""
        server_name = tool_call.server_name
        if not server_name or server_name == "":
            server_name = (
                self._registry.get_server_for_tool(tool_call.tool_name) or ""
            )

        if not server_name:
            raise ToolNotFoundError(
                f"No server found for tool '{tool_call.tool_name}'"
            )

        client = self._clients.get(server_name)
        if client is None:
            raise ToolNotFoundError(
                f"MCP server '{server_name}' is not connected"
            )

        logger.info(
            "Executing tool '%s' on server '%s'",
            tool_call.tool_name, server_name,
        )

        resolved_call = ToolCall(
            id=tool_call.id,
            server_name=server_name,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
        )

        return await client.execute(resolved_call)
