"""Text-to-Speech via Piper.

Wraps Piper's ONNX-based VITS voice models for fast, offline speech
synthesis. Supports per-language voices and both blocking and streaming
output modes.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np
from piper.voice import PiperVoice

from dax.core.exceptions import TTSError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from dax.core.config import VoiceConfig

logger = logging.getLogger(__name__)


@runtime_checkable
class Synthesizer(Protocol):
    """Common surface every TTS engine exposes to the pipeline."""

    @property
    def sample_rate(self) -> int: ...

    @property
    def engine_name(self) -> str: ...

    def voice_name(self, language: str) -> str | None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def synthesize(self, text: str, language: str = "en") -> np.ndarray: ...


class OpenAITextToSpeech:
    """Natural hosted speech using OpenAI's PCM Audio API."""

    def __init__(
        self,
        model: str = "gpt-4o-mini-tts",
        voice: str = "marin",
        instructions_es: str = "",
        instructions_en: str = "",
        timeout_s: int = 30,
    ) -> None:
        self._model = model
        self._voice = voice
        self._instructions = {"es": instructions_es, "en": instructions_en}
        self._timeout_s = max(1, timeout_s)
        self._client: Any = None

    @property
    def sample_rate(self) -> int:
        return 24_000

    @property
    def engine_name(self) -> str:
        return "openai"

    def voice_name(self, language: str) -> str | None:
        return self._voice

    def start(self) -> None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise TTSError(
                "OpenAI TTS requires OPENAI_API_KEY; configure it in Voice settings"
            )
        try:
            from openai import OpenAI

            self._client = OpenAI(timeout=self._timeout_s)
        except Exception as exc:
            raise TTSError(f"Failed to initialize OpenAI TTS: {exc}") from exc
        logger.info(
            "TTS started (engine=openai, model=%s, voice=%s)",
            self._model,
            self._voice,
        )

    def stop(self) -> None:
        client = self._client
        self._client = None
        close = getattr(client, "close", None)
        if callable(close):
            close()
        logger.info("OpenAI TTS stopped")

    def synthesize(self, text: str, language: str = "en") -> np.ndarray:
        if self._client is None:
            raise TTSError("OpenAI TTS not started")
        kwargs: dict[str, object] = {
            "model": self._model,
            "voice": self._voice,
            "input": text,
            "response_format": "pcm",
        }
        instructions = self._instructions.get(language) or self._instructions["en"]
        if instructions:
            kwargs["instructions"] = instructions
        try:
            response = self._client.audio.speech.create(**kwargs)
            content = bytes(response.content)
        except Exception as exc:
            raise TTSError(f"OpenAI TTS synthesis failed: {exc}") from exc
        return np.frombuffer(content, dtype="<i2").copy()


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
    def engine_name(self) -> str:
        return "piper"

    def voice_name(self, language: str) -> str | None:
        if language in self._voices:
            return self._voice_es_path if language == "es" else self._voice_en_path
        if self._voices:
            fallback_lang = next(iter(self._voices))
            return self._voice_es_path if fallback_lang == "es" else self._voice_en_path
        return None

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


def _build_piper(config: VoiceConfig, models_path: str) -> TextToSpeech:
    return TextToSpeech(
        voice_es=config.tts_voice_es,
        voice_en=config.tts_voice_en,
        download_dir=str(Path(models_path) / "piper"),
    )


def build_tts(config: VoiceConfig, models_path: str) -> Synthesizer:
    """Build the configured TTS engine, with Piper as the safety net.

    ``tts_engine = "kokoro"`` gets a natural neural voice but needs the
    ``kokoro-onnx`` package + model files; if either is missing at start-up the
    pipeline still speaks via Piper instead of going silent.
    """
    if config.tts_engine == "openai":
        hosted = OpenAITextToSpeech(
            model=config.tts_openai_model,
            voice=config.tts_openai_voice,
            instructions_es=config.tts_openai_instructions_es,
            instructions_en=config.tts_openai_instructions_en,
            timeout_s=config.tts_openai_timeout_s,
        )
        if config.tts_fallback_to_local:
            return _FallbackSynthesizer(
                hosted, lambda: _build_local_tts(config, models_path)
            )
        return hosted
    return _build_local_tts(config, models_path)


def _build_local_tts(config: VoiceConfig, models_path: str) -> Synthesizer:
    if config.tts_engine in {"kokoro", "openai"}:
        from dax.voice.tts_kokoro import KokoroTTS

        kokoro = KokoroTTS(
            voice_es=config.tts_kokoro_voice_es,
            voice_en=config.tts_kokoro_voice_en,
            speed=config.tts_kokoro_speed,
            model_dir=str(Path(models_path) / "kokoro"),
        )
        return _FallbackSynthesizer(kokoro, lambda: _build_piper(config, models_path))
    return _build_piper(config, models_path)


class _FallbackSynthesizer:
    """Wraps a primary engine and lazily swaps to a fallback if it fails.

    The swap happens at :meth:`start` (engine fails to load) or on the first
    failed :meth:`synthesize`, so a missing model or a bad utterance degrades
    to Piper instead of breaking the whole voice loop.
    """

    def __init__(
        self,
        primary: Synthesizer,
        fallback_factory: Callable[[], Synthesizer],
    ) -> None:
        self._primary = primary
        self._fallback_factory = fallback_factory
        self._active: Synthesizer = primary
        self._fell_back = False

    def _swap_to_fallback(self) -> None:
        if self._fell_back:
            return
        logger.warning("TTS falling back to the configured local engine")
        fallback = self._fallback_factory()
        fallback.start()
        self._active = fallback
        self._fell_back = True

    @property
    def sample_rate(self) -> int:
        return self._active.sample_rate

    @property
    def engine_name(self) -> str:
        return self._active.engine_name

    def voice_name(self, language: str) -> str | None:
        return self._active.voice_name(language)

    def start(self) -> None:
        try:
            self._primary.start()
        except Exception:
            logger.warning("Primary TTS engine failed to start", exc_info=True)
            self._swap_to_fallback()

    def stop(self) -> None:
        self._active.stop()

    def synthesize(self, text: str, language: str = "en") -> np.ndarray:
        try:
            return self._active.synthesize(text, language=language)
        except Exception:
            if self._fell_back:
                raise
            logger.warning("Primary TTS synth failed — switching to Piper", exc_info=True)
            self._swap_to_fallback()
            return self._active.synthesize(text, language=language)
