"""Text-to-Speech via Kokoro (kokoro-onnx).

Kokoro is a small (82M) Apache-2.0 neural TTS model that sounds markedly more
natural than Piper while still running near real-time on CPU via onnxruntime.
We wrap it behind the same ``synthesize(text, language) -> int16 ndarray`` +
``sample_rate`` surface the pipeline already expects from :class:`TextToSpeech`,
so the two engines are interchangeable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from dax.core.exceptions import TTSError

if TYPE_CHECKING:
    from kokoro_onnx import Kokoro

logger = logging.getLogger(__name__)

# Native output rate of the Kokoro model.
_SAMPLE_RATE = 24_000

# Model artefacts (downloaded by scripts/download_models.py into <dir>/kokoro/).
_MODEL_FILE = "kokoro-v1.0.onnx"
_VOICES_FILE = "voices-v1.0.bin"

# Map our ISO language codes to Kokoro's espeak-style language codes.
_LANG_CODES = {"es": "es", "en": "en-us"}


class KokoroTTS:
    """Synthesise speech with Kokoro, per-language voice selection."""

    def __init__(
        self,
        voice_es: str = "ef_dora",
        voice_en: str = "af_heart",
        speed: float = 1.0,
        model_dir: str = "models/kokoro",
    ) -> None:
        self._voices = {"es": voice_es, "en": voice_en}
        self._speed = speed
        self._model_dir = Path(model_dir).expanduser()
        self._kokoro: Kokoro | None = None
        self._sample_rate = _SAMPLE_RATE

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Load the Kokoro ONNX model and voice bank.

        Raises:
            TTSError: if kokoro-onnx is unavailable or the model files are
                missing — the caller (``build_tts``) falls back to Piper.
        """
        try:
            from kokoro_onnx import Kokoro
        except ImportError as exc:  # pragma: no cover - optional dep
            raise TTSError(
                "kokoro-onnx is not installed (add the 'voice' extra)"
            ) from exc

        model = self._model_dir / _MODEL_FILE
        voices = self._model_dir / _VOICES_FILE
        if not model.is_file() or not voices.is_file():
            raise TTSError(
                f"Kokoro model files not found in {self._model_dir} "
                f"(run scripts/download_models.py)"
            )

        try:
            self._kokoro = Kokoro(str(model), str(voices))
        except Exception as exc:  # pragma: no cover - depends on runtime
            raise TTSError(f"Failed to load Kokoro: {exc}") from exc
        logger.info("TTS started (engine=kokoro, voices=%s)", self._voices)

    def stop(self) -> None:
        """Release the model."""
        self._kokoro = None
        logger.info("TTS stopped (kokoro)")

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def available_languages(self) -> list[str]:
        return list(self._voices.keys())

    # ── Public API ─────────────────────────────────────────────────────────

    def synthesize(self, text: str, language: str = "en") -> np.ndarray:
        """Synthesise *text* into an ``int16`` buffer at 24 kHz."""
        if self._kokoro is None:
            raise TTSError("Kokoro TTS not started")

        voice = self._voices.get(language, self._voices["en"])
        lang_code = _LANG_CODES.get(language, "en-us")
        try:
            samples, sample_rate = self._kokoro.create(
                text, voice=voice, speed=self._speed, lang=lang_code,
            )
        except Exception as exc:
            raise TTSError(f"Kokoro synthesis failed: {exc}") from exc

        self._sample_rate = int(sample_rate)
        # Kokoro returns float32 in [-1, 1]; the player expects int16 PCM.
        arr = np.asarray(samples, dtype=np.float32)
        return (np.clip(arr, -1.0, 1.0) * 32767.0).astype(np.int16)
