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
        policy=ToolPolicy(ask=[tool_name]),
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


@pytest.mark.asyncio
async def test_approval_reaches_the_node_that_has_to_enforce_it() -> None:
    """The flag has to survive every hop, or Allow silently does nothing.

    A node applies its own shell allowlist and cannot see the confirmation
    modal, so it refuses anything not marked approved. This shipped broken
    twice: once because the gate never set the flag, and once because
    ``MCPManager.execute`` rebuilt the call on the way out and dropped it.
    """
    tool_name = canonical_name("node", "shell_run")
    provider = _Provider(tool_name)
    gate = ToolGate(
        provider,  # type: ignore[arg-type]
        policy=ToolPolicy(ask=[]),
        approval=_Approval("once"),  # type: ignore[arg-type]
    )

    await gate.execute(
        ToolCall("call", "capability-node:node", tool_name, {"command": "flatpak run x"})
    )

    assert [c.human_approved for c in provider.executed] == [True]


@pytest.mark.asyncio
async def test_a_remembered_node_command_stops_asking_but_stays_approved() -> None:
    """"Approve and save" has to mean it, and keep meaning it next time."""
    from dax.core.config import NodesConfig

    tool_name = canonical_name("node", "shell_run")
    provider = _Provider(tool_name)
    approval = _Approval("save")
    nodes = NodesConfig()
    saved: list[bool] = []

    async def persist() -> None:
        saved.append(True)

    gate = ToolGate(
        provider,  # type: ignore[arg-type]
        policy=ToolPolicy(ask=[tool_name]),
        approval=approval,  # type: ignore[arg-type]
        nodes=nodes,
        save_config=persist,
    )
    call = ToolCall(
        "call", "capability-node:node", tool_name, {"command": "flatpak run x"}
    )

    await gate.execute(call)
    assert nodes.node_allows_command("node", "flatpak") is True
    assert saved == [True]

    # Second time: no prompt, but the node still has to be told it is approved.
    await gate.execute(call)
    assert len(approval.requests) == 1
    assert [c.human_approved for c in provider.executed] == [True, True]


@pytest.mark.asyncio
async def test_remembering_a_node_command_does_not_grant_it_on_the_backend() -> None:
    """Different machines, different contents — the lists must stay separate."""
    from dax.core.config import NodesConfig
    from dax.core.shell_allow import ShellAllowlist

    tool_name = canonical_name("node", "shell_run")
    provider = _Provider(tool_name)
    backend_allow = ShellAllowlist([])
    nodes = NodesConfig()
    gate = ToolGate(
        provider,  # type: ignore[arg-type]
        policy=ToolPolicy(ask=[]),
        approval=_Approval("save"),  # type: ignore[arg-type]
        shell_allow=backend_allow,
        nodes=nodes,
    )

    await gate.execute(
        ToolCall("call", "capability-node:node", tool_name, {"command": "flatpak run x"})
    )

    assert nodes.node_allows_command("node", "flatpak") is True
    assert backend_allow.allows_command("flatpak run x") is False


@pytest.mark.asyncio
async def test_a_remembered_node_app_stops_asking_only_for_that_app() -> None:
    from dax.core.config import NodesConfig

    tool_name = canonical_name("node", "app_open")
    provider = _Provider(tool_name)
    approval = _Approval("save")
    nodes = NodesConfig()
    saved: list[bool] = []

    async def persist() -> None:
        saved.append(True)

    gate = ToolGate(
        provider,  # type: ignore[arg-type]
        policy=ToolPolicy(ask=[tool_name]),
        approval=approval,  # type: ignore[arg-type]
        nodes=nodes,
        save_config=persist,
    )
    spotify = ToolCall(
        "spotify", "capability-node:node", tool_name, {"app": " Spotify "}
    )

    await gate.execute(spotify)
    await gate.execute(spotify)
    await gate.execute(
        ToolCall("code", "capability-node:node", tool_name, {"app": "Code"})
    )

    assert nodes.node_allows_app("node", "spotify") is True
    assert nodes.node_allows_app("node", "code") is True
    assert saved == [True, True]
    assert len(approval.requests) == 2
    assert approval.requests[0]["options"] == ["once", "save"]
    assert [call.human_approved for call in provider.executed] == [True, True, True]


@pytest.mark.asyncio
async def test_node_app_denial_overrides_a_remembered_app() -> None:
    from dax.core.config import NodesConfig

    tool_name = canonical_name("node", "app_open")
    provider = _Provider(tool_name)
    nodes = NodesConfig()
    nodes.remember_node_app("node", "spotify")
    gate = ToolGate(
        provider,  # type: ignore[arg-type]
        policy=ToolPolicy(ask=[], deny=[tool_name]),
        approval=_Approval("save"),  # type: ignore[arg-type]
        nodes=nodes,
    )

    result = await gate.execute(
        ToolCall("call", "capability-node:node", tool_name, {"app": "Spotify"})
    )

    assert result.is_error is True
    assert provider.executed == []
