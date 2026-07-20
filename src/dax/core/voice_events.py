"""Voice event transport — thread-to-loop fan-out with no optional deps.

Lives in ``core`` rather than ``dax.voice`` on purpose. The voice package pulls
in the optional ``voice`` extra (sounddevice, numpy, onnxruntime), but the app
wiring and the ``/ws/voice`` route must import the hub unconditionally: a client
needs to connect and be told "voice is off" even on an install with no voice
extra at all.

The DSP half — turning a raw audio chunk into an envelope and spectrum — lives
in :mod:`dax.voice.events`, where numpy is already a given.

Two properties matter for a client drawing a live waveform:

* **Never block the audio thread.** Emission is fire-and-forget via
  ``loop.call_soon_threadsafe``; a subscriber that falls behind drops frames
  rather than stalling capture.
* **Cost nothing when nobody is watching.** :attr:`VoiceEventHub.has_subscribers`
  is False with no clients attached, and the pipeline skips the metering work
  entirely — an idle backend does no FFT.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# Per-subscriber queue depth. At ~12.5 frames/s this is ~5 s of backlog; past
# that the client is too far behind to be worth buffering for and we drop.
_QUEUE_MAXSIZE = 64


class VoiceEventType(StrEnum):
    """Discriminator for events on the voice stream."""

    STATE = "state"
    LEVEL = "level"
    TRANSCRIPT = "transcript"
    SPEECH = "speech"
    TURN_COMPLETE = "turn_complete"
    APPROVAL_REQUEST = "approval_request"
    SPEAKER = "speaker"
    ERROR = "error"


class LevelSource(StrEnum):
    """Which side of the conversation a level frame describes."""

    INPUT = "input"  # microphone — the user speaking
    OUTPUT = "output"  # TTS playback — Dax speaking


@dataclass(slots=True)
class VoiceEvent:
    """A single event on the voice stream."""

    type: VoiceEventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    owner: str | None = None
    generation: int = 0

    def to_json(self) -> dict[str, Any]:
        return {"type": str(self.type), "data": self.data, "timestamp": self.timestamp}


class VoiceEventHub:
    """Fan-out of voice events from the pipeline thread to asyncio subscribers.

    Mirrors the role ``Agent.set_event_broadcaster`` plays for agent activity,
    but crosses a thread boundary and tolerates lossy delivery: a dropped level
    frame is invisible in a waveform, whereas a blocked audio thread is not.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop
        self._subscribers: set[asyncio.Queue[VoiceEvent]] = set()
        self._subscriber_lock = threading.Lock()
        self._last_state: VoiceEvent | None = None
        self._dropped = 0
        self._owner: str | None = None
        self._generation = 0
        self._context_lock = threading.Lock()

    # -- Loop binding --

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach the event loop events are dispatched onto.

        The hub is constructed during app wiring, before the pipeline (and its
        loop) exist, so binding is deferred.
        """
        self._loop = loop

    # -- Subscription (asyncio side) --

    @property
    def has_subscribers(self) -> bool:
        """True when at least one client is listening.

        The pipeline checks this before computing level frames, so metering
        costs nothing on a headless server with no UI attached.
        """
        with self._subscriber_lock:
            return bool(self._subscribers)

    @property
    def last_state(self) -> VoiceEvent | None:
        """The most recent state event, replayed to clients on connect.

        Without this a client connecting mid-conversation would render "idle"
        until the next transition happened to fire.
        """
        return self._last_state

    def subscribe(self) -> asyncio.Queue[VoiceEvent]:
        """Register a new subscriber and return its queue."""
        queue: asyncio.Queue[VoiceEvent] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        with self._subscriber_lock:
            self._subscribers.add(queue)
            subscriber_count = len(self._subscribers)
        logger.debug("Voice event subscriber added (total: %d)", subscriber_count)
        return queue

    @property
    def event_context(self) -> tuple[str | None, int]:
        """Return the active delivery owner and its monotonic generation."""
        with self._context_lock:
            return self._owner, self._generation

    def set_event_owner(self, owner: str | None) -> int:
        """Start a new local or remote event generation."""
        with self._context_lock:
            self._generation += 1
            self._owner = owner
            return self._generation

    def unsubscribe(self, queue: asyncio.Queue[VoiceEvent]) -> None:
        """Remove a subscriber's queue."""
        with self._subscriber_lock:
            self._subscribers.discard(queue)
            subscriber_count = len(self._subscribers)
        logger.debug("Voice event subscriber removed (total: %d)", subscriber_count)

    # -- Emission (pipeline thread side) --

    def emit(self, event: VoiceEvent) -> None:
        """Publish *event* to all subscribers. Safe to call from any thread.

        Never raises and never blocks — the caller is often the audio thread.
        """
        with self._context_lock:
            event.owner = self._owner
            event.generation = self._generation

        if event.type is VoiceEventType.STATE:
            # Cached before the subscriber check: a client connecting later
            # still needs the current state even if nobody was listening when
            # the transition happened.
            self._last_state = event

        if not self.has_subscribers or self._loop is None:
            return

        # A closed loop (shutdown race) has nothing to deliver to.
        with contextlib.suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._deliver, event)

    def _deliver(self, event: VoiceEvent) -> None:
        """Push *event* onto every subscriber queue. Runs on the event loop."""
        with self._subscriber_lock:
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._dropped += 1
                if self._dropped % 100 == 1:
                    logger.debug(
                        "Voice event queue full — dropped %d frames total",
                        self._dropped,
                    )

    # -- Convenience emitters --

    def emit_state(
        self,
        state: str,
        conversation_id: str | None = None,
        *,
        session_expires_at: float | None = None,
    ) -> None:
        self.emit(
            VoiceEvent(
                type=VoiceEventType.STATE,
                data={
                    "state": state,
                    "conversation_id": conversation_id,
                    "session_expires_at": session_expires_at,
                },
            )
        )

    def emit_transcript(self, text: str, language: str, final: bool = True) -> None:
        self.emit(
            VoiceEvent(
                type=VoiceEventType.TRANSCRIPT,
                data={"text": text, "language": language, "final": final},
            )
        )

    def emit_speech(self, text: str, language: str) -> None:
        """Publish the sentence whose synthesized audio is about to play."""
        self.emit(
            VoiceEvent(
                type=VoiceEventType.SPEECH,
                data={"text": text, "language": language},
            )
        )

    def emit_turn_completed(self, voice_turn: str) -> None:
        """Mark that every client-owned speech sentence for a turn was emitted."""
        self.emit(
            VoiceEvent(
                type=VoiceEventType.TURN_COMPLETE,
                data={"voice_turn": voice_turn},
            )
        )

    def emit_approval_request(
        self,
        *,
        approval_id: str,
        tool_name: str,
        server_name: str,
        arguments: dict[str, Any],
        options: list[str],
        timeout_seconds: int,
    ) -> None:
        self.emit(
            VoiceEvent(
                type=VoiceEventType.APPROVAL_REQUEST,
                data={
                    "approval_id": approval_id,
                    "tool_name": tool_name,
                    "server_name": server_name,
                    "arguments": arguments,
                    "options": options,
                    "timeout_seconds": timeout_seconds,
                },
            )
        )

    def emit_speaker(self, verified: bool, score: float | None = None) -> None:
        self.emit(
            VoiceEvent(
                type=VoiceEventType.SPEAKER,
                data={"verified": verified, "score": score},
            )
        )

    def emit_error(self, message: str) -> None:
        self.emit(VoiceEvent(type=VoiceEventType.ERROR, data={"message": message}))
