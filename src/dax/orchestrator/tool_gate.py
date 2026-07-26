"""Tool execution gate — policy, human-in-the-loop confirmation, audit.

Extracted from the Agent so the orchestration loop stays focused on the
LLM↔tool conversation. The gate owns *whether and how* a tool call runs:

1. resolve the owning server (for the policy decision + audit record),
2. apply the allow/ask/deny policy, with the shell tool gated by the
   user-managed binary allowlist instead of the name-pattern policy,
3. block on the confirmation modal for ``ask`` decisions,
4. execute via the tool provider and write an audit-log entry.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from dax.capabilities.protocol import canonical_name, is_canonical_shell
from dax.core.exceptions import ToolError
from dax.core.models import ToolCall, ToolResult
from dax.core.policy import Decision
from dax.core.shell_allow import is_auto_allowable, shell_binary

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from dax.core.config import NodesConfig
    from dax.core.policy import ToolPolicy
    from dax.core.ports import Storage, ToolProvider
    from dax.core.shell_allow import ShellAllowlist
    from dax.orchestrator.approval import ApprovalManager

logger = logging.getLogger(__name__)

# The dax-system tool that runs shell commands — gated by the shell allowlist
# rather than the generic name-pattern policy.
_SHELL_TOOL_NAME = "shell_run"
_APP_OPEN_TOOL_NAME = "app_open"


class ToolGate:
    """Decides and performs tool execution under policy + confirmation."""

    def __init__(
        self,
        tools: ToolProvider,
        *,
        policy: ToolPolicy | None = None,
        approval: ApprovalManager | None = None,
        shell_allow: ShellAllowlist | None = None,
        storage: Storage | None = None,
        nodes: NodesConfig | None = None,
        save_config: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._tools = tools
        # Held live so a remembered command is visible to the next turn without
        # a reload, matching how every other settings edit behaves.
        self._nodes = nodes
        self._save_config = save_config
        # When no policy/approval is wired, tools run unrestricted (used in
        # tests). In the app both are provided so destructive actions are gated.
        self._policy = policy
        self._approval = approval
        self._shell_allow = shell_allow
        self._storage = storage

    async def execute(
        self,
        tool_call: ToolCall,
        *,
        channel: str | None = None,
        session_id: str | None = None,
    ) -> ToolResult:
        """Resolve, gate, execute, and audit a single tool call.

        ``channel`` is the originating channel (e.g. "voice"); it routes
        confirmation prompts to the right place (spoken vs web modal).
        """
        resolved_call = self._resolve_server(tool_call)

        blocked, resolved_call = await self._gate(
            resolved_call, channel=channel, session_id=session_id
        )
        if blocked is not None:
            return blocked

        try:
            result = await self._tools.execute(resolved_call)
            logger.info(
                "Tool '%s' executed (error=%s): %.100s",
                resolved_call.tool_name,
                result.is_error,
                result.content,
            )
            await self._audit(resolved_call, "error" if result.is_error else "executed")
            return result
        except ToolError as e:
            logger.warning("Tool execution failed: %s", e)
            await self._audit(resolved_call, "error")
            return ToolResult(
                call_id=tool_call.id,
                content=f"Error: {e}",
                is_error=True,
            )

    def _resolve_server(self, tool_call: ToolCall) -> ToolCall:
        """Fill in the owning server so the gate + audit record it (the tool
        provider also resolves it at execution time)."""
        if tool_call.server_name:
            return tool_call
        server = self._tools.get_server_for_tool(tool_call.tool_name)
        if not server:
            return tool_call
        return ToolCall(
            id=tool_call.id,
            server_name=server,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            human_approved=tool_call.human_approved,
        )

    async def _gate(
        self,
        call: ToolCall,
        *,
        channel: str | None = None,
        session_id: str | None = None,
    ) -> tuple[ToolResult | None, ToolCall]:
        """Apply the policy.

        Returns a blocking ToolResult (or None to proceed) together with the
        call to actually run — which carries ``human_approved`` when the user
        confirmed it, so an executor with its own allowlist can tell the
        difference between the agent asking and the user agreeing.
        """
        if self._policy is None:
            return None, call
        decision = self._policy.decide(call.tool_name)
        if decision is Decision.DENY:
            logger.warning("Tool '%s' denied by policy", call.tool_name)
            await self._audit(call, "denied")
            return (
                ToolResult(
                    call_id=call.id,
                    content=f"Error: tool '{call.tool_name}' is not permitted.",
                    is_error=True,
                ),
                call,
            )
        # Local shell calls use the user-managed allowlist; canonical node shell
        # calls always enter the one-time approval path.
        if self._is_trusted_shell(call) and (
            is_canonical_shell(call.tool_name) or self._shell_allow is not None
        ):
            return await self._gate_shell(call, channel=channel, session_id=session_id)
        if self._is_trusted_node_app_open(call):
            if decision is Decision.ALLOW:
                return None, replace(call, human_approved=True)
            return await self._gate_node_app_open(
                call, channel=channel, session_id=session_id
            )
        if decision is Decision.ALLOW:
            return None, call
        # ASK — require confirmation.
        if self._approval is None:
            await self._audit(call, "denied")
            return (
                ToolResult(
                    call_id=call.id,
                    content=(
                        f"Error: '{call.tool_name}' requires confirmation but no "
                        "approval channel is available."
                    ),
                    is_error=True,
                ),
                call,
            )
        result = await self._approval.request(
            tool_name=call.tool_name,
            server_name=call.server_name,
            arguments=dict(call.arguments),
            channel=channel,
            session_id=session_id,
        )
        approved = result != "deny"
        await self._audit(call, "approved" if approved else "declined")
        if not approved:
            return (
                ToolResult(
                    call_id=call.id,
                    content=f"Error: the user declined to run '{call.tool_name}'.",
                    is_error=True,
                ),
                call,
            )
        return None, replace(call, human_approved=True)

    @staticmethod
    def _node_id(call: ToolCall) -> str | None:
        """The node behind a canonical node tool, from its owning server name.

        The tool name itself carries only a hash of the id, so the server name
        is the only place the id survives intact.
        """
        prefix = "capability-node:"
        if not call.server_name.startswith(prefix):
            return None
        return call.server_name.removeprefix(prefix) or None

    async def _persist_nodes(self) -> None:
        """Write remembered node authorizations through across restarts."""
        if self._save_config is None:
            return
        try:
            await self._save_config()
        except Exception:
            # The decision still stands for this turn; only its persistence
            # failed, and saying so is better than pretending it was kept.
            logger.exception("Could not persist node authorizations")

    def _is_trusted_shell(self, call: ToolCall) -> bool:
        if call.tool_name == _SHELL_TOOL_NAME:
            return call.server_name == "dax-system"
        if not is_canonical_shell(call.tool_name):
            return False
        owner = self._tools.get_server_for_tool(call.tool_name)
        return owner == call.server_name and owner.startswith("capability-node:")

    def _is_trusted_node_app_open(self, call: ToolCall) -> bool:
        node_id = self._node_id(call)
        if node_id is None or call.tool_name != canonical_name(node_id, _APP_OPEN_TOOL_NAME):
            return False
        return self._tools.get_server_for_tool(call.tool_name) == call.server_name

    async def _gate_node_app_open(
        self,
        call: ToolCall,
        *,
        channel: str | None = None,
        session_id: str | None = None,
    ) -> tuple[ToolResult | None, ToolCall]:
        """Remember an app approval only for its exact capability node."""
        node_id = self._node_id(call)
        app_value = call.arguments.get("app")
        app = app_value.strip() if isinstance(app_value, str) else ""
        if node_id is None or not app or len(app) > 128 or "\x00" in app:
            await self._audit(call, "denied")
            return (
                ToolResult(
                    call_id=call.id,
                    content="Error: app_open requires a valid application name.",
                    is_error=True,
                ),
                call,
            )
        if self._nodes is not None and self._nodes.node_allows_app(node_id, app):
            await self._audit(call, "executed")
            return None, replace(call, human_approved=True)
        if self._approval is None:
            await self._audit(call, "denied")
            return (
                ToolResult(
                    call_id=call.id,
                    content=(
                        f"Error: opening '{app}' requires confirmation but no "
                        "approval channel is available."
                    ),
                    is_error=True,
                ),
                call,
            )
        options = ["once", "save"] if self._nodes is not None else ["once"]
        decision = await self._approval.request(
            tool_name=call.tool_name,
            server_name=call.server_name,
            arguments=dict(call.arguments),
            options=options,
            channel=channel,
            session_id=session_id,
        )
        if decision not in options:
            await self._audit(call, "declined")
            return (
                ToolResult(
                    call_id=call.id,
                    content=f"Error: the user declined to open '{app}'.",
                    is_error=True,
                ),
                call,
            )
        if decision == "save" and self._nodes is not None:
            self._nodes.remember_node_app(node_id, app)
            logger.info("Remembered app '%s' for node %s", app, node_id)
            await self._persist_nodes()
        await self._audit(call, "approved")
        return None, replace(call, human_approved=True)

    async def _gate_shell(
        self,
        call: ToolCall,
        *,
        channel: str | None = None,
        session_id: str | None = None,
    ) -> tuple[ToolResult | None, ToolCall]:
        """Gate a shell_run call against the user-managed command allowlist.

        Local allowlisted, bounded read-only commands run with no prompt. A
        capability-node shell always requires explicit one-time approval because
        its generic argv is not confined to the node's configured file roots.
        Eligible local commands can also be saved; denials block the call.

        An approved node command is returned marked, because the node applies
        its own allowlist and would otherwise refuse everything the user just
        agreed to.
        """
        command = str(call.arguments.get("command", ""))
        binary = shell_binary(command)
        node_shell = is_canonical_shell(call.tool_name)

        if (
            not node_shell
            and self._shell_allow is not None
            and self._shell_allow.allows_command(command)
        ):
            await self._audit(call, "executed")
            return None, call

        # A node command the user already chose to remember runs without asking
        # again — but still carries the approval, because the node's own
        # allowlist knows nothing about what was saved on the backend.
        node_id = self._node_id(call) if node_shell else None
        if (
            node_id is not None
            and self._nodes is not None
            and binary
            and self._nodes.node_allows_command(node_id, binary)
        ):
            await self._audit(call, "executed")
            return None, replace(call, human_approved=True)

        if self._approval is None:
            await self._audit(call, "denied")
            return (
                ToolResult(
                    call_id=call.id,
                    content=(
                        f"Error: command '{binary or command}' is not in the shell "
                        "allowlist and no approval channel is available to ask."
                    ),
                    is_error=True,
                ),
                call,
            )

        # A node command can be remembered too, into that node's own list. It is
        # not held to `is_auto_allowable` the way a backend command is: that test
        # asks whether a command is safe to run *silently and unreviewed*, which
        # is the right bar for a list the user never explicitly touched. Here the
        # user is looking at this exact command and choosing to keep it.
        can_save_node = node_shell and node_id is not None and self._nodes is not None
        can_save = can_save_node or (not node_shell and is_auto_allowable(command))
        options = ["once", "save"] if can_save and binary else ["once"]
        decision = await self._approval.request(
            tool_name=call.tool_name,
            server_name=call.server_name,
            arguments=dict(call.arguments),
            options=options,
            channel=channel,
            session_id=session_id,
        )
        if decision not in options:
            await self._audit(call, "declined")
            return (
                ToolResult(
                    call_id=call.id,
                    content=f"Error: the user declined to run '{binary or command}'.",
                    is_error=True,
                ),
                call,
            )
        if decision == "save" and binary and can_save:
            if can_save_node and node_id is not None and self._nodes is not None:
                self._nodes.remember_node_command(node_id, binary)
                logger.info("Remembered '%s' for node %s", binary, node_id)
                await self._persist_nodes()
            elif self._shell_allow is not None:
                self._shell_allow.add(binary)
                logger.info("Added '%s' to the shell allowlist", binary)
        await self._audit(call, "approved")
        return None, replace(call, human_approved=True)

    async def _audit(self, call: ToolCall, status: str) -> None:
        """Record a tool execution decision to the audit log, if supported."""
        logger_fn = getattr(self._storage, "log_tool_execution", None)
        if logger_fn is None:
            return
        try:
            await logger_fn(
                server_name=call.server_name,
                tool_name=call.tool_name,
                arguments=dict(call.arguments),
                status=status,
            )
        except Exception:
            logger.exception("Failed to write tool audit log")
