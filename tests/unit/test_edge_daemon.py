from __future__ import annotations

import asyncio
import json
import threading
import time

import numpy as np
import pytest

from dax.core.models import ToolCall, ToolResult
from dax.edge import daemon as daemon_module
from dax.edge.credentials import NodeCredentials
from dax.edge.daemon import (
    EdgeDaemon,
    LocalTTSExecutor,
    SystemExecutor,
    WebSocketConnection,
    available_local_tts_engines,
    backoff_delay,
)
from dax.edge.protocol import ExecuteRequest, SynthesizeRequest


@pytest.mark.parametrize(
    ("attempt", "random_value", "expected"),
    [(0, 0.5, 0.5), (3, 0.5, 4.0), (20, 1.0, 60.0)],
)
def test_backoff_is_exponential_jittered_and_capped(
    attempt: int, random_value: float, expected: float
) -> None:
    assert backoff_delay(attempt, random_value=random_value) == expected


def test_tts_features_require_local_models(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(daemon_module.importlib.util, "find_spec", lambda _name: object())
    assert available_local_tts_engines(str(tmp_path)) == []

    piper = tmp_path / "piper"
    piper.mkdir()
    (piper / "es.onnx").write_bytes(b"model")
    (piper / "es.onnx.json").write_text("{}", encoding="utf-8")
    assert available_local_tts_engines(str(tmp_path)) == ["piper"]

    kokoro = tmp_path / "kokoro"
    kokoro.mkdir()
    (kokoro / "kokoro-v1.0.onnx").write_bytes(b"model")
    (kokoro / "voices-v1.0.bin").write_bytes(b"voices")
    assert available_local_tts_engines(str(tmp_path)) == ["kokoro", "piper"]


class _FakeExecutor:
    def __init__(self) -> None:
        self.stopped = False

    async def start(self) -> list[dict[str, object]]:
        return [{"name": "system_info", "server_name": "dax-system"}]

    async def stop(self) -> None:
        self.stopped = True


class _FakeConnection:
    def __init__(self, *incoming: str) -> None:
        self.sent: list[str] = []
        self.closed = False
        self.incoming = incoming

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True

    async def _iterate(self):
        for message in self.incoming:
            yield message

    def __aiter__(self):
        return self._iterate()


@pytest.mark.asyncio
async def test_daemon_refreshes_token_and_reconnects_with_backoff() -> None:
    connections: list[_FakeConnection] = []
    headers: list[dict[str, str]] = []
    sleeps: list[float] = []
    executor = _FakeExecutor()

    async def connect_fake(url: str, request_headers: dict[str, str]) -> WebSocketConnection:
        assert url == "wss://dax.example/ws/capabilities"
        headers.append(request_headers)
        connection = _FakeConnection()
        connections.append(connection)
        return connection

    async def sleep_fake(delay: float) -> None:
        sleeps.append(delay)

    class TestDaemon(EdgeDaemon):
        token_count = 0
        connection_count = 0

        async def _issue_token(self) -> tuple[str, int]:
            self.token_count += 1
            return f"token-{self.token_count}", 300

        async def _serve_until_stop(
            self, connection: WebSocketConnection, expires: int
        ) -> None:
            self.connection_count += 1
            if self.connection_count == 2:
                self.stop()

    daemon = TestDaemon(
        NodeCredentials("https://dax.example", "device", "secret", "laptop"),
        executor=executor,  # type: ignore[arg-type]
        connect_factory=connect_fake,
        sleep=sleep_fake,
    )
    await daemon.run()

    assert daemon.token_count == 2
    assert headers == [
        {"Authorization": "Bearer token-1"},
        {"Authorization": "Bearer token-2"},
    ]
    assert len(sleeps) == 1
    assert 0 <= sleeps[0] <= 1
    assert executor.stopped
    assert all(connection.closed for connection in connections)


@pytest.mark.asyncio
async def test_server_heartbeat_gets_an_application_response() -> None:
    connection = _FakeConnection(json.dumps({"type": "heartbeat"}))

    async def sleep_forever(_delay: float) -> None:
        await asyncio.Event().wait()

    daemon = EdgeDaemon(
        NodeCredentials("https://dax.example", "device", "secret", "laptop"),
        executor=_FakeExecutor(),  # type: ignore[arg-type]
        sleep=sleep_forever,
    )
    await daemon._serve(connection, expires=300)

    assert json.loads(connection.sent[0]) == {"type": "heartbeat"}


@pytest.mark.asyncio
async def test_edge_shell_rejects_approved_binary_outside_node_allowlist() -> None:
    class Client:
        def __init__(self) -> None:
            self.commands: list[str] = []

        async def execute(self, call: ToolCall) -> ToolResult:
            self.commands.append(call.arguments["command"])
            return ToolResult(call.id, "ok", False)

    executor = SystemExecutor.__new__(SystemExecutor)
    executor._tools = {"shell_run": {"name": "shell_run"}}
    executor._shell_allow = {"ls"}
    executor._shell_disabled = False
    client = Client()
    executor._client = client  # type: ignore[assignment]

    request = ExecuteRequest(
        "unapproved", 1, "shell_run", {"command": "approved-tool --version"}, 5
    )
    with pytest.raises(ValueError, match="allowlist"):
        await executor.execute(request)
    assert client.commands == []

    rejected = ExecuteRequest(
        "rejected", 1, "shell_run", {"command": "ls; id"}, 5
    )
    with pytest.raises(ValueError, match="metacharacters"):
        await executor.execute(rejected)
    assert client.commands == []


@pytest.mark.asyncio
async def test_a_user_approved_command_runs_even_outside_the_allowlist() -> None:
    """Clicking Allow has to actually run the thing.

    The node keeps its own allowlist and cannot see the confirmation modal, so
    it used to refuse whatever the user had just approved: the modal appeared,
    Allow did nothing, and the turn failed with no explanation.
    """

    class Client:
        def __init__(self) -> None:
            self.commands: list[str] = []

        async def execute(self, call: ToolCall) -> ToolResult:
            self.commands.append(call.arguments["command"])
            return ToolResult(call.id, "ok", False)

    executor = SystemExecutor.__new__(SystemExecutor)
    executor._tools = {"shell_run": {"name": "shell_run"}}
    executor._shell_allow = {"ls"}
    executor._shell_disabled = False
    client = Client()
    executor._client = client  # type: ignore[assignment]

    approved = ExecuteRequest(
        "approved",
        1,
        "shell_run",
        {"command": "flatpak run com.spotify.Client"},
        5,
        approved=True,
    )
    assert await executor.execute(approved) == "ok"
    assert client.commands == ["flatpak run com.spotify.Client"]

    # Injection safety is never waived by approval.
    with pytest.raises(ValueError, match="metacharacters"):
        await executor.execute(
            ExecuteRequest("x", 1, "shell_run", {"command": "ls; id"}, 5, approved=True)
        )
    assert client.commands == ["flatpak run com.spotify.Client"]


@pytest.mark.asyncio
async def test_an_empty_allowlist_disables_shell_even_for_approved_commands() -> None:
    """The local kill switch outranks approval — it means "no shell here"."""

    class Client:
        def __init__(self) -> None:
            self.commands: list[str] = []

        async def execute(self, call: ToolCall) -> ToolResult:
            self.commands.append(call.arguments["command"])
            return ToolResult(call.id, "ok", False)

    executor = SystemExecutor.__new__(SystemExecutor)
    executor._tools = {"shell_run": {"name": "shell_run"}}
    executor._shell_allow = set()
    executor._shell_disabled = True
    client = Client()
    executor._client = client  # type: ignore[assignment]

    with pytest.raises(ValueError, match="disabled"):
        await executor.execute(
            ExecuteRequest("a", 1, "shell_run", {"command": "ls"}, 5, approved=True)
        )
    assert client.commands == []


def test_edge_forwards_explicitly_empty_shell_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    class Client:
        def __init__(
            self,
            _name: str,
            *,
            command: str,
            args: list[str],
            env: dict[str, str],
        ) -> None:
            del command, args
            captured.update(env)

    monkeypatch.setenv("DAX_SYSTEM_SHELL_ALLOW", "")
    monkeypatch.setattr(daemon_module, "MCPClient", Client)

    executor = SystemExecutor()

    assert executor._shell_allow == set()
    assert executor._shell_disabled is True
    # The binary cap is no longer handed to the subprocess: it cannot vary per
    # call, so it would refuse the very commands the user approved on screen.
    # Enforcement moved to `execute`, which is the only layer that can see the
    # approval. Injection safety in the subprocess is unaffected.
    assert "DAX_SYSTEM_SHELL_ALLOW" not in captured


@pytest.mark.asyncio
async def test_local_tts_is_resident_serialized_and_off_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Engine:
        sample_rate = 24_000
        engine_name = "kokoro"

        def __init__(self) -> None:
            self.starts = 0
            self.active = 0
            self.max_active = 0
            self.threads: set[int] = set()

        def start(self) -> None:
            self.starts += 1

        def stop(self) -> None:
            pass

        def synthesize(self, _text: str, language: str = "en") -> np.ndarray:
            del language
            self.threads.add(threading.get_ident())
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            time.sleep(0.02)
            self.active -= 1
            return np.arange(8, dtype=np.int16)

        def voice_name(self, _language: str) -> str:
            return "local-voice"

    engine = Engine()
    monkeypatch.setattr("dax.voice.tts.build_tts", lambda *_: engine)
    executor = LocalTTSExecutor()
    executor.engines = ["kokoro"]
    request = SynthesizeRequest(
        "tts",
        1,
        "hello",
        "en",
        "kokoro",
        {
            "kokoro_voice_es": "es",
            "kokoro_voice_en": "en",
            "piper_voice_es": "piper-es",
            "piper_voice_en": "piper-en",
            "speed": 1.0,
        },
    )
    event_loop_thread = threading.get_ident()

    results = await asyncio.gather(
        executor.synthesize(request), executor.synthesize(request)
    )

    assert engine.starts == 1
    assert engine.max_active == 1
    assert engine.threads and event_loop_thread not in engine.threads
    assert all(result[0] == np.arange(8, dtype="<i2").tobytes() for result in results)


@pytest.mark.asyncio
async def test_cancelled_tts_keeps_admission_until_worker_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    release = threading.Event()

    class Engine:
        sample_rate = 24_000
        engine_name = "piper"

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def synthesize(self, _text: str, language: str = "en") -> np.ndarray:
            del language
            started.set()
            release.wait(timeout=2)
            return np.arange(4, dtype=np.int16)

        def voice_name(self, _language: str) -> str:
            return "voice"

    monkeypatch.setattr("dax.voice.tts.build_tts", lambda *_: Engine())
    executor = LocalTTSExecutor()
    executor.engines = ["piper"]
    request = SynthesizeRequest(
        "tts",
        1,
        "hello",
        "en",
        "piper",
        {"piper_voice_es": "es", "piper_voice_en": "en"},
    )
    first = asyncio.create_task(executor.synthesize(request))
    await asyncio.to_thread(started.wait, 1)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    second = asyncio.create_task(executor.synthesize(request))
    await asyncio.sleep(0.02)
    assert not second.done()
    release.set()
    await second
    await executor.stop()


@pytest.mark.asyncio
async def test_daemon_uses_dedicated_tts_chunks_and_sanitizes_failures() -> None:
    class TTS:
        def __init__(self) -> None:
            self.engines = ["piper"]

        async def synthesize(self, _request: SynthesizeRequest):
            return b"\x00\x00\x01\x00", 22_050, "piper", "voice", "fingerprint"

        async def stop(self) -> None:
            pass

    daemon = EdgeDaemon(
        NodeCredentials("https://dax.example", "device", "secret", "laptop"),
        executor=_FakeExecutor(),  # type: ignore[arg-type]
        tts_executor=TTS(),  # type: ignore[arg-type]
    )
    connection = _FakeConnection()
    request = SynthesizeRequest(
        "tts",
        3,
        "hello",
        "en",
        "piper",
        {"piper_voice_es": "es", "piper_voice_en": "en"},
    )

    await daemon._synthesize_and_send(connection, request)

    frames = [json.loads(frame) for frame in connection.sent]
    assert [frame["type"] for frame in frames] == [
        "synthesize_chunk",
        "synthesize_final",
    ]
    assert frames[-1]["success"] is True
    assert frames[-1]["size"] == 4
    assert not any(frame["type"] == "result" for frame in frames)

    async def fail(_request: SynthesizeRequest):
        raise RuntimeError("/home/user/model.onnx OPENAI_API_KEY=secret")

    daemon._tts_executor.synthesize = fail  # type: ignore[method-assign]
    connection.sent.clear()
    await daemon._synthesize_and_send(connection, request)
    failure = json.loads(connection.sent[-1])
    assert failure["error"] == "Local TTS synthesis failed"
    assert "secret" not in json.dumps(failure)


@pytest.mark.asyncio
async def test_wake_synthesis_plays_before_acknowledging_success() -> None:
    order: list[str] = []

    class TTS:
        def __init__(self) -> None:
            self.engines = ["piper"]

        async def synthesize(self, _request: SynthesizeRequest):
            order.append("synthesize")
            return b"\x00\x00\x01\x00", 22_050, "piper", "voice", "fingerprint"

        async def stop(self) -> None:
            pass

    class Player:
        def play(self, audio: np.ndarray, sample_rate: int) -> None:
            assert audio.dtype == np.dtype("<i2")
            assert sample_rate == 22_050
            order.append("play")

    daemon = EdgeDaemon(
        NodeCredentials("https://dax.example", "device", "secret", "laptop"),
        executor=_FakeExecutor(),  # type: ignore[arg-type]
        tts_executor=TTS(),  # type: ignore[arg-type]
        audio_player=Player(),  # type: ignore[arg-type]
    )
    connection = _FakeConnection()
    request = SynthesizeRequest(
        "tts",
        3,
        "respuesta",
        "es",
        "piper",
        {"piper_voice_es": "es", "piper_voice_en": "en"},
        playback=True,
    )

    await daemon._synthesize_and_send(connection, request)

    order.append("ack")
    final = json.loads(connection.sent[-1])
    assert order == ["synthesize", "play", "ack"]
    assert final["success"] is True
