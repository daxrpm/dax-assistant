"""WebSocket endpoint that streams live backend logs to the web UI."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dax.web.dependencies import auth_from_app, log_buffer_from_app

router = APIRouter(tags=["logs"])

logger = logging.getLogger(__name__)


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    """Stream log records as JSON. Authenticated like the chat socket."""
    auth = auth_from_app(websocket.app)
    if auth is None or not auth.authenticate_websocket(websocket):
        await websocket.close(code=1008)
        return

    log_buffer = log_buffer_from_app(websocket.app)
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
