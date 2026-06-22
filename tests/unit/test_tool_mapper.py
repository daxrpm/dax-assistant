"""Tests for MCP → OpenAI tool schema mapping and relevance filtering."""

from __future__ import annotations

from dax.llm.tool_mapper import (
    filter_tools_by_relevance,
    mcp_tools_to_openai,
    parse_tool_calls_from_response,
)


class TestMCPToolsToOpenAI:
    def test_basic_conversion(self):
        mcp_tools = [
            {
                "name": "get_weather",
                "description": "Get current weather",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                    },
                    "required": ["city"],
                },
            }
        ]

        result = mcp_tools_to_openai(mcp_tools)

        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "get_weather"
        assert result[0]["function"]["description"] == "Get current weather"
        assert "city" in result[0]["function"]["parameters"]["properties"]

    def test_empty_input(self):
        assert mcp_tools_to_openai([]) == []

    def test_missing_schema(self):
        mcp_tools = [{"name": "simple_tool", "description": "A tool"}]
        result = mcp_tools_to_openai(mcp_tools)
        assert result[0]["function"]["parameters"] == {"type": "object", "properties": {}}

    def test_multiple_tools(self):
        mcp_tools = [
            {"name": "tool_a", "description": "A", "inputSchema": {}},
            {"name": "tool_b", "description": "B", "inputSchema": {}},
            {"name": "tool_c", "description": "C", "inputSchema": {}},
        ]
        result = mcp_tools_to_openai(mcp_tools)
        assert len(result) == 3
        assert [t["function"]["name"] for t in result] == ["tool_a", "tool_b", "tool_c"]


class TestParseToolCalls:
    def test_parse_dict_format(self):
        calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "get_events",
                    "arguments": '{"date": "2026-03-19"}',
                },
            }
        ]
        lookup = {"get_events": "nextcloud"}

        result = parse_tool_calls_from_response(calls, lookup)

        assert len(result) == 1
        assert result[0]["id"] == "call_1"
        assert result[0]["server_name"] == "nextcloud"
        assert result[0]["tool_name"] == "get_events"
        assert result[0]["arguments"]["date"] == "2026-03-19"

    def test_unknown_server(self):
        calls = [{"id": "c1", "function": {"name": "mystery", "arguments": "{}"}}]
        result = parse_tool_calls_from_response(calls, {})
        assert result[0]["server_name"] == "unknown"

    def test_invalid_json_arguments(self):
        calls = [{"id": "c1", "function": {"name": "foo", "arguments": "not json"}}]
        result = parse_tool_calls_from_response(calls, {})
        assert result[0]["arguments"] == {}


class TestFilterToolsByRelevance:
    def _make_tools(self, names_and_descs: list[tuple[str, str]]) -> list[dict]:
        return [{"name": n, "description": d} for n, d in names_and_descs]

    def test_returns_all_when_under_limit(self):
        tools = self._make_tools([("a", "desc"), ("b", "desc")])
        result = filter_tools_by_relevance(tools, "anything", max_tools=5)
        assert len(result) == 2

    def test_filters_by_keyword_match(self):
        tools = self._make_tools([
            ("play_music", "Play a song on Spotify"),
            ("get_calendar", "Get calendar events from Nextcloud"),
            ("turn_on_light", "Turn on a smart home light"),
            ("list_files", "List files in a directory"),
            ("search_contacts", "Search contacts in address book"),
            ("execute_command", "Execute a shell command"),
            ("create_event", "Create a calendar event"),
            ("get_weather", "Get weather forecast"),
            ("set_alarm", "Set an alarm"),
            ("send_message", "Send a message"),
        ])

        result = filter_tools_by_relevance(tools, "play some music", max_tools=3)
        names = [t["name"] for t in result]

        # play_music should be first — name matches "play" and desc matches "music"
        assert "play_music" in names

    def test_name_bonus(self):
        tools = self._make_tools([
            ("get_calendar", "Retrieve calendar events"),
            ("set_reminder", "Calendar reminder tool"),
        ])

        result = filter_tools_by_relevance(tools, "calendar", max_tools=1)
        # get_calendar gets name bonus for containing "calendar"
        assert result[0]["name"] == "get_calendar"

    def test_max_tools_respected(self):
        tools = self._make_tools([(f"tool_{i}", f"description {i}") for i in range(20)])
        result = filter_tools_by_relevance(tools, "query", max_tools=5)
        assert len(result) == 5
