"""Text-to-Speech via Piper.

Wraps Piper's ONNX-based VITS voice models for fast, offline speech
synthesis. Supports per-language voices and both blocking and streaming
output modes.
"""

from __future__ import annotations

import logging
from pathlib import Path
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

    def __init__(
        self,
        voice_es: str = "",
        voice_en: str = "",
        download_dir: str = "models/piper",
    ) -> None:
        self._voice_es_path = voice_es
        self._voice_en_path = voice_en
        self._download_dir = Path(download_dir).expanduser()
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
        """Load a voice by file path or by name (auto-downloading if needed)."""
        if not path:
            return
        try:
            resolved = self._resolve_voice_path(path)
            if resolved is None:
                logger.warning(
                    "Could not resolve/download TTS voice for '%s' (%s)",
                    language, path,
                )
                return
            self._voices[language] = PiperVoice.load(str(resolved))
            logger.info("Loaded TTS voice for '%s' from %s", language, resolved)
        except Exception:
            logger.warning(
                "Failed to load TTS voice for '%s' from %s", language, path,
                exc_info=True,
            )

    def _resolve_voice_path(self, value: str) -> Path | None:
        """Resolve *value* to a local ``.onnx`` file.

        Accepts either a path to an existing model file, or a Piper voice name
        (e.g. ``es_ES-davefx-medium``) which is downloaded from the official
        rhasspy/piper-voices repo into the models dir on first use — so voices
        "just work" out of the box, like the auto-downloaded Whisper model.
        """
        candidate = Path(value).expanduser()
        if candidate.is_file():
            return candidate

        # Treat it as a voice name and ensure it's downloaded.
        target = self._download_dir / f"{value}.onnx"
        if target.is_file():
            return target

        try:
            from piper.download_voices import download_voice

            self._download_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Downloading Piper voice '%s' → %s", value, self._download_dir)
            download_voice(value, self._download_dir)
        except Exception:
            logger.warning("Failed to download Piper voice '%s'", value, exc_info=True)
            return None

        return target if target.is_file() else None

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
