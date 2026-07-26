"""Tests for the dax-system MCP server's safety primitives."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from dax.mcp_servers.system.server import (
    _command_environment,
    _completed_command_output,
    _launch_application,
    _resolve_application,
    build_server,
    configured_shell_allowlist,
    safe_path,
    validate_command,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestSafePath:
    def test_within_root(self, tmp_path: Path):
        p = safe_path(str(tmp_path / "sub" / "file.txt"), [tmp_path])
        assert str(p).startswith(str(tmp_path))

    def test_root_itself(self, tmp_path: Path):
        assert safe_path(str(tmp_path), [tmp_path]) == tmp_path.resolve()

    def test_escape_absolute(self, tmp_path: Path):
        with pytest.raises(ValueError, match="outside"):
            safe_path("/etc/passwd", [tmp_path])

    def test_escape_traversal(self, tmp_path: Path):
        with pytest.raises(ValueError, match="outside"):
            safe_path(str(tmp_path / ".." / "secret"), [tmp_path])


class TestValidateCommand:
    def test_allowed(self):
        argv = validate_command("ls -la /home", {"ls"})
        assert argv[0] == "ls"
        assert "-la" in argv

    def test_binary_path_basename_checked(self):
        with pytest.raises(ValueError, match="allowlist"):
            validate_command("/bin/ls -la", {"ls"})

    def test_not_in_allowlist(self):
        with pytest.raises(ValueError, match="allowlist"):
            validate_command("rm -rf /", {"ls"})

    def test_rejects_metacharacters(self):
        with pytest.raises(ValueError, match="metacharacters"):
            validate_command("ls; rm -rf /", {"ls", "rm"})

    def test_rejects_pipe(self):
        with pytest.raises(ValueError, match="metacharacters"):
            validate_command("ls | grep x", {"ls", "grep"})

    def test_empty(self):
        with pytest.raises(ValueError, match="Empty"):
            validate_command("   ", {"ls"})

    def test_execution_does_not_inherit_user_controlled_path(self, monkeypatch):
        monkeypatch.setenv("PATH", "/tmp/attacker-bin")
        assert _command_environment()["PATH"] != "/tmp/attacker-bin"

    def test_explicit_empty_node_allowlist_disables_shell(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DAX_SYSTEM_SHELL_ALLOW", "")
        allowlist = configured_shell_allowlist()
        assert allowlist == set()
        with pytest.raises(ValueError, match="allowlist"):
            validate_command("ls", allowlist)

    def test_unconfigured_local_backend_keeps_separate_approval_semantics(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DAX_SYSTEM_SHELL_ALLOW", raising=False)
        assert configured_shell_allowlist() is None
        assert validate_command("custom-approved-tool --version") == [
            "custom-approved-tool",
            "--version",
        ]


class TestCommandResult:
    def test_nonzero_exit_is_a_tool_error(self):
        proc = subprocess.CompletedProcess(
            ["flatpak"], 1, stdout="", stderr="bwrap: Operation not permitted"
        )

        with pytest.raises(RuntimeError, match="bwrap: Operation not permitted"):
            _completed_command_output(proc)

    def test_zero_exit_returns_output(self):
        proc = subprocess.CompletedProcess(["which"], 0, stdout="/usr/bin/which\n", stderr="")

        assert _completed_command_output(proc) == "/usr/bin/which\n\n[exit 0]"


class TestApplicationLaunch:
    @staticmethod
    def _desktop_file(directory: Path, desktop_id: str, name: str) -> None:
        directory.mkdir(exist_ok=True)
        (directory / f"{desktop_id}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName={name}\n",
            encoding="utf-8",
        )

    def test_resolves_human_name_to_desktop_id(self, tmp_path: Path):
        self._desktop_file(tmp_path, "com.spotify.Client", "Spotify")

        assert _resolve_application("spotify", [tmp_path]) == (
            "com.spotify.Client",
            "Spotify",
        )

    def test_rejects_ambiguous_partial_name(self, tmp_path: Path):
        tmp_path.mkdir(exist_ok=True)
        for desktop_id, name in (("org.foo.Music", "Music"), ("org.bar.Music", "Music Box")):
            (tmp_path / f"{desktop_id}.desktop").write_text(
                f"[Desktop Entry]\nType=Application\nName={name}\n",
                encoding="utf-8",
            )

        with pytest.raises(ValueError, match="ambiguous"):
            _resolve_application("mus", [tmp_path])

    def test_launches_resolved_app_outside_the_node_scope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._desktop_file(tmp_path, "com.spotify.Client", "Spotify")
        seen: list[list[str]] = []

        monkeypatch.setattr(
            "dax.mcp_servers.system.server.shutil.which",
            lambda command: f"/usr/bin/{command}",
        )

        def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr("dax.mcp_servers.system.server.subprocess.run", run)

        assert _launch_application("Spotify", [tmp_path]) == (
            "Started Spotify (com.spotify.Client)"
        )
        assert seen == [
            [
                "/usr/bin/systemd-run",
                "--user",
                "--collect",
                "--quiet",
                "--property=Type=exec",
                "--property=ExitType=cgroup",
                "/usr/bin/gtk-launch",
                "com.spotify.Client",
            ]
        ]


def test_build_server_registers_tools():
    server = build_server()
    assert server is not None
    assert server.name == "dax-system"
