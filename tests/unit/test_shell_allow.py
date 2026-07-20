"""Tests for the shell-command allowlist."""

from __future__ import annotations

import pytest

from dax.core.shell_allow import (
    DEFAULT_SHELL_ALLOW,
    ShellAllowlist,
    is_auto_allowable,
    shell_binary,
)


class TestShellBinary:
    def test_bare_name(self):
        assert shell_binary("git status") == "git"

    def test_absolute_path_basename(self):
        assert shell_binary("/usr/bin/flatpak run x") == "flatpak"

    def test_empty(self):
        assert shell_binary("   ") is None

    def test_unbalanced_quote(self):
        assert shell_binary("echo 'oops") is None


class TestShellAllowlist:
    def test_defaults_when_empty(self):
        a = ShellAllowlist()
        assert a.is_allowed("ls")
        assert set(a.items()) == set(DEFAULT_SHELL_ALLOW)
        assert not set(DEFAULT_SHELL_ALLOW) & {
            "env",
            "find",
            "git",
            "node",
            "npm",
            "ps",
            "python3",
            "uv",
        }

    def test_explicit_empty_list_stays_empty(self):
        assert ShellAllowlist([]).items() == []

    def test_is_allowed(self):
        a = ShellAllowlist(["git", "ls"])
        assert a.is_allowed("git")
        assert not a.is_allowed("flatpak")
        assert not a.is_allowed(None)

    def test_add_new_fires_on_change(self):
        seen: list[list[str]] = []
        a = ShellAllowlist(["git"], on_change=seen.append)
        assert a.add("flatpak") is True
        assert a.is_allowed("flatpak")
        assert seen == [["git", "flatpak"]]

    def test_add_duplicate_is_noop(self):
        seen: list[list[str]] = []
        a = ShellAllowlist(["git"], on_change=seen.append)
        assert a.add("git") is False
        assert seen == []

    def test_replace_dedupes_and_persists(self):
        seen: list[list[str]] = []
        a = ShellAllowlist(["git"], on_change=seen.append)
        a.replace(["ls", "ls", "cat", ""])
        assert a.items() == ["ls", "cat"]
        assert seen == [["ls", "cat"]]

    def test_full_command_must_be_both_listed_and_read_only(self):
        a = ShellAllowlist(["ls", "python3"])
        assert a.allows_command("ls -la")
        assert not a.allows_command("python3 -c pass")


class TestAutoAllowable:
    @pytest.mark.parametrize(
        "command",
        [
            "python3 -c pass",
            "bash -c id",
            "env python3 -c pass",
            "sudo ls",
            "timeout 5 sh -c id",
            "npm exec tool",
            "ps eww -p 1",
            "npx tool",
            "uv run script.py",
            "git -c alias.pwn=!id pwn",
            "find . -exec id {} +",
            "find . -delete",
            "date --set=tomorrow",
            "date -stomorrow",
            "hostname attacker",
            "/tmp/ls -la",
            "ls; id",
            "ls $(id)",
        ],
    )
    def test_execution_write_and_escape_forms_require_approval(self, command: str):
        assert not is_auto_allowable(command)

    @pytest.mark.parametrize(
        "command",
        ["ls -la", "grep -n needle file", "date --iso-8601", "find . -name file.py"],
    )
    def test_bounded_read_only_forms_are_eligible(self, command: str):
        assert is_auto_allowable(command)

    def test_unknown_binary_is_not_made_safe_by_allowlist_membership(self):
        allow = ShellAllowlist(["custom-tool"])
        assert allow.is_allowed("custom-tool")
        assert not allow.allows_command("custom-tool --read-only-looking")
