"""Encrypted secret-store tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from dax.storage.secrets import SecretStore

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_external_master_key_avoids_local_key_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DAX_MASTER_KEY", Fernet.generate_key().decode("ascii"))

    store = SecretStore(str(tmp_path / "dax.db"))
    store.set("TOKEN", "secret")

    assert store.get("TOKEN") == "secret"
    assert not (tmp_path / "dax.key").exists()
