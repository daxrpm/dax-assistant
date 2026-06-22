"""MCP client wrapper — manages a connection to a single MCP server.

Supports two transport modes:
- stdio: spawns a local subprocess, communicates via stdin/stdout
- http: connects to a remote MCP server via Streamable HTTP
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dax.core.exceptions import ToolExecutionError
from dax.core.models import ToolCall, ToolResult

logger = logging.getLogger(__name__)


class MCPClient:
    """Wraps a connection to a single MCP server.

    Args:
        server_name: Unique identifier for this server.
        command: Program to run (stdio transport only).
        args: Command arguments (stdio transport only).
        env: Environment variables (stdio transport only).
        transport: "stdio" or "http".
        url: Server URL (http transport only).
        headers: HTTP headers (http transport only).
    """

    def __init__(
        self,
        server_name: str,
        command: str = "",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        transport: str = "stdio",
        url: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._server_name = server_name
        self._transport = transport
        self._command = command
        self._args = args or []
        self._env = env or {}
        self._url = url
        self._headers = headers or {}
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None

    @property
    def server_name(self) -> str:
        return self._server_name

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    async def connect(self) -> None:
        """Establish a connection using the configured transport."""
        self._exit_stack = AsyncExitStack()

        if self._transport == "stdio":
            await self._connect_stdio()
        elif self._transport in ("http", "streamable_http", "sse"):
            await self._connect_http()
        else:
            raise ValueError(f"Unknown transport: {self._transport}")

    async def _connect_stdio(self) -> None:
        """Connect via stdio transport (local subprocess)."""
        assert self._exit_stack is not None

        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env if self._env else None,
        )

        try:
            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read_stream, write_stream = stdio_transport
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
        except Exception as exc:
            # Clean up exit stack in this task context to avoid anyio
            # cancel scope errors during garbage collection.
            await self._safe_cleanup()
            raise ConnectionError(
                f"Failed to connect to '{self._server_name}': {exc}"
            ) from exc

        logger.info(
            "Connected to MCP server '%s' via stdio (%s %s)",
            self._server_name, self._command, " ".join(self._args),
        )

    async def _connect_http(self) -> None:
        """Connect via Streamable HTTP transport (remote server)."""
        assert self._exit_stack is not None

        try:
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError:
            from mcp.client.sse import sse_client as streamablehttp_client
            logger.info(
                "streamable_http not available, falling back to SSE for '%s'",
                self._server_name,
            )

        # Pre-check: verify the server is reachable and doesn't need auth
        import httpx as _httpx
        try:
            async with _httpx.AsyncClient(timeout=10) as check_client:
                resp = await check_client.post(
                    self._url,
                    json={"jsonrpc": "2.0", "method": "initialize", "id": 0},
                    headers=self._headers or {},
                )
                if resp.status_code == 401:
                    raise ConnectionError(
                        "Server requires authentication (401). "
                        "Use the web UI to authenticate first."
                    )
                if resp.status_code == 403:
                    raise ConnectionError(
                        "Access forbidden (403). Check your credentials."
                    )
        except _httpx.RequestError as e:
            raise ConnectionError(f"Cannot reach server: {e}") from e

        try:
            transport_result = await self._exit_stack.enter_async_context(
                streamablehttp_client(self._url, headers=self._headers)
            )

            # MCP SDK >=1.9 returns (read, write, get_session_id)
            if isinstance(transport_result, tuple) and len(transport_result) >= 3:
                read_stream, write_stream = (
                    transport_result[0], transport_result[1],
                )
            else:
                read_stream, write_stream = transport_result

            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
        except ConnectionError:
            raise
        except Exception as exc:
            await self._safe_cleanup()
            raise ConnectionError(
                f"Failed to connect to '{self._server_name}': {exc}"
            ) from exc

        logger.info(
            "Connected to MCP server '%s' via HTTP (%s)",
            self._server_name, self._url,
        )

    async def disconnect(self) -> None:
        """Close the session and terminate any subprocesses."""
        await self._safe_cleanup()
        logger.info("Disconnected from MCP server '%s'", self._server_name)

    async def _safe_cleanup(self) -> None:
        """Clean up resources, suppressing anyio cancel scope errors."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # anyio cancel scope cleanup in wrong task
            except Exception:
                pass
            self._exit_stack = None
        self._session = None

    async def list_tools(self) -> list[dict[str, Any]]:
        """Query the server for available tools and return their schemas."""
        if not self._session:
            raise RuntimeError(
                f"MCP server '{self._server_name}' not connected"
            )

        result = await self._session.list_tools()
        tools: list[dict[str, Any]] = []

        for tool in result.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema if tool.inputSchema else {},
                "server_name": self._server_name,
            })

        logger.debug(
            "Server '%s' provides %d tools",
            self._server_name, len(tools),
        )
        return tools

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call on this server."""
        if not self._session:
            raise RuntimeError(
                f"MCP server '{self._server_name}' not connected"
            )

        try:
            result = await self._session.call_tool(
                tool_call.tool_name,
                arguments=tool_call.arguments,
            )

            content_parts: list[str] = []
            for block in result.content:
                if hasattr(block, "text"):
                    content_parts.append(block.text)
                else:
                    content_parts.append(str(block))

            return ToolResult(
                call_id=tool_call.id,
                content="\n".join(content_parts),
                is_error=result.isError or False,
            )

        except Exception as e:
            raise ToolExecutionError(
                f"Tool '{tool_call.tool_name}' on server "
                f"'{self._server_name}' failed: {e}"
            ) from e
