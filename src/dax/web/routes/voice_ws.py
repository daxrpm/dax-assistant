"""WebSocket endpoint that streams live voice pipeline events to UI clients.

Carries the state machine's transitions plus the audio level frames that drive
a waveform. The transport lives in :mod:`dax.core.voice_events` rather than
``dax.voice`` specifically so this route works on an install without the
optional ``voice`` extra — a client must be able to connect and be told that
voice is off, instead of failing to import.

Delivery is deliberately lossy upstream: the hub drops frames rather than
blocking the audio thread. A dropped level frame is invisible in a waveform.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dax.core.voice_events import VoiceEvent, VoiceEventType
from dax.web.dependencies import auth_from_app, voice_events_from_app

router = APIRouter(tags=["voice"])

logger = logging.getLogger(__name__)


def _idle_state() -> dict[str, object]:
    """Synthetic idle frame for when no pipeline has ever run.

    Gives a connecting client a definite starting state instead of leaving it
    to guess between "idle" and "not wired up".
    """
    return VoiceEvent(
        type=VoiceEventType.STATE,
        data={"state": "idle", "conversation_id": None},
    ).to_json()


@router.websocket("/voice")
async def websocket_voice(websocket: WebSocket) -> None:
    """Stream voice events as JSON. Authenticated like the chat socket.

    Protocol is server → client only in v1; the inbound direction is reserved
    for streaming PCM from a remote client's microphone.
    """
    auth = auth_from_app(websocket.app)
    if auth is None or not auth.authenticate_websocket(websocket):
        await websocket.close(code=1008)  # policy violation
        logger.warning("Rejected unauthenticated voice WebSocket connection")
        return

    hub = voice_events_from_app(websocket.app)
    if hub is None:
        await websocket.close(code=1011)  # internal error — not wired
        return

    # The hub is constructed during app wiring, before a loop exists. Binding
    # here is idempotent and covers the case where voice never started.
    hub.bind_loop(asyncio.get_running_loop())

    await websocket.accept()
    queue = hub.subscribe()
    try:
        # Replay the current state so a client connecting mid-conversation
        # renders correctly instead of showing "idle" until the next
        # transition happens to fire.
        last_state = hub.last_state
        await websocket.send_json(
            last_state.to_json() if last_state is not None else _idle_state()
        )

        while True:
            event = await queue.get()
            await websocket.send_json(event.to_json())
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        logger.debug("Voice WebSocket closed unexpectedly", exc_info=True)
    finally:
        # Mandatory: has_subscribers gates all DSP work, so a leaked
        # subscriber would leave the pipeline computing FFTs forever.
        hub.unsubscribe(queue)
