"""Tests for MCP manager env var resolution and transport selection."""

from __future__ import annotations

import os
from unittest.mock import patch

from dax.mcp.manager import _resolve_env_dict, _resolve_env_vars


class TestEnvVarResolution:
    def test_no_pattern(self):
        assert _resolve_env_vars("plain text") == "plain text"

    def test_single_env_var(self):
        with patch.dict(os.environ, {"MY_API_KEY": "secret123"}):
            result = _resolve_env_vars("{env:MY_API_KEY}")
            assert result == "secret123"

    def test_env_var_in_url(self):
        with patch.dict(os.environ, {"HA_TOKEN": "abc"}):
            result = _resolve_env_vars("Bearer {env:HA_TOKEN}")
            assert result == "Bearer abc"

    def test_multiple_env_vars(self):
        with patch.dict(os.environ, {"USER": "dax", "HOST": "local"}):
            result = _resolve_env_vars("{env:USER}@{env:HOST}")
            assert result == "dax@local"

    def test_missing_env_var_returns_empty(self):
        result = _resolve_env_vars("{env:NONEXISTENT_VAR_12345}")
        assert result == ""

    def test_resolve_dict(self):
        with patch.dict(os.environ, {"KEY": "value"}):
            result = _resolve_env_dict({
                "plain": "no change",
                "secret": "{env:KEY}",
            })
            assert result == {"plain": "no change", "secret": "value"}

    def test_resolve_dict_uses_server_variables(self):
        result = _resolve_env_dict(
            {"Authorization": "Bearer {env:HA_TOKEN}"},
            {"HA_TOKEN": "server-token"},
        )
        assert result == {"Authorization": "Bearer server-token"}


class TestApprovalSurvivesDispatch:
    """The manager rebuilds a call before dispatch; it must not lose the flag.

    A capability node refuses any command it cannot see was approved, so a
    dropped ``human_approved`` here makes the confirmation modal appear, the
    user click Allow, and the node refuse it anyway. That shipped once.
    """

    async def test_a_node_bound_call_arrives_still_marked_approved(self) -> None:
        from dax.core.config import DaxConfig
        from dax.core.models import ToolCall, ToolResult
        from dax.mcp.manager import MCPManager

        received: list[ToolCall] = []

        async def dynamic(call: ToolCall) -> ToolResult:
            received.append(call)
            return ToolResult(call.id, "ok")

        manager = MCPManager(DaxConfig().mcp)
        tool = {
            "name": "node_x__shell_run",
            "description": "",
            "inputSchema": {"type": "object", "properties": {}},
            "server_name": "capability-node:x",
        }
        manager.register_dynamic_provider("capability-node:x", [tool], dynamic)

        result = await manager.execute(
            ToolCall(
                "call",
                "capability-node:x",
                "node_x__shell_run",
                {"command": "flatpak run x"},
                human_approved=True,
            )
        )

        assert not result.is_error
        assert [c.human_approved for c in received] == [True]
