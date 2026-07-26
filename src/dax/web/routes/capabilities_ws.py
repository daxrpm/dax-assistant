"""Authenticated WebSocket endpoint for optional capability nodes."""

from __future__ import annotations

import contextlib
import logging

from fastapi import APIRouter, WebSocket

from dax.web.dependencies import auth_from_app

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/capabilities")
async def websocket_capabilities(websocket: WebSocket) -> None:
    auth = auth_from_app(websocket.app)
    node_id = (
        auth.authenticate_capability_websocket(websocket) if auth is not None else None
    )
    if node_id is None:
        # Accept first so the node sees 1008 rather than a 1006 it would treat
        # as a flaky link and retry against. See routes/chat.py.
        with contextlib.suppress(Exception):
            await websocket.accept()
        with contextlib.suppress(Exception):
            await websocket.close(code=1008)
        logger.warning("Rejected unauthenticated capability node")
        return
    hub = getattr(websocket.app.state, "capability_hub", None)
    if hub is None:
        await websocket.close(code=1011)
        return
    await websocket.accept()
    await hub.handle(websocket, node_id)
