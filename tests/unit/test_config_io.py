"""Tests for TOML config serialization + secret extraction (config_io)."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest

from dax.core.config import DaxConfig, MCPServerConfig, load_config
from dax.core.config_io import SECRET_FIELDS, dump_config_toml
from dax.storage.secrets import SecretStore

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def store(tmp_path: Path) -> SecretStore:
    return SecretStore(str(tmp_path / "dax.db"))


def test_roundtrip_preserves_non_default_fields(
    tmp_path: Path, store: SecretStore
) -> None:
    """A modified config survives dump → load unchanged (no silent field loss)."""
    cfg = DaxConfig()
    cfg.name = "Custom"
    cfg.web.port = 9999
    cfg.web.expose_lan = True
    cfg.voice.stt_model = "large-v3"
    cfg.voice.wake_word_model = "models/wakeword/custom.onnx"  # was dropped before
    cfg.llm.default_provider = "anthropic"
    cfg.llm.max_tools = 77
    cfg.tools.policy.deny = ["dangerous_*"]
    cfg.tools.shell_allow = ["git", "ls"]

    path = tmp_path / "dax.toml"
    dump_config_toml(cfg, store, path)
    reloaded = load_config(path)

    assert reloaded.name == "Custom"
    assert reloaded.web.port == 9999
    assert reloaded.web.expose_lan is True
    assert reloaded.voice.stt_model == "large-v3"
    assert reloaded.voice.wake_word_model == "models/wakeword/custom.onnx"
    assert reloaded.llm.default_provider == "anthropic"
    assert reloaded.llm.max_tools == 77
    assert reloaded.tools.policy.deny == ["dangerous_*"]
    assert reloaded.tools.shell_allow == ["git", "ls"]


def test_secrets_are_never_written_to_toml(
    tmp_path: Path, store: SecretStore
) -> None:
    """Every declared secret stays out of the TOML file."""
    cfg = DaxConfig()
    cfg.llm.anthropic.api_key = "sk-ant-secret"
    cfg.llm.openai.api_key = "sk-openai-secret"
    cfg.telegram.bot_token = "123:telegram-secret"
    cfg.security.password_hash = "$argon2id$secret"

    path = tmp_path / "dax.toml"
    dump_config_toml(cfg, store, path)
    raw = path.read_text()

    assert "sk-ant-secret" not in raw
    assert "sk-openai-secret" not in raw
    assert "123:telegram-secret" not in raw
    assert "$argon2id$secret" not in raw

    # REF secrets become {env:VAR}; OMIT secrets vanish entirely.
    data = tomllib.loads(raw)
    assert data["llm"]["anthropic"]["api_key"] == "{env:ANTHROPIC_API_KEY}"
    assert "bot_token" not in data.get("telegram", {})
    assert "password_hash" not in data.get("security", {})

    # …and all are persisted to the encrypted store.
    assert store.get("ANTHROPIC_API_KEY") == "sk-ant-secret"
    assert store.get("OPENAI_API_KEY") == "sk-openai-secret"
    assert store.get("DAX_TELEGRAM__BOT_TOKEN") == "123:telegram-secret"
    assert store.get("DAX_SECURITY__PASSWORD_HASH") == "$argon2id$secret"


def test_empty_secret_not_written_as_placeholder(
    tmp_path: Path, store: SecretStore
) -> None:
    """An unset api key must not leak an empty {env:…} ref into the file."""
    cfg = DaxConfig()  # all secrets empty
    path = tmp_path / "dax.toml"
    dump_config_toml(cfg, store, path)
    data = tomllib.loads(path.read_text())

    assert "api_key" not in data["llm"]["anthropic"]
    assert store.get("ANTHROPIC_API_KEY") is None


def test_existing_env_ref_is_not_double_wrapped(
    tmp_path: Path, store: SecretStore
) -> None:
    """A field already holding an {env:…} ref is kept verbatim, not re-stored."""
    cfg = DaxConfig()
    cfg.llm.openai.api_key = "{env:OPENAI_API_KEY}"
    path = tmp_path / "dax.toml"
    dump_config_toml(cfg, store, path)
    data = tomllib.loads(path.read_text())

    assert data["llm"]["openai"]["api_key"] == "{env:OPENAI_API_KEY}"
    assert store.get("OPENAI_API_KEY") is None  # nothing re-persisted


def test_sensitive_mcp_headers_are_extracted(
    tmp_path: Path, store: SecretStore
) -> None:
    """Authorization-style headers move to the store as {env:…} refs."""
    cfg = DaxConfig()
    cfg.mcp.servers["coolify"] = MCPServerConfig(
        transport="streamable_http",
        url="https://example.test/mcp",
        headers={"Authorization": "Bearer tok-secret", "X-Trace": "on"},
    )
    path = tmp_path / "dax.toml"
    dump_config_toml(cfg, store, path)
    raw = path.read_text()

    assert "tok-secret" not in raw
    data = tomllib.loads(raw)
    hdrs = data["mcp"]["servers"]["coolify"]["headers"]
    assert hdrs["Authorization"] == "{env:DAX_MCP_COOLIFY_HDR_AUTHORIZATION}"
    assert hdrs["X-Trace"] == "on"  # non-sensitive header untouched
    assert store.get("DAX_MCP_COOLIFY_HDR_AUTHORIZATION") == "Bearer tok-secret"


def test_secret_fields_cover_known_secret_paths() -> None:
    """Guard: the secret table references real, current config fields."""
    cfg = DaxConfig()
    for path in SECRET_FIELDS:
        obj: object = cfg
        for part in path.split("."):
            assert hasattr(obj, part), f"stale secret path: {path}"
            obj = getattr(obj, part)
