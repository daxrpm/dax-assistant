"""Human-in-the-loop approval gate for gated tool calls.

When the policy says a tool needs confirmation, the agent calls
:meth:`ApprovalManager.request`, which pushes a confirmation request to the web
UI and blocks until the user approves/denies (or it times out → denied). The
WebSocket route calls :meth:`resolve` when the user answers.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    # Spoken-confirmation handler: asks by voice and returns the decision string
    # ("approve"/"deny", or a chosen option like "once"/"save").
    VoiceApprover = Callable[..., Awaitable[str]]

logger = logging.getLogger(__name__)


class ApprovalManager:
    """Tracks pending tool-confirmation requests and their resolutions."""

    def __init__(self, timeout_seconds: int = 120) -> None:
        self._timeout = timeout_seconds
        self._pending: dict[str, asyncio.Future[str]] = {}
        self._notifier: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self._voice_approver: VoiceApprover | None = None

    def set_notifier(self, notifier: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Register the async callback that delivers requests to the UI."""
        self._notifier = notifier

    def set_voice_approver(self, approver: VoiceApprover) -> None:
        """Register the spoken-confirmation handler used for voice turns.

        When a gated tool originates from the voice channel, we ask the user out
        loud (and listen for sí/no) instead of popping a web modal they can't
        see — so voice-only use isn't blocked waiting for a click.
        """
        self._voice_approver = approver

    async def request(
        self,
        *,
        tool_name: str,
        server_name: str,
        arguments: dict[str, Any],
        options: list[str] | None = None,
        channel: str | None = None,
    ) -> str:
        """Ask the user to confirm a tool call.

        Returns the chosen decision string. For a plain yes/no gate (``options``
        omitted) the result is ``"approve"`` or ``"deny"``. Callers that offer
        richer choices (e.g. the shell gate's ``["once", "save"]``) get back the
        chosen option, or ``"deny"``. Always fails safe to ``"deny"``.

        Voice-channel requests are routed to the spoken approver when one is
        registered; everything else goes to the web UI.
        """
        if channel == "voice" and self._voice_approver is not None:
            try:
                return await self._voice_approver(
                    tool_name=tool_name,
                    server_name=server_name,
                    arguments=arguments,
                    options=options,
                )
            except Exception:
                logger.exception("Voice confirmation failed for '%s' — denying", tool_name)
                return "deny"

        if self._notifier is None:
            # No UI to ask — fail safe (deny) rather than run unconfirmed.
            logger.warning(
                "Tool '%s' needs confirmation but no UI is connected — denying",
                tool_name,
            )
            return "deny"

        approval_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending[approval_id] = future

        payload = {
            "type": "tool_confirmation_request",
            "approval_id": approval_id,
            "tool_name": tool_name,
            "server_name": server_name,
            "arguments": arguments,
            "options": options or ["approve"],
            "timeout_seconds": self._timeout,
        }
        try:
            await self._notifier(payload)
            return await asyncio.wait_for(future, timeout=self._timeout)
        except TimeoutError:
            logger.info("Confirmation for '%s' timed out — denying", tool_name)
            return "deny"
        except Exception:
            logger.exception("Failed to request confirmation for '%s'", tool_name)
            return "deny"
        finally:
            self._pending.pop(approval_id, None)

    def resolve(self, approval_id: str, decision: str) -> bool:
        """Resolve a pending request. Returns True if it matched a pending one."""
        future = self._pending.get(approval_id)
        if future is not None and not future.done():
            future.set_result(decision)
            return True
        return False

    @property
    def pending_count(self) -> int:
        return len(self._pending)
