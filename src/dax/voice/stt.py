"""Speech-to-Text via faster-whisper.

Wraps the CTranslate2-based Whisper model for efficient CPU inference.
Accepts a float32 audio buffer and returns the transcription with
detected language.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from faster_whisper import WhisperModel

from dax.core.exceptions import STTError

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


class SpeechToText:
    """Transcribe audio buffers to text using faster-whisper.

    Args:
        model_size: Whisper model size (``"tiny"``, ``"base"``, ``"small"``,
            ``"medium"``, ``"large-v3"``).
        compute_type: CTranslate2 quantisation (``"int8"``, ``"float16"``,
            ``"float32"``).
        language: ISO 639-1 code or ``"auto"`` for language detection.
    """

    def __init__(
        self,
        model_size: str = "base",
        compute_type: str = "int8",
        language: str = "auto",
    ) -> None:
        self._model_size = model_size
        self._compute_type = compute_type
        self._language = language
        self._model: WhisperModel | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Download (if needed) and load the Whisper model."""
        try:
            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type=self._compute_type,
            )
            logger.info(
                "STT started (model=%s, compute=%s, lang=%s)",
                self._model_size,
                self._compute_type,
                self._language,
            )
        except Exception as exc:
            raise STTError(
                f"Failed to load Whisper model '{self._model_size}': {exc}"
            ) from exc

    def stop(self) -> None:
        """Release model resources."""
        self._model = None
        logger.info("STT stopped")

    # ── Public API ─────────────────────────────────────────────────────────

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        """Transcribe a float audio buffer to text.

        Args:
            audio: Mono ``float32`` numpy array at 16 kHz,
                normalised to ``[-1.0, 1.0]``.

        Returns:
            A ``(text, detected_language)`` tuple. *text* is the full
            transcription; *detected_language* is an ISO 639-1 code.

        Raises:
            STTError: If the model is not loaded or transcription fails.
        """
        if self._model is None:
            raise STTError("STT model not started")

        kwargs: dict[str, object] = {"beam_size": 5, "vad_filter": True}
        if self._language != "auto":
            kwargs["language"] = self._language

        try:
            segments, info = self._model.transcribe(audio, **kwargs)
            text = " ".join(seg.text.strip() for seg in segments)
        except Exception as exc:
            raise STTError(f"Transcription failed: {exc}") from exc

        logger.debug("Transcribed (%s): %s", info.language, text)
        return text, info.language
