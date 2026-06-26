"""WebSocket chat endpoint for the web UI.

Handles inbound messages from browser clients. Outbound delivery
is handled by the Dispatcher → WebChannel → WebSocketManager path.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dax.core.models import ChannelType, Language, Message, MessageRole

router = APIRouter(tags=["chat"])

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages active WebSocket connections.

    For a single-user assistant, we typically have one connection at a time,
    but this supports multiple for robustness (e.g., multiple browser tabs).
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket client connected (total: %d)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WebSocket client disconnected (total: %d)", len(self._connections))

    async def send_to(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """Send data to a specific WebSocket connection."""
        try:
            await websocket.send_json(data)
        except Exception:
            logger.warning("Failed to send to WebSocket, removing connection")
            self.disconnect(websocket)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send data to all connected WebSocket clients."""
        disconnected: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Module-level manager instance — shared across the app
ws_manager = WebSocketManager()


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time chat with Dax.

    Protocol:
        Client sends: {"content": "message text", "language": "auto"}
        Server sends: {"content": "response text", "role": "assistant", "channel": "web"}

    Inbound messages are published to the bus here.
    Outbound delivery goes through: Dispatcher → WebChannel → ws_manager.broadcast()
    """
    auth = websocket.app.state.auth
    if not auth.authenticate_websocket(websocket):
        await websocket.close(code=1008)  # policy violation
        logger.warning("Rejected unauthenticated WebSocket connection")
        return

    bus = websocket.app.state.bus
    await ws_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()

            # Tool-confirmation responses from the UI resolve a pending gate.
            if data.get("type") == "tool_confirmation":
                approval = getattr(websocket.app.state, "approval", None)
                approval_id = data.get("approval_id", "")
                # Newer clients send a decision string ("approve"/"once"/"save"/
                # "deny"); older ones send the boolean "approved".
                if "decision" in data:
                    decision = str(data["decision"])
                else:
                    decision = "approve" if data.get("approved") else "deny"
                if approval is not None and approval_id:
                    approval.resolve(approval_id, decision)
                continue

            content = data.get("content", "").strip()
            if not content:
                continue

            language_str = data.get("language", "auto")
            try:
                language = Language(language_str)
            except ValueError:
                language = Language.AUTO

            metadata: dict[str, object] = {}
            session_id = data.get("session_id", "")
            if isinstance(session_id, str) and session_id:
                metadata["session_id"] = session_id

            message = Message(
                role=MessageRole.USER,
                content=content,
                channel=ChannelType.WEB,
                language=language,
                metadata=metadata,
            )

            await bus.publish_inbound(message)
            logger.debug("WebSocket message published to bus: %.50s", content)

    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        ws_manager.disconnect(websocket)
