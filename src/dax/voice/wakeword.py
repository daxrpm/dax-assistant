"""Wake word detection via OpenWakeWord.

Wraps the OpenWakeWord inference model behind a simple detect/reset API.
The pipeline feeds 80 ms audio chunks and checks whether any configured
wake word exceeds the confidence threshold.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import openwakeword
import openwakeword.utils
from openwakeword.model import Model as OWWModel

from dax.core.exceptions import WakeWordError

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """Detect wake words in streaming audio chunks.

    Args:
        model_names: List of OpenWakeWord model names to load.
            Defaults to ``["hey_jarvis"]``.
        threshold: Minimum confidence score to trigger a detection.
    """

    def __init__(
        self,
        model_names: list[str] | None = None,
        threshold: float = 0.5,
    ) -> None:
        self._threshold = threshold
        self._model_names = model_names or ["hey_jarvis"]
        self._model: OWWModel | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Download models (if needed) and initialise the detector."""
        try:
            openwakeword.utils.download_models()
            self._model = OWWModel(
                wakeword_models=self._model_names,
                inference_framework="onnx",
            )
            logger.info(
                "Wake word detector started (models=%s, threshold=%.2f)",
                self._model_names,
                self._threshold,
            )
        except Exception as exc:
            raise WakeWordError(
                f"Failed to initialise wake word detector: {exc}"
            ) from exc

    def stop(self) -> None:
        """Release the model resources."""
        self._model = None
        logger.info("Wake word detector stopped")

    # ── Public API ─────────────────────────────────────────────────────────

    def detect(self, audio_chunk: np.ndarray) -> str | None:
        """Check whether a wake word was detected in an audio chunk.

        Args:
            audio_chunk: Mono ``int16`` numpy array, typically 1 280 samples
                (80 ms at 16 kHz).

        Returns:
            The name of the detected model, or ``None`` if nothing triggered.

        Raises:
            WakeWordError: If the detector has not been started.
        """
        detection = self.detect_with_score(audio_chunk)
        return detection[0] if detection is not None else None

    def detect_with_score(self, audio_chunk: np.ndarray) -> tuple[str, float] | None:
        """Detect, reporting the confidence alongside the model name.

        The score matters when more than one microphone is listening: the
        backend compares confidences to decide which one was closest to the
        speaker, so a detector that only reported "yes" would leave the
        arbiter nothing to arbitrate on.

        Returns:
            ``(model_name, score)`` for the highest-scoring model above the
            threshold, or ``None`` if nothing triggered.
        """
        if self._model is None:
            raise WakeWordError("WakeWordDetector not started")

        try:
            predictions: dict[str, float] = self._model.predict(audio_chunk)
        except Exception as exc:
            raise WakeWordError(f"Prediction failed: {exc}") from exc

        best: tuple[str, float] | None = None
        for model_name, score in predictions.items():
            if score > self._threshold and (best is None or score > best[1]):
                best = (model_name, float(score))
        if best is not None:
            logger.debug("Wake word '%s' detected (score=%.3f)", best[0], best[1])
        return best

    def reset(self) -> None:
        """Reset the model's internal state between activations."""
        if self._model is not None:
            self._model.reset()
