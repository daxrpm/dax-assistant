"""WebSocket chat endpoint for the web UI.

Handles inbound messages from browser clients. Outbound delivery
is handled by the Dispatcher → WebChannel → WebSocketManager path.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dax.core.models import ChannelType, Language, Message, MessageRole
from dax.web.auth import AuthManager
from dax.web.dependencies import approval_from_app, auth_from_app, bus_from_app

router = APIRouter(tags=["chat"])

logger = logging.getLogger(__name__)

# A client legitimately holds a handful of conversations open at once. The cap
# keeps a misbehaving or hostile client from growing the interest set forever.
_MAX_SESSIONS_PER_CLIENT = 32
_SESSION_CONTROL_TYPES = frozenset({"session_subscribe", "session_unsubscribe"})
_SEND_TIMEOUT_SECONDS = 5.0


def _parse_session_control(data: dict[str, Any]) -> tuple[str, list[str], bool]:
    """Validate a session ownership control frame without coercion."""
    frame_type = data.get("type")
    if frame_type not in _SESSION_CONTROL_TYPES:
        raise ValueError("unsupported control type")
    if set(data) - {"type", "session_ids", "ack"}:
        raise ValueError("unexpected control field")
    session_ids = data.get("session_ids")
    if (
        not isinstance(session_ids, list)
        or not 1 <= len(session_ids) <= _MAX_SESSIONS_PER_CLIENT
        or any(
            not isinstance(item, str) or not item or item != item.strip()
            for item in session_ids
        )
        or len(set(session_ids)) != len(session_ids)
    ):
        raise ValueError("session_ids must contain 1-32 unique non-empty strings")
    ack = data.get("ack", False)
    if not isinstance(ack, bool):
        raise ValueError("ack must be a boolean")
    return frame_type, session_ids, ack


class WebSocketManager:
    """Manages active WebSocket connections and their session interests.

    A single-user assistant still has several concurrent clients — a browser
    tab, the desktop app, and the phone. Text messages are shared across those
    authenticated clients, while ``session_id`` keeps transient agent controls
    and approval decisions attached to the clients participating in that turn.

    Interest is registered explicitly by subscription frames and implicitly
    when a client publishes a message with a ``session_id``. Unscoped frames
    and text messages broadcast; scoped control frames never do.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        # Sessions each connection explicitly subscribed to or published on.
        self._interests: dict[int, set[str]] = {}
        # Which enrolled device (if any) each connection authenticated as, so
        # the desktop can show whether the phone is actually attached rather
        # than only when it last asked for a token.
        self._devices: dict[int, str] = {}
        self._send_locks: dict[int, asyncio.Lock] = {}
        self._state_lock = threading.RLock()

    async def connect(self, websocket: WebSocket, device_id: str | None = None) -> None:
        await websocket.accept()
        with self._state_lock:
            self._connections.append(websocket)
            self._interests[id(websocket)] = set()
            self._send_locks[id(websocket)] = asyncio.Lock()
            if device_id:
                self._devices[id(websocket)] = device_id
            connection_count = len(self._connections)
        logger.info(
            "WebSocket client connected (total: %d%s)",
            connection_count,
            f", device {device_id}" if device_id else "",
        )

    def disconnect(self, websocket: WebSocket) -> None:
        with self._state_lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
            self._interests.pop(id(websocket), None)
            self._devices.pop(id(websocket), None)
            self._send_locks.pop(id(websocket), None)
            connection_count = len(self._connections)
        logger.info("WebSocket client disconnected (total: %d)", connection_count)

    @property
    def connected_device_ids(self) -> set[str]:
        """Devices with a live chat socket right now."""
        with self._state_lock:
            return set(self._devices.values())

    def register_interest(self, websocket: WebSocket, session_id: str) -> bool:
        """Record that *websocket* owns ``session_id``.

        Called when a client publishes on a session. Bounded so a client that
        churns through sessions cannot grow this set without limit.
        """
        with self._state_lock:
            interests = self._interests.get(id(websocket))
            if interests is None:
                return False
            if session_id not in interests and len(interests) >= _MAX_SESSIONS_PER_CLIENT:
                logger.warning(
                    "WebSocket client reached the %d-session limit",
                    _MAX_SESSIONS_PER_CLIENT,
                )
                return False
            interests.add(session_id)
            return True

    def subscribe(self, websocket: WebSocket, session_ids: list[str]) -> bool:
        """Atomically add session ownership, respecting the per-client cap."""
        with self._state_lock:
            interests = self._interests.get(id(websocket))
            if interests is None:
                return False
            if len(interests | set(session_ids)) > _MAX_SESSIONS_PER_CLIENT:
                return False
            interests.update(session_ids)
            return True

    def unsubscribe(self, websocket: WebSocket, session_ids: list[str]) -> None:
        """Release session ownership for a connected client."""
        with self._state_lock:
            interests = self._interests.get(id(websocket))
            if interests is not None:
                interests.difference_update(session_ids)

    def owns_session(self, websocket: WebSocket, session_id: str) -> bool:
        """True when *websocket* has subscribed to or published on ``session_id``.

        Gates approval resolution: a client may only answer confirmations for
        conversations it started.
        """
        with self._state_lock:
            return session_id in self._interests.get(id(websocket), frozenset())

    def _subscribers(self, session_id: str) -> list[WebSocket]:
        with self._state_lock:
            return [
                ws
                for ws in self._connections
                if session_id in self._interests.get(id(ws), ())
            ]

    def _connection_snapshot(self) -> list[WebSocket]:
        with self._state_lock:
            return list(self._connections)

    async def send_to(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """Send data to a specific WebSocket connection."""
        await self._send_one(websocket, data)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send data to all connected WebSocket clients."""
        await self._send_many(self._connection_snapshot(), data)

    async def dispatch(self, data: dict[str, Any]) -> None:
        """Route *data* by its ``session_id``.

        Every frame carrying a session ID reaches only clients subscribed to
        that session. Frames without one are intentionally global.
        """
        session_id = data.get("session_id")
        if "session_id" in data:
            if isinstance(session_id, str) and session_id:
                targets = self._subscribers(session_id)
                if targets:
                    await self._send_many(targets, data)
                    return
                logger.debug("Dropping frame for unowned session %r", session_id)
                return
            logger.warning("Dropping frame with invalid session %r", session_id)
            return
        await self._send_many(self._connection_snapshot(), data)

    async def deliver_approval(self, data: dict[str, Any]) -> None:
        """Deliver a confirmation request only to the client that can answer it.

        Unlike :meth:`dispatch` this never falls back to a broadcast: a tool
        confirmation is an authorization decision, so an unclaimed session
        must not leak the request (and its arguments) to every attached
        client. With no eligible target the request goes unanswered and
        :class:`ApprovalManager` fails safe to deny.
        """
        session_id = data.get("session_id")
        if "session_id" in data:
            targets = (
                self._subscribers(session_id)
                if isinstance(session_id, str) and session_id
                else []
            )
        else:
            targets = self._connection_snapshot()
        if not targets:
            logger.warning(
                "No client owns session %r — confirmation for '%s' will be denied",
                session_id,
                data.get("tool_name"),
            )
            return
        await self._send_many(targets, data)

    async def _send_many(self, targets: list[WebSocket], data: dict[str, Any]) -> None:
        await asyncio.gather(*(self._send_one(ws, data) for ws in targets))

    async def _send_one(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        with self._state_lock:
            send_lock = self._send_locks.get(id(websocket))
        if send_lock is None:
            return
        try:
            async with asyncio.timeout(_SEND_TIMEOUT_SECONDS):
                async with send_lock:
                    with self._state_lock:
                        if websocket not in self._connections:
                            return
                    await websocket.send_json(data)
        except Exception:
            logger.warning("Failed to send to WebSocket, removing connection")
            self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        with self._state_lock:
            return len(self._connections)


# Module-level manager instance — shared across the app
ws_manager = WebSocketManager()


def _device_for(auth: Any, websocket: WebSocket) -> str | None:
    """The enrolled device behind this socket, if it authenticated as one.

    A browser or the desktop app presents a session token and has no device
    identity; only the phone does. Failures are swallowed because presence is
    a display concern — it must never be able to reject a valid connection.
    """
    try:
        candidates = [
            websocket.query_params.get("token"),
            AuthManager._bearer_token(websocket.headers.get("authorization")),
        ]
        for token in candidates:
            if not token:
                continue
            device_id = auth.device_from_token(token)
            if device_id:
                return str(device_id)
    except Exception:
        logger.debug("Could not resolve a device for this socket", exc_info=True)
    return None


async def _reject(websocket: WebSocket) -> None:
    """Refuse a socket with a close code the client can actually read.

    Closing before accepting makes the ASGI server answer the handshake with
    HTTP 403, and a browser reports that to the page as code 1006 — an abnormal
    closure, indistinguishable from a dropped network. Clients therefore treat
    an expired session as a transient fault and reconnect forever instead of
    asking the user to sign in again. Accepting first costs one frame and makes
    1008 arrive as 1008.
    """
    with contextlib.suppress(Exception):
        await websocket.accept()
    with contextlib.suppress(Exception):
        await websocket.close(code=1008)  # policy violation


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
        await _reject(websocket)
        logger.warning("Rejected unauthenticated WebSocket connection")
        return

    bus = bus_from_app(websocket.app)
    if bus is None:
        await websocket.close(code=1011)  # internal error — not wired
        return
    await ws_manager.connect(websocket, device_id=_device_for(auth, websocket))

    try:
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                logger.warning("Ignoring non-object WebSocket chat frame")
                continue

            if data.get("type") in _SESSION_CONTROL_TYPES:
                try:
                    control_type, session_ids, ack = _parse_session_control(data)
                    if control_type == "session_subscribe":
                        accepted = ws_manager.subscribe(websocket, session_ids)
                    else:
                        ws_manager.unsubscribe(websocket, session_ids)
                        accepted = True
                except ValueError as exc:
                    logger.warning("Rejected invalid session control frame: %s", exc)
                    if data.get("ack") is True:
                        await ws_manager.send_to(
                            websocket,
                            {
                                "type": f"{data.get('type')}_ack",
                                "ok": False,
                                "error": str(exc),
                            },
                        )
                    continue
                if ack:
                    response: dict[str, Any] = {
                        "type": f"{control_type}_ack",
                        "ok": accepted,
                        "session_ids": session_ids,
                    }
                    if not accepted:
                        response["error"] = "session limit exceeded"
                    await ws_manager.send_to(websocket, response)
                continue

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
            if "session_id" in data and (
                not isinstance(session_id, str)
                or not session_id
                or session_id != session_id.strip()
            ):
                logger.warning("Ignoring chat message with invalid session_id")
                continue
            if isinstance(session_id, str) and session_id:
                metadata["session_id"] = session_id
                # Claim the session so transient agent events and confirmations
                # route only to participating clients. Text replies remain shared.
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
