"""Tests for the /ws/voice event stream.

The subscriber lifecycle matters more than it looks: ``has_subscribers`` gates
all DSP work in the pipeline, so a leaked subscription means the backend
computes FFTs forever after a client walks away.
"""

from __future__ import annotations

import time

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from dax.core.config import DaxConfig
from dax.core.voice_events import VoiceEvent, VoiceEventHub, VoiceEventType
from dax.orchestrator.approval import ApprovalManager
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
        self.input_owner: str | None = None
        self.owner_generation = 0
        self.state = "idle"
        self.events: VoiceEventHub | None = None

    def select_audio_source(self, source) -> None:
        self.source = source

    def set_output_owner(self, owner: str | None) -> None:
        self.output_owner = owner

    def acquire_remote_owner(self, owner: str) -> int:
        if self.state != "idle":
            raise RuntimeError("Voice pipeline is busy")
        self.owner_generation += 1
        self.input_owner = owner
        self.output_owner = owner
        if self.events is not None:
            self.owner_generation = self.events.set_event_owner(owner)
        return self.owner_generation

    def release_remote_owner(self, owner: str) -> None:
        if self.input_owner == owner:
            if self.state != "idle":
                raise RuntimeError("Voice pipeline is busy")
            self.source = None
            self.input_owner = None
            self.output_owner = None
            if self.events is not None:
                self.owner_generation = self.events.set_event_owner(None)

    def push_to_talk_press(self) -> str:
        return "listening"

    def push_to_talk_release(self) -> str:
        return "processing"

    def push_to_talk_cancel(self) -> str:
        self.cancelled += 1
        return "idle"

    def interrupt_remote_turn(self) -> str:
        if self.output_owner is None:
            raise RuntimeError("Remote output is not owned")
        self.cancelled += 1
        self.state = "idle"
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
    app.state.approval = ApprovalManager(timeout_seconds=5)
    if pipeline is not None:
        app.state.voice_pipeline = pipeline
        pipeline.events = hub
    return app, hub


def _token(app) -> str:
    return app.state.auth.issue_token()


def test_unauthenticated_connection_is_rejected():
    """Rejected with a close code the client can read, not a failed handshake.

    Closing before accepting would make the server answer the handshake with
    HTTP 403, which a browser reports to the page as 1006 — indistinguishable
    from a dropped network, so clients reconnect forever instead of asking the
    user to sign in. The handshake therefore completes and 1008 arrives as 1008.
    """
    app, hub = _make_app()
    client = TestClient(app)

    with (
        client.websocket_connect("/ws/voice") as websocket,
        pytest.raises(WebSocketDisconnect) as rejection,
    ):
        websocket.receive_json()

    assert rejection.value.code == 1008
    assert not hub.has_subscribers


def test_an_expired_chat_session_closes_with_1008_not_a_dead_handshake():
    """The regression that made the desktop app reconnect in a loop forever.

    An expired session token used to fail the handshake outright, so the client
    saw 1006, decided the network had blipped, and retried every two seconds
    for as long as the app stayed open — never once telling the user to sign in.
    """
    app, _hub = _make_app()
    client = TestClient(app)

    with (
        client.websocket_connect("/ws/chat") as websocket,
        pytest.raises(WebSocketDisconnect) as rejection,
    ):
        websocket.receive_json()

    assert rejection.value.code == 1008


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


def test_client_text_turn_completion_is_streamed_after_sentences():
    app, hub = _make_app()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        hub.emit_speech("Primera.", "es")
        hub.emit_speech("Segunda.", "es")
        hub.emit_turn_completed("7")

        assert ws.receive_json()["type"] == "speech"
        assert ws.receive_json()["type"] == "speech"
        completed = ws.receive_json()

    assert completed["type"] == "turn_complete"
    assert completed["data"] == {"voice_turn": "7"}


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
        # The remote source remains selected until the pipeline reaches IDLE;
        # restoring the host microphone while processing would break isolation.
        assert pipeline.source is not None


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


def test_remote_lease_events_are_delivered_only_to_owner_and_stale_events_are_dropped():
    pipeline = FakePipeline()
    app, hub = _make_app(pipeline=pipeline)
    client = TestClient(app)

    with (
        client.websocket_connect(f"/ws/voice?token={_token(app)}") as owner,
        client.websocket_connect(f"/ws/voice?token={_token(app)}") as observer,
    ):
        owner.receive_json()
        observer.receive_json()
        owner.send_json(_acquire("client_text"))
        assert owner.receive_json()["type"] == "remote_audio.acquired"

        stale = VoiceEvent(
            VoiceEventType.TRANSCRIPT,
            {"text": "stale local", "language": "en", "final": True},
            owner=None,
            generation=0,
        )
        assert hub._loop is not None
        hub._loop.call_soon_threadsafe(hub._deliver, stale)

        hub.emit_transcript("owner only", "en")
        assert owner.receive_json()["data"]["text"] == "owner only"

        owner.send_json({"type": "remote_audio.release"})
        assert owner.receive_json()["type"] == "remote_audio.released"
        hub.emit_transcript("local again", "en")
        assert observer.receive_json()["data"]["text"] == "local again"


def test_stale_local_generation_is_dropped_after_remote_lease_turnover():
    pipeline = FakePipeline()
    app, hub = _make_app(pipeline=pipeline)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        stale = VoiceEvent(
            VoiceEventType.TRANSCRIPT,
            {"text": "old local", "language": "en", "final": True},
            owner=None,
            generation=0,
        )
        ws.send_json(_acquire("client_text"))
        ws.receive_json()
        ws.send_json({"type": "remote_audio.release"})
        ws.receive_json()
        assert hub._loop is not None
        hub._loop.call_soon_threadsafe(hub._deliver, stale)
        hub.emit_transcript("current local", "en")

        assert ws.receive_json()["data"]["text"] == "current local"


def test_remote_lease_owns_input_output_and_cleanup_restores_host_only_when_idle():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_text"))
        ws.receive_json()
        assert pipeline.input_owner is not None
        assert pipeline.output_owner == pipeline.input_owner

        ws.send_json({"type": "remote_audio.release"})
        assert ws.receive_json()["type"] == "remote_audio.released"

    assert pipeline.input_owner is None
    assert pipeline.output_owner is None
    assert pipeline.source is None


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


def test_server_output_mode_still_suppresses_unattended_host_speakers():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire())
        acquired = ws.receive_json()

        assert acquired["data"]["output"]["mode"] == "server"
        assert pipeline.output_owner is not None


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


def test_disconnect_invalidates_pending_remote_reply_before_restoring_host():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_text"))
        ws.receive_json()
        pipeline.state = "speaking"

    assert pipeline.cancelled == 1
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


def test_voice_approval_is_accepted_only_once_from_output_owner():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    approval = app.state.approval
    seen: dict = {}

    async def approver(**payload):
        seen.update(payload)

    approval.set_voice_approver(approver)

    async def request():
        return await approval.request(
            tool_name="shell_run",
            server_name="dax-system",
            arguments={},
            channel="voice",
        )

    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_text"))
        ws.receive_json()
        import asyncio

        task = asyncio.run_coroutine_threadsafe(request(), app.state.voice_events._loop)
        for _ in range(50):
            if seen:
                break
            time.sleep(0.01)
        ws.send_json({
            "type": "voice.approval",
            "approval_id": seen["approval_id"],
            "decision": "approve",
        })
        assert task.result(timeout=1) == "approve"
        ws.send_json({
            "type": "voice.approval",
            "approval_id": seen["approval_id"],
            "decision": "approve",
        })
        assert ws.receive_json()["data"]["code"] == "invalid_approval"


def test_voice_owner_cannot_resolve_chat_approval():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    approval = app.state.approval
    seen: dict = {}

    async def notifier(payload):
        seen.update(payload)

    approval.set_notifier(notifier)

    async def request():
        return await approval.request(
            tool_name="shell_run",
            server_name="dax-system",
            arguments={},
            channel="web",
        )

    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_text"))
        ws.receive_json()
        import asyncio

        task = asyncio.run_coroutine_threadsafe(request(), app.state.voice_events._loop)
        for _ in range(50):
            if seen:
                break
            time.sleep(0.01)
        ws.send_json({
            "type": "voice.approval",
            "approval_id": seen["approval_id"],
            "decision": "approve",
        })
        assert ws.receive_json()["data"]["code"] == "invalid_approval"

        async def deny_on_owner_loop():
            return approval.resolve(seen["approval_id"], "deny")

        denied = asyncio.run_coroutine_threadsafe(
            deny_on_owner_loop(), app.state.voice_events._loop
        )
        assert denied.result(timeout=1)
        assert task.result(timeout=1) == "deny"


def test_remote_interrupt_reports_delivery_only_semantics():
    pipeline = FakePipeline()
    app, _hub = _make_app(pipeline=pipeline)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        ws.send_json(_acquire("client_text"))
        ws.receive_json()
        ws.send_json({"type": "remote_audio.interrupt"})
        frame = ws.receive_json()

    assert frame == {
        "type": "remote_audio.interrupted",
        "data": {"state": "idle", "agent_cancelled": False},
    }
