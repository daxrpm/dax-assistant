"""Runtime allowlist of shell binaries the assistant may run on this PC.

This is the **single source of truth** for which commands the ``dax-system``
``shell_run`` tool is allowed to execute. The agent consults it before every
shell call:

* binary **in** the list  → run immediately, no confirmation;
* binary **not** in the list → ask the user, who can *approve once* or
  *approve & save* (which appends it here permanently).

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

# Safe, useful defaults seeded on first run. Read-only/inspection binaries plus
# the common dev tools. Anything else is learned on approval.
DEFAULT_SHELL_ALLOW: tuple[str, ...] = (
    "ls", "cat", "echo", "pwd", "date", "whoami", "uname", "uptime", "df",
    "free", "du", "ps", "hostname", "id", "env", "which", "head", "tail", "wc",
    "find", "grep", "git", "python3", "node", "npm", "uv",
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


class ShellAllowlist:
    """Mutable, observable set of allowed shell binaries (order preserved)."""

    def __init__(
        self,
        commands: list[str] | None = None,
        on_change: Callable[[list[str]], None] | None = None,
    ) -> None:
        self._commands: list[str] = (
            list(dict.fromkeys(commands)) if commands else list(DEFAULT_SHELL_ALLOW)
        )
        self._on_change = on_change

    def set_on_change(self, callback: Callable[[list[str]], None] | None) -> None:
        self._on_change = callback

    def is_allowed(self, binary: str | None) -> bool:
        return bool(binary) and binary in self._commands

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
