"""WebSocket chat endpoint for the web UI.

Handles inbound messages from browser clients. Outbound delivery
is handled by the Dispatcher → WebChannel → WebSocketManager path.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dax.core.models import ChannelType, Language, Message, MessageRole
from dax.web.dependencies import approval_from_app, auth_from_app, bus_from_app

router = APIRouter(tags=["chat"])

logger = logging.getLogger(__name__)

# A client legitimately holds a handful of conversations open at once. The cap
# keeps a misbehaving or hostile client from growing the interest set forever.
_MAX_SESSIONS_PER_CLIENT = 32


class WebSocketManager:
    """Manages active WebSocket connections and their session interests.

    A single-user assistant still has several concurrent clients — a browser
    tab, the desktop app, and the phone. They must not see each other's
    frames: ``session_id`` scopes a conversation, and a client only receives
    frames for sessions it has spoken on.

    Interest is registered implicitly when a client publishes a message with a
    ``session_id``, so existing clients gain isolation without a protocol
    change. Frames with no session (legacy clients that never send one) still
    broadcast, which preserves the old behaviour exactly.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        # Which sessions each connection has spoken on. A connection with an
        # empty set has not claimed any session yet.
        self._interests: dict[int, set[str]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        self._interests[id(websocket)] = set()
        logger.info("WebSocket client connected (total: %d)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        self._interests.pop(id(websocket), None)
        logger.info("WebSocket client disconnected (total: %d)", len(self._connections))

    def register_interest(self, websocket: WebSocket, session_id: str) -> None:
        """Record that *websocket* owns ``session_id``.

        Called when a client publishes on a session. Bounded so a client that
        churns through sessions cannot grow this set without limit.
        """
        interests = self._interests.get(id(websocket))
        if interests is None:
            return
        if len(interests) >= _MAX_SESSIONS_PER_CLIENT:
            interests.pop()
        interests.add(session_id)

    def owns_session(self, websocket: WebSocket, session_id: str) -> bool:
        """True when *websocket* has published on ``session_id``.

        Gates approval resolution: a client may only answer confirmations for
        conversations it started.
        """
        return session_id in self._interests.get(id(websocket), frozenset())

    def _subscribers(self, session_id: str) -> list[WebSocket]:
        return [ws for ws in self._connections if session_id in self._interests.get(id(ws), ())]

    async def send_to(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """Send data to a specific WebSocket connection."""
        try:
            await websocket.send_json(data)
        except Exception:
            logger.warning("Failed to send to WebSocket, removing connection")
            self.disconnect(websocket)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send data to all connected WebSocket clients."""
        await self._send_many(self._connections, data)

    async def dispatch(self, data: dict[str, Any]) -> None:
        """Route *data* by its ``session_id``, falling back to a broadcast.

        Session-scoped frames reach only the clients that own the session, so
        the phone never renders the desktop's conversation and vice versa. A
        frame without a session, or for a session nobody claims, broadcasts —
        that keeps pre-session clients and server-initiated frames working.
        """
        session_id = data.get("session_id")
        if isinstance(session_id, str) and session_id:
            targets = self._subscribers(session_id)
            if targets:
                await self._send_many(targets, data)
                return
        await self._send_many(self._connections, data)

    async def deliver_approval(self, data: dict[str, Any]) -> None:
        """Deliver a confirmation request only to the client that can answer it.

        Unlike :meth:`dispatch` this never falls back to a broadcast: a tool
        confirmation is an authorization decision, so an unclaimed session
        must not leak the request (and its arguments) to every attached
        client. With no eligible target the request goes unanswered and
        :class:`ApprovalManager` fails safe to deny.
        """
        session_id = data.get("session_id")
        targets = (
            self._subscribers(session_id)
            if isinstance(session_id, str) and session_id
            else self._connections
        )
        if not targets:
            logger.warning(
                "No client owns session %r — confirmation for '%s' will be denied",
                session_id,
                data.get("tool_name"),
            )
            return
        await self._send_many(targets, data)

    async def _send_many(self, targets: list[WebSocket], data: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []
        for ws in targets:
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
    auth = auth_from_app(websocket.app)
    if auth is None or not auth.authenticate_websocket(websocket):
        await websocket.close(code=1008)  # policy violation
        logger.warning("Rejected unauthenticated WebSocket connection")
        return

    bus = bus_from_app(websocket.app)
    if bus is None:
        await websocket.close(code=1011)  # internal error — not wired
        return
    await ws_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()

            # Tool-confirmation responses from the UI resolve a pending gate.
            if data.get("type") == "tool_confirmation":
                approval = approval_from_app(websocket.app)
                approval_id = data.get("approval_id", "")
                # Newer clients send a decision string ("approve"/"once"/"save"/
                # "deny"); older ones send the boolean "approved".
                if "decision" in data:
                    decision = str(data["decision"])
                else:
                    decision = "approve" if data.get("approved") else "deny"
                if approval is not None and approval_id:
                    # Only the client that owns the conversation may authorize
                    # its tool calls. Without this any attached client could
                    # approve another's gated action by guessing an id.
                    owner = approval.session_for(approval_id)
                    if owner is not None and not ws_manager.owns_session(websocket, owner):
                        logger.warning(
                            "Rejected confirmation for %s from a client that "
                            "does not own session %r",
                            approval_id,
                            owner,
                        )
                        continue
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
                # Claim the session so replies, agent events, and confirmations
                # for it route back to this connection instead of every client.
                ws_manager.register_interest(websocket, session_id)

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
