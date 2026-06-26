"""Voice channel adapter — bridges the dispatcher to the voice pipeline.

The voice pipeline publishes inbound messages directly to the message bus.
The dispatcher routes assistant responses to this channel via :meth:`send`,
which enqueues them into an internal ``asyncio.Queue``. The pipeline's
thread reads from that queue through :meth:`get_response`, keeping the
dispatcher as the single routing authority.

Flow::

    [Mic] → Pipeline → bus.publish_inbound()
                                ↓
                           Orchestrator
                                ↓
                        bus.publish_outbound()
                                ↓
                           Dispatcher
                                ↓
                     VoiceChannel.send()  → _response_queue
                                                    ↓
                                    Pipeline._wait_and_speak()
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dax.core.models import Message

logger = logging.getLogger(__name__)


class VoiceChannel:
    """Voice channel adapter for the dispatcher.

    Inbound messages are published by the voice pipeline directly to the
    bus. Outbound messages arrive here via :meth:`send` (called by the
    dispatcher) and are forwarded to the pipeline through an internal
    response queue.
    """

    def __init__(self) -> None:
        self._response_queue: asyncio.Queue[Message] = asyncio.Queue()

    @property
    def name(self) -> str:
        return "voice"

    async def start(self) -> None:
        """No-op — the voice pipeline manages its own lifecycle."""
        logger.info("Voice channel started")

    async def stop(self) -> None:
        """No-op — the voice pipeline manages its own lifecycle."""
        logger.info("Voice channel stopped")

    async def send(self, message: Message) -> None:
        """Enqueue an outbound message for the voice pipeline to consume.

        Called by the dispatcher when an assistant response is routed to
        the voice channel.
        """
        await self._response_queue.put(message)
        logger.debug("Voice response queued: %.50s", message.content)

    async def drain(self) -> None:
        """Discard any queued responses left over from a previous turn.

        The pipeline calls this before publishing a new request so a late reply
        from a prior (e.g. timed-out) turn can't be mistakenly spoken as the
        answer to the new question.
        """
        discarded = 0
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
                discarded += 1
            except asyncio.QueueEmpty:
                break
        if discarded:
            logger.info("Discarded %d stale voice response(s)", discarded)

    async def get_response(
        self, timeout: float = 30.0, expected_turn: str | None = None,
    ) -> Message | None:
        """Wait for the next outbound message from the dispatcher.

        Called by the voice pipeline thread (via
        ``asyncio.run_coroutine_threadsafe``) to receive routed responses.

        Args:
            timeout: Maximum seconds to wait before returning ``None``.
            expected_turn: When set, responses whose ``voice_turn`` metadata
                doesn't match are discarded (a late reply from a previous,
                timed-out turn) and we keep waiting for the right one.

        Returns:
            The assistant's :class:`Message`, or ``None`` on timeout.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning("Voice response queue timed out after %.1f s", timeout)
                return None
            try:
                msg = await asyncio.wait_for(self._response_queue.get(), timeout=remaining)
            except TimeoutError:
                logger.warning("Voice response queue timed out after %.1f s", timeout)
                return None
            turn = str(msg.metadata.get("voice_turn", ""))
            if expected_turn is not None and turn != expected_turn:
                logger.info("Discarding stale voice response (turn mismatch)")
                continue
            return msg
