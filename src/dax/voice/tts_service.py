"""Resident, serialized access to the configured TTS engine."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dax.core.exceptions import TTSError
from dax.voice.tts import build_tts

if TYPE_CHECKING:
    import numpy as np

    from dax.core.config import VoiceConfig


_TTS_CONFIG_FIELDS = (
    "tts_engine",
    "tts_voice_es",
    "tts_voice_en",
    "tts_kokoro_voice_es",
    "tts_kokoro_voice_en",
    "tts_kokoro_speed",
    "tts_openai_model",
    "tts_openai_voice",
    "tts_openai_instructions_es",
    "tts_openai_instructions_en",
    "tts_openai_timeout_s",
    "tts_fallback_to_local",
)
_SPANISH_MARKERS = re.compile(
    r"[áéíóúñ¿¡]|\b(?:el|la|los|las|un|una|que|de|en|para|por|con|hola|gracias)\b",
    re.IGNORECASE,
)


class TTSServiceBusyError(TTSError):
    """The bounded mobile synthesis queue cannot accept more work."""


class TTSRateLimitError(TTSError):
    """The mobile synthesis rate limit was exceeded."""


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    audio: np.ndarray
    sample_rate: int
    engine: str
    voice: str | None
    language: str


class TTSService:
    """Own one configured engine and serialize all access to it.

    The pipeline and HTTP endpoint share this instance. Engines are initialized
    lazily so voice-disabled/headless installations only pay the model cost when
    synthesis is actually requested.
    """

    def __init__(
        self,
        config: VoiceConfig,
        models_path: str,
        *,
        mobile_requests_per_minute: int = 30,
        mobile_wait_seconds: float = 5.0,
    ) -> None:
        self._config = config
        self._engine = build_tts(config, models_path)
        self._lock = threading.Lock()
        self._started = False
        self._mobile_requests: deque[float] = deque()
        self._mobile_requests_per_minute = mobile_requests_per_minute
        self._mobile_wait_seconds = mobile_wait_seconds
        payload = {
            **{field: getattr(config, field) for field in _TTS_CONFIG_FIELDS},
            "models_path": models_path,
        }
        self._fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def start(self) -> None:
        with self._lock:
            self._start_locked()

    def stop(self) -> None:
        with self._lock:
            if self._started:
                self._engine.stop()
                self._started = False

    def synthesize(self, text: str, language: str) -> SynthesisResult:
        """Synthesize for an internal caller, waiting for the shared engine."""
        with self._lock:
            return self._synthesize_locked(text, language)

    def synthesize_mobile(self, text: str, language: str) -> SynthesisResult:
        """Synthesize one bounded/rate-limited HTTP request."""
        now = time.monotonic()
        with self._lock:
            cutoff = now - 60.0
            while self._mobile_requests and self._mobile_requests[0] <= cutoff:
                self._mobile_requests.popleft()
            if len(self._mobile_requests) >= self._mobile_requests_per_minute:
                raise TTSRateLimitError("Voice synthesis rate limit exceeded")
            self._mobile_requests.append(now)

        if not self._lock.acquire(timeout=self._mobile_wait_seconds):
            raise TTSServiceBusyError("Voice synthesizer is busy")
        try:
            return self._synthesize_locked(text, language)
        finally:
            self._lock.release()

    def _start_locked(self) -> None:
        if not self._started:
            self._engine.start()
            self._started = True

    def _synthesize_locked(self, text: str, language: str) -> SynthesisResult:
        self._start_locked()
        resolved_language = self._resolve_language(text, language)
        audio = self._engine.synthesize(text, language=resolved_language)
        if audio.size == 0:
            raise TTSError("The TTS engine returned no audio")
        return SynthesisResult(
            audio=audio,
            sample_rate=self._engine.sample_rate,
            engine=self._engine.engine_name,
            voice=self._engine.voice_name(resolved_language),
            language=resolved_language,
        )

    def _resolve_language(self, text: str, language: str) -> str:
        if language in {"es", "en"}:
            return language
        if self._config.stt_language in {"es", "en"}:
            return self._config.stt_language
        return "es" if _SPANISH_MARKERS.search(text) else "en"
