"""WebSocket endpoint that streams live backend logs to the web UI."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["logs"])

logger = logging.getLogger(__name__)


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    """Stream log records as JSON. Authenticated like the chat socket."""
    auth = websocket.app.state.auth
    if not auth.authenticate_websocket(websocket):
        await websocket.close(code=1008)
        return

    log_buffer = getattr(websocket.app.state, "log_buffer", None)
    if log_buffer is None:
        await websocket.close(code=1011)
        return

    await websocket.accept()
    queue = log_buffer.subscribe()
    try:
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        pass
    finally:
        log_buffer.unsubscribe(queue)
