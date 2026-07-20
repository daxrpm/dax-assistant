"""Tests for the human-in-the-loop approval manager."""

from __future__ import annotations

import asyncio
from typing import Any

from dax.orchestrator.approval import ApprovalManager


class TestApprovalManager:
    async def test_no_notifier_denies(self):
        m = ApprovalManager(timeout_seconds=5)
        decision = await m.request(tool_name="fs_write", server_name="s", arguments={})
        assert decision == "deny"

    async def test_resolve_approved(self):
        m = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def notifier(payload: dict[str, Any]) -> None:
            seen.update(payload)

        m.set_notifier(notifier)
        task = asyncio.create_task(
            m.request(tool_name="shell_run", server_name="dax-system", arguments={"x": 1})
        )
        await asyncio.sleep(0.01)
        assert seen["type"] == "tool_confirmation_request"
        assert seen["options"] == ["approve"]
        assert m.resolve(seen["approval_id"], "approve") is True
        assert await task == "approve"
        assert m.pending_count == 0

    async def test_request_carries_session_id(self):
        m = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def notifier(payload: dict[str, Any]) -> None:
            seen.update(payload)

        m.set_notifier(notifier)
        task = asyncio.create_task(
            m.request(
                tool_name="fs_write",
                server_name="s",
                arguments={},
                session_id="client-session",
            )
        )
        await asyncio.sleep(0.01)
        assert seen["session_id"] == "client-session"
        m.resolve(seen["approval_id"], "deny")
        assert await task == "deny"

    async def test_resolve_denied(self):
        m = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def notifier(payload: dict[str, Any]) -> None:
            seen.update(payload)

        m.set_notifier(notifier)
        task = asyncio.create_task(m.request(tool_name="fs_write", server_name="s", arguments={}))
        await asyncio.sleep(0.01)
        m.resolve(seen["approval_id"], "deny")
        assert await task == "deny"

    async def test_shell_options_passed_through(self):
        m = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def notifier(payload: dict[str, Any]) -> None:
            seen.update(payload)

        m.set_notifier(notifier)
        task = asyncio.create_task(
            m.request(
                tool_name="shell_run",
                server_name="dax-system",
                arguments={"command": "flatpak run x"},
                options=["once", "save"],
            )
        )
        await asyncio.sleep(0.01)
        assert seen["options"] == ["once", "save"]
        m.resolve(seen["approval_id"], "save")
        assert await task == "save"

    async def test_timeout_denies(self):
        m = ApprovalManager(timeout_seconds=0)

        async def notifier(payload: dict[str, Any]) -> None:
            pass

        m.set_notifier(notifier)
        decision = await m.request(tool_name="fs_write", server_name="s", arguments={})
        assert decision == "deny"

    def test_resolve_unknown(self):
        m = ApprovalManager()
        assert m.resolve("does-not-exist", "approve") is False

    async def test_rejects_decision_not_offered_by_request(self):
        m = ApprovalManager(timeout_seconds=5)

        async def notifier(payload: dict[str, Any]) -> None:
            approval_id = payload["approval_id"]
            assert m.resolve(approval_id, "unexpected") is False
            assert m.resolve(approval_id, "approve") is True

        m.set_notifier(notifier)
        decision = await m.request(tool_name="read", server_name="s", arguments={})

        assert decision == "approve"

    async def test_voice_approver_gets_managed_id_and_resolves_once(self):
        m = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def approver(**payload: Any) -> None:
            seen.update(payload)
            assert m.resolve(payload["approval_id"], "once") is True
            assert m.resolve(payload["approval_id"], "once") is False

        m.set_voice_approver(approver)
        decision = await m.request(
            tool_name="shell_run",
            server_name="dax-system",
            arguments={"command": "touch x"},
            options=["once", "save"],
            channel="voice",
        )

        assert decision == "once"
        assert seen["options"] == ["once", "save"]
        assert seen["timeout_seconds"] == 5
        assert seen["approval_id"]

    async def test_pending_request_exposes_its_originating_channel(self):
        m = ApprovalManager(timeout_seconds=5)
        seen: dict[str, Any] = {}

        async def approver(**payload: Any) -> None:
            seen.update(payload)
            assert m.channel_for(payload["approval_id"]) == "voice"
            m.resolve(payload["approval_id"], "deny")

        m.set_voice_approver(approver)
        assert await m.request(
            tool_name="read",
            server_name="s",
            arguments={},
            channel="voice",
        ) == "deny"
        assert m.channel_for(seen["approval_id"]) is None
