"""Wake-word listening on a capability node.

The backend cannot hear the user. It usually lives in a cupboard, and in this
deployment it has no sound card at all — a wake word spoken at the laptop was
being offered to a microphone that does not exist. This module gives the laptop
its own detector so the machine that *is* in the room is the one that listens.

What it deliberately does not do is act on its own detection. Several machines
can be in earshot of the same sentence, so a detection here is a *claim* sent
to the backend, which judges it against every other microphone's and answers
with a grant or a yield. Only a grant makes this node stream anything.

Two details carry most of the design:

* **Pre-roll.** Arbitration takes a few hundred milliseconds, and the user does
  not politely wait through it — they say "hey jarvis, pon música" in one
  breath. Audio is therefore buffered from the moment of detection and flushed
  the instant a grant arrives, so the command survives the round trip. Without
  it every activation would lose its first syllable.

* **Suppression.** A node that loses still hears the rest of the sentence
  perfectly well and would happily re-trigger on it. Losing means going deaf
  for a moment, not merely staying quiet.

Audio never leaves the machine unless this node wins, which is the property
that makes listening in several rooms acceptable rather than alarming.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import threading
import time
import uuid
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import numpy as np

from dax.edge.protocol import (
    MAX_AUDIO_FRAME_BYTES,
    MAX_AUDIO_FRAMES_PER_LEASE,
    audio_chunk_frame,
    audio_end_frame,
    wake_claim_frame,
)

if TYPE_CHECKING:
    import concurrent.futures

    from dax.edge.protocol import WakePolicy
    from dax.voice.audio_io import LocalAudioSource
    from dax.voice.wakeword import WakeWordDetector

logger = logging.getLogger(__name__)

# Enough pre-roll to cover the arbitration window plus the tail of the wake word
# itself — 1.6 s at 16 kHz in 80 ms frames.
_PREROLL_FRAMES = 20
# Stop streaming after this much silence even if the backend never says stop, so
# a lost `listen_stop` cannot leave the microphone open indefinitely.
_SILENCE_TIMEOUT_S = 3.0
# Below this RMS a frame counts as silence for the timeout above. Deliberately
# crude: the backend runs the real VAD, this only bounds a stuck lease.
_SILENCE_RMS = 300.0

SendFrame = Callable[[dict[str, object]], Coroutine[Any, Any, None]]


def _default_source() -> LocalAudioSource:
    from dax.voice.audio_io import CHUNK_SIZE, SAMPLE_RATE, LocalAudioSource

    return LocalAudioSource(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)


def _default_detector(model: str, threshold: float) -> WakeWordDetector:
    from dax.voice.wakeword import WakeWordDetector

    return WakeWordDetector(model_names=[model], threshold=threshold)


class WakeListener:
    """Runs this node's microphone and turns detections into backend claims."""

    def __init__(
        self,
        send: SendFrame,
        loop: asyncio.AbstractEventLoop,
        *,
        source_factory: Callable[[], LocalAudioSource] | None = None,
        detector_factory: Callable[[str, float], WakeWordDetector] | None = None,
    ) -> None:
        self._send = send
        self._loop = loop
        # Imported inside the factories, not at module scope: a node installed
        # without the `voice` extra only lends tools, and must still start
        # rather than die importing a microphone stack it will never open.
        self._source_factory = source_factory or _default_source
        self._detector_factory = detector_factory or _default_detector
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._generation = 0
        self._policy: WakePolicy | None = None
        # Claim/lease state, all written from the capture thread and read from
        # the event loop when a grant or yield lands.
        self._claim_id: str | None = None
        self._lease_id: str | None = None
        self._suppressed_until = 0.0
        self._granted = threading.Event()

    # -- Lifecycle --

    def apply_policy(self, policy: WakePolicy, generation: int) -> None:
        """Start, stop, or retune the detector to match the backend's policy."""
        with self._lock:
            previous = self._policy
            self._policy = policy
            self._generation = generation
        if not policy.enabled:
            if previous is not None and previous.enabled:
                logger.info("Wake word listening disabled by policy")
            self.stop()
            return
        if (
            previous is not None
            and previous.enabled
            and previous.model == policy.model
            and previous.threshold == policy.threshold
            and self._thread is not None
            and self._thread.is_alive()
        ):
            return
        self.stop()
        self._start()

    def _start(self) -> None:
        self._stop.clear()
        thread = threading.Thread(
            target=self._run, name="edge-wake-listener", daemon=True
        )
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)

    # -- Backend responses --

    def on_grant(self, claim_id: str, lease_id: str) -> None:
        with self._lock:
            if self._claim_id != claim_id:
                # A grant for a claim we already abandoned. Streaming now would
                # send the backend audio from a sentence that has moved on.
                return
            self._lease_id = lease_id
        self._granted.set()

    def on_yield(self, claim_id: str, suppress_ms: int) -> None:
        with self._lock:
            if self._claim_id != claim_id:
                return
            self._claim_id = None
            self._lease_id = None
            self._suppressed_until = time.monotonic() + max(0, suppress_ms) / 1000.0
        self._granted.set()

    def on_listen_stop(self, lease_id: str) -> None:
        with self._lock:
            if self._lease_id == lease_id:
                self._lease_id = None

    # -- Capture thread --

    def _run(self) -> None:
        with self._lock:
            policy = self._policy
        if policy is None:
            return
        source: LocalAudioSource | None = None
        try:
            source = self._source_factory()
            detector = self._detector_factory(policy.model, policy.threshold)
            detector.start()
            source.start()
        except Exception:
            # No microphone, no audio stack, or no model. This node simply does
            # not listen; the backend and any other node still do.
            logger.exception("Wake word listening unavailable on this node")
            if source is not None:
                with contextlib.suppress(Exception):
                    source.stop()
            return

        logger.info(
            "Listening for '%s' on this node (threshold=%.2f)",
            policy.model,
            policy.threshold,
        )
        preroll: list[np.ndarray] = []
        try:
            while not self._stop.is_set():
                chunk = source.read_chunk(timeout=0.5)
                if chunk is None:
                    continue
                preroll.append(chunk)
                if len(preroll) > _PREROLL_FRAMES:
                    preroll.pop(0)
                if time.monotonic() < self._suppressed_until:
                    continue
                detection = detector.detect_with_score(chunk)
                if detection is None:
                    continue
                name, score = detection
                logger.info("Wake word '%s' heard here (score=%.3f)", name, score)
                detector.reset()
                self._claim_and_stream(source, list(preroll), score)
                preroll.clear()
                detector.reset()
        except Exception:
            logger.exception("Wake word listener stopped unexpectedly")
        finally:
            with contextlib.suppress(Exception):
                source.stop()
            with contextlib.suppress(Exception):
                detector.stop()

    def _claim_and_stream(
        self, source: LocalAudioSource, preroll: list[np.ndarray], score: float
    ) -> None:
        """Bid for this activation and, if it is granted, stream the sentence."""
        claim_id = uuid.uuid4().hex
        with self._lock:
            generation = self._generation
            self._claim_id = claim_id
            self._lease_id = None
        self._granted.clear()

        if not self._dispatch(wake_claim_frame(generation, claim_id, score)):
            return
        # Keep capturing while the backend decides, or the pre-roll would stop
        # exactly where the user's command begins.
        buffered = self._capture_until(source, preroll, self._granted, timeout=2.0)
        if not self._granted.wait(timeout=0.1):
            logger.debug("No verdict on wake claim %s — dropping it", claim_id[:8])
            self._clear_claim(claim_id)
            return

        with self._lock:
            lease_id = self._lease_id
        if lease_id is None:
            logger.info("Another microphone answered — this node stands down")
            return

        self._stream_lease(source, buffered, lease_id, generation)

    def _stream_lease(
        self,
        source: LocalAudioSource,
        buffered: list[np.ndarray],
        lease_id: str,
        generation: int,
    ) -> None:
        seq = 0
        silent_since: float | None = None
        for frame in buffered:
            if not self._send_audio(generation, lease_id, seq, frame):
                return
            seq += 1

        while not self._stop.is_set() and seq < MAX_AUDIO_FRAMES_PER_LEASE:
            with self._lock:
                if self._lease_id != lease_id:
                    break  # The backend called end-of-speech.
            chunk = source.read_chunk(timeout=0.5)
            if chunk is None:
                continue
            if not self._send_audio(generation, lease_id, seq, chunk):
                return
            seq += 1
            now = time.monotonic()
            if float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2))) < _SILENCE_RMS:
                if silent_since is None:
                    silent_since = now
                elif now - silent_since > _SILENCE_TIMEOUT_S:
                    logger.debug("Ending wake lease on local silence")
                    break
            else:
                silent_since = None

        self._dispatch(audio_end_frame(generation, lease_id, "complete"))
        with self._lock:
            if self._lease_id == lease_id:
                self._lease_id = None
            self._claim_id = None

    # -- Helpers --

    def _capture_until(
        self,
        source: LocalAudioSource,
        preroll: list[np.ndarray],
        decided: threading.Event,
        *,
        timeout: float,
    ) -> list[np.ndarray]:
        """Keep buffering audio until the verdict lands or *timeout* expires."""
        buffered = list(preroll)
        deadline = time.monotonic() + timeout
        while not decided.is_set() and time.monotonic() < deadline:
            chunk = source.read_chunk(timeout=0.1)
            if chunk is not None and len(buffered) < MAX_AUDIO_FRAMES_PER_LEASE:
                buffered.append(chunk)
        return buffered

    def _send_audio(
        self, generation: int, lease_id: str, seq: int, chunk: np.ndarray
    ) -> bool:
        pcm = np.asarray(chunk, dtype="<i2").tobytes()[:MAX_AUDIO_FRAME_BYTES]
        if not pcm:
            return True
        encoded = base64.b64encode(pcm).decode("ascii")
        return self._dispatch(audio_chunk_frame(generation, lease_id, seq, encoded))

    def _dispatch(self, frame: dict[str, object]) -> bool:
        """Hand one frame to the event loop from the capture thread."""
        try:
            future: concurrent.futures.Future[None] = asyncio.run_coroutine_threadsafe(
                self._send(frame), self._loop
            )
            future.result(timeout=5.0)
        except Exception:
            logger.debug("Wake frame could not be sent", exc_info=True)
            return False
        return True

    def _clear_claim(self, claim_id: str) -> None:
        with self._lock:
            if self._claim_id == claim_id:
                self._claim_id = None
                self._lease_id = None
