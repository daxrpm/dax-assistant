from __future__ import annotations

import pytest

from dax.edge.protocol import MAX_RESULT_BYTES, hello_frame, parse_execute, result_frame


def test_hello_advertises_protocol_and_inventory() -> None:
    tools = [{"name": "system_info", "server_name": "dax-system"}]
    assert hello_frame("work-laptop", tools) == {
        "type": "hello",
        "version": 1,
        "node_name": "work-laptop",
        "tools": tools,
    }


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
