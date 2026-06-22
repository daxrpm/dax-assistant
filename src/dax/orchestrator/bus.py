"""Async message bus for inter-component communication.

Decouples channels from the orchestrator via inbound/outbound queues.
Channels push to inbound, the orchestrator consumes from inbound,
and pushes responses to outbound for the dispatcher.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dax.core.models import Message

logger = logging.getLogger(__name__)


@dataclass
class MessageBus:
    """Async message bus using asyncio queues.

    Thread-safe for posting from voice pipeline threads via
    asyncio.run_coroutine_threadsafe.
    """

    max_size: int = 100
    _inbound: asyncio.Queue[Message] = field(init=False)
    _outbound: asyncio.Queue[Message] = field(init=False)
    _started: bool = field(init=False, default=False)

    def start(self) -> None:
        """Initialize the queues. Must be called from an async context."""
        self._inbound = asyncio.Queue(maxsize=self.max_size)
        self._outbound = asyncio.Queue(maxsize=self.max_size)
        self._started = True
        logger.info("Message bus started (max_size=%d)", self.max_size)

    async def publish_inbound(self, message: Message) -> None:
        """Publish a message from a channel to the orchestrator."""
        if not self._started:
            raise RuntimeError("Message bus not started")
        await self._inbound.put(message)
        logger.debug(
            "Inbound message from %s: %.50s", message.channel, message.content
        )

    async def consume_inbound(self) -> Message:
        """Wait for and return the next inbound message."""
        return await self._inbound.get()

    async def publish_outbound(self, message: Message) -> None:
        """Publish a response from the orchestrator to a channel."""
        if not self._started:
            raise RuntimeError("Message bus not started")
        await self._outbound.put(message)
        logger.debug(
            "Outbound message to %s: %.50s", message.channel, message.content
        )

    async def consume_outbound(self) -> Message:
        """Wait for and return the next outbound message."""
        return await self._outbound.get()

    @property
    def inbound_pending(self) -> int:
        """Number of messages waiting to be processed."""
        return self._inbound.qsize() if self._started else 0

    @property
    def outbound_pending(self) -> int:
        """Number of responses waiting to be dispatched."""
        return self._outbound.qsize() if self._started else 0
