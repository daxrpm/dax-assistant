"""Runtime allowlist of shell binaries the assistant may run on this PC.

This is the **single source of truth** for which commands the ``dax-system``
``shell_run`` tool is allowed to execute. The agent consults it before every
shell call:

* bounded read-only command **in** the list -> run without confirmation;
* every other command -> ask the user, who can approve it explicitly;
* eligible read-only commands can also be saved for future silent execution.

The list is editable from the web UI (a dedicated page) and persisted to the
TOML config. Mutations fire ``on_change`` so the app can write the file without
the agent knowing anything about persistence.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Conservative defaults seeded on first run. These commands only report to
# stdout; commands that launch programs, interpret code, or modify files are
# deliberately excluded even when they are common development tools.
DEFAULT_SHELL_ALLOW: tuple[str, ...] = (
    "ls",
    "cat",
    "echo",
    "pwd",
    "whoami",
    "uname",
    "uptime",
    "df",
    "free",
    "du",
    "id",
    "which",
    "head",
    "tail",
    "wc",
    "grep",
)

# These extra commands can be saved by a user, but only their read-only forms
# become eligible for silent execution. Unknown binaries are never assumed safe
# merely because their name was persisted in the allowlist.
_CONDITIONALLY_READ_ONLY = frozenset({"date", "find", "hostname"})
_SHELL_METACHARS = frozenset(";&|`$><\n\\\"'*?(){}[]~!#")
_FIND_WRITE_OR_EXEC_ACTIONS = (
    "-delete",
    "-exec",
    "-execdir",
    "-fls",
    "-fprint",
    "-fprintf",
    "-ok",
    "-okdir",
)


def shell_binary(command: str) -> str | None:
    """Extract the bare binary name from a command string (``/bin/ls -l`` → ``ls``).

    Returns None if the command is empty or cannot be parsed (e.g. contains an
    unbalanced quote). Mirrors how ``validate_command`` resolves the binary.
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv:
        return None
    return Path(argv[0]).name


def is_auto_allowable(command: str) -> bool:
    """Return whether ``command`` has a bounded, read-only argv shape.

    This is intentionally stricter than command parsing. A command can still be
    run after explicit approval when this returns False.
    """
    if any(ch in _SHELL_METACHARS for ch in command):
        return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if not argv or argv[0] != Path(argv[0]).name:
        # A trusted basename must not authorize an attacker-controlled path.
        return False

    binary = argv[0]
    if binary in DEFAULT_SHELL_ALLOW:
        return True
    if binary not in _CONDITIONALLY_READ_ONLY:
        return False
    if binary == "date":
        return not any(
            arg.startswith("-s") or arg == "--set" or arg.startswith("--set=")
            for arg in argv[1:]
        )
    if binary == "find":
        return not any(
            arg.startswith(action)
            for arg in argv[1:]
            for action in _FIND_WRITE_OR_EXEC_ACTIONS
        )
    # hostname operands and options vary by platform and can change host/domain
    # names. Only the no-argument reporting form is portable and read-only.
    return len(argv) == 1


class ShellAllowlist:
    """Mutable command preference list constrained by read-only profiles."""

    def __init__(
        self,
        commands: list[str] | None = None,
        on_change: Callable[[list[str]], None] | None = None,
    ) -> None:
        self._commands: list[str] = (
            list(dict.fromkeys(commands))
            if commands is not None
            else list(DEFAULT_SHELL_ALLOW)
        )
        self._on_change = on_change

    def set_on_change(self, callback: Callable[[list[str]], None] | None) -> None:
        self._on_change = callback

    def is_allowed(self, binary: str | None) -> bool:
        return bool(binary) and binary in self._commands

    def allows_command(self, command: str) -> bool:
        """Return whether a full command may run without human approval."""
        return self.is_allowed(shell_binary(command)) and is_auto_allowable(command)

    def items(self) -> list[str]:
        return list(self._commands)

    def add(self, binary: str) -> bool:
        """Append a binary if new. Returns True if it was actually added."""
        if not binary or binary in self._commands:
            return False
        self._commands.append(binary)
        self._notify()
        return True

    def replace(self, commands: list[str]) -> None:
        """Replace the whole list (de-duped, order preserved) and persist."""
        self._commands = list(dict.fromkeys(c for c in commands if c))
        self._notify()

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change(list(self._commands))
