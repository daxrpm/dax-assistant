"""Multi-client isolation: session-scoped delivery and approval binding.

Several clients attach at once — a browser tab, the desktop app, the phone.
They share one agent and one approval manager, so the transport is what keeps
one client's conversation (and its tool confirmations) away from another's.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dax.core.config import DaxConfig
from dax.orchestrator.approval import ApprovalManager
from dax.orchestrator.bus import MessageBus
from dax.web.routes.chat import WebSocketManager, _parse_session_control
from dax.web.server import create_app


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
    async def test_text_messages_reach_only_session_subscribers(self):
        manager = WebSocketManager()
        phone = await _attach(manager, "phone-1")
        desktop = await _attach(manager, "desktop-1")

        await manager.dispatch({"type": "message", "session_id": "phone-1", "content": "hi"})

        assert [f["content"] for f in phone.sent] == ["hi"]
        assert desktop.sent == []

    async def test_control_frame_reaches_only_the_owning_client(self):
        manager = WebSocketManager()
        phone = await _attach(manager, "phone-1")
        desktop = await _attach(manager, "desktop-1")

        await manager.dispatch({"type": "agent_event", "session_id": "phone-1"})

        assert len(phone.sent) == 1
        assert desktop.sent == []

    async def test_unclaimed_session_broadcasts(self):
        """Legacy clients that never send a session_id must keep working."""
        manager = WebSocketManager()
        a = await _attach(manager)
        b = await _attach(manager)

        await manager.dispatch({"type": "message", "content": "global"})

        assert len(a.sent) == 1
        assert len(b.sent) == 1

    async def test_unknown_session_is_dropped(self):
        manager = WebSocketManager()
        a = await _attach(manager, "phone-1")

        await manager.dispatch({"type": "agent_event", "session_id": "nobody-owns-this"})

        assert a.sent == []

    @pytest.mark.parametrize("session_id", ["", None, 42])
    async def test_malformed_scoped_frame_never_broadcasts(self, session_id: Any):
        manager = WebSocketManager()
        a = await _attach(manager)

        await manager.dispatch({"type": "agent_event", "session_id": session_id})

        assert a.sent == []

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

    async def test_slow_client_does_not_delay_healthy_client(self, monkeypatch):
        from dax.web.routes import chat

        monkeypatch.setattr(chat, "_SEND_TIMEOUT_SECONDS", 0.05)
        manager = WebSocketManager()
        healthy = await _attach(manager, "s")
        blocked = asyncio.Event()

        class SlowWebSocket(_FakeWebSocket):
            async def send_json(self, data: dict[str, Any]) -> None:
                await blocked.wait()

        slow = SlowWebSocket()
        await manager.connect(slow)  # type: ignore[arg-type]
        manager.register_interest(slow, "s")  # type: ignore[arg-type]

        task = asyncio.create_task(manager.dispatch({"type": "agent_event", "session_id": "s"}))
        await asyncio.sleep(0.01)

        assert len(healthy.sent) == 1
        await task
        assert manager.connection_count == 1

    async def test_concurrent_sends_are_serialized_per_socket(self):
        manager = WebSocketManager()

        class ConcurrentWebSocket(_FakeWebSocket):
            def __init__(self) -> None:
                super().__init__()
                self.active = 0
                self.max_active = 0

            async def send_json(self, data: dict[str, Any]) -> None:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.01)
                self.sent.append(data)
                self.active -= 1

        ws = ConcurrentWebSocket()
        await manager.connect(ws)  # type: ignore[arg-type]

        await asyncio.gather(
            manager.send_to(ws, {"sequence": 1}),  # type: ignore[arg-type]
            manager.send_to(ws, {"sequence": 2}),  # type: ignore[arg-type]
        )

        assert ws.max_active == 1
        assert [frame["sequence"] for frame in ws.sent] == [1, 2]

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

    async def test_subscribe_restores_ownership_without_publishing(self):
        manager = WebSocketManager()
        ws = await _attach(manager)

        assert manager.subscribe(ws, ["restored"]) is True  # type: ignore[arg-type]
        assert manager.owns_session(ws, "restored") is True  # type: ignore[arg-type]

        await manager.dispatch({"type": "message", "session_id": "restored"})
        assert len(ws.sent) == 1

    async def test_unsubscribe_releases_ownership(self):
        manager = WebSocketManager()
        ws = await _attach(manager, "released")

        manager.unsubscribe(ws, ["released"])  # type: ignore[arg-type]

        assert manager.owns_session(ws, "released") is False  # type: ignore[arg-type]
        await manager.dispatch({"type": "agent_event", "session_id": "released"})
        assert ws.sent == []

    async def test_subscription_limit_is_atomic(self):
        manager = WebSocketManager()
        ws = await _attach(manager)
        existing = [f"s{i}" for i in range(32)]
        assert manager.subscribe(ws, existing) is True  # type: ignore[arg-type]

        assert manager.subscribe(ws, ["overflow"]) is False  # type: ignore[arg-type]
        assert manager.owns_session(ws, "overflow") is False  # type: ignore[arg-type]
        assert all(manager.owns_session(ws, item) for item in existing)  # type: ignore[arg-type]


class TestSessionControlValidation:
    def test_valid_control_frame(self):
        assert _parse_session_control(
            {"type": "session_subscribe", "session_ids": ["one", "two"], "ack": True}
        ) == ("session_subscribe", ["one", "two"], True)

    @pytest.mark.parametrize(
        "frame",
        [
            {"type": "session_subscribe", "session_ids": "one"},
            {"type": "session_subscribe", "session_ids": []},
            {"type": "session_subscribe", "session_ids": ["duplicate", "duplicate"]},
            {"type": "session_subscribe", "session_ids": [""]},
            {"type": "session_subscribe", "session_ids": [" padded "]},
            {"type": "session_subscribe", "session_ids": ["one"], "ack": 1},
            {"type": "session_subscribe", "session_ids": ["one"], "extra": True},
            {"type": "session_unsubscribe", "session_ids": [str(i) for i in range(33)]},
        ],
    )
    def test_rejects_malformed_control_frame(self, frame: dict[str, Any]):
        with pytest.raises(ValueError):
            _parse_session_control(frame)

    def test_endpoint_returns_optional_control_ack(self):
        bus = MessageBus()
        bus.start()
        app = create_app(
            config=DaxConfig(security={"auth_enabled": False}),
            bus=bus,
        )

        with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
            ws.send_json(
                {"type": "session_subscribe", "session_ids": ["restored"], "ack": True}
            )
            assert ws.receive_json() == {
                "type": "session_subscribe_ack",
                "ok": True,
                "session_ids": ["restored"],
            }
            ws.send_json(
                {"type": "session_unsubscribe", "session_ids": ["restored"], "ack": True}
            )
            assert ws.receive_json() == {
                "type": "session_unsubscribe_ack",
                "ok": True,
                "session_ids": ["restored"],
            }


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

    async def test_malformed_scoped_approval_is_not_broadcast(self):
        manager = WebSocketManager()
        desktop = await _attach(manager)

        await manager.deliver_approval(
            {"type": "tool_confirmation_request", "session_id": None, "tool_name": "fs_write"}
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
