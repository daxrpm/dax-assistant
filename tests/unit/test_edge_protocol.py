from __future__ import annotations

import pytest

from dax.edge.protocol import (
    MAX_RESULT_BYTES,
    hello_frame,
    parse_execute,
    parse_ready,
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
