"""Speech-to-Text via faster-whisper.

Wraps the CTranslate2-based Whisper model for efficient CPU inference.
Accepts a float32 audio buffer and returns the transcription with
detected language.
"""

from __future__ import annotations

import io
import logging
import os
import wave
from typing import TYPE_CHECKING, Any

import numpy as np
from faster_whisper import WhisperModel

from dax.core.exceptions import STTError

if TYPE_CHECKING:
    from dax.core.config import VoiceConfig

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


class OpenAISpeechToText:
    """Transcribe bounded utterances with OpenAI's hosted Audio API."""

    def __init__(
        self,
        model: str = "gpt-4o-mini-transcribe",
        language: str = "es",
        timeout_s: int = 30,
        prompt: str = "",
        fallback_language: str = "es",
    ) -> None:
        self._model = model
        self._language = language
        self._timeout_s = max(1, timeout_s)
        self._prompt = prompt.strip()
        self._fallback_language = (
            fallback_language if fallback_language in {"es", "en"} else "es"
        )
        self._client: Any = None

    def start(self) -> None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise STTError(
                "OpenAI hosted STT requires OPENAI_API_KEY; configure it in Voice settings"
            )
        try:
            from openai import OpenAI

            self._client = OpenAI(timeout=self._timeout_s)
        except Exception as exc:
            raise STTError(f"Failed to initialize OpenAI hosted STT: {exc}") from exc
        logger.info(
            "STT started (backend=openai, model=%s, lang=%s)",
            self._model,
            self._language,
        )

    def stop(self) -> None:
        client = self._client
        self._client = None
        close = getattr(client, "close", None)
        if callable(close):
            close()
        logger.info("OpenAI hosted STT stopped")

    @staticmethod
    def _wav_bytes(audio: np.ndarray) -> bytes:
        """Encode normalized mono float audio as a 16 kHz PCM WAV."""
        pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16_000)
            wav.writeframes(pcm.tobytes())
        return output.getvalue()

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        if self._client is None:
            raise STTError("OpenAI hosted STT not started")

        kwargs: dict[str, object] = {
            "model": self._model,
            "file": ("speech.wav", self._wav_bytes(audio), "audio/wav"),
            "response_format": "json",
        }
        if self._language != "auto":
            kwargs["language"] = self._language
        if self._prompt:
            kwargs["prompt"] = self._prompt

        try:
            response = self._client.audio.transcriptions.create(**kwargs)
            text = str(getattr(response, "text", "") or "").strip()
        except Exception as exc:
            raise STTError(f"OpenAI transcription failed: {exc}") from exc

        language = self._language if self._language != "auto" else self._fallback_language
        logger.debug("Transcribed via OpenAI (%s): %s", language, text)
        return text, language


class FallbackSpeechToText:
    """Use hosted STT first and lazily load local Whisper after a failure."""

    def __init__(
        self,
        primary: OpenAISpeechToText,
        fallback: SpeechToText,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_ready = False
        self._fallback_ready = False

    def start(self) -> None:
        try:
            self._primary.start()
            self._primary_ready = True
        except STTError as exc:
            logger.warning("Hosted STT unavailable at startup; using local fallback: %s", exc)
            self._start_fallback()

    def stop(self) -> None:
        if self._primary_ready:
            self._primary.stop()
        if self._fallback_ready:
            self._fallback.stop()
        self._primary_ready = False
        self._fallback_ready = False

    def _start_fallback(self) -> None:
        if not self._fallback_ready:
            self._fallback.start()
            self._fallback_ready = True

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        if self._primary_ready:
            try:
                return self._primary.transcribe(audio)
            except STTError as exc:
                logger.warning("Hosted STT failed; retrying locally: %s", exc)
                self._primary.stop()
                self._primary_ready = False
        self._start_fallback()
        return self._fallback.transcribe(audio)


def build_stt(config: VoiceConfig) -> SpeechToText | OpenAISpeechToText | FallbackSpeechToText:
    """Build the configured local or hosted STT implementation."""
    fallback_lang = config.stt_language if config.stt_language in {"es", "en"} else "es"
    local = SpeechToText(
        model_size=config.stt_model,
        compute_type=config.stt_compute_type,
        language=config.stt_language,
        device=config.stt_device,
        beam_size=config.stt_beam_size,
        fallback_language=fallback_lang,
    )
    if config.stt_backend == "local":
        return local
    if config.stt_backend != "openai":
        raise STTError(f"Unsupported STT backend: {config.stt_backend}")

    hosted = OpenAISpeechToText(
        model=config.stt_openai_model,
        language=config.stt_language,
        timeout_s=config.stt_openai_timeout_s,
        prompt=config.stt_openai_prompt,
        fallback_language=fallback_lang,
    )
    if config.stt_fallback_to_local:
        return FallbackSpeechToText(hosted, local)
    return hosted
