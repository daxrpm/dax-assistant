"""Encrypted secret-store tests."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from cryptography.fernet import Fernet

from dax.storage.secrets import SecretStore, SecretStoreError

if TYPE_CHECKING:
    from pathlib import Path


def test_external_master_key_avoids_local_key_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DAX_MASTER_KEY", Fernet.generate_key().decode("ascii"))

    store = SecretStore(str(tmp_path / "dax.db"))
    store.set("TOKEN", "secret")

    assert store.get("TOKEN") == "secret"
    assert not (tmp_path / "dax.key").exists()


def test_missing_key_fails_closed_when_secrets_exist(tmp_path: Path) -> None:
    db_path = tmp_path / "dax.db"
    store = SecretStore(str(db_path))
    store.set("TOKEN", "must-survive")
    encrypted_database = db_path.read_bytes()
    (tmp_path / "dax.key").unlink()

    with pytest.raises(SecretStoreError, match="key is unavailable"):
        SecretStore(str(db_path))

    assert db_path.read_bytes() == encrypted_database
    assert b"must-survive" not in encrypted_database


def test_changed_external_key_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "dax.db"
    monkeypatch.setenv("DAX_MASTER_KEY", Fernet.generate_key().decode("ascii"))
    store = SecretStore(str(db_path))
    store.set("TOKEN", "must-survive")
    encrypted_database = db_path.read_bytes()
    monkeypatch.setenv("DAX_MASTER_KEY", Fernet.generate_key().decode("ascii"))

    with pytest.raises(SecretStoreError, match="cannot be decrypted"):
        SecretStore(str(db_path))

    assert db_path.read_bytes() == encrypted_database


def test_second_process_cannot_open_same_persistence_database(tmp_path: Path) -> None:
    db_path = tmp_path / "dax.db"
    SecretStore(str(db_path))
    code = """
from dax.storage.database import DatabaseLockedError
from dax.storage.secrets import SecretStore
try:
    SecretStore(DB_PATH)
except DatabaseLockedError:
    raise SystemExit(0)
raise SystemExit(1)
"""
    code = code.replace("DB_PATH", repr(str(db_path)))

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
