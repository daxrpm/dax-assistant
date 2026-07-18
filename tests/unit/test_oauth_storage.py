"""Encrypted persistence tests for MCP OAuth credentials."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from dax.storage.secrets import SecretStore
from dax.web.routes import oauth

if TYPE_CHECKING:
    from pathlib import Path


def test_legacy_oauth_files_migrate_encrypted(
    tmp_path: Path, monkeypatch,
) -> None:
    token_file = tmp_path / "mcp-tokens.json"
    client_file = tmp_path / "mcp-clients.json"
    token_file.write_text(json.dumps({"home": {"access_token": "access-secret"}}))
    client_file.write_text(json.dumps({"home": {"client_secret": "client-secret"}}))
    monkeypatch.setattr(oauth, "_TOKEN_FILE", token_file)
    monkeypatch.setattr(oauth, "_CLIENT_FILE", client_file)
    store = SecretStore(str(tmp_path / "dax.db"))

    oauth.configure_oauth_store(store)

    assert not token_file.exists()
    assert not client_file.exists()
    assert oauth._load_tokens("home") == {"access_token": "access-secret"}
    assert oauth._load_client_info("home") == {"client_secret": "client-secret"}
    database = (tmp_path / "dax.db").read_bytes()
    assert b"access-secret" not in database
    assert b"client-secret" not in database
