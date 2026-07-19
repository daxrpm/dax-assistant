"""Bidirectional voice events and authenticated remote push-to-talk audio.

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
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dax.core.voice_events import VoiceEvent, VoiceEventType
from dax.web.dependencies import auth_from_app, voice_events_from_app

router = APIRouter(tags=["voice"])

logger = logging.getLogger(__name__)

_REMOTE_MAX_BYTES = 16_000 * 2 * 30


class VoiceProtocolError(Exception):
    def __init__(self, code: str, message: str, close_code: int = 1008) -> None:
        super().__init__(message)
        self.code = code
        self.close_code = close_code


@dataclass
class _RemoteLease:
    owner: str | None = None

    async def acquire(self, owner: str) -> bool:
        if self.owner is not None and self.owner != owner:
            return False
        self.owner = owner
        return True

    def release(self, owner: str) -> None:
        if self.owner == owner:
            self.owner = None


def _lease_from_app(app: Any) -> _RemoteLease:
    lease = getattr(app.state, "remote_voice_lease", None)
    if lease is None:
        lease = _RemoteLease()
        app.state.remote_voice_lease = lease
    return lease


def _pipeline_from_app(app: Any) -> Any:
    pipeline = getattr(app.state, "voice_pipeline", None)
    if pipeline is None:
        raise VoiceProtocolError("voice_unavailable", "Voice input is not available")
    return pipeline


def _validate_acquire(frame: dict[str, object]) -> None:
    expected = {
        "sample_rate": 16_000,
        "channels": 1,
        "sample_format": "pcm_s16le",
    }
    if frame.get("format") != expected:
        raise VoiceProtocolError(
            "unsupported_format",
            "Remote audio must be mono 16 kHz signed 16-bit little-endian PCM",
        )


def _idle_state() -> dict[str, object]:
    """Synthetic idle frame for when no pipeline has ever run.

    Gives a connecting client a definite starting state instead of leaving it
    to guess between "idle" and "not wired up".
    """
    return cast(
        "dict[str, object]",
        VoiceEvent(
            type=VoiceEventType.STATE,
            data={
                "state": "idle",
                "conversation_id": None,
                "session_expires_at": None,
            },
        ).to_json(),
    )


@router.websocket("/voice")
async def websocket_voice(websocket: WebSocket) -> None:
    """Stream events and accept one bounded remote PTT stream at a time."""
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
    owner = uuid.uuid4().hex
    lease = _lease_from_app(websocket.app)
    source: Any = None
    acquired = False
    active = False
    received_bytes = 0
    send_lock = asyncio.Lock()

    async def send_json(frame: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_json(frame)

    async def send_events() -> None:
        while True:
            event = await queue.get()
            await send_json(event.to_json())

    async def cleanup_remote() -> None:
        nonlocal acquired, active, source
        if not acquired:
            return
        try:
            pipeline = getattr(websocket.app.state, "voice_pipeline", None)
            if active and pipeline is not None:
                try:
                    await asyncio.to_thread(pipeline.push_to_talk_cancel)
                except Exception:
                    logger.debug("Failed to cancel disconnected remote PTT", exc_info=True)
            if pipeline is not None:
                try:
                    pipeline.select_audio_source(None)
                except Exception:
                    logger.debug("Failed to restore local audio source", exc_info=True)
            if source is not None:
                source.stop()
        finally:
            active = False
            acquired = False
            source = None
            lease.release(owner)

    async def handle_control(frame: dict[str, object]) -> None:
        nonlocal acquired, active, source, received_bytes
        kind = frame.get("type")
        if not isinstance(kind, str):
            raise VoiceProtocolError("malformed_control", "Control frame requires a string type")
        if kind == "remote_audio.acquire":
            if acquired:
                raise VoiceProtocolError("invalid_order", "Remote audio is already acquired")
            _validate_acquire(frame)
            pipeline = _pipeline_from_app(websocket.app)
            if not await lease.acquire(owner):
                raise VoiceProtocolError(
                    "remote_audio_busy",
                    "Remote microphone is owned by another client",
                )
            try:
                from dax.voice.audio_io import RemoteAudioSource

                source = RemoteAudioSource()
                source.start()
                acquired = True
                received_bytes = 0
            except Exception:
                lease.release(owner)
                raise
            await send_json({
                "type": "remote_audio.acquired",
                "data": {
                    "format": frame["format"],
                    "max_frame_bytes": 3_200,
                    "max_duration_seconds": 30,
                    "output": {"mode": "server", "client_audio_supported": False},
                },
            })
            return
        if kind == "remote_audio.start":
            if not acquired or active or source is None:
                raise VoiceProtocolError("invalid_order", "Acquire remote audio before starting")
            pipeline = _pipeline_from_app(websocket.app)
            source.start()
            pipeline.select_audio_source(source)
            try:
                state = await asyncio.to_thread(pipeline.push_to_talk_press)
            except Exception as exc:
                pipeline.select_audio_source(None)
                raise VoiceProtocolError("ptt_rejected", str(exc)) from exc
            active = True
            received_bytes = 0
            await send_json({"type": "remote_audio.started", "data": {"state": str(state)}})
            return
        if kind == "remote_audio.stop":
            if not acquired or not active or source is None:
                raise VoiceProtocolError("invalid_order", "Remote audio is not streaming")
            pipeline = _pipeline_from_app(websocket.app)
            try:
                state = await asyncio.to_thread(pipeline.push_to_talk_release)
            except Exception as exc:
                raise VoiceProtocolError("ptt_rejected", str(exc)) from exc
            active = False
            source.stop()
            pipeline.select_audio_source(None)
            await send_json({"type": "remote_audio.stopped", "data": {"state": str(state)}})
            return
        if kind == "remote_audio.release":
            if not acquired or active:
                raise VoiceProtocolError("invalid_order", "Stop remote audio before releasing it")
            await cleanup_remote()
            await send_json({"type": "remote_audio.released", "data": {}})
            return
        raise VoiceProtocolError("unknown_control", f"Unknown control frame: {kind}")

    async def receive_audio() -> None:
        nonlocal received_bytes
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))
            binary = message.get("bytes")
            if binary is not None:
                if not acquired or not active or source is None:
                    raise VoiceProtocolError(
                        "invalid_order",
                        "PCM frames require an active remote stream",
                    )
                received_bytes += len(binary)
                if received_bytes > _REMOTE_MAX_BYTES:
                    raise VoiceProtocolError(
                        "duration_limit",
                        "Remote audio exceeds 30 seconds",
                        close_code=1009,
                    )
                try:
                    source.feed_pcm(binary)
                except BufferError as exc:
                    raise VoiceProtocolError("backpressure", str(exc), close_code=1013) from exc
                except ValueError as exc:
                    close_code = 1009 if "exceeds" in str(exc) else 1008
                    raise VoiceProtocolError(
                        "invalid_pcm", str(exc), close_code=close_code
                    ) from exc
                continue
            text = message.get("text")
            if text is None:
                raise VoiceProtocolError(
                    "malformed_control",
                    "Expected JSON control or binary PCM",
                )
            try:
                frame = json.loads(text)
            except (TypeError, ValueError) as exc:
                raise VoiceProtocolError(
                    "malformed_control", "Control frame is not valid JSON"
                ) from exc
            if not isinstance(frame, dict):
                raise VoiceProtocolError(
                    "malformed_control", "Control frame must be a JSON object"
                )
            try:
                await handle_control(frame)
            except VoiceProtocolError:
                raise
            except Exception as exc:
                raise VoiceProtocolError(
                    "voice_error", "Remote voice input failed", close_code=1011
                ) from exc

    event_task: asyncio.Task[None] | None = None
    try:
        # Replay the current state so a client connecting mid-conversation
        # renders correctly instead of showing "idle" until the next
        # transition happens to fire.
        last_state = hub.last_state
        await send_json(
            last_state.to_json() if last_state is not None else _idle_state()
        )
        event_task = asyncio.create_task(send_events())
        await receive_audio()
    except VoiceProtocolError as exc:
        try:
            await send_json(
                {
                    "type": "remote_audio.error",
                    "data": {"code": exc.code, "message": str(exc)},
                }
            )
            await websocket.close(code=exc.close_code, reason=str(exc)[:123])
        except Exception:
            pass
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        logger.debug("Voice WebSocket closed unexpectedly", exc_info=True)
    finally:
        # These synchronous gates must close before any cancellation-sensitive
        # cleanup await; otherwise a cancelled TestClient or server shutdown can
        # leave metering enabled even though the socket is already gone.
        hub.unsubscribe(queue)
        if event_task is not None:
            event_task.cancel()
        try:
            await asyncio.shield(cleanup_remote())
        finally:
            if event_task is not None:
                await asyncio.gather(event_task, return_exceptions=True)
