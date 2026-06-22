"""`dax-system` — a local MCP server exposing safe, typed PC-control tools.

Runs as a stdio subprocess (``python -m dax.mcp_servers.system``) and is wired
in like any other MCP server. Safety is layered:

* **Path confinement** — file tools only touch paths under allowed roots
  (``DAX_SYSTEM_ROOTS``, default: the user's home).
* **Shell allowlist** — ``shell_run`` only runs binaries in an allowlist
  (``DAX_SYSTEM_SHELL_ALLOW``) with no shell metacharacters; never via a shell.
* **Confirmation gate** — destructive tools (write/shell/open/clipboard_set)
  are additionally gated by the agent's policy and confirmed in the web UI.

The functions ``safe_path`` and ``validate_command`` are pure and unit-tested.
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Characters that would let a string break out of a single argv token.
_SHELL_METACHARS = set(";&|`$><\n\\\"'*?(){}[]~!#")

_DEFAULT_SHELL_ALLOW = (
    "ls,cat,echo,pwd,date,whoami,uname,uptime,df,free,du,ps,hostname,"
    "id,env,which,head,tail,wc,find,grep,git,python3,node,npm,uv"
)

_MAX_OUTPUT = 8000
_SHELL_TIMEOUT = 30


def allowed_roots() -> list[Path]:
    raw = os.environ.get("DAX_SYSTEM_ROOTS", "")
    if raw:
        return [Path(p).expanduser().resolve() for p in raw.split(os.pathsep) if p]
    return [Path.home().resolve()]


def shell_allowlist() -> set[str]:
    raw = os.environ.get("DAX_SYSTEM_SHELL_ALLOW", _DEFAULT_SHELL_ALLOW)
    return {c.strip() for c in raw.split(",") if c.strip()}


def safe_path(path: str, roots: list[Path] | None = None) -> Path:
    """Resolve ``path`` and ensure it stays within an allowed root.

    Raises ValueError if the resolved path escapes every allowed root.
    """
    roots = roots if roots is not None else allowed_roots()
    resolved = Path(path).expanduser().resolve()
    for root in roots:
        if resolved == root or root in resolved.parents:
            return resolved
    raise ValueError(
        f"Path '{path}' is outside the allowed roots "
        f"({', '.join(str(r) for r in roots)})"
    )


def validate_command(command: str, allowlist: set[str] | None = None) -> list[str]:
    """Parse ``command`` into argv, enforcing the allowlist and no metachars.

    Raises ValueError on rejection. Returns the argv list for subprocess.run.
    """
    allowlist = allowlist if allowlist is not None else shell_allowlist()
    if any(ch in _SHELL_METACHARS for ch in command):
        raise ValueError("Command contains disallowed shell metacharacters")
    argv = shlex.split(command)
    if not argv:
        raise ValueError("Empty command")
    binary = Path(argv[0]).name
    if binary not in allowlist:
        raise ValueError(
            f"Command '{binary}' is not in the allowlist. "
            f"Allowed: {', '.join(sorted(allowlist))}"
        )
    return argv


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT:
        return text[:_MAX_OUTPUT] + f"\n…(truncated, {len(text)} bytes total)"
    return text


def build_server() -> FastMCP:
    """Construct the FastMCP server with all dax-system tools registered."""
    mcp = FastMCP("dax-system")

    # ── Read-only tools (auto-allowed by policy) ──────────────────────────

    @mcp.tool()
    def system_info() -> str:
        """Report OS, host, CPU count, and disk usage of the home directory."""
        usage = shutil.disk_usage(str(Path.home()))
        load = "n/a"
        if hasattr(os, "getloadavg"):
            load = ", ".join(f"{x:.2f}" for x in os.getloadavg())
        return (
            f"system: {platform.platform()}\n"
            f"host: {platform.node()}\n"
            f"python: {platform.python_version()}\n"
            f"cpus: {os.cpu_count()}\n"
            f"loadavg: {load}\n"
            f"home_disk: {usage.used // 2**30} GiB used / {usage.total // 2**30} GiB"
        )

    @mcp.tool()
    def fs_list(path: str = ".") -> str:
        """List the entries of a directory (within allowed roots)."""
        target = safe_path(path)
        if not target.is_dir():
            return f"Error: '{path}' is not a directory"
        entries = []
        for child in sorted(target.iterdir()):
            kind = "d" if child.is_dir() else "f"
            entries.append(f"{kind} {child.name}")
        return "\n".join(entries) or "(empty)"

    @mcp.tool()
    def fs_read(path: str, max_bytes: int = 20000) -> str:
        """Read a UTF-8 text file (within allowed roots)."""
        target = safe_path(path)
        if not target.is_file():
            return f"Error: '{path}' is not a file"
        data = target.read_text(encoding="utf-8", errors="replace")[:max_bytes]
        return data

    @mcp.tool()
    def fs_search(root: str, pattern: str, max_results: int = 50) -> str:
        """Find files under a directory matching a glob pattern (e.g. '*.py')."""
        base = safe_path(root)
        if not base.is_dir():
            return f"Error: '{root}' is not a directory"
        matches = [str(p) for p in list(base.rglob(pattern))[:max_results]]
        return "\n".join(matches) or "(no matches)"

    @mcp.tool()
    def clipboard_get() -> str:
        """Read the system clipboard (requires wl-paste or xclip)."""
        for cmd in (["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"]):
            if shutil.which(cmd[0]):
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                return out.stdout
        return "Error: no clipboard tool available (install wl-clipboard or xclip)"

    @mcp.tool()
    def notify(title: str, message: str) -> str:
        """Show a desktop notification (requires notify-send)."""
        if not shutil.which("notify-send"):
            return "Error: notify-send not available"
        subprocess.run(["notify-send", title, message], timeout=5)
        return "Notification sent"

    # ── Destructive tools (gated by the confirmation policy) ──────────────

    @mcp.tool()
    def fs_write(path: str, content: str) -> str:
        """Write text to a file, creating parent directories (within roots)."""
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {target}"

    @mcp.tool()
    def shell_run(command: str) -> str:
        """Run an allowlisted shell command (no shell, no metacharacters)."""
        argv = validate_command(command)
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=_SHELL_TIMEOUT,
                cwd=str(allowed_roots()[0]),
            )
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {_SHELL_TIMEOUT}s"
        out = proc.stdout + (f"\n[stderr]\n{proc.stderr}" if proc.stderr else "")
        return _truncate(out) + f"\n[exit {proc.returncode}]"

    @mcp.tool()
    def open_path(path: str) -> str:
        """Open a file or directory with the default app (xdg-open)."""
        target = safe_path(path)
        if not shutil.which("xdg-open"):
            return "Error: xdg-open not available"
        subprocess.Popen(["xdg-open", str(target)])
        return f"Opened {target}"

    @mcp.tool()
    def clipboard_set(text: str) -> str:
        """Write text to the system clipboard (requires wl-copy or xclip)."""
        for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, input=text, text=True, timeout=5)
                return "Clipboard updated"
        return "Error: no clipboard tool available (install wl-clipboard or xclip)"

    return mcp
