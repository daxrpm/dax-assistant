"""Tests for the async message bus."""

from __future__ import annotations

import asyncio

import pytest

from dax.core.models import Message, MessageRole
from dax.orchestrator.bus import MessageBus


class TestMessageBus:
    def test_start(self):
        bus = MessageBus()
        bus.start()
        assert bus.inbound_pending == 0
        assert bus.outbound_pending == 0

    async def test_publish_inbound(self, message_bus: MessageBus):
        msg = Message(content="hello")
        await message_bus.publish_inbound(msg)
        assert message_bus.inbound_pending == 1

    async def test_consume_inbound(self, message_bus: MessageBus):
        msg = Message(content="hello")
        await message_bus.publish_inbound(msg)
        received = await message_bus.consume_inbound()
        assert received.content == "hello"
        assert message_bus.inbound_pending == 0

    async def test_publish_outbound(self, message_bus: MessageBus):
        msg = Message(role=MessageRole.ASSISTANT, content="response")
        await message_bus.publish_outbound(msg)
        assert message_bus.outbound_pending == 1

    async def test_consume_outbound(self, message_bus: MessageBus):
        msg = Message(role=MessageRole.ASSISTANT, content="response")
        await message_bus.publish_outbound(msg)
        received = await message_bus.consume_outbound()
        assert received.content == "response"

    async def test_fifo_order(self, message_bus: MessageBus):
        for i in range(3):
            await message_bus.publish_inbound(Message(content=f"msg-{i}"))

        for i in range(3):
            received = await message_bus.consume_inbound()
            assert received.content == f"msg-{i}"

    async def test_publish_before_start_raises(self):
        bus = MessageBus()
        with pytest.raises(RuntimeError, match="not started"):
            await bus.publish_inbound(Message(content="fail"))

    async def test_pending_counts_before_start(self):
        bus = MessageBus()
        assert bus.inbound_pending == 0
        assert bus.outbound_pending == 0

    async def test_consume_blocks_until_available(self, message_bus: MessageBus):
        async def delayed_publish():
            await asyncio.sleep(0.05)
            await message_bus.publish_inbound(Message(content="delayed"))

        task = asyncio.create_task(delayed_publish())  # noqa: RUF006, F841
        received = await asyncio.wait_for(message_bus.consume_inbound(), timeout=1.0)
        assert received.content == "delayed"
