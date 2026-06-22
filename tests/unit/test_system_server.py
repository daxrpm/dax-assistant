"""Tests for the dax-system MCP server's safety primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from dax.mcp_servers.system.server import build_server, safe_path, validate_command

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
        argv = validate_command("/bin/ls -la", {"ls"})
        assert argv[0] == "/bin/ls"

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


def test_build_server_registers_tools():
    server = build_server()
    assert server is not None
    assert server.name == "dax-system"
