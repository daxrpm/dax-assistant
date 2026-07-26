"""Capability-node protocol v1 frame validation and construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 256 * 1024
MAX_RESULT_BYTES = 64 * 1024
MAX_TIMEOUT_SECONDS = 60.0
MAX_TTS_TEXT_CHARS = 2000
MAX_TTS_CONFIG_BYTES = 4096
MAX_TTS_CHUNK_BYTES = 48 * 1024
MAX_TTS_CHUNKS = 128
MAX_TTS_AUDIO_BYTES = 6 * 1024 * 1024
MAX_AUDIO_FRAME_BYTES = 3_200
MAX_AUDIO_FRAMES_PER_LEASE = 300


@dataclass(frozen=True, slots=True)
class ExecuteRequest:
    request_id: str
    generation: int
    tool_name: str
    arguments: dict[str, object]
    timeout_seconds: float
    # Whether a human confirmed this exact call on a client. Absent on an older
    # backend, which is why it defaults to False: a node must never widen what
    # it will run because a field it does not understand went missing.
    approved: bool = False


@dataclass(frozen=True, slots=True)
class SynthesizeRequest:
    request_id: str
    generation: int
    text: str
    language: Literal["es", "en"]
    engine: Literal["kokoro", "piper"]
    config: dict[str, object]


def hello_frame(
    node_name: str,
    tools: list[dict[str, Any]],
    endpoints: list[str] | None = None,
) -> dict[str, object]:
    return {
        "type": "hello",
        "version": PROTOCOL_VERSION,
        "node_name": node_name,
        "tools": tools,
        # Proposed, not asserted: the backend re-validates these and drops any
        # address that is not on a private network.
        "endpoints": list(endpoints or []),
    }


def parse_ready(frame: dict[str, object]) -> str | None:
    """The backend's ticket-signing public key, from the ready frame.

    Absent on an older backend, in which case the node simply cannot verify
    tickets and must refuse direct sessions rather than accept unverified ones.
    """
    if frame.get("type") != "ready":
        return None
    key = frame.get("public_key")
    if not isinstance(key, str) or not key or len(key) > 128:
        return None
    return key


def local_tts_features_frame(
    ready: dict[str, object], engines: list[str]
) -> dict[str, object] | None:
    """Negotiate optional TTS only when the backend explicitly supports it."""
    features = ready.get("features")
    generation = ready.get("generation")
    if (
        ready.get("type") != "ready"
        or not isinstance(features, dict)
        or features.get("local_tts") != 1
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
        or not engines
    ):
        return None
    return {
        "type": "features",
        "generation": generation,
        "local_tts": {"engines": list(engines)},
    }


@dataclass(frozen=True, slots=True)
class WakePolicy:
    """What the backend last told this node about listening.

    Model and threshold come from the backend so that every microphone in the
    house is judged on the same scale — an arbitration between detectors tuned
    differently would compare numbers that do not mean the same thing.
    """

    enabled: bool
    model: str
    threshold: float


def parse_wake_policy(frame: dict[str, object]) -> WakePolicy | None:
    """Read the wake settings out of a policy frame, if it carries them.

    An older backend sends no wake fields at all; the node must then not
    listen, because nothing on the other side would arbitrate its claims and
    it would answer over whatever else is in the room.
    """
    if frame.get("type") != "policy":
        return None
    enabled = frame.get("wake_word")
    model = frame.get("wake_word_model")
    threshold = frame.get("wake_word_threshold")
    if not isinstance(enabled, bool):
        return None
    if not isinstance(model, str) or not model or len(model) > 256:
        return None
    if (
        not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not 0.0 <= float(threshold) <= 1.0
    ):
        return None
    return WakePolicy(enabled=enabled, model=model, threshold=float(threshold))


def wake_claim_frame(generation: int, claim_id: str, score: float) -> dict[str, object]:
    return {
        "type": "wake_claim",
        "generation": generation,
        "claim_id": claim_id,
        "score": max(0.0, min(1.0, float(score))),
    }


def audio_chunk_frame(
    generation: int, lease_id: str, seq: int, data: str
) -> dict[str, object]:
    return {
        "type": "audio_chunk",
        "generation": generation,
        "lease_id": lease_id,
        "seq": seq,
        "data": data,
    }


def audio_end_frame(
    generation: int, lease_id: str, reason: str = "complete"
) -> dict[str, object]:
    return {
        "type": "audio_end",
        "generation": generation,
        "lease_id": lease_id,
        "reason": reason,
    }


def parse_frame(raw: str | bytes) -> dict[str, object]:
    encoded = raw.encode() if isinstance(raw, str) else raw
    if len(encoded) > MAX_FRAME_BYTES:
        raise ValueError("Frame exceeds the maximum size")
    value = json.loads(encoded)
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ValueError("Frame must be an object with a type")
    return value


def parse_execute(frame: dict[str, object]) -> ExecuteRequest:
    if frame.get("type") != "execute":
        raise ValueError("Not an execute frame")
    request_id = frame.get("request_id")
    generation = frame.get("generation")
    tool_name = frame.get("tool_name")
    arguments = frame.get("arguments")
    timeout = frame.get("timeout_seconds")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
        raise ValueError("Invalid request_id")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise ValueError("Invalid generation")
    if not isinstance(tool_name, str) or not tool_name or len(tool_name) > 128:
        raise ValueError("Invalid tool_name")
    if not isinstance(arguments, dict):
        raise ValueError("Invalid arguments")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise ValueError("Invalid timeout_seconds")
    bounded_timeout = min(float(timeout), MAX_TIMEOUT_SECONDS)
    if bounded_timeout <= 0:
        raise ValueError("Invalid timeout_seconds")
    approved = frame.get("approved")
    if not isinstance(approved, bool):
        approved = False
    return ExecuteRequest(
        request_id, generation, tool_name, arguments, bounded_timeout, approved
    )


def parse_synthesize(frame: dict[str, object]) -> SynthesizeRequest:
    if frame.get("type") != "synthesize":
        raise ValueError("Not a synthesize frame")
    request_id = frame.get("request_id")
    generation = frame.get("generation")
    text = frame.get("text")
    language = frame.get("language")
    engine = frame.get("engine")
    config = frame.get("config")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
        raise ValueError("Invalid request_id")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise ValueError("Invalid generation")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TTS_TEXT_CHARS:
        raise ValueError("Invalid synthesis text")
    if language not in {"es", "en"}:
        raise ValueError("Invalid synthesis language")
    if engine not in {"kokoro", "piper"}:
        raise ValueError("Invalid synthesis engine")
    if not isinstance(config, dict):
        raise ValueError("Invalid synthesis config")
    if len(json.dumps(config, separators=(",", ":")).encode()) > MAX_TTS_CONFIG_BYTES:
        raise ValueError("Synthesis config exceeds limit")
    allowed = {"piper_voice_es", "piper_voice_en"}
    if engine == "kokoro":
        allowed.update({"kokoro_voice_es", "kokoro_voice_en", "speed"})
    if set(config) != allowed:
        raise ValueError("Invalid synthesis config fields")
    voice_fields = ["piper_voice_es", "piper_voice_en"]
    if engine == "kokoro":
        voice_fields.extend(("kokoro_voice_es", "kokoro_voice_en"))
    for key in voice_fields:
        value = config.get(key)
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ValueError(f"Invalid {key}")
    if engine == "kokoro":
        speed = config.get("speed")
        if (
            not isinstance(speed, (int, float))
            or isinstance(speed, bool)
            or not 0.5 <= float(speed) <= 2.0
        ):
            raise ValueError("Invalid speed")
    return SynthesizeRequest(
        request_id, generation, text.strip(), language, engine, dict(config)  # type: ignore[arg-type]
    )


def synthesize_chunk_frame(
    request: SynthesizeRequest, index: int, data: str
) -> dict[str, object]:
    return {
        "type": "synthesize_chunk",
        "request_id": request.request_id,
        "generation": request.generation,
        "index": index,
        "data": data,
    }


def synthesize_final_frame(
    request: SynthesizeRequest, *, success: bool, **fields: object
) -> dict[str, object]:
    return {
        "type": "synthesize_final",
        "request_id": request.request_id,
        "generation": request.generation,
        "success": success,
        **fields,
    }


def result_frame(
    request: ExecuteRequest,
    *,
    success: bool,
    content: str = "",
    error: str | None = None,
) -> dict[str, object]:
    content_bytes = content.encode()
    if len(content_bytes) > MAX_RESULT_BYTES:
        suffix = b"\n[truncated]"
        content = content_bytes[: MAX_RESULT_BYTES - len(suffix)].decode(errors="ignore")
        content += suffix.decode()
    if error is not None:
        error_bytes = error.encode()
        if len(error_bytes) > MAX_RESULT_BYTES:
            suffix = b" [truncated]"
            error = error_bytes[: MAX_RESULT_BYTES - len(suffix)].decode(errors="ignore")
            error += suffix.decode()
    return {
        "type": "result",
        "request_id": request.request_id,
        "generation": request.generation,
        "success": success,
        "content": content,
        "error": error,
    }
