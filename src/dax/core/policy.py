"""Tool execution policy — allow / ask / deny per tool name.

The agent consults this before running any tool. Destructive or irreversible
actions (shell, writes, deletes, launching apps) default to ``ask`` so they
require explicit confirmation in the web UI; read-only actions ``allow``.
Patterns are case-insensitive fnmatch globs matched against the tool name.
"""

from __future__ import annotations

import fnmatch
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dax.core.config import ToolPolicyConfig


class Decision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


# Sensible defaults: anything that writes, deletes, executes, or launches
# requires confirmation. Everything else is allowed.
DEFAULT_ASK_PATTERNS: tuple[str, ...] = (
    "*write*",
    "*delete*",
    "*remove*",
    "*move*",
    "*rename*",
    "*create*",
    "*shell*",
    "*exec*",
    "*run*",
    "*kill*",
    "*open_app*",
    "*open_path*",
    "*launch*",
    "*clipboard_set*",
    "*install*",
    "*send*",
)


class ToolPolicy:
    """Resolves an allow/ask/deny decision for a tool name."""

    def __init__(
        self,
        *,
        default: Decision = Decision.ALLOW,
        allow: list[str] | None = None,
        ask: list[str] | None = None,
        deny: list[str] | None = None,
    ) -> None:
        self._default = default
        self._allow = [p.lower() for p in (allow or [])]
        self._ask = [p.lower() for p in (ask if ask is not None else DEFAULT_ASK_PATTERNS)]
        self._deny = [p.lower() for p in (deny or [])]

    @classmethod
    def from_config(cls, config: ToolPolicyConfig) -> ToolPolicy:
        return cls(
            default=Decision(config.default),
            allow=config.allow,
            ask=config.ask if config.ask else list(DEFAULT_ASK_PATTERNS),
            deny=config.deny,
        )

    def reload(self, config: ToolPolicyConfig) -> None:
        """Update rules in place so the agent picks them up without a restart."""
        self._default = Decision(config.default)
        self._allow = [p.lower() for p in config.allow]
        self._ask = [
            p.lower()
            for p in (config.ask if config.ask else DEFAULT_ASK_PATTERNS)
        ]
        self._deny = [p.lower() for p in config.deny]

    @staticmethod
    def _matches(name: str, patterns: list[str]) -> bool:
        n = name.lower()
        return any(fnmatch.fnmatch(n, p) for p in patterns)

    def decide(self, tool_name: str) -> Decision:
        # deny wins, then ask, then explicit allow, then the default.
        if self._matches(tool_name, self._deny):
            return Decision.DENY
        if self._matches(tool_name, self._ask):
            return Decision.ASK
        if self._matches(tool_name, self._allow):
            return Decision.ALLOW
        return self._default
