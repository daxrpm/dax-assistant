"""Voice profile enrollment and non-mutating TTS previews."""

from __future__ import annotations

import asyncio
import io
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import numpy as np
from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator

from dax.core.exceptions import TTSError, VoiceError
from dax.voice.speaker import SpeakerVerifier
from dax.voice.tts_service import (
    RemoteTTSCoordinator,
    TTSRateLimitError,
    TTSService,
    TTSServiceBusyError,
)
from dax.web.dependencies import ConfigDep

if TYPE_CHECKING:
    from dax.voice.tts import Synthesizer

router = APIRouter(prefix="/voice", tags=["voice"])

_SAMPLE_RATE = 16_000
_MIN_SAMPLES = 3
_MAX_SAMPLES = 5
_MAX_UPLOAD_BYTES = 400_000
_MIN_FRAMES = _SAMPLE_RATE
_MAX_FRAMES = _SAMPLE_RATE * 12
_PREVIEW_LOCK = asyncio.Lock()
_PROFILE_LOCK = asyncio.Lock()


def _voice_pipeline(request: Request) -> object:
    pipeline = getattr(request.app.state, "voice_pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Local voice input is unavailable; enable voice and check the audio device",
        )
    return pipeline


async def _push_to_talk(request: Request, action: Literal["press", "release"]) -> dict[str, str]:
    pipeline = _voice_pipeline(request)
    method = getattr(pipeline, f"push_to_talk_{action}")
    try:
        state = await asyncio.to_thread(method)
    except VoiceError as exc:
        status_code = 503 if "not available" in str(exc).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {"status": "ok", "state": str(state)}


class VoicePreviewRequest(BaseModel):
    engine: Literal["kokoro", "piper", "openai"]
    voice: str = Field(min_length=1, max_length=100)
    language: Literal["es", "en"] = "es"
    text: str = Field(
        default="Hola, soy Dax. Esta es una muestra de mi voz.",
        min_length=1,
        max_length=300,
    )
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    model: str = Field(default="gpt-4o-mini-tts", min_length=1, max_length=100)
    instructions: str = Field(default="", max_length=500)
    timeout_s: int = Field(default=30, ge=1, le=120)


class VoiceSynthesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="auto", min_length=2, max_length=5)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = value.replace("_", "-").lower()
        languages = {"auto": "auto", "es": "es", "es-es": "es", "en": "en", "en-us": "en"}
        try:
            return languages[normalized]
        except KeyError as exc:
            raise ValueError("language must be auto, es, es-ES, en, or en-US") from exc


@router.post("/push-to-talk/press")
async def push_to_talk_press(request: Request) -> dict[str, str]:
    """Begin backend-local microphone capture without wake-word detection."""
    return await _push_to_talk(request, "press")


@router.post("/push-to-talk/release")
async def push_to_talk_release(request: Request) -> dict[str, str]:
    """Finalize backend-local microphone capture and process buffered audio."""
    return await _push_to_talk(request, "release")


def _decode_enrollment_wav(data: bytes) -> np.ndarray:
    if len(data) > _MAX_UPLOAD_BYTES:
        raise ValueError("recording is too large")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if wav.getnchannels() != 1:
                raise ValueError("recording must be mono")
            if wav.getsampwidth() != 2:
                raise ValueError("recording must use 16-bit PCM")
            if wav.getframerate() != _SAMPLE_RATE:
                raise ValueError("recording must use a 16 kHz sample rate")
            frames = wav.getnframes()
            if not _MIN_FRAMES <= frames <= _MAX_FRAMES:
                raise ValueError("recording must be between 1 and 12 seconds")
            raw = wav.readframes(frames)
    except (EOFError, wave.Error) as exc:
        raise ValueError("recording is not a valid WAV file") from exc
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if float(np.sqrt(np.mean(np.square(audio)))) < 0.003:
        raise ValueError("recording is too quiet; speak closer to the microphone")
    return audio


def _encode_wav(audio: np.ndarray, sample_rate: int) -> bytes:
    pcm = np.asarray(audio, dtype="<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return output.getvalue()


def _tts_service(request: Request, config: ConfigDep) -> TTSService:
    service = getattr(request.app.state, "tts_service", None)
    if isinstance(service, TTSService):
        return service
    service = TTSService(config.voice, config.storage.models_path)
    request.app.state.tts_service = service
    return service


@router.post("/synthesize")
async def synthesize_voice(
    request: Request,
    body: VoiceSynthesisRequest,
    config: ConfigDep,
) -> Response:
    """Return a complete WAV using the backend's active TTS configuration."""
    service = _tts_service(request, config)
    coordinator = RemoteTTSCoordinator(
        service, getattr(request.app.state, "capability_hub", None), config.voice
    )
    try:
        result = await coordinator.synthesize_mobile(body.text.strip(), body.language)
    except TTSRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": "60"},
        ) from exc
    except TTSServiceBusyError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except TTSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Voice synthesis failed: {exc}") from exc

    headers = {
        "X-Dax-TTS-Engine": result.engine,
        "X-Dax-TTS-Fingerprint": result.executor_fingerprint,
    }
    if result.voice:
        headers["X-Dax-TTS-Voice"] = result.voice
    return Response(
        content=_encode_wav(result.audio, result.sample_rate),
        media_type="audio/wav",
        headers=headers,
    )


async def _reload_voice(request: Request) -> None:
    dax_app = getattr(request.app.state, "dax_app", None)
    if dax_app is not None:
        await dax_app.reload_voice()


@router.get("/profile")
async def get_voice_profile(config: ConfigDep) -> dict[str, bool]:
    profile = Path(config.storage.models_path).expanduser() / "voice_profile.npy"
    return {"enrolled": profile.is_file()}


@router.post("/enroll")
async def enroll_voice(
    request: Request,
    config: ConfigDep,
    samples: Annotated[list[UploadFile], File()],
) -> dict[str, object]:
    if not _MIN_SAMPLES <= len(samples) <= _MAX_SAMPLES:
        raise HTTPException(status_code=422, detail="Upload between 3 and 5 recordings")

    recordings: list[np.ndarray] = []
    for index, sample in enumerate(samples, start=1):
        data = await sample.read(_MAX_UPLOAD_BYTES + 1)
        try:
            recordings.append(_decode_enrollment_wav(data))
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"Recording {index}: {exc}"
            ) from exc

    profile = Path(config.storage.models_path).expanduser() / "voice_profile.npy"

    def enroll() -> bool:
        verifier = SpeakerVerifier(str(profile), threshold=config.voice.speaker_threshold)
        verifier.start()
        try:
            if not verifier.encoder_ready:
                reason = verifier.unavailable_reason or "install the voice extra"
                raise RuntimeError(f"Voice ID model is unavailable: {reason}")
            return verifier.enroll(recordings)
        finally:
            verifier.stop()

    async with _PROFILE_LOCK:
        try:
            enrolled = await asyncio.to_thread(enroll)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not enrolled:
            raise HTTPException(
                status_code=422, detail="The recordings did not contain usable speech"
            )
        await _reload_voice(request)
    return {"status": "ok", "enrolled": True, "samples": len(recordings)}


@router.delete("/profile")
async def delete_voice_profile(request: Request, config: ConfigDep) -> dict[str, object]:
    profile = Path(config.storage.models_path).expanduser() / "voice_profile.npy"
    async with _PROFILE_LOCK:
        profile.unlink(missing_ok=True)
        await _reload_voice(request)
    return {"status": "ok", "enrolled": False}


def _build_preview_engine(
    body: VoicePreviewRequest, config: ConfigDep
) -> Synthesizer:
    models_path = Path(config.storage.models_path).expanduser()
    if body.engine == "kokoro":
        from dax.voice.tts_kokoro import KokoroTTS

        return KokoroTTS(
            voice_es=body.voice,
            voice_en=body.voice,
            speed=body.speed,
            model_dir=str(models_path / "kokoro"),
        )
    if body.engine == "openai":
        from dax.voice.tts import OpenAITextToSpeech

        return OpenAITextToSpeech(
            model=body.model,
            voice=body.voice,
            instructions_es=body.instructions,
            instructions_en=body.instructions,
            timeout_s=body.timeout_s,
        )

    from dax.voice.tts import TextToSpeech

    return TextToSpeech(
        voice_es=body.voice,
        voice_en=body.voice,
        download_dir=str(models_path / "piper"),
    )


@router.post("/preview")
async def preview_voice(body: VoicePreviewRequest, config: ConfigDep) -> Response:
    async with _PREVIEW_LOCK:
        engine = _build_preview_engine(body, config)

        def synthesize() -> bytes:
            engine.start()
            try:
                audio = engine.synthesize(body.text.strip(), language=body.language)
                if audio.size == 0:
                    raise TTSError("The TTS engine returned no audio")
                return _encode_wav(audio, engine.sample_rate)
            finally:
                engine.stop()

        try:
            wav = await asyncio.to_thread(synthesize)
        except TTSError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Voice preview failed: {exc}") from exc
    return Response(content=wav, media_type="audio/wav")
