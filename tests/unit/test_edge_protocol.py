from __future__ import annotations

import pytest

from dax.edge.protocol import (
    MAX_RESULT_BYTES,
    MAX_TTS_CONFIG_BYTES,
    hello_frame,
    local_tts_features_frame,
    parse_execute,
    parse_ready,
    parse_synthesize,
    result_frame,
)


def test_hello_advertises_protocol_and_inventory() -> None:
    tools = [{"name": "system_info", "server_name": "dax-system"}]
    assert hello_frame("work-laptop", tools) == {
        "type": "hello",
        "version": 1,
        "node_name": "work-laptop",
        "tools": tools,
        "endpoints": [],
    }


def test_hello_proposes_endpoints_when_a_session_server_is_listening() -> None:
    frame = hello_frame("work-laptop", [], ["192.168.1.30:8765"])

    assert frame["endpoints"] == ["192.168.1.30:8765"]


def test_local_tts_is_negotiated_only_after_backend_ready() -> None:
    hello = hello_frame("laptop", [])
    assert "features" not in hello
    assert local_tts_features_frame(
        {"type": "ready", "generation": 2, "features": {"local_tts": 1}},
        ["kokoro", "piper"],
    ) == {
        "type": "features",
        "generation": 2,
        "local_tts": {"engines": ["kokoro", "piper"]},
    }
    assert local_tts_features_frame(
        {"type": "ready", "generation": 2}, ["kokoro"]
    ) is None


def test_ready_yields_the_session_signing_key() -> None:
    assert parse_ready({"type": "ready", "public_key": "abc"}) == "abc"


def test_ready_without_a_key_yields_none() -> None:
    """An older backend cannot vouch, so the node must refuse direct sessions."""
    assert parse_ready({"type": "ready", "version": 1}) is None
    assert parse_ready({"type": "ready", "public_key": ""}) is None
    assert parse_ready({"type": "ready", "public_key": 42}) is None
    assert parse_ready({"type": "ready", "public_key": "x" * 200}) is None


def test_a_non_ready_frame_yields_no_key() -> None:
    assert parse_ready({"type": "execute", "public_key": "abc"}) is None


def test_execute_and_result_preserve_correlation() -> None:
    request = parse_execute(
        {
            "type": "execute",
            "request_id": "req-1",
            "generation": 7,
            "tool_name": "system_info",
            "arguments": {},
            "timeout_seconds": 10,
        }
    )
    assert result_frame(request, success=True, content="ok") == {
        "type": "result",
        "request_id": "req-1",
        "generation": 7,
        "success": True,
        "content": "ok",
        "error": None,
    }


def test_synthesize_request_is_strict_and_bounded() -> None:
    request = parse_synthesize(
        {
            "type": "synthesize",
            "request_id": "tts-1",
            "generation": 2,
            "text": " Hola ",
            "language": "es",
            "engine": "kokoro",
            "config": {
                "kokoro_voice_es": "em_alex",
                "kokoro_voice_en": "af_heart",
                "piper_voice_es": "es_ES",
                "piper_voice_en": "en_US",
                "speed": 1.0,
            },
        }
    )

    assert request.text == "Hola"
    assert request.engine == "kokoro"
    assert request.playback is False
    playback = parse_synthesize(
        {
            "type": "synthesize",
            "request_id": "tts-play",
            "generation": 2,
            "text": "Hola",
            "language": "es",
            "engine": "piper",
            "config": {"piper_voice_es": "es_ES", "piper_voice_en": "en_US"},
            "playback": True,
        }
    )
    assert playback.playback is True
    with pytest.raises(ValueError, match="playback"):
        parse_synthesize(
            {
                "type": "synthesize",
                "request_id": "tts-bad-play",
                "generation": 2,
                "text": "Hola",
                "language": "es",
                "engine": "piper",
                "config": {"piper_voice_es": "es_ES", "piper_voice_en": "en_US"},
                "playback": "yes",
            }
        )
    with pytest.raises(ValueError, match="fields"):
        parse_synthesize(
            {
                "type": "synthesize",
                "request_id": "tts-2",
                "generation": 2,
                "text": "Hola",
                "language": "es",
                "engine": "piper",
                "config": {
                    "piper_voice_es": "es_ES",
                    "piper_voice_en": "en_US",
                    "api_key": "must-not-cross",
                },
            }
        )
    with pytest.raises(ValueError, match="exceeds"):
        parse_synthesize(
            {
                "type": "synthesize",
                "request_id": "tts-3",
                "generation": 2,
                "text": "Hola",
                "language": "es",
                "engine": "piper",
                "config": {
                    "piper_voice_es": "x" * MAX_TTS_CONFIG_BYTES,
                    "piper_voice_en": "en",
                },
            }
        )


def test_timeout_is_capped() -> None:
    request = parse_execute(
        {
            "type": "execute",
            "request_id": "req-1",
            "generation": 1,
            "tool_name": "system_info",
            "arguments": {},
            "timeout_seconds": 999,
        }
    )
    assert request.timeout_seconds == 60


def test_result_content_is_bounded() -> None:
    request = parse_execute(
        {
            "type": "execute",
            "request_id": "req-1",
            "generation": 1,
            "tool_name": "fs_read",
            "arguments": {"path": "/tmp/file"},
            "timeout_seconds": 10,
        }
    )
    frame = result_frame(request, success=True, content="x" * (MAX_RESULT_BYTES + 100))
    assert len(str(frame["content"]).encode()) <= MAX_RESULT_BYTES
    assert str(frame["content"]).endswith("[truncated]")


@pytest.mark.parametrize("arguments", [None, [], "bad"])
def test_execute_requires_object_arguments(arguments: object) -> None:
    with pytest.raises(ValueError, match="arguments"):
        parse_execute(
            {
                "type": "execute",
                "request_id": "req-1",
                "generation": 1,
                "tool_name": "system_info",
                "arguments": arguments,
                "timeout_seconds": 10,
            }
        )
