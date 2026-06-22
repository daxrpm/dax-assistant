"""Entry point for running Dax Assistant: python -m dax"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dax.app import DaxApp


def main() -> None:
    """Parse arguments and run the application."""
    config_path: Path | None = None

    # Simple arg parsing — no heavy CLI framework needed for Phase 0
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg in ("--config", "-c") and i < len(sys.argv):
            config_path = Path(sys.argv[i + 1])
            break

    if config_path is None:
        default = Path("config/dax.toml")
        if default.exists():
            config_path = default

    app = DaxApp.from_config_path(config_path)
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
