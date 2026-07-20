from __future__ import annotations

from typing import Any

import pytest

from dax.capabilities.protocol import canonical_name
from dax.core.models import ToolCall, ToolResult
from dax.core.policy import ToolPolicy
from dax.orchestrator.tool_gate import ToolGate


class _Provider:
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self.executed: list[ToolCall] = []

    def get_server_for_tool(self, tool_name: str) -> str | None:
        return "capability-node:node" if tool_name == self.tool_name else None

    async def execute(self, call: ToolCall) -> ToolResult:
        self.executed.append(call)
        return ToolResult(call.id, "ok")


class _Approval:
    def __init__(self, decision: str) -> None:
        self.decision = decision
        self.requests: list[dict[str, Any]] = []

    async def request(self, **kwargs: Any) -> str:
        self.requests.append(kwargs)
        return self.decision


@pytest.mark.asyncio
async def test_capability_node_shell_never_auto_runs() -> None:
    tool_name = canonical_name("node", "shell_run")
    provider = _Provider(tool_name)
    approval = _Approval("once")
    gate = ToolGate(
        provider,  # type: ignore[arg-type]
        policy=ToolPolicy(ask=[]),
        approval=approval,  # type: ignore[arg-type]
    )

    result = await gate.execute(
        ToolCall("call", "capability-node:node", tool_name, {"command": "ls -la"})
    )

    assert not result.is_error
    assert len(provider.executed) == 1
    assert approval.requests[0]["options"] == ["once"]


@pytest.mark.asyncio
async def test_capability_node_shell_denial_stays_fail_closed() -> None:
    tool_name = canonical_name("node", "shell_run")
    provider = _Provider(tool_name)
    approval = _Approval("deny")
    gate = ToolGate(
        provider,  # type: ignore[arg-type]
        policy=ToolPolicy(ask=[], deny=[tool_name]),
        approval=approval,  # type: ignore[arg-type]
    )

    result = await gate.execute(
        ToolCall("call", "capability-node:node", tool_name, {"command": "ls -la"})
    )

    assert result.is_error
    assert provider.executed == []
    assert approval.requests == []
