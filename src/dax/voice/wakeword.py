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
        if self._model is None:
            raise WakeWordError("WakeWordDetector not started")

        try:
            predictions: dict[str, float] = self._model.predict(audio_chunk)
        except Exception as exc:
            raise WakeWordError(f"Prediction failed: {exc}") from exc

        for model_name, score in predictions.items():
            if score > self._threshold:
                logger.debug(
                    "Wake word '%s' detected (score=%.3f)", model_name, score
                )
                return model_name
        return None

    def reset(self) -> None:
        """Reset the model's internal state between activations."""
        if self._model is not None:
            self._model.reset()
