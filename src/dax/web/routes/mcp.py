"""MCP server management — CRUD over configured servers (with live connect/
reconnect), the shell-command allowlist, external-client config export
(Codex/Claude), and the MCP marketplace (presets + official registry search)."""

from __future__ import annotations

import json
from typing import Any

import aiohttp
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dax.web.dependencies import ConfigDep, persist_config

router = APIRouter(tags=["mcp"])


class MCPServerCreate(BaseModel):
    name: str
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    export_codex: bool = False
    export_claude: bool = False


class MCPServerUpdate(BaseModel):
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    export_codex: bool = False
    export_claude: bool = False


class ShellAllowUpdate(BaseModel):
    commands: list[str] = Field(default_factory=list)


def _server_dict(srv: Any) -> dict[str, Any]:
    return {
        "command": srv.command,
        "args": srv.args,
        "env": srv.env,
        "transport": srv.transport,
        "url": srv.url,
        "headers": srv.headers,
        "enabled": srv.enabled,
        "export_codex": getattr(srv, "export_codex", False),
        "export_claude": getattr(srv, "export_claude", False),
    }


@router.get("/config/mcp/servers")
async def list_mcp_servers(config: ConfigDep) -> dict[str, Any]:
    """List all configured MCP servers."""
    return {name: _server_dict(srv) for name, srv in config.mcp.servers.items()}


@router.post("/config/mcp/servers")
async def add_mcp_server(
    request: Request, body: MCPServerCreate, config: ConfigDep
) -> dict[str, Any]:
    """Add a new MCP server, persist it, and connect to it live."""
    from dax.core.config import MCPServerConfig

    if body.name in config.mcp.servers:
        raise HTTPException(status_code=409, detail=f"Server '{body.name}' already exists")

    server_config = MCPServerConfig(
        command=body.command,
        args=body.args,
        env=body.env,
        transport=body.transport,
        url=body.url,
        headers=body.headers,
        enabled=body.enabled,
        export_codex=body.export_codex,
        export_claude=body.export_claude,
    )
    config.mcp.servers[body.name] = server_config
    persist_config(request)

    # Connect live (best-effort): the server is saved either way.
    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is not None and body.enabled:
        try:
            tools = await manager.add_server(body.name, server_config)
            return {"status": "ok", "name": body.name, "tools": tools}
        except Exception as e:
            return {"status": "saved", "name": body.name, "error": str(e)}

    return {"status": "ok", "name": body.name, "tools": 0}


@router.post("/config/mcp/servers/{server_name}/reconnect")
async def reconnect_mcp_server(request: Request, server_name: str) -> dict[str, Any]:
    """Reconnect a server with current config and any stored OAuth token."""
    manager = getattr(request.app.state, "mcp_manager", None)
    if not manager:
        raise HTTPException(500, "MCP Manager not available")

    server_config = request.app.state.config.mcp.servers.get(server_name)
    if not server_config:
        raise HTTPException(404, f"Server '{server_name}' not found")

    try:
        tools = await manager.add_server(server_name, server_config)
    except Exception as e:
        raise HTTPException(500, f"Failed to connect: {e}") from e
    return {"status": "ok", "tools": tools}


@router.patch("/config/mcp/servers/{server_name}")
async def update_mcp_server(
    request: Request, server_name: str, body: MCPServerUpdate, config: ConfigDep
) -> dict[str, Any]:
    """Update an existing MCP server config, persist, and reconnect live."""
    from dax.core.config import MCPServerConfig

    if server_name not in config.mcp.servers:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    previous = config.mcp.servers[server_name]
    server_config = MCPServerConfig(
        command=body.command,
        args=body.args,
        env=body.env,
        transport=body.transport,
        url=body.url,
        headers=body.headers,
        enabled=body.enabled,
        export_codex=body.export_codex,
        export_claude=body.export_claude,
    )
    config.mcp.servers[server_name] = server_config
    persist_config(request)

    connection_changed = any(
        getattr(previous, field) != getattr(server_config, field)
        for field in ("command", "args", "env", "transport", "url", "headers", "enabled")
    )
    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is not None and body.enabled and connection_changed:
        try:
            tools = await manager.add_server(server_name, server_config)
            return {"status": "ok", "name": server_name, "tools": tools}
        except Exception as e:
            return {"status": "saved", "name": server_name, "error": str(e)}

    return {"status": "ok", "name": server_name, "tools": 0}


@router.delete("/config/mcp/servers/{server_name}")
async def delete_mcp_server(
    request: Request, server_name: str, config: ConfigDep
) -> dict[str, str]:
    """Disconnect, drop tools, remove the server config, and persist."""
    if server_name not in config.mcp.servers:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    manager = getattr(request.app.state, "mcp_manager", None)
    if manager is not None:
        await manager.remove_server(server_name)

    del config.mcp.servers[server_name]
    persist_config(request)
    return {"status": "ok"}


# --- Shell command allowlist ---
#
# The binaries the assistant may run on this PC via the dax-system `shell_run`
# tool. The agent runs allowlisted commands without asking and prompts for the
# rest. Editing here updates the live allowlist and persists to TOML.


def _shell_allow_runtime(request: Request) -> Any | None:
    return getattr(request.app.state, "shell_allow", None)


@router.get("/config/system/shell-allow")
async def get_system_shell_allow(request: Request, config: ConfigDep) -> dict[str, Any]:
    """Return the current shell-command allowlist and the built-in defaults."""
    from dax.core.shell_allow import DEFAULT_SHELL_ALLOW

    runtime = _shell_allow_runtime(request)
    if runtime is not None:
        commands = runtime.items()
    else:
        commands = list(getattr(config.tools, "shell_allow", []))
    return {"commands": commands, "default": list(DEFAULT_SHELL_ALLOW)}


@router.put("/config/system/shell-allow")
async def update_system_shell_allow(
    request: Request, body: ShellAllowUpdate, config: ConfigDep
) -> dict[str, Any]:
    """Replace the shell allowlist. Applies live and persists to TOML."""
    from dax.mcp_servers.system.server import _SHELL_METACHARS

    # Normalise: trim, drop blanks, de-dupe (order preserved). Each entry must be
    # a bare binary name — no whitespace, commas or shell metacharacters.
    seen: set[str] = set()
    commands: list[str] = []
    for raw in body.commands:
        cmd = raw.strip()
        if not cmd or cmd in seen:
            continue
        if (
            "," in cmd
            or any(ch.isspace() for ch in cmd)
            or any(ch in _SHELL_METACHARS for ch in cmd)
        ):
            raise HTTPException(
                422, f"Invalid command '{cmd}': use a bare binary name (e.g. 'git')"
            )
        seen.add(cmd)
        commands.append(cmd)

    object.__setattr__(config.tools, "shell_allow", commands)

    runtime = _shell_allow_runtime(request)
    if runtime is not None:
        # replace() fires the persistence hook; avoid double-writing the TOML.
        runtime.replace(commands)
    else:
        persist_config(request)

    return {"status": "ok", "commands": commands}


# --- External-client config export ---


@router.get("/codex-config")
async def get_codex_config(config: ConfigDep) -> dict[str, Any]:
    """Generate ~/.codex/config.toml for MCP servers flagged export_codex."""
    toml_lines = ["# Generated by Dax — paste into ~/.codex/config.toml", ""]
    count = 0

    for name, srv in config.mcp.servers.items():
        if not srv.enabled or not getattr(srv, "export_codex", False):
            continue
        count += 1
        toml_lines.append(f"[mcp_servers.{name}]")
        if srv.transport in ("http", "streamable_http", "sse") and srv.url:
            toml_lines.append(f'url = "{srv.url}"')
            static, env_hdrs = {}, {}
            for k, v in srv.headers.items():
                if v.startswith("{env:") and v.endswith("}"):
                    env_hdrs[k] = v[5:-1]
                else:
                    static[k] = v
            if env_hdrs:
                inner = ", ".join(f'"{k}" = "{var}"' for k, var in env_hdrs.items())
                toml_lines.append(f"env_http_headers = {{ {inner} }}")
            if static:
                inner = ", ".join(f'"{k}" = "{v}"' for k, v in static.items())
                toml_lines.append(f"http_headers = {{ {inner} }}")
        elif srv.command:
            toml_lines.append(f'command = "{srv.command}"')
            if srv.args:
                items = ", ".join(f'"{a}"' for a in srv.args)
                toml_lines.append(f"args = [{items}]")
            if srv.env:
                items = ", ".join(f'"{k}"' for k in srv.env)
                toml_lines.append(f"env_vars = [{items}]")
        toml_lines.append("")

    return {
        "toml": "\n".join(toml_lines),
        "server_count": count,
        "note": (
            "Requires Codex CLI (npm i -g @openai/codex). Works with ChatGPT Pro "
            "account or OpenAI API key."
        ),
    }


@router.get("/claude-config")
async def get_claude_config(config: ConfigDep) -> dict[str, Any]:
    """Generate Claude Desktop / Claude Code MCP config (servers flagged export_claude)."""
    servers: dict[str, Any] = {}

    for name, srv in config.mcp.servers.items():
        if not srv.enabled or not getattr(srv, "export_claude", False):
            continue
        if srv.transport in ("http", "streamable_http", "sse") and srv.url:
            entry: dict[str, Any] = {"type": "http", "url": srv.url}
            if srv.headers:
                entry["headers"] = {
                    k: (
                        f"${{{v[5:-1]}}}"
                        if v.startswith("{env:") and v.endswith("}")
                        else v
                    )
                    for k, v in srv.headers.items()
                }
        else:
            entry = {"command": srv.command, "args": srv.args}
            if srv.env:
                entry["env"] = {k: f"${{{k}}}" for k in srv.env}
        servers[name] = entry

    payload = {"mcpServers": servers}
    return {
        "json": json.dumps(payload, indent=2),
        "server_count": len(servers),
        "note": (
            "Add to claude_desktop_config.json, or run "
            "`claude mcp add-json <name> '<entry>'` for Claude Code."
        ),
    }


# --- MCP Marketplace — official registry + curated presets ---

_MCP_REGISTRY_BASE = "https://registry.modelcontextprotocol.io"

# Curated, ready-to-use presets for the most popular MCP servers. Each maps to
# an MCPServerCreate-compatible payload the UI can install with one click.
_MCP_PRESETS: list[dict[str, Any]] = [
    {
        "id": "filesystem", "name": "Filesystem", "category": "Files",
        "description": "Read/write local files in allowed directories.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home"],
        "env": {},
    },
    {
        "id": "github", "name": "GitHub", "category": "Dev",
        "description": "Manage repos, issues, PRs and code search.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
    },
    {
        "id": "brave-search", "name": "Brave Search", "category": "Web",
        "description": "Web and local search via the Brave Search API.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": ""},
    },
    {
        "id": "puppeteer", "name": "Puppeteer", "category": "Web",
        "description": "Browse and scrape the web with a headless browser.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"], "env": {},
    },
    {
        "id": "postgres", "name": "PostgreSQL", "category": "Data",
        "description": "Read-only SQL queries against a Postgres database.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres",
                 "postgresql://localhost/mydb"], "env": {},
    },
    {
        "id": "memory", "name": "Memory (Knowledge Graph)", "category": "Productivity",
        "description": "Persistent knowledge-graph memory across sessions.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"], "env": {},
    },
    {
        "id": "slack", "name": "Slack", "category": "Productivity",
        "description": "Read and post messages in Slack channels.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env": {"SLACK_BOT_TOKEN": "", "SLACK_TEAM_ID": ""},
    },
    {
        "id": "sequential-thinking", "name": "Sequential Thinking",
        "category": "Reasoning",
        "description": "Step-by-step structured reasoning tool.",
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "env": {},
    },
]


@router.get("/mcp/presets")
async def mcp_presets() -> list[dict[str, Any]]:
    """Return the curated list of ready-to-install MCP server presets."""
    return _MCP_PRESETS


@router.get("/mcp/registry/search")
async def mcp_registry_search(q: str = "", limit: int = 30) -> dict[str, Any]:
    """Search the official MCP registry. Proxies registry.modelcontextprotocol.io."""
    params: dict[str, Any] = {"limit": min(limit, 100)}
    if q:
        params["search"] = q
    try:
        async with aiohttp.ClientSession() as session, session.get(
            f"{_MCP_REGISTRY_BASE}/v0/servers",
            params=params,
            timeout=aiohttp.ClientTimeout(total=12),
        ) as r:
            if r.status != 200:
                return {"servers": [], "error": f"registry returned {r.status}"}
            data = await r.json()
    except Exception as e:
        return {"servers": [], "error": str(e)}

    # The registry wraps each entry as {"server": {...}, "_meta": {...}} and may
    # return several versions of the same server — keep the latest of each name.
    results: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for entry in data.get("servers", []):
        srv = entry.get("server", entry) if isinstance(entry, dict) else {}
        meta = (entry.get("_meta") or {}).get(
            "io.modelcontextprotocol.registry/official", {}
        )
        name = srv.get("name", "")
        if not name:
            continue
        # Skip superseded versions when the registry tells us which is latest.
        if meta.get("isLatest") is False and name in seen:
            continue

        pkgs = srv.get("packages", []) or []
        remotes = srv.get("remotes", []) or []
        record = {
            "name": name,
            "description": srv.get("description", "") or srv.get("title", ""),
            "version": srv.get("version", ""),
            "packages": [
                {
                    "registry_type": p.get("registryType", p.get("registry_type", "")),
                    "identifier": p.get("identifier", ""),
                    "version": p.get("version", ""),
                }
                for p in pkgs
            ],
            "remotes": [
                {"type": rm.get("type", ""), "url": rm.get("url", "")}
                for rm in remotes
            ],
        }
        if name in seen:
            results[seen[name]] = record
        else:
            seen[name] = len(results)
            results.append(record)

    return {"servers": results, "count": len(results)}
