"""Bounded wire protocol and trusted bundled capability inventory."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 256 * 1024
MAX_TOOLS = 16
MAX_ENDPOINTS = 4
MAX_SCHEMA_BYTES = 32_000
MAX_ARGUMENT_BYTES = 64_000
MAX_RESULT_CHARS = 64 * 1024
MAX_TTS_CHUNK_BYTES = 48 * 1024
MAX_TTS_CHUNKS = 128
MAX_TTS_AUDIO_BYTES = 6 * 1024 * 1024

_STRING: dict[str, object] = {"type": "string"}
_INTEGER: dict[str, object] = {"type": "integer"}


def _object(
    properties: dict[str, dict[str, object]], required: list[str] | None = None
) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


# Nodes identify availability only. Schemas and descriptions always come from
# this server-owned table and intentionally mirror the bundled dax-system API.
BUNDLED_TOOLS: dict[str, tuple[str, dict[str, object]]] = {
    "system_info": ("Report OS, host, CPU count, and disk usage.", _object({})),
    "fs_list": ("List entries in a directory.", _object({"path": _STRING})),
    "fs_read": (
        "Read a UTF-8 text file.",
        _object({"path": _STRING, "max_bytes": _INTEGER}, ["path"]),
    ),
    "fs_search": (
        "Find files under a directory matching a glob pattern.",
        _object(
            {"root": _STRING, "pattern": _STRING, "max_results": _INTEGER},
            ["root", "pattern"],
        ),
    ),
    "clipboard_get": ("Read the system clipboard.", _object({})),
    "notify": (
        "Show a desktop notification.",
        _object({"title": _STRING, "message": _STRING}, ["title", "message"]),
    ),
    "fs_write": (
        "Write text to a file.",
        _object({"path": _STRING, "content": _STRING}, ["path", "content"]),
    ),
    "shell_run": (
        "Run a shell command under the server-side command gate.",
        _object({"command": _STRING}, ["command"]),
    ),
    "open_path": ("Open a file or directory.", _object({"path": _STRING}, ["path"])),
    "clipboard_set": (
        "Write text to the system clipboard.",
        _object({"text": _STRING}, ["text"]),
    ),
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InventoryTool(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    input_schema: dict[str, object] = Field(
        validation_alias=AliasChoices("input_schema", "inputSchema")
    )
    description: str = Field(default="", max_length=2048)
    server_name: str = Field(default="dax-system", max_length=64)


class LocalTTSFeature(StrictModel):
    engines: list[Literal["kokoro", "piper"]] = Field(min_length=1, max_length=2)

    @field_validator("engines")
    @classmethod
    def engines_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("local TTS engines must be unique")
        return value


class CapabilityFeatures(StrictModel):
    local_tts: LocalTTSFeature | None = None


class HelloFrame(StrictModel):
    type: Literal["hello"]
    version: Literal[1]
    node_name: str = Field(default="", max_length=64)
    tools: list[InventoryTool] = Field(max_length=MAX_TOOLS)
    # Where a client on the same network could reach this node directly. The
    # node proposes; `trusted_endpoints` decides. See below for why.
    endpoints: list[str] = Field(default_factory=list, max_length=MAX_ENDPOINTS)
    features: CapabilityFeatures = Field(default_factory=CapabilityFeatures)


class ResultFrame(StrictModel):
    type: Literal["result"]
    generation: int = Field(ge=1)
    request_id: str = Field(min_length=1, max_length=128)
    content: str = Field(max_length=MAX_RESULT_CHARS)
    success: bool
    error: str | None = Field(default=None, max_length=MAX_RESULT_CHARS)


class HeartbeatFrame(StrictModel):
    type: Literal["heartbeat"]


class FeaturesFrame(StrictModel):
    type: Literal["features"]
    generation: int = Field(ge=1)
    local_tts: LocalTTSFeature


class SynthesizeChunkFrame(StrictModel):
    type: Literal["synthesize_chunk"]
    generation: int = Field(ge=1)
    request_id: str = Field(min_length=1, max_length=128)
    index: int = Field(ge=0, lt=MAX_TTS_CHUNKS)
    data: str = Field(min_length=1, max_length=MAX_TTS_CHUNK_BYTES * 2)


class SynthesizeFinalFrame(StrictModel):
    type: Literal["synthesize_final"]
    generation: int = Field(ge=1)
    request_id: str = Field(min_length=1, max_length=128)
    success: bool
    chunks: int = Field(default=0, ge=0, le=MAX_TTS_CHUNKS)
    size: int = Field(default=0, ge=0, le=MAX_TTS_AUDIO_BYTES)
    sha256: str = Field(default="", max_length=64, pattern=r"^(?:[0-9a-f]{64})?$")
    sample_rate: int = Field(default=0, ge=0, le=96_000)
    channels: int = Field(default=1, ge=1, le=2)
    sample_width: int = Field(default=2, ge=1, le=4)
    engine: Literal["kokoro", "piper"] | None = None
    voice: str | None = Field(default=None, max_length=256)
    language: Literal["es", "en"] | None = None
    executor_fingerprint: str = Field(default="", max_length=64)
    error: str | None = Field(default=None, max_length=512)


InboundFrame = Annotated[
    ResultFrame | HeartbeatFrame | FeaturesFrame | SynthesizeChunkFrame | SynthesizeFinalFrame,
    Field(discriminator="type"),
]


def canonical_prefix(node_id: str) -> str:
    digest = hashlib.sha256(node_id.encode()).hexdigest()[:16]
    return f"node_{digest}__"


def canonical_name(node_id: str, tool_name: str) -> str:
    return f"{canonical_prefix(node_id)}{tool_name}"


_CANONICAL_SHELL = re.compile(r"^node_[0-9a-f]{16}__shell_run$")


def is_canonical_shell(name: str) -> bool:
    return _CANONICAL_SHELL.fullmatch(name) is not None


def trusted_inventory(node_id: str, hello: HelloFrame) -> list[dict[str, object]]:
    seen: set[str] = set()
    tools: list[dict[str, object]] = []
    for advertised in hello.tools:
        trusted = BUNDLED_TOOLS.get(advertised.name)
        if trusted is None or advertised.name in seen:
            raise ValueError(f"Unsupported or duplicate capability: {advertised.name}")
        description, schema = trusted
        if not _matches_schema(advertised.input_schema, schema):
            raise ValueError(f"Untrusted schema for capability: {advertised.name}")
        if (
            len(
                json.dumps(advertised.input_schema, separators=(",", ":")).encode()
            )
            > MAX_SCHEMA_BYTES
        ):
            raise ValueError("Capability schema exceeds limit")
        seen.add(advertised.name)
        tools.append(
            {
                "name": canonical_name(node_id, advertised.name),
                "description": description,
                "inputSchema": schema,
                "server_name": f"capability-node:{node_id}",
            }
        )
    return tools


def trusted_endpoints(hello: HelloFrame) -> list[str]:
    """Filter a node's advertised addresses down to ones worth handing out.

    The node is not trusted to name its own address any more than it is trusted
    to describe its own tools. An address the backend repeats to a phone is an
    instruction about where to send credentials, so a node that advertised a
    public IP — or a neighbour's — would be redirecting clients somewhere the
    user never enrolled.

    The rule is therefore: private, link-local, or loopback only. Anything a
    laptop could legitimately be reached at on a home network passes; nothing
    routable from outside it does. Unparseable entries are dropped rather than
    rejected outright, so one bad address does not cost a node its connection.
    """
    accepted: list[str] = []
    for candidate in hello.endpoints:
        endpoint = _validated_endpoint(candidate)
        if endpoint is not None and endpoint not in accepted:
            accepted.append(endpoint)
    return accepted


def _validated_endpoint(candidate: str) -> str | None:
    if not candidate or len(candidate) > 64:
        return None
    host, separator, port_text = candidate.rpartition(":")
    if not separator or not host:
        return None
    # A bracketed IPv6 literal, as it appears in a URL authority.
    host = host.removeprefix("[").removesuffix("]")
    try:
        port = int(port_text)
    except ValueError:
        return None
    if not 1 <= port <= 65535:
        return None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return None
    if not (address.is_private or address.is_link_local or address.is_loopback):
        return None
    return candidate


def _matches_schema(
    advertised: dict[str, object], trusted: dict[str, object]
) -> bool:
    """Accept harmless JSON-Schema metadata while enforcing argument shape."""
    if advertised.get("type") != "object":
        return False
    properties = advertised.get("properties")
    trusted_properties = trusted["properties"]
    if not isinstance(properties, dict) or not isinstance(trusted_properties, dict):
        return False
    if set(properties) != set(trusted_properties):
        return False
    for name, expected in trusted_properties.items():
        actual = properties.get(name)
        if not isinstance(actual, dict) or not isinstance(expected, dict):
            return False
        if actual.get("type") != expected.get("type"):
            return False
    required = advertised.get("required", [])
    trusted_required = trusted.get("required", [])
    return (
        isinstance(required, list)
        and isinstance(trusted_required, list)
        and set(required) == set(trusted_required)
    )
