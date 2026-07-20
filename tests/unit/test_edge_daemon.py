from __future__ import annotations

import asyncio
import json

import pytest

from dax.core.models import ToolResult
from dax.edge.credentials import NodeCredentials
from dax.edge.daemon import EdgeDaemon, SystemExecutor, WebSocketConnection, backoff_delay
from dax.edge.protocol import ExecuteRequest


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
async def test_edge_shell_accepts_server_approved_binary_but_rejects_metacharacters() -> None:
    class Client:
        def __init__(self) -> None:
            self.commands: list[str] = []

        async def execute(self, call):
            self.commands.append(call.arguments["command"])
            return ToolResult(call.id, "ok", False)

    executor = SystemExecutor.__new__(SystemExecutor)
    executor._tools = {"shell_run": {"name": "shell_run"}}
    client = Client()
    executor._client = client

    request = ExecuteRequest(
        "approved", 1, "shell_run", {"command": "approved-tool --version"}, 5
    )
    assert await executor.execute(request) == "ok"
    assert client.commands == ["approved-tool --version"]

    rejected = ExecuteRequest(
        "rejected", 1, "shell_run", {"command": "approved-tool; id"}, 5
    )
    with pytest.raises(ValueError, match="metacharacters"):
        await executor.execute(rejected)
    assert client.commands == ["approved-tool --version"]
