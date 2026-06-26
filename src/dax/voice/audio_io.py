"""Audio I/O — microphone capture and speaker playback.

Uses sounddevice for cross-platform audio. Capture runs in a callback-driven
InputStream, feeding chunks into a thread-safe queue for consumers.
Playback supports both blocking (full buffer) and streaming modes.
"""

from __future__ import annotations

import logging
import queue
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16_000  # Capture rate — matches wake word, VAD, and STT expectations.
PLAYBACK_RATE = 22_050  # Piper TTS native output rate.
CHANNELS = 1
CAPTURE_DTYPE = "int16"
CHUNK_SIZE = 1_280  # 80 ms at 16 kHz — good balance for OpenWakeWord frames.


# ── Capture ────────────────────────────────────────────────────────────────────


class AudioCapture:
    """Capture audio from the default microphone in fixed-size chunks.

    Chunks are enqueued via sounddevice's callback and consumed by the
    voice pipeline thread with :meth:`read_chunk`.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        chunk_size: int = CHUNK_SIZE,
    ) -> None:
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Open the microphone stream and begin capturing."""
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=CHANNELS,
            dtype=CAPTURE_DTYPE,
            blocksize=self._chunk_size,
            callback=self._callback,
        )
        self._stream.start()
        logger.info(
            "Audio capture started (rate=%d, chunk=%d)",
            self._sample_rate,
            self._chunk_size,
        )

    def stop(self) -> None:
        """Close the microphone stream and drain the queue."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        # Drain leftover chunks so next start is clean.
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        logger.info("Audio capture stopped")

    # ── Public API ─────────────────────────────────────────────────────────

    def read_chunk(self, timeout: float = 1.0) -> np.ndarray | None:
        """Block until a chunk is available or *timeout* elapses.

        Returns:
            A mono ``int16`` numpy array of *chunk_size* samples, or ``None``
            if no data was available within the timeout.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ── Internal ───────────────────────────────────────────────────────────

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time: object,
        status: sd.CallbackFlags,
    ) -> None:
        """sounddevice callback — runs on the audio thread."""
        if status:
            logger.warning("Audio capture status: %s", status)
        # indata is (frames, channels); flatten to mono and copy out of the
        # callback buffer before it gets reused.
        self._queue.put(indata[:, 0].copy())


# ── Playback ───────────────────────────────────────────────────────────────────


class AudioPlayer:
    """Play audio through the default output device."""

    def play(self, audio: np.ndarray, sample_rate: int = PLAYBACK_RATE) -> None:
        """Play a full audio buffer and block until playback finishes.

        Args:
            audio: Audio samples (``int16`` or ``float32``).
            sample_rate: Sample rate of the audio data.
        """
        sd.play(audio, samplerate=sample_rate)
        sd.wait()

    def play_blocks(
        self,
        audio: np.ndarray,
        sample_rate: int = PLAYBACK_RATE,
        should_stop: Callable[[], bool] | None = None,
        block: int = 2_048,
    ) -> bool:
        """Play an int16 buffer in small blocks, stopping early on demand.

        ``should_stop`` is polled between blocks; when it returns True playback
        halts immediately. Enables barge-in (interrupting Dax mid-reply) and
        low-latency streaming playback.

        Returns:
            True if playback was interrupted, False if it played to the end.
        """
        stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=CHANNELS,
            dtype=CAPTURE_DTYPE,
        )
        stream.start()
        interrupted = False
        try:
            for offset in range(0, len(audio), block):
                if should_stop is not None and should_stop():
                    interrupted = True
                    break
                stream.write(audio[offset: offset + block])
        finally:
            stream.stop()
            stream.close()
        return interrupted

    def play_stream(
        self,
        audio_chunks: Iterable[bytes],
        sample_rate: int = PLAYBACK_RATE,
    ) -> None:
        """Play audio from an iterable of raw ``int16`` byte chunks.

        Useful for low-latency streaming from TTS engines.

        Args:
            audio_chunks: Iterable yielding raw ``int16`` audio bytes.
            sample_rate: Sample rate of the audio data.
        """
        stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=CHANNELS,
            dtype=CAPTURE_DTYPE,
        )
        stream.start()
        try:
            for chunk in audio_chunks:
                data = np.frombuffer(chunk, dtype=np.int16)
                stream.write(data)
        finally:
            stream.stop()
            stream.close()
