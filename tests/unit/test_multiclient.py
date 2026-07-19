"""Multi-client isolation: session-scoped delivery and approval binding.

Several clients attach at once — a browser tab, the desktop app, the phone.
They share one agent and one approval manager, so the transport is what keeps
one client's conversation (and its tool confirmations) away from another's.
"""

from __future__ import annotations

import asyncio
from typing import Any

from dax.orchestrator.approval import ApprovalManager
from dax.web.routes.chat import WebSocketManager


class _FakeWebSocket:
    """Records the frames sent to one client."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[dict[str, Any]] = []
        self.accepted = False
        self._fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict[str, Any]) -> None:
        if self._fail:
            raise ConnectionError("client is gone")
        self.sent.append(data)


async def _attach(manager: WebSocketManager, *sessions: str) -> _FakeWebSocket:
    ws = _FakeWebSocket()
    await manager.connect(ws)  # type: ignore[arg-type]
    for session in sessions:
        manager.register_interest(ws, session)  # type: ignore[arg-type]
    return ws


class TestSessionScopedDelivery:
    async def test_dispatch_reaches_only_the_owning_client(self):
        manager = WebSocketManager()
        phone = await _attach(manager, "phone-1")
        desktop = await _attach(manager, "desktop-1")

        await manager.dispatch({"type": "message", "session_id": "phone-1", "content": "hi"})

        assert [f["content"] for f in phone.sent] == ["hi"]
        assert desktop.sent == []

    async def test_unclaimed_session_broadcasts(self):
        """Legacy clients that never send a session_id must keep working."""
        manager = WebSocketManager()
        a = await _attach(manager)
        b = await _attach(manager)

        await manager.dispatch({"type": "message", "content": "global"})

        assert len(a.sent) == 1
        assert len(b.sent) == 1

    async def test_unknown_session_falls_back_to_broadcast(self):
        manager = WebSocketManager()
        a = await _attach(manager, "phone-1")

        await manager.dispatch({"type": "message", "session_id": "nobody-owns-this"})

        assert len(a.sent) == 1

    async def test_two_clients_may_share_a_session(self):
        manager = WebSocketManager()
        tab_one = await _attach(manager, "shared")
        tab_two = await _attach(manager, "shared")

        await manager.dispatch({"type": "message", "session_id": "shared"})

        assert len(tab_one.sent) == 1
        assert len(tab_two.sent) == 1

    async def test_failed_send_disconnects_the_client(self):
        manager = WebSocketManager()
        healthy = await _attach(manager, "s")
        broken = _FakeWebSocket(fail=True)
        await manager.connect(broken)  # type: ignore[arg-type]
        manager.register_interest(broken, "s")  # type: ignore[arg-type]

        await manager.dispatch({"type": "message", "session_id": "s"})

        assert manager.connection_count == 1
        assert len(healthy.sent) == 1

    async def test_disconnect_clears_interest(self):
        manager = WebSocketManager()
        ws = await _attach(manager, "s")
        assert manager.owns_session(ws, "s") is True  # type: ignore[arg-type]

        manager.disconnect(ws)  # type: ignore[arg-type]

        assert manager.owns_session(ws, "s") is False  # type: ignore[arg-type]

    async def test_interest_set_is_bounded(self):
        manager = WebSocketManager()
        ws = await _attach(manager)
        for i in range(200):
            manager.register_interest(ws, f"s{i}")  # type: ignore[arg-type]

        owned = sum(1 for i in range(200) if manager.owns_session(ws, f"s{i}"))  # type: ignore[arg-type]
        assert owned <= 32


class TestApprovalDelivery:
    async def test_approval_never_broadcasts_to_non_owners(self):
        manager = WebSocketManager()
        phone = await _attach(manager, "phone-1")
        desktop = await _attach(manager, "desktop-1")

        await manager.deliver_approval(
            {
                "type": "tool_confirmation_request",
                "session_id": "phone-1",
                "tool_name": "shell_run",
                "arguments": {"cmd": "rm -rf /tmp/x"},
            }
        )

        assert len(phone.sent) == 1
        assert desktop.sent == [], "tool arguments leaked to a non-owning client"

    async def test_unowned_approval_is_not_delivered_at_all(self):
        """No eligible client means the gate must fail safe, not fan out."""
        manager = WebSocketManager()
        desktop = await _attach(manager, "desktop-1")

        await manager.deliver_approval(
            {"type": "tool_confirmation_request", "session_id": "orphan", "tool_name": "fs_write"}
        )

        assert desktop.sent == []


class TestApprovalBinding:
    async def test_session_for_tracks_the_owning_conversation(self):
        approval = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def notifier(payload: dict[str, Any]) -> None:
            seen.update(payload)

        approval.set_notifier(notifier)
        task = asyncio.create_task(
            approval.request(
                tool_name="fs_write",
                server_name="dax-system",
                arguments={},
                session_id="phone-1",
            )
        )
        await asyncio.sleep(0.01)

        assert approval.session_for(seen["approval_id"]) == "phone-1"
        approval.resolve(seen["approval_id"], "approve")
        assert await task == "approve"
        # Cleared once settled, so a late frame cannot match it.
        assert approval.session_for(seen["approval_id"]) is None

    async def test_unscoped_request_has_no_owner(self):
        approval = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def notifier(payload: dict[str, Any]) -> None:
            seen.update(payload)

        approval.set_notifier(notifier)
        task = asyncio.create_task(
            approval.request(tool_name="fs_write", server_name="s", arguments={})
        )
        await asyncio.sleep(0.01)

        assert approval.session_for(seen["approval_id"]) is None
        approval.resolve(seen["approval_id"], "deny")
        await task

    async def test_resolution_is_single_use(self):
        """A replayed confirmation frame must not run the tool twice."""
        approval = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def notifier(payload: dict[str, Any]) -> None:
            seen.update(payload)

        approval.set_notifier(notifier)
        task = asyncio.create_task(
            approval.request(tool_name="shell_run", server_name="s", arguments={})
        )
        await asyncio.sleep(0.01)
        approval_id = seen["approval_id"]

        assert approval.resolve(approval_id, "approve") is True
        assert approval.resolve(approval_id, "approve") is False
        assert approval.resolve(approval_id, "deny") is False
        assert await task == "approve"

    async def test_unknown_approval_id_is_rejected(self):
        approval = ApprovalManager(timeout_seconds=5)
        assert approval.resolve("does-not-exist", "approve") is False
