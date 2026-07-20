from __future__ import annotations

import json
import stat
from typing import TYPE_CHECKING

import pytest

from dax.edge.credentials import (
    NodeCredentials,
    load_credentials,
    normalize_server_url,
    save_credentials,
    websocket_url,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://DAX.EXAMPLE/", "https://dax.example"),
        ("wss://dax.example", "https://dax.example"),
        ("http://localhost:8000/", "http://localhost:8000"),
        ("ws://127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("http://[::1]:8000", "http://[::1]:8000"),
    ],
)
def test_normalize_server_url(raw: str, expected: str) -> None:
    assert normalize_server_url(raw) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://dax.example",
        "ws://192.168.1.4:8000",
        "ftp://localhost",
        "https://user:secret@dax.example",
        "https://dax.example/base",
        "https://dax.example?token=secret",
    ],
)
def test_rejects_unsafe_or_ambiguous_urls(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_server_url(url)


def test_websocket_token_is_not_put_in_url() -> None:
    assert websocket_url("https://dax.example") == "wss://dax.example/ws/capabilities"


def test_atomic_credentials_are_owner_only(tmp_path: Path) -> None:
    target = tmp_path / "state" / "edge.json"
    credentials = NodeCredentials("https://dax.example", "device-1", "secret-value", "laptop")
    save_credentials(credentials, target)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert load_credentials(target) == credentials
    assert json.loads(target.read_text())["device_secret"] == "secret-value"


def test_credentials_repr_redacts_secret() -> None:
    credentials = NodeCredentials("https://dax.example", "device-1", "do-not-log", "laptop")
    assert "do-not-log" not in repr(credentials)
