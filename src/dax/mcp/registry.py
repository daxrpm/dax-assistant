"""Tool registry — aggregates tools from all MCP servers.

Provides lookup by tool name to find the correct server,
and filtering by relevance for LLM context window management.
"""

from __future__ import annotations

import logging
from typing import Any

from dax.llm.tool_mapper import filter_tools_by_relevance

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Aggregates tool schemas from multiple MCP servers.

    Maintains a mapping of tool_name → server_name for routing
    tool calls to the correct MCP client.
    """

    def __init__(self) -> None:
        self._tools: list[dict[str, Any]] = []
        self._tool_to_server: dict[str, str] = {}

    def register(self, tools: list[dict[str, Any]]) -> None:
        """Register tools from an MCP server.

        Each tool dict must include a 'server_name' field.
        """
        for tool in tools:
            name = tool["name"]
            server = tool.get("server_name", "unknown")

            if name in self._tool_to_server:
                logger.warning(
                    "Tool '%s' already registered from server '%s', "
                    "overwriting with server '%s'",
                    name,
                    self._tool_to_server[name],
                    server,
                )

            self._tool_to_server[name] = server
            self._tools.append(tool)

        logger.info("Registered %d tools from server", len(tools))

    def unregister_server(self, server_name: str) -> None:
        """Remove all tools belonging to a server (e.g. on disconnect)."""
        self._tools = [
            t for t in self._tools if t.get("server_name") != server_name
        ]
        self._tool_to_server = {
            name: server
            for name, server in self._tool_to_server.items()
            if server != server_name
        }

    def replace_server(
        self,
        server_name: str,
        tools: list[dict[str, Any]],
        *,
        reject_collisions: bool = False,
    ) -> None:
        """Atomically replace one server's inventory."""
        names = [str(tool["name"]) for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate tool names in inventory")
        if any(tool.get("server_name") != server_name for tool in tools):
            raise ValueError("Tool inventory has an invalid server owner")
        if reject_collisions:
            collisions = {
                name
                for name in names
                if (owner := self._tool_to_server.get(name)) is not None
                and owner != server_name
            }
            if collisions:
                raise ValueError(
                    f"Tool name collision: {', '.join(sorted(collisions))}"
                )
        retained = [
            tool for tool in self._tools if tool.get("server_name") != server_name
        ]
        retained_lookup = {
            name: owner
            for name, owner in self._tool_to_server.items()
            if owner != server_name
        }
        self._tools = [*retained, *tools]
        self._tool_to_server = retained_lookup | dict.fromkeys(names, server_name)

    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()
        self._tool_to_server.clear()

    @property
    def all_tools(self) -> list[dict[str, Any]]:
        """Return all registered tool schemas."""
        return list(self._tools)

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def server_lookup(self) -> dict[str, str]:
        """Return the tool_name → server_name mapping."""
        return dict(self._tool_to_server)

    def get_server_for_tool(self, tool_name: str) -> str | None:
        """Look up which server owns a tool."""
        return self._tool_to_server.get(tool_name)

    def get_relevant_tools(
        self,
        query: str,
        max_tools: int = 120,
    ) -> list[dict[str, Any]]:
        """Return the most relevant tools for a given query.

        Uses keyword matching to filter down to max_tools.
        If total tools <= max_tools, returns all.
        """
        return filter_tools_by_relevance(self._tools, query, max_tools)
