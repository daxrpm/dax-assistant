"""Capability-node protocol v1 frame validation and construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 256 * 1024
MAX_RESULT_BYTES = 64 * 1024
MAX_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class ExecuteRequest:
    request_id: str
    generation: int
    tool_name: str
    arguments: dict[str, object]
    timeout_seconds: float


def hello_frame(node_name: str, tools: list[dict[str, Any]]) -> dict[str, object]:
    return {
        "type": "hello",
        "version": PROTOCOL_VERSION,
        "node_name": node_name,
        "tools": tools,
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
    return ExecuteRequest(request_id, generation, tool_name, arguments, bounded_timeout)


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
