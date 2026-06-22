"""Run the dax-system MCP server over stdio: python -m dax.mcp_servers.system"""

from __future__ import annotations

from dax.mcp_servers.system.server import build_server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
