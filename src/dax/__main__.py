"""Entry point for running Dax Assistant: python -m dax"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def main() -> None:
    """Parse arguments and run the application."""
    parser = argparse.ArgumentParser(prog="dax")
    subparsers = parser.add_subparsers(dest="command")
    from dax.edge.cli import add_edge_parser

    add_edge_parser(subparsers)
    if len(sys.argv) > 1 and sys.argv[1] == "edge":
        from dax.edge.cli import edge_main

        raise SystemExit(edge_main(parser.parse_args()))

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

    from dax.app import DaxApp

    app = DaxApp.from_config_path(config_path)
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
