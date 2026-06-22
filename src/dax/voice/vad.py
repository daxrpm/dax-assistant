"""Voice Activity Detection via Silero VAD.

Wraps Silero VAD behind a chunk-oriented API that the pipeline uses to
detect speech boundaries (start / end). The VADIterator handles the
min-silence logic internally — we just feed 32 ms chunks and read events.
"""

from __future__ import annotations

import logging

import numpy as np
import torch
from silero_vad import VADIterator, load_silero_vad

from dax.core.exceptions import VoiceError

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16_000
VAD_CHUNK_SIZE = 512  # 32 ms at 16 kHz — required by Silero VAD.


class VoiceActivityDetector:
    """Detect speech start and end boundaries in streaming audio.

    Args:
        threshold: VAD probability threshold (0.0-1.0).
        silence_duration_ms: Minimum silence duration before declaring
            end-of-speech.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        silence_duration_ms: int = 800,
    ) -> None:
        self._threshold = threshold
        self._silence_duration_ms = silence_duration_ms
        self._model: torch.jit.ScriptModule | None = None
        self._iterator: VADIterator | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Load the Silero VAD model and create the iterator."""
        try:
            self._model = load_silero_vad()
            self._iterator = VADIterator(
                self._model,
                sampling_rate=SAMPLE_RATE,
                threshold=self._threshold,
                min_silence_duration_ms=self._silence_duration_ms,
                speech_pad_ms=30,
            )
            logger.info(
                "VAD started (threshold=%.2f, silence=%d ms)",
                self._threshold,
                self._silence_duration_ms,
            )
        except Exception as exc:
            raise VoiceError(f"Failed to initialise VAD: {exc}") from exc

    def stop(self) -> None:
        """Release model resources."""
        self._model = None
        self._iterator = None
        logger.info("VAD stopped")

    # ── Public API ─────────────────────────────────────────────────────────

    def process_chunk(self, audio_chunk: np.ndarray) -> dict[str, float] | None:
        """Process a single VAD-sized audio chunk.

        Args:
            audio_chunk: A ``float32`` numpy array of exactly
                :data:`VAD_CHUNK_SIZE` samples (512 at 16 kHz).

        Returns:
            ``{"start": timestamp}`` when speech begins,
            ``{"end": timestamp}`` when speech ends, or ``None``
            if no boundary was detected.

        Raises:
            VoiceError: If the detector has not been started.
        """
        if self._iterator is None:
            raise VoiceError("VAD not started")

        tensor = torch.from_numpy(audio_chunk.astype(np.float32))
        return self._iterator(tensor)

    def reset(self) -> None:
        """Reset the iterator state between utterances."""
        if self._iterator is not None:
            self._iterator.reset_states()
