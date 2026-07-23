"""Entry point for running Dax Assistant: python -m dax"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

SUBCOMMANDS = ("edge", "claim")


def main() -> None:
    """Parse arguments and run the application."""
    parser = argparse.ArgumentParser(prog="dax")
    subparsers = parser.add_subparsers(dest="command")
    from dax.claim import add_claim_parser
    from dax.edge.cli import add_edge_parser

    add_edge_parser(subparsers)
    add_claim_parser(subparsers)

    first = sys.argv[1] if len(sys.argv) > 1 else ""
    if first == "edge":
        from dax.edge.cli import edge_main

        raise SystemExit(edge_main(parser.parse_args()))
    if first == "claim":
        from dax.claim import claim_main

        raise SystemExit(claim_main(parser.parse_args()))
    # Bare `dax` runs the server. A word that is not a known subcommand is a
    # typo, not an instruction to boot the backend — silently starting the whole
    # application in that case hid a missing subcommand behind a normal startup.
    if first and not first.startswith("-"):
        parser.error(
            f"unknown command {first!r}; expected one of {', '.join(SUBCOMMANDS)}"
        )

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
