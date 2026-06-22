"""Response dispatcher — routes outbound messages to the correct channel.

Consumes from the outbound queue and delegates to the appropriate
channel based on the message's channel field.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dax.core.ports import Channel
    from dax.orchestrator.bus import MessageBus

logger = logging.getLogger(__name__)


class Dispatcher:
    """Routes outbound messages to registered channels."""

    def __init__(self, bus: MessageBus, channels: dict[str, Channel]) -> None:
        self._bus = bus
        self._channels = channels
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Begin consuming outbound messages."""
        self._task = asyncio.create_task(self._dispatch_loop(), name="dispatcher")
        logger.info(
            "Dispatcher started with channels: %s",
            list(self._channels.keys()),
        )

    async def stop(self) -> None:
        """Cancel the dispatch loop."""
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Dispatcher stopped")

    async def _dispatch_loop(self) -> None:
        """Main loop: consume outbound messages and route to channels."""
        while True:
            message = await self._bus.consume_outbound()
            channel_name = message.channel.value

            channel = self._channels.get(channel_name)
            if channel is None:
                logger.warning(
                    "No channel registered for '%s', dropping message: %.50s",
                    channel_name,
                    message.content,
                )
                continue

            try:
                await channel.send(message)
            except Exception:
                logger.exception(
                    "Failed to dispatch message to channel '%s'",
                    channel_name,
                )
