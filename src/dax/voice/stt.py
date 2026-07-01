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
        compute_type: str = "auto",
        language: str = "auto",
        device: str = "auto",
        beam_size: int = 1,
        fallback_language: str = "es",
    ) -> None:
        self._model_size = model_size
        self._compute_type = compute_type
        self._language = language
        self._device = device
        self._beam_size = max(1, beam_size)
        # Used in "auto" mode when detection is low-confidence or implausible.
        self._fallback_language = fallback_language if fallback_language in {"es", "en"} else "es"
        self._model: WhisperModel | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_device(device: str) -> str:
        """Resolve "auto" to "cuda" when a GPU is available, else "cpu"."""
        if device != "auto":
            return device
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda"
        except Exception:  # pragma: no cover - depends on hardware
            pass
        return "cpu"

    def start(self) -> None:
        """Download (if needed) and load the Whisper model.

        Auto-selects GPU + float16 when available (large latency win) and falls
        back to CPU + int8 if the GPU path fails to initialise.
        """
        device = self._resolve_device(self._device)
        compute = self._compute_type
        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"

        try:
            self._model = WhisperModel(
                self._model_size, device=device, compute_type=compute,
            )
        except Exception as exc:
            if device == "cuda":
                logger.warning(
                    "GPU STT init failed (%s) — falling back to CPU int8", exc,
                )
                device, compute = "cpu", "int8"
                try:
                    self._model = WhisperModel(
                        self._model_size, device=device, compute_type=compute,
                    )
                except Exception as exc2:
                    raise STTError(
                        f"Failed to load Whisper model '{self._model_size}': {exc2}"
                    ) from exc2
            else:
                raise STTError(
                    f"Failed to load Whisper model '{self._model_size}': {exc}"
                ) from exc

        logger.info(
            "STT started (model=%s, device=%s, compute=%s, beam=%d, lang=%s)",
            self._model_size, device, compute, self._beam_size, self._language,
        )

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

        kwargs: dict[str, object] = {
            "beam_size": self._beam_size,
            # The pipeline already does Silero endpointing before calling us;
            # a second VAD here clips short commands, so keep it off.
            "vad_filter": False,
            # Short voice commands don't benefit from prior-text conditioning,
            # and disabling it avoids context bleed + speeds up decoding.
            "condition_on_previous_text": False,
        }
        if self._language != "auto":
            # Pinning the language stops Whisper from mis-guessing "ru"/etc. on
            # short or noisy clips — the single biggest accuracy win on CPU.
            kwargs["language"] = self._language

        try:
            segments, info = self._model.transcribe(audio, **kwargs)
            text = " ".join(seg.text.strip() for seg in segments)
        except Exception as exc:
            raise STTError(f"Transcription failed: {exc}") from exc

        detected = self._resolve_language(info)
        logger.debug("Transcribed (%s): %s", detected, text)
        return text, detected

    def _resolve_language(self, info: object) -> str:
        """Pick a trustworthy language code from Whisper's transcription info.

        When the language is pinned we honour it. In ``auto`` mode Whisper can
        report an implausible language with low confidence on short clips; we
        only trust a detected es/en above ~50% probability and otherwise fall
        back to the fallback language, never surfacing a spurious "ru".
        """
        if self._language != "auto":
            return self._language
        lang = str(getattr(info, "language", "") or "")
        prob = float(getattr(info, "language_probability", 0.0) or 0.0)
        if lang in {"es", "en"} and prob >= 0.5:
            return lang
        return self._fallback_language
