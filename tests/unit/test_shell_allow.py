"""Tests for the shell-command allowlist."""

from __future__ import annotations

from dax.core.shell_allow import DEFAULT_SHELL_ALLOW, ShellAllowlist, shell_binary


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
        assert a.is_allowed("git")
        assert set(a.items()) == set(DEFAULT_SHELL_ALLOW)

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
