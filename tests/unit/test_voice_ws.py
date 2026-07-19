"""Tests for the /ws/voice event stream.

The subscriber lifecycle matters more than it looks: ``has_subscribers`` gates
all DSP work in the pipeline, so a leaked subscription means the backend
computes FFTs forever after a client walks away.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from dax.core.config import DaxConfig
from dax.core.voice_events import VoiceEventHub
from dax.orchestrator.bus import MessageBus
from dax.web.auth import hash_password
from dax.web.server import create_app

PASSWORD = "correct horse battery staple"
SECRET = "x" * 40


class FakePipeline:
    def __init__(self) -> None:
        self.source = None
        self.cancelled = 0
        self.output_owner: str | None = None

    def select_audio_source(self, source) -> None:
        self.source = source

    def set_output_owner(self, owner: str | None) -> None:
        self.output_owner = owner

    def push_to_talk_press(self) -> str:
        return "listening"

    def push_to_talk_release(self) -> str:
        return "processing"

    def push_to_talk_cancel(self) -> str:
        self.cancelled += 1
        return "idle"


def _make_app(*, auth_enabled: bool = True, pipeline=None):
    """Build an app with a voice hub attached, mirroring DaxApp wiring."""
    bus = MessageBus()
    bus.start()
    config = DaxConfig(
        security={
            "password_hash": hash_password(PASSWORD) if auth_enabled else "",
            "session_secret": SECRET,
        }
    )
    app = create_app(config=config, bus=bus)
    hub = VoiceEventHub()
    app.state.voice_events = hub
    if pipeline is not None:
        app.state.voice_pipeline = pipeline
    return app, hub


def _token(app) -> str:
    return app.state.auth.issue_token()


def test_unauthenticated_connection_is_rejected():
    app, hub = _make_app()
    client = TestClient(app)

    # Starlette surfaces the 1008 policy-violation close as an exception.
    with pytest.raises(Exception), client.websocket_connect("/ws/voice"):  # noqa: B017
        pass

    assert not hub.has_subscribers


def test_connect_replays_synthetic_idle_when_no_state_yet():
    """A client must get a definite starting state, not silence."""
    app, _hub = _make_app()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        frame = ws.receive_json()

    assert frame["type"] == "state"
    assert frame["data"]["state"] == "idle"
    assert frame["data"]["session_expires_at"] is None


def test_connect_replays_last_state():
    """Connecting mid-conversation must not render as idle."""
    app, hub = _make_app()
    hub.emit_state("speaking", conversation_id="abc123")
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        frame = ws.receive_json()

    assert frame["data"]["state"] == "speaking"
    assert frame["data"]["conversation_id"] == "abc123"


def test_connect_replays_real_session_expiration():
    app, hub = _make_app()
    hub.emit_state("listening", conversation_id="abc123", session_expires_at=1_800_000_600.0)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        frame = ws.receive_json()

    assert frame["data"]["session_expires_at"] == 1_800_000_600.0


def test_events_are_streamed_to_a_subscriber():
    app, hub = _make_app()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()  # the replayed state frame
        hub.emit_transcript("prende la luz", "es", final=True)
        frame = ws.receive_json()

    assert frame["type"] == "transcript"
    assert frame["data"]["text"] == "prende la luz"
    assert frame["data"]["language"] == "es"


def test_current_speech_sentence_is_streamed_to_a_subscriber():
    app, hub = _make_app()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        hub.emit_speech("Ahora mismo está sonando.", "es")
        frame = ws.receive_json()

    assert frame == {
        "type": "speech",
        "data": {"text": "Ahora mismo está sonando.", "language": "es"},
        "timestamp": frame["timestamp"],
    }


def test_unsubscribe_runs_on_disconnect():
    """A leaked subscriber would keep the pipeline metering forever."""
    app, hub = _make_app()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        assert hub.has_subscribers

    for _ in range(20):
        if not hub.has_subscribers:
            break
        time.sleep(0.01)
    assert not hub.has_subscribers


def test_remote_audio_happy_path_switches_source_and_processes_on_stop():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json({
            "type": "remote_audio.acquire",
            "format": {"sample_rate": 16_000, "channels": 1, "sample_format": "pcm_s16le"},
        })
        assert ws.receive_json()["type"] == "remote_audio.acquired"
        ws.send_json({"type": "remote_audio.start"})
        assert ws.receive_json()["type"] == "remote_audio.started"
        assert pipeline.source is not None
        ws.send_bytes(b"\x01\x00" * 160)
        ws.send_json({"type": "remote_audio.stop"})
        stopped = ws.receive_json()
        assert stopped == {"type": "remote_audio.stopped", "data": {"state": "processing"}}
        assert pipeline.source is None


def test_only_one_authenticated_connection_can_own_remote_audio():
    app, _hub = _make_app(pipeline=FakePipeline())
    client = TestClient(app)
    acquire = {
        "type": "remote_audio.acquire",
        "format": {"sample_rate": 16_000, "channels": 1, "sample_format": "pcm_s16le"},
    }
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as first:
        first.receive_json()
        first.send_json(acquire)
        assert first.receive_json()["type"] == "remote_audio.acquired"
        with client.websocket_connect(f"/ws/voice?token={_token(app)}") as second:
            second.receive_json()
            second.send_json(acquire)
            error = second.receive_json()
            assert error["data"]["code"] == "remote_audio_busy"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"type": "remote_audio.start"}, "invalid_order"),
        ({"type": "remote_audio.acquire", "format": {}}, "unsupported_format"),
        ({"hello": "world"}, "malformed_control"),
    ],
)
def test_invalid_control_is_rejected(payload, code):
    app, _hub = _make_app(pipeline=FakePipeline())
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(payload)
        assert ws.receive_json()["data"]["code"] == code


def test_oversize_pcm_is_rejected_and_disconnect_cleans_up():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json({
            "type": "remote_audio.acquire",
            "format": {"sample_rate": 16_000, "channels": 1, "sample_format": "pcm_s16le"},
        })
        ws.receive_json()
        ws.send_json({"type": "remote_audio.start"})
        ws.receive_json()
        ws.send_bytes(b"\x00" * 3_202)
        assert ws.receive_json()["data"]["code"] == "invalid_pcm"
    assert pipeline.cancelled == 1
    assert pipeline.source is None


def test_duration_limit_is_enforced_before_buffering(monkeypatch):
    from dax.web.routes import voice_ws

    monkeypatch.setattr(voice_ws, "_REMOTE_MAX_BYTES", 2)
    app, _hub = _make_app(pipeline=FakePipeline())
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json({
            "type": "remote_audio.acquire",
            "format": {"sample_rate": 16_000, "channels": 1, "sample_format": "pcm_s16le"},
        })
        ws.receive_json()
        ws.send_json({"type": "remote_audio.start"})
        ws.receive_json()
        ws.send_bytes(b"\x00\x00\x00\x00")
        assert ws.receive_json()["data"]["code"] == "duration_limit"


def test_owner_lease_is_released_after_disconnect():
    app, _hub = _make_app(pipeline=FakePipeline())
    client = TestClient(app)
    acquire = {
        "type": "remote_audio.acquire",
        "format": {"sample_rate": 16_000, "channels": 1, "sample_format": "pcm_s16le"},
    }
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(acquire)
        assert ws.receive_json()["type"] == "remote_audio.acquired"
    for _ in range(20):
        if app.state.remote_voice_lease.owner is None:
            break
        time.sleep(0.01)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(acquire)
        assert ws.receive_json()["type"] == "remote_audio.acquired"


# -- Client-owned output ------------------------------------------------------
#
# A phone is not in the same room as the backend, so answering on the backend's
# speakers answers nobody. These cover the negotiation and, more importantly,
# that a client which drops while owning output cannot leave the host mute.

_ACQUIRE_FORMAT = {"sample_rate": 16_000, "channels": 1, "sample_format": "pcm_s16le"}


def _acquire(output_mode: str | None = None) -> dict:
    frame: dict = {"type": "remote_audio.acquire", "format": dict(_ACQUIRE_FORMAT)}
    if output_mode is not None:
        frame["output"] = {"mode": output_mode}
    return frame


def test_output_defaults_to_the_server_host():
    """Omitting `output` must preserve the pre-existing behaviour exactly."""
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire())
        acquired = ws.receive_json()

        assert acquired["data"]["output"]["mode"] == "server"
        assert pipeline.output_owner is None


def test_client_can_claim_text_output():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_text"))
        acquired = ws.receive_json()

        assert acquired["data"]["output"]["mode"] == "client_text"
        assert acquired["data"]["output"]["client_audio_supported"] is False
        assert "client_text" in acquired["data"]["output"]["supported_modes"]
        assert pipeline.output_owner is not None


def test_releasing_the_lease_returns_output_to_the_host():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_text"))
        ws.receive_json()
        assert pipeline.output_owner is not None

        ws.send_json({"type": "remote_audio.release"})
        assert ws.receive_json()["type"] == "remote_audio.released"

        assert pipeline.output_owner is None


def test_disconnect_while_owning_output_restores_the_host():
    """The failure that would otherwise mute the backend permanently."""
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_text"))
        ws.receive_json()
        assert pipeline.output_owner is not None

    assert pipeline.output_owner is None


def test_unsupported_output_mode_is_rejected_not_downgraded():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_audio"))
        error = ws.receive_json()

        assert error["type"] == "remote_audio.error"
        assert error["data"]["code"] == "unsupported_output_mode"
        assert pipeline.output_owner is None


def test_malformed_output_object_is_rejected():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json({
            "type": "remote_audio.acquire",
            "format": dict(_ACQUIRE_FORMAT),
            "output": "client_text",
        })
        error = ws.receive_json()

        assert error["data"]["code"] == "malformed_control"
