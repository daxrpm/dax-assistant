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

logger = logging.getLogger(__name__)


class ApprovalManager:
    """Tracks pending tool-confirmation requests and their resolutions."""

    def __init__(self, timeout_seconds: int = 120) -> None:
        self._timeout = timeout_seconds
        self._pending: dict[str, asyncio.Future[bool]] = {}
        self._notifier: Callable[[dict[str, Any]], Awaitable[None]] | None = None

    def set_notifier(self, notifier: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Register the async callback that delivers requests to the UI."""
        self._notifier = notifier

    async def request(
        self,
        *,
        tool_name: str,
        server_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """Ask the user to confirm a tool call. Returns True if approved."""
        if self._notifier is None:
            # No UI to ask — fail safe (deny) rather than run unconfirmed.
            logger.warning(
                "Tool '%s' needs confirmation but no UI is connected — denying",
                tool_name,
            )
            return False

        approval_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending[approval_id] = future

        payload = {
            "type": "tool_confirmation_request",
            "approval_id": approval_id,
            "tool_name": tool_name,
            "server_name": server_name,
            "arguments": arguments,
            "timeout_seconds": self._timeout,
        }
        try:
            await self._notifier(payload)
            return await asyncio.wait_for(future, timeout=self._timeout)
        except TimeoutError:
            logger.info("Confirmation for '%s' timed out — denying", tool_name)
            return False
        except Exception:
            logger.exception("Failed to request confirmation for '%s'", tool_name)
            return False
        finally:
            self._pending.pop(approval_id, None)

    def resolve(self, approval_id: str, approved: bool) -> bool:
        """Resolve a pending request. Returns True if it matched a pending one."""
        future = self._pending.get(approval_id)
        if future is not None and not future.done():
            future.set_result(approved)
            return True
        return False

    @property
    def pending_count(self) -> int:
        return len(self._pending)
