"""Web channel — delegates to WebSocket manager.

The actual WebSocket handling is done in web/routes/chat.py.
This channel provides the Channel protocol interface for the dispatcher
to route outbound messages to connected WebSocket clients.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dax.web.routes.chat import ws_manager

if TYPE_CHECKING:
    from dax.core.models import Message

logger = logging.getLogger(__name__)


class WebChannel:
    """Web UI channel adapter.

    Bridges between the dispatcher and the WebSocket manager.
    Inbound messages come from the WebSocket route directly.
    Outbound messages are broadcast to all connected clients.
    """

    @property
    def name(self) -> str:
        return "web"

    async def start(self) -> None:
        logger.info("Web channel started")

    async def stop(self) -> None:
        logger.info("Web channel stopped")

    async def send(self, message: Message) -> None:
        """Broadcast a message to all connected WebSocket clients."""
        if ws_manager.connection_count == 0:
            logger.debug("No WebSocket clients connected, message not delivered")
            return

        await ws_manager.broadcast({
            "type": "message",
            "content": message.content,
            "role": message.role.value,
            "channel": message.channel.value,
            "language": message.language.value,
            "timestamp": message.timestamp.isoformat(),
        })
