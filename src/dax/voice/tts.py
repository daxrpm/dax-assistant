"""Text-to-Speech via Piper.

Wraps Piper's ONNX-based VITS voice models for fast, offline speech
synthesis. Supports per-language voices and both blocking and streaming
output modes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from piper.voice import PiperVoice

from dax.core.exceptions import TTSError

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


class TextToSpeech:
    """Synthesise text to audio using Piper TTS voices.

    Args:
        voice_es: Filesystem path to the Spanish ``.onnx`` voice model.
        voice_en: Filesystem path to the English ``.onnx`` voice model.
    """

    def __init__(self, voice_es: str = "", voice_en: str = "") -> None:
        self._voice_es_path = voice_es
        self._voice_en_path = voice_en
        self._voices: dict[str, PiperVoice] = {}
        self._sample_rate: int = 22_050

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Load configured voice models."""
        self._load_voice("es", self._voice_es_path)
        self._load_voice("en", self._voice_en_path)

        if not self._voices:
            logger.warning("No TTS voices loaded — speech output will be unavailable")
        else:
            logger.info("TTS started (voices=%s)", list(self._voices.keys()))

    def stop(self) -> None:
        """Release all loaded voices."""
        self._voices.clear()
        logger.info("TTS stopped")

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def sample_rate(self) -> int:
        """Native sample rate of the most recently used voice."""
        return self._sample_rate

    @property
    def available_languages(self) -> list[str]:
        """Language codes for which a voice is loaded."""
        return list(self._voices.keys())

    # ── Public API ─────────────────────────────────────────────────────────

    def synthesize(self, text: str, language: str = "en") -> np.ndarray:
        """Synthesise *text* into an audio buffer.

        Args:
            text: The string to speak.
            language: ISO 639-1 code selecting which voice to use.
                Falls back to any loaded voice when the requested one
                is unavailable.

        Returns:
            An ``int16`` numpy array at the voice's native sample rate.

        Raises:
            TTSError: If no voice is loaded.
        """
        voice = self._resolve_voice(language)
        self._sample_rate = voice.config.sample_rate

        try:
            arrays: list[np.ndarray] = []
            for chunk in voice.synthesize(text):
                arrays.append(chunk.audio_int16_array)
            if not arrays:
                return np.array([], dtype=np.int16)
            return np.concatenate(arrays)
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"Synthesis failed: {exc}") from exc

    def synthesize_stream(
        self, text: str, language: str = "en"
    ) -> Iterator[bytes]:
        """Stream synthesis — yields raw ``int16`` audio byte chunks.

        Useful for low-latency playback where you want to start speaking
        before the full utterance is synthesised.

        Args:
            text: The string to speak.
            language: ISO 639-1 code selecting which voice to use.

        Yields:
            Raw ``int16`` audio bytes at the voice's native sample rate.

        Raises:
            TTSError: If no voice is loaded.
        """
        voice = self._resolve_voice(language)
        self._sample_rate = voice.config.sample_rate

        try:
            for chunk in voice.synthesize(text):
                yield chunk.audio_int16_bytes
        except Exception as exc:
            raise TTSError(f"Stream synthesis failed: {exc}") from exc

    # ── Internal ───────────────────────────────────────────────────────────

    def _load_voice(self, language: str, path: str) -> None:
        """Attempt to load a single voice model."""
        if not path:
            return
        try:
            self._voices[language] = PiperVoice.load(path)
            logger.info("Loaded TTS voice for '%s' from %s", language, path)
        except Exception:
            logger.warning(
                "Failed to load TTS voice for '%s' from %s", language, path,
                exc_info=True,
            )

    def _resolve_voice(self, language: str) -> PiperVoice:
        """Return the best available voice for *language*."""
        voice = self._voices.get(language)
        if voice is not None:
            return voice

        # Fall back to any loaded voice.
        if self._voices:
            fallback_lang = next(iter(self._voices))
            logger.debug(
                "No voice for '%s', falling back to '%s'", language, fallback_lang
            )
            return self._voices[fallback_lang]

        raise TTSError("No TTS voice loaded")
