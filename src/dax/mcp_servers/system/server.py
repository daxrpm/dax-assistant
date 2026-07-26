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
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from dax.core.shell_allow import DEFAULT_SHELL_ALLOW

# Characters that would let a string break out of a single argv token.
_SHELL_METACHARS = set(";&|`$><\n\\\"'*?(){}[]~!#")

_DEFAULT_SHELL_ALLOW = ",".join(DEFAULT_SHELL_ALLOW)

_MAX_OUTPUT = 8000
_SHELL_TIMEOUT = 30
_APP_LAUNCH_TIMEOUT = 15


def allowed_roots() -> list[Path]:
    raw = os.environ.get("DAX_SYSTEM_ROOTS", "")
    if raw:
        return [Path(p).expanduser().resolve() for p in raw.split(os.pathsep) if p]
    return [Path.home().resolve()]


def configured_shell_allowlist() -> set[str] | None:
    """Return the hard subprocess cap, or None for the local backend mode."""
    raw = os.environ.get("DAX_SYSTEM_SHELL_ALLOW")
    if raw is None:
        return None
    return {c.strip() for c in raw.split(",") if c.strip()}


def shell_allowlist() -> set[str]:
    """Return the effective edge allowlist, defaulting conservatively."""
    configured = configured_shell_allowlist()
    if configured is not None:
        return configured
    return {c.strip() for c in _DEFAULT_SHELL_ALLOW.split(",") if c.strip()}


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
    """Parse ``command`` into argv, rejecting shell metacharacters.

    The injection-safety guarantees (no shell, argv-only, no metacharacters) are
    always enforced. The binary allowlist is applied when ``allowlist`` is given.
    Capability nodes set one explicitly, including an empty set; an unconfigured
    local backend remains permissive after its separate approval gate.

    Raises ValueError on rejection. Returns the argv list for subprocess.run.
    """
    if any(ch in _SHELL_METACHARS for ch in command):
        raise ValueError("Command contains disallowed shell metacharacters")
    argv = shlex.split(command)
    if not argv:
        raise ValueError("Empty command")
    binary = Path(argv[0]).name
    if allowlist is not None and (binary not in allowlist or argv[0] != binary):
        raise ValueError(
            f"Command '{binary}' is not in the allowlist. "
            f"Allowed: {', '.join(sorted(allowlist))}"
        )
    return argv


def _command_environment() -> dict[str, str]:
    """Keep inherited settings but prevent user PATH entries shadowing utilities."""
    env = os.environ.copy()
    env["PATH"] = os.defpath
    return env


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT:
        return text[:_MAX_OUTPUT] + f"\n…(truncated, {len(text)} bytes total)"
    return text


def _completed_command_output(proc: subprocess.CompletedProcess[str]) -> str:
    """Format command output and expose a non-zero exit as an MCP error."""
    out = proc.stdout + (f"\n[stderr]\n{proc.stderr}" if proc.stderr else "")
    result = _truncate(out) + f"\n[exit {proc.returncode}]"
    if proc.returncode != 0:
        raise RuntimeError(result)
    return result


def _application_dirs() -> list[Path]:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(
        os.pathsep
    )
    roots = [
        data_home,
        Path.home() / ".local/share/flatpak/exports/share",
        Path("/var/lib/flatpak/exports/share"),
        *(Path(path) for path in data_dirs if path),
    ]
    directories: list[Path] = []
    for root in roots:
        directory = root / "applications"
        if directory not in directories:
            directories.append(directory)
    return directories


def _app_key(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold())


def _resolve_application(app: str, directories: list[Path] | None = None) -> tuple[str, str]:
    """Resolve a human app name to one visible desktop entry."""
    query = app.strip()
    if not query or len(query) > 128 or "/" in query or "\x00" in query:
        raise ValueError("Application name is invalid")
    query_key = _app_key(query.removesuffix(".desktop"))
    candidates: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for directory in directories or _application_dirs():
        if not directory.is_dir():
            continue
        for entry in sorted(directory.glob("*.desktop")):
            desktop_id = entry.stem
            if desktop_id in seen:
                continue
            seen.add(desktop_id)
            names: list[str] = []
            hidden = False
            desktop_entry = False
            try:
                for raw_line in entry.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = raw_line.strip()
                    if line.startswith("["):
                        desktop_entry = line == "[Desktop Entry]"
                        continue
                    if not desktop_entry or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key in {"Hidden", "NoDisplay"} and value.casefold() == "true":
                        hidden = True
                    elif key == "Name" or key.startswith("Name["):
                        names.append(value.strip())
            except OSError:
                continue
            if hidden:
                continue
            display_name = names[0] if names else desktop_id
            keys = {_app_key(desktop_id), *(_app_key(name) for name in names)}
            if query_key in keys:
                score = 0
            elif any(key.startswith(query_key) for key in keys):
                score = 1
            elif any(query_key in key for key in keys):
                score = 2
            else:
                continue
            candidates.append((score, desktop_id, display_name))
    if not candidates:
        raise ValueError(f"Application '{query}' is not installed")
    best_score = min(candidate[0] for candidate in candidates)
    best = [candidate for candidate in candidates if candidate[0] == best_score]
    if len(best) != 1:
        choices = ", ".join(sorted(candidate[2] for candidate in best)[:5])
        raise ValueError(f"Application name '{query}' is ambiguous: {choices}")
    _, desktop_id, display_name = best[0]
    return desktop_id, display_name


def _launch_application(app: str, directories: list[Path] | None = None) -> str:
    desktop_id, display_name = _resolve_application(app, directories)
    systemd_run = shutil.which("systemd-run")
    gtk_launch = shutil.which("gtk-launch")
    if not systemd_run or not gtk_launch:
        raise RuntimeError("Application launching requires systemd-run and gtk-launch")
    try:
        proc = subprocess.run(
            [
                systemd_run,
                "--user",
                "--collect",
                "--wait",
                "--quiet",
                "--property=Type=exec",
                gtk_launch,
                desktop_id,
            ],
            capture_output=True,
            text=True,
            timeout=_APP_LAUNCH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Application launcher timed out after {_APP_LAUNCH_TIMEOUT}s"
        ) from None
    if proc.returncode != 0:
        raise RuntimeError(_truncate(proc.stderr or proc.stdout or "Application launch failed"))
    return f"Opened {display_name} ({desktop_id})"


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
        argv = validate_command(command, configured_shell_allowlist())
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=_SHELL_TIMEOUT,
                cwd=str(allowed_roots()[0]),
                env=_command_environment(),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Command timed out after {_SHELL_TIMEOUT}s"
            ) from None
        return _completed_command_output(proc)

    @mcp.tool()
    def open_path(path: str) -> str:
        """Open a file or directory with the default app (xdg-open)."""
        target = safe_path(path)
        if not shutil.which("xdg-open"):
            return "Error: xdg-open not available"
        subprocess.Popen(["xdg-open", str(target)])
        return f"Opened {target}"

    @mcp.tool()
    def app_open(app: str) -> str:
        """Open an installed desktop application by name or desktop ID."""
        return _launch_application(app)

    @mcp.tool()
    def clipboard_set(text: str) -> str:
        """Write text to the system clipboard (requires wl-copy or xclip)."""
        for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, input=text, text=True, timeout=5)
                return "Clipboard updated"
        return "Error: no clipboard tool available (install wl-clipboard or xclip)"

    return mcp
