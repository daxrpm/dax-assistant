"""Tests for the MCP tool registry."""

from __future__ import annotations

from dax.mcp.registry import ToolRegistry


def _make_tools(server: str, names: list[str]) -> list[dict]:
    return [
        {
            "name": name,
            "description": f"{name} description",
            "inputSchema": {"type": "object", "properties": {}},
            "server_name": server,
        }
        for name in names
    ]


class TestToolRegistry:
    def test_empty_registry(self):
        registry = ToolRegistry()
        assert registry.tool_count == 0
        assert registry.all_tools == []

    def test_register_tools(self):
        registry = ToolRegistry()
        tools = _make_tools("shell", ["execute", "list_processes"])
        registry.register(tools)

        assert registry.tool_count == 2
        assert registry.get_server_for_tool("execute") == "shell"
        assert registry.get_server_for_tool("list_processes") == "shell"

    def test_register_multiple_servers(self):
        registry = ToolRegistry()
        registry.register(_make_tools("shell", ["execute"]))
        registry.register(_make_tools("nextcloud", ["get_events", "create_event"]))
        registry.register(_make_tools("spotify", ["play", "pause"]))

        assert registry.tool_count == 5
        assert registry.get_server_for_tool("execute") == "shell"
        assert registry.get_server_for_tool("get_events") == "nextcloud"
        assert registry.get_server_for_tool("play") == "spotify"

    def test_unknown_tool_returns_none(self):
        registry = ToolRegistry()
        assert registry.get_server_for_tool("nonexistent") is None

    def test_server_lookup_dict(self):
        registry = ToolRegistry()
        registry.register(_make_tools("shell", ["cmd_a", "cmd_b"]))

        lookup = registry.server_lookup
        assert lookup == {"cmd_a": "shell", "cmd_b": "shell"}
        # Should be a copy
        lookup["cmd_a"] = "hacked"
        assert registry.get_server_for_tool("cmd_a") == "shell"

    def test_clear(self):
        registry = ToolRegistry()
        registry.register(_make_tools("shell", ["execute"]))
        registry.clear()

        assert registry.tool_count == 0
        assert registry.get_server_for_tool("execute") is None

    def test_get_relevant_tools_with_few_tools(self):
        registry = ToolRegistry()
        registry.register(_make_tools("shell", ["execute", "list"]))

        # With fewer tools than max, returns all
        result = registry.get_relevant_tools("anything", max_tools=10)
        assert len(result) == 2

    def test_get_relevant_tools_filters_by_query(self):
        registry = ToolRegistry()
        tools = [
            {
                "name": "play_music",
                "description": "Play a song",
                "inputSchema": {},
                "server_name": "spotify",
            },
            {
                "name": "get_events",
                "description": "Get calendar events",
                "inputSchema": {},
                "server_name": "nc",
            },
            {
                "name": "turn_light",
                "description": "Turn on/off light",
                "inputSchema": {},
                "server_name": "ha",
            },
        ]
        for t in tools:
            registry.register([t])

        result = registry.get_relevant_tools("play some music", max_tools=1)
        assert len(result) == 1
        assert result[0]["name"] == "play_music"

    def test_duplicate_tool_overwrites(self):
        registry = ToolRegistry()
        registry.register(_make_tools("server_a", ["shared_tool"]))
        registry.register(_make_tools("server_b", ["shared_tool"]))

        # Last registration wins
        assert registry.get_server_for_tool("shared_tool") == "server_b"
