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
    client = Client()
    executor._client = client  # type: ignore[assignment]

    request = ExecuteRequest(
        "approved", 1, "shell_run", {"command": "approved-tool --version"}, 5
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
    assert captured["DAX_SYSTEM_SHELL_ALLOW"] == ""


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
