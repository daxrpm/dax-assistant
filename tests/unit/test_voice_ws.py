"""Tests for the /ws/voice event stream.

The subscriber lifecycle matters more than it looks: ``has_subscribers`` gates
all DSP work in the pipeline, so a leaked subscription means the backend
computes FFTs forever after a client walks away.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dax.core.config import DaxConfig
from dax.core.voice_events import VoiceEventHub
from dax.orchestrator.bus import MessageBus
from dax.web.auth import hash_password
from dax.web.server import create_app

PASSWORD = "correct horse battery staple"
SECRET = "x" * 40


def _make_app(*, auth_enabled: bool = True):
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


def test_connect_replays_last_state():
    """Connecting mid-conversation must not render as idle."""
    app, hub = _make_app()
    hub.emit_state("speaking", conversation_id="abc123")
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        frame = ws.receive_json()

    assert frame["data"]["state"] == "speaking"
    assert frame["data"]["conversation_id"] == "abc123"


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


def test_unsubscribe_runs_on_disconnect():
    """A leaked subscriber would keep the pipeline metering forever."""
    app, hub = _make_app()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/voice?token={_token(app)}") as ws:
        ws.receive_json()
        assert hub.has_subscribers

    assert not hub.has_subscribers
