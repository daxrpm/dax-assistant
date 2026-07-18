"""Smoke tests for the portable Linux installer."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def test_installer_dry_run_uses_xdg_layout(tmp_path: Path) -> None:
    root = tmp_path / "install"
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }

    result = subprocess.run(
        [
            "bash", "scripts/install.sh", "install", "--dry-run", "--yes",
            "--install-dir", str(root), "--language", "en",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert f"Application: {root}" in result.stdout
    assert f"State:       {tmp_path / 'state' / 'dax-assistant'}" in result.stdout
    assert not root.exists()


def test_installer_scripts_parse() -> None:
    subprocess.run(["bash", "-n", "scripts/install.sh"], check=True)
    subprocess.run(["bash", "-n", "scripts/install-service.sh"], check=True)
