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
from typing import TYPE_CHECKING

from dax.core.exceptions import ToolError
from dax.core.models import ToolCall, ToolResult
from dax.core.policy import Decision
from dax.core.shell_allow import shell_binary

if TYPE_CHECKING:
    from dax.core.policy import ToolPolicy
    from dax.core.ports import Storage, ToolProvider
    from dax.core.shell_allow import ShellAllowlist
    from dax.orchestrator.approval import ApprovalManager

logger = logging.getLogger(__name__)

# The dax-system tool that runs shell commands — gated by the shell allowlist
# rather than the generic name-pattern policy.
_SHELL_TOOL_NAME = "shell_run"


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
    ) -> None:
        self._tools = tools
        # When no policy/approval is wired, tools run unrestricted (used in
        # tests). In the app both are provided so destructive actions are gated.
        self._policy = policy
        self._approval = approval
        self._shell_allow = shell_allow
        self._storage = storage

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Resolve, gate, execute, and audit a single tool call."""
        resolved_call = self._resolve_server(tool_call)

        blocked = await self._gate(resolved_call)
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
        )

    async def _gate(self, call: ToolCall) -> ToolResult | None:
        """Apply the policy. Returns a blocking ToolResult, or None to proceed."""
        if self._policy is None:
            return None
        decision = self._policy.decide(call.tool_name)
        if decision is Decision.DENY:
            logger.warning("Tool '%s' denied by policy", call.tool_name)
            await self._audit(call, "denied")
            return ToolResult(
                call_id=call.id,
                content=f"Error: tool '{call.tool_name}' is not permitted.",
                is_error=True,
            )
        # The shell tool is gated by the user-managed binary allowlist, not the
        # name-pattern policy: known binaries run freely, unknown ones prompt.
        if call.tool_name == _SHELL_TOOL_NAME and self._shell_allow is not None:
            return await self._gate_shell(call)
        if decision is Decision.ALLOW:
            return None
        # ASK — require confirmation.
        if self._approval is None:
            await self._audit(call, "denied")
            return ToolResult(
                call_id=call.id,
                content=(
                    f"Error: '{call.tool_name}' requires confirmation but no "
                    "approval channel is available."
                ),
                is_error=True,
            )
        result = await self._approval.request(
            tool_name=call.tool_name,
            server_name=call.server_name,
            arguments=dict(call.arguments),
        )
        approved = result != "deny"
        await self._audit(call, "approved" if approved else "declined")
        if not approved:
            return ToolResult(
                call_id=call.id,
                content=f"Error: the user declined to run '{call.tool_name}'.",
                is_error=True,
            )
        return None

    async def _gate_shell(self, call: ToolCall) -> ToolResult | None:
        """Gate a shell_run call against the user-managed command allowlist.

        Allowlisted binaries run with no prompt. Unknown ones ask the user, who
        can *approve once* (run, don't remember) or *approve & save* (run and add
        the binary to the allowlist permanently). Denials block the call.
        """
        assert self._shell_allow is not None
        command = str(call.arguments.get("command", ""))
        binary = shell_binary(command)

        if self._shell_allow.is_allowed(binary):
            await self._audit(call, "executed")
            return None

        if self._approval is None:
            await self._audit(call, "denied")
            return ToolResult(
                call_id=call.id,
                content=(
                    f"Error: command '{binary or command}' is not in the shell "
                    "allowlist and no approval channel is available to ask."
                ),
                is_error=True,
            )

        decision = await self._approval.request(
            tool_name=call.tool_name,
            server_name=call.server_name,
            arguments=dict(call.arguments),
            options=["once", "save"],
        )
        if decision == "deny":
            await self._audit(call, "declined")
            return ToolResult(
                call_id=call.id,
                content=f"Error: the user declined to run '{binary or command}'.",
                is_error=True,
            )
        if decision == "save" and binary:
            self._shell_allow.add(binary)
            logger.info("Added '%s' to the shell allowlist", binary)
        await self._audit(call, "approved")
        return None

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
