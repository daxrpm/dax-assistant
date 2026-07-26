"""Installer and release contract tests.

The installer runs as a real subprocess against a fixture release, with
`systemctl`, `uv`, `curl`, `loginctl` and friends replaced by mocks on PATH. That
keeps the tests honest about the script's actual control flow — including paths
that only run when something fails — without touching the host.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.0"

_HEALTHY: dict[str, object] = {
    "status": "ok",
    "instance_id": "authority-1",
    "role": "authoritative",
    "api_protocol": "dax",
    "api_version": 1,
    "liveness": True,
    "readiness": True,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(
    tmp_path: Path, artifacts: list[dict[str, object]], **overrides: object
) -> tuple[Path, Path]:
    document: dict[str, object] = {
        "schema_version": 1,
        "version": VERSION,
        "commit": "a" * 40,
        "api_compatibility": {
            "backend": "1",
            "desktop": "1",
            "android": "1",
            "capability_node": "1",
        },
        "artifacts": artifacts,
    }
    document.update(overrides)
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    checksums = tmp_path / "SHA256SUMS"
    checksums.write_text(f"{_sha256(manifest)}  release-manifest.json\n", encoding="utf-8")
    return manifest, checksums


def _release_fixture(tmp_path: Path, *, arch: str = "x86_64") -> tuple[Path, Path]:
    artifacts: list[dict[str, object]] = []
    for role, name, artifact_arch in (
        ("backend-wheel", f"dax_assistant-{VERSION}-py3-none-any.whl", "any"),
        ("backend-dependency-lock", "backend-requirements.txt", "any"),
        ("backend-service", "dax-assistant.service", "any"),
        ("node-service", "dax-assistant-node.service", "any"),
        ("desktop-rpm", f"Dax-{VERSION}-1.x86_64.rpm", arch),
        ("desktop-deb", f"Dax_{VERSION}_amd64.deb", arch),
    ):
        path = tmp_path / name
        path.write_bytes(f"fixture:{role}\n".encode())
        artifacts.append(
            {
                "role": role,
                "name": name,
                "url": path.as_uri(),
                "arch": artifact_arch,
                "sha256": _sha256(path),
                "size": path.stat().st_size,
            }
        )
    return _write_manifest(tmp_path, artifacts)


def _mock_bin(tmp_path: Path, scripts: dict[str, str]) -> Path:
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir(exist_ok=True)
    # Present the audio libraries as installed and lingering as already on, so
    # no test reaches for sudo unless it means to.
    base = {
        "espeak-ng": "exit 0\n",
        "ldconfig": "printf 'libportaudio.so\\nlibsndfile.so\\n'\nexit 0\n",
        "loginctl": 'if [[ "$1" == show-user ]]; then printf "yes\\n"; fi\nexit 0\n',
        "sudo": 'printf \'%s\\n\' "$*" >> "${DAX_MOCK_SUDO_LOG:-/dev/null}"\nexit 0\n',
    }
    for name, content in {**base, **scripts}.items():
        path = mock_bin / name
        path.write_text(f"#!/usr/bin/env bash\n{content}", encoding="utf-8")
        path.chmod(0o755)
    return mock_bin


def _run_installer(
    tmp_path: Path,
    *arguments: str,
    manifest: Path | str | None = None,
    checksums: Path | None = None,
    distro: str = "fedora",
    arch: str = "x86_64",
    check: bool = True,
    provide_gh: bool = False,
    scripts: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    os_release = tmp_path / f"os-release-{distro}"
    if distro == "fedora":
        os_release.write_text('ID="fedora"\nID_LIKE="fedora"\n', encoding="utf-8")
    else:
        os_release.write_text('ID="debian"\nID_LIKE="debian"\n', encoding="utf-8")

    scripts = dict(scripts or {})
    if provide_gh:
        scripts.setdefault(
            "gh",
            'printf \'%s\\n\' "$*" >> "${DAX_MOCK_GH_LOG:-/dev/null}"\n'
            'if [[ "${DAX_MOCK_GH_FAIL:-0}" == 1 && "$1" == attestation ]]; then exit 1; fi\n'
            "exit 0\n",
        )
    mock_bin = _mock_bin(tmp_path, scripts)

    home = tmp_path / "home"
    env = {
        **os.environ,
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "DAX_OS_RELEASE_FILE": str(os_release),
        "DAX_UNAME_MACHINE": arch,
        "DAX_RELEASE_REPOSITORY": "daxrpm/dax-assistant",
        "PATH": f"{mock_bin}{os.pathsep}{os.environ['PATH']}",
        **(extra_env or {}),
    }
    command = ["bash", "scripts/install.sh", *arguments]
    if manifest is not None:
        command += ["--manifest", str(manifest), "--checksums", str(checksums)]
    return subprocess.run(
        command, cwd=ROOT, check=check, capture_output=True, text=True, env=env
    )


# --------------------------------------------------------------- verification


def test_dry_run_verifies_a_release_without_installing(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path, "--all", "--yes", "--dry-run", manifest=manifest, checksums=checksums
    )
    assert f"Dax {VERSION}" in result.stdout
    assert "nothing installed" in result.stdout
    assert not (tmp_path / "home/.local/share/dax-assistant/releases").exists()


@pytest.mark.parametrize(("distro", "expected"), [("fedora", ".rpm"), ("debian", ".deb")])
def test_dry_run_selects_the_package_for_the_distribution(
    tmp_path: Path, distro: str, expected: str
) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path,
        "--desktop",
        "--yes",
        "--dry-run",
        distro=distro,
        manifest=manifest,
        checksums=checksums,
    )
    assert expected in result.stdout


def test_a_release_without_the_host_architecture_is_refused(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path, arch="aarch64")
    result = _run_installer(
        tmp_path,
        "--desktop",
        "--yes",
        "--dry-run",
        arch="x86_64",
        manifest=manifest,
        checksums=checksums,
        check=False,
    )
    assert result.returncode != 0


def test_the_desktop_package_is_refused_on_an_unpublished_architecture(
    tmp_path: Path,
) -> None:
    # The release carries x86_64 packages; this host is not x86_64. Exercises the
    # architecture check itself rather than artifact lookup falling short.
    manifest, checksums = _release_fixture(tmp_path, arch="x86_64")
    result = _run_installer(
        tmp_path,
        "--desktop",
        "--yes",
        "--dry-run",
        arch="aarch64",
        manifest=manifest,
        checksums=checksums,
        check=False,
    )
    assert result.returncode != 0
    assert "x86_64 only" in result.stderr
    assert "aarch64" in result.stderr


def test_a_tampered_manifest_is_rejected(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    checksums.write_text(f"{'0' * 64}  release-manifest.json\n", encoding="utf-8")
    result = _run_installer(
        tmp_path,
        "--backend",
        "--yes",
        "--dry-run",
        manifest=manifest,
        checksums=checksums,
        check=False,
    )
    assert result.returncode != 0
    assert "does not match the release SHA256SUMS" in result.stderr


def test_a_tampered_artifact_is_rejected(tmp_path: Path) -> None:
    manifest, _ = _release_fixture(tmp_path)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in document["artifacts"]:
        if artifact["role"] == "backend-wheel":
            artifact["sha256"] = "1" * 64
    manifest, checksums = _write_manifest(tmp_path, document["artifacts"])
    result = _run_installer(
        tmp_path,
        "--backend",
        "--yes",
        "--dry-run",
        manifest=manifest,
        checksums=checksums,
        check=False,
    )
    assert result.returncode != 0
    assert "failed its SHA-256 check" in result.stderr


def test_an_artifact_size_that_disagrees_with_the_manifest_is_rejected(
    tmp_path: Path,
) -> None:
    manifest, _ = _release_fixture(tmp_path)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in document["artifacts"]:
        if artifact["role"] == "backend-wheel":
            artifact["size"] = 999_999
    manifest, checksums = _write_manifest(tmp_path, document["artifacts"])
    result = _run_installer(
        tmp_path,
        "--backend",
        "--yes",
        "--dry-run",
        manifest=manifest,
        checksums=checksums,
        check=False,
    )
    assert result.returncode != 0
    assert "the manifest says" in result.stderr


def test_an_incompatible_api_version_is_refused(tmp_path: Path) -> None:
    manifest, _ = _release_fixture(tmp_path)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    compatibility = dict(document["api_compatibility"], backend="99")
    manifest, checksums = _write_manifest(
        tmp_path, document["artifacts"], api_compatibility=compatibility
    )
    result = _run_installer(
        tmp_path,
        "--backend",
        "--yes",
        "--dry-run",
        manifest=manifest,
        checksums=checksums,
        check=False,
    )
    assert result.returncode != 0
    assert "backend API 99" in result.stderr


def test_a_pinned_version_must_match_the_manifest(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path,
        "--backend",
        "--yes",
        "--dry-run",
        "--version",
        "9.9.9",
        manifest=manifest,
        checksums=checksums,
        check=False,
    )
    assert result.returncode != 0
    assert "asked for 9.9.9" in result.stderr


def test_a_local_manifest_installs_without_provenance(tmp_path: Path) -> None:
    # Build provenance attests a published artifact. A manifest handed over on
    # disk was never published, so the digest chain is the whole guarantee and
    # the installer should say so rather than warn about a missing signature.
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path, "--backend", "--yes", "--dry-run", manifest=manifest, checksums=checksums
    )
    assert "provenance does not apply" in result.stdout
    assert "did not verify" not in result.stdout


def test_require_attestation_refuses_a_local_manifest(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path,
        "--backend",
        "--yes",
        "--dry-run",
        "--require-attestation",
        manifest=manifest,
        checksums=checksums,
        check=False,
    )
    assert result.returncode != 0
    assert "cannot apply to a local --manifest" in result.stderr


def test_provenance_is_optional_for_a_published_release_but_can_be_demanded() -> None:
    # The remote path needs a real release to exercise end to end; assert the
    # contract the script encodes: gh is consulted only when present, a failure
    # is a warning by default, and --require-attestation upgrades it to fatal.
    installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
    assert "if ! have gh || ! gh auth status" in installer
    assert "Provenance not checked" in installer
    assert 'die "--require-attestation needs the GitHub CLI, authenticated"' in installer
    assert 'die "build provenance did not verify' in installer


# ------------------------------------------------------------------ installs


def _backend_install(
    tmp_path: Path,
    health: dict[str, object],
    *,
    arguments: tuple[str, ...] = (),
    service_active: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    manifest, checksums = _release_fixture(tmp_path)
    health_path = tmp_path / "health.json"
    health_path.write_text(json.dumps(health), encoding="utf-8")

    scripts = {
        "sleep": "exit 0\n",
        "curl": 'command cat "$DAX_MOCK_HEALTH_JSON"\n',
        "systemctl": (
            'printf \'%s\\n\' "$*" >> "$DAX_MOCK_SYSTEMCTL_LOG"\n'
            'if [[ "$*" == *"is-active --quiet dax-assistant-node.service"* ]]; then exit 1; fi\n'
            'if [[ "$*" == *"is-active --quiet dax-assistant.service"* ]]; then\n'
            '  [[ "$DAX_MOCK_SERVICE_ACTIVE" == 1 ]] || exit 1\n'
            "fi\n"
            "exit 0\n"
        ),
        "uv": (
            'printf \'%s\\n\' "$*" >> "${DAX_MOCK_UV_LOG:-/dev/null}"\n'
            'if [[ "$1 $2" == "python find" ]]; then printf \'%s\\n\' /usr/bin/python3; fi\n'
            'if [[ "$1" == venv ]]; then mkdir -p "${@: -1}/bin"; fi\n'
            "exit 0\n"
        ),
    }

    home = tmp_path / "home"
    previous = home / ".local/share/dax-assistant/releases/0.0.9"
    (previous / ".venv/bin").mkdir(parents=True)
    current = previous.parent.parent / "current"
    current.symlink_to(previous)

    result = _run_installer(
        tmp_path,
        "--backend",
        "--yes",
        "--no-account",
        *arguments,
        manifest=manifest,
        checksums=checksums,
        scripts=scripts,
        check=False,
        extra_env={
            "DAX_READINESS_TIMEOUT_SECONDS": "1",
            "DAX_MOCK_SYSTEMCTL_LOG": str(tmp_path / "systemctl.log"),
            "DAX_MOCK_HEALTH_JSON": str(health_path),
            "DAX_MOCK_SERVICE_ACTIVE": "1" if service_active else "0",
            "DAX_MOCK_SUDO_LOG": str(tmp_path / "sudo.log"),
            "DAX_MOCK_UV_LOG": str(tmp_path / "uv.log"),
        },
    )
    return result, current, previous


def test_a_ready_backend_becomes_the_current_release(tmp_path: Path) -> None:
    result, current, _ = _backend_install(tmp_path, _HEALTHY)
    assert result.returncode == 0, result.stderr
    assert current.resolve().name == VERSION
    # Dependencies come from the release's hash-locked file, never re-resolved.
    assert "--require-hashes" in (tmp_path / "uv.log").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "missing",
    ["status", "role", "api_protocol", "api_version", "liveness", "readiness", "instance_id"],
)
def test_an_incomplete_health_contract_is_not_readiness(tmp_path: Path, missing: str) -> None:
    health = dict(_HEALTHY)
    health.pop(missing)
    result, current, previous = _backend_install(tmp_path, health)
    assert result.returncode != 0
    # An unready release must never be left as the current target.
    assert current.resolve() == previous.resolve()


def test_a_backend_that_never_becomes_ready_restores_its_predecessor(tmp_path: Path) -> None:
    result, current, previous = _backend_install(tmp_path, dict(_HEALTHY, readiness=False))
    assert result.returncode != 0
    assert "never became ready" in result.stderr
    assert current.resolve() == previous.resolve()
    assert "restart dax-assistant.service" in (tmp_path / "systemctl.log").read_text(
        encoding="utf-8"
    )


def test_a_stopped_service_cannot_be_masked_by_a_stale_health_listener(
    tmp_path: Path,
) -> None:
    # Something else answering on the port must not count as our backend being up.
    result, current, previous = _backend_install(tmp_path, _HEALTHY, service_active=False)
    assert result.returncode != 0
    assert current.resolve() == previous.resolve()


def test_installing_never_escalates_when_audio_libraries_are_present(tmp_path: Path) -> None:
    result, _, _ = _backend_install(tmp_path, _HEALTHY)
    assert result.returncode == 0
    sudo_log = tmp_path / "sudo.log"
    assert not sudo_log.exists() or not sudo_log.read_text(encoding="utf-8").strip()
    assert "already present" in result.stdout


def test_retention_prunes_old_releases_but_never_the_active_one(tmp_path: Path) -> None:
    releases = tmp_path / "home/.local/share/dax-assistant/releases"
    for version in ("0.0.1", "0.0.2", "0.0.3", "0.0.4"):
        (releases / version).mkdir(parents=True)
    result, current, _ = _backend_install(tmp_path, _HEALTHY, arguments=("--keep", "2"))
    assert result.returncode == 0
    remaining = sorted(path.name for path in releases.iterdir())
    assert VERSION in remaining
    assert "0.0.1" not in remaining
    assert current.resolve().name == VERSION


def test_the_node_installs_stopped_and_never_starts_an_authority(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    scripts = {
        "systemctl": (
            'printf \'%s\\n\' "$*" >> "$DAX_MOCK_SYSTEMCTL_LOG"\n'
            'if [[ "$*" == *"is-active"* || "$*" == *"is-enabled"* ]]; then exit 1; fi\n'
            "exit 0\n"
        ),
        "uv": (
            'if [[ "$1 $2" == "python find" ]]; then printf \'%s\\n\' /usr/bin/python3; fi\n'
            'if [[ "$1" == venv ]]; then mkdir -p "${@: -1}/bin"; fi\n'
            "exit 0\n"
        ),
    }
    log = tmp_path / "systemctl.log"
    result = _run_installer(
        tmp_path,
        "--node",
        "--yes",
        manifest=manifest,
        checksums=checksums,
        scripts=scripts,
        check=False,
        extra_env={"DAX_MOCK_SYSTEMCTL_LOG": str(log)},
    )
    assert result.returncode == 0, result.stderr
    home = tmp_path / "home"
    assert (home / ".config/systemd/user/dax-assistant-node.service").exists()
    assert not (home / ".config/systemd/user/dax-assistant.service").exists()
    assert (home / ".local/share/dax-assistant/node-current").is_symlink()
    commands = log.read_text(encoding="utf-8")
    assert "enable --now dax-assistant-node.service" not in commands
    assert "start dax-assistant-node.service" not in commands
    assert "dax-assistant.service" not in commands


def test_the_node_unit_uses_a_runtime_separate_from_the_authority() -> None:
    node_unit = (ROOT / "systemd/dax-assistant-node.service").read_text(encoding="utf-8")
    assert "/node-current/.venv/bin/dax edge run" in node_unit
    assert "/current/.venv/bin/dax edge run" not in node_unit
    assert "ConditionPathExists=" in node_unit


# ----------------------------------------------------------------- lifecycle


def _installed_home(tmp_path: Path, versions: tuple[str, ...], active: str) -> Path:
    home = tmp_path / "home"
    releases = home / ".local/share/dax-assistant/releases"
    for version in versions:
        binaries = releases / version / ".venv/bin"
        binaries.mkdir(parents=True, exist_ok=True)
        (binaries / "python").write_text("", encoding="utf-8")
        (binaries / "python").chmod(0o755)
    current = releases.parent / "current"
    if current.is_symlink():
        current.unlink()
    current.symlink_to(releases / active)
    units = home / ".config/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    (units / "dax-assistant.service").write_text("[Unit]\n", encoding="utf-8")
    state = home / ".local/state/dax-assistant"
    state.mkdir(parents=True, exist_ok=True)
    # A real database, because the installer backs it up with sqlite3's backup
    # API and refuses to continue if that fails.
    connection = sqlite3.connect(state / "dax.db")
    connection.execute("CREATE TABLE IF NOT EXISTS marker (id INTEGER)")
    connection.commit()
    connection.close()
    (state / "dax.key").write_text("key", encoding="utf-8")
    return home


def _run_lifecycle(
    tmp_path: Path,
    *arguments: str,
    health: dict[str, object] | None = None,
    service_active: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    health_path = tmp_path / "health.json"
    health_path.write_text(json.dumps(health or _HEALTHY), encoding="utf-8")
    scripts = {
        "sleep": "exit 0\n",
        "curl": 'command cat "$DAX_MOCK_HEALTH_JSON"\n',
        "systemctl": (
            'printf \'%s\\n\' "$*" >> "$DAX_MOCK_SYSTEMCTL_LOG"\n'
            'if [[ "$*" == *"is-active --quiet dax-assistant.service"* ]]; then\n'
            '  [[ "$DAX_MOCK_SERVICE_ACTIVE" == 1 ]] || exit 1\n'
            "fi\n"
            "exit 0\n"
        ),
    }
    return _run_installer(
        tmp_path,
        *arguments,
        scripts=scripts,
        check=check,
        extra_env={
            "DAX_READINESS_TIMEOUT_SECONDS": "1",
            "DAX_MOCK_SYSTEMCTL_LOG": str(tmp_path / "systemctl.log"),
            "DAX_MOCK_HEALTH_JSON": str(health_path),
            "DAX_MOCK_SERVICE_ACTIVE": "1" if service_active else "0",
            "DAX_MOCK_GH_LOG": str(tmp_path / "gh.log"),
        },
    )


def test_list_marks_the_active_release_and_orders_newest_first(tmp_path: Path) -> None:
    _installed_home(tmp_path, ("0.1.0", "0.2.0", "0.10.0"), active="0.2.0")
    result = _run_lifecycle(tmp_path, "list", check=True)
    # The pointer install.sh puts beside the active release.
    marker = "\u276f"
    versions = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and line.strip()[0] in marker + "0123456789"
    ]
    # 0.10.0 sorts above 0.2.0 numerically, not lexically.
    assert versions[0].startswith("0.10.0")
    assert any("0.2.0" in line and "active" in line for line in versions)


def test_status_reports_the_active_release_and_readiness(tmp_path: Path) -> None:
    _installed_home(tmp_path, ("0.2.0",), active="0.2.0")
    result = _run_lifecycle(tmp_path, "status", check=True)
    assert "0.2.0" in result.stdout
    assert "ready" in result.stdout


def test_lifecycle_commands_never_reach_the_network(tmp_path: Path) -> None:
    _installed_home(tmp_path, ("0.1.0", "0.2.0"), active="0.2.0")
    for command in ("list", "status"):
        result = _run_lifecycle(tmp_path, command, check=True)
        assert "github.com" not in result.stdout
    assert not (tmp_path / "gh.log").exists()


def test_rollback_defaults_to_the_newest_inactive_release(tmp_path: Path) -> None:
    home = _installed_home(tmp_path, ("0.1.0", "0.2.0", "0.3.0"), active="0.3.0")
    result = _run_lifecycle(tmp_path, "rollback", "--yes", check=True)
    assert (home / ".local/share/dax-assistant/current").resolve().name == "0.2.0"
    assert "now running 0.2.0" in result.stdout


def test_rollback_backs_up_the_database_and_its_key(tmp_path: Path) -> None:
    home = _installed_home(tmp_path, ("0.1.0", "0.2.0"), active="0.2.0")
    _run_lifecycle(tmp_path, "rollback", "--yes", check=True)
    backups = list((home / ".local/state/dax-assistant/backups").iterdir())
    # The database is unreadable without the key that decrypts its secrets.
    assert any(path.suffix == ".db" for path in backups)
    assert any(path.suffix == ".key" for path in backups)


def test_rollback_restores_the_previous_release_when_the_older_one_fails(
    tmp_path: Path,
) -> None:
    home = _installed_home(tmp_path, ("0.1.0", "0.2.0"), active="0.2.0")
    result = _run_lifecycle(
        tmp_path, "rollback", "--yes", health=dict(_HEALTHY, readiness=False)
    )
    assert result.returncode != 0
    assert (home / ".local/share/dax-assistant/current").resolve().name == "0.2.0"


def test_rollback_rejects_an_uninstalled_or_already_active_release(tmp_path: Path) -> None:
    _installed_home(tmp_path, ("0.1.0", "0.2.0"), active="0.2.0")
    missing = _run_lifecycle(tmp_path, "rollback", "9.9.9", "--yes")
    assert missing.returncode != 0
    assert "not installed" in missing.stderr

    active = _run_lifecycle(tmp_path, "rollback", "0.2.0", "--yes")
    assert active.returncode != 0
    assert "already active" in active.stderr


def test_uninstall_keeps_the_database_unless_purge_is_asked_for(tmp_path: Path) -> None:
    home = _installed_home(tmp_path, ("0.2.0",), active="0.2.0")
    state = home / ".local/state/dax-assistant"
    _run_lifecycle(tmp_path, "uninstall", "--yes", check=True)
    assert (state / "dax.db").exists()
    assert not (home / ".local/share/dax-assistant/releases").exists()

    _installed_home(tmp_path, ("0.2.0",), active="0.2.0")
    _run_lifecycle(tmp_path, "uninstall", "--purge", "--yes", check=True)
    assert not state.exists()


def test_destructive_commands_refuse_to_assume_consent(tmp_path: Path) -> None:
    _installed_home(tmp_path, ("0.1.0", "0.2.0"), active="0.2.0")
    # No TTY and no --yes: the only safe answer is to stop.
    for command in ("uninstall", "rollback"):
        result = _run_lifecycle(tmp_path, command)
        assert result.returncode != 0
        assert "refusing to assume" in result.stderr


def test_purge_is_rejected_outside_uninstall(tmp_path: Path) -> None:
    result = _run_lifecycle(tmp_path, "rollback", "--purge", "--yes")
    assert result.returncode != 0
    assert "--purge only applies to uninstall" in result.stderr


# ------------------------------------------------------------- release checks


def test_readme_documents_the_unpinned_install_path() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # A reader must not have to discover a version number before installing.
    assert "releases/latest/download/install.sh" in readme
    assert "bash install.sh" in readme


def test_documented_versions_cannot_drift_from_the_release() -> None:
    guarded = ROOT / "docs/deployment.md"
    original = guarded.read_text(encoding="utf-8")
    try:
        guarded.write_text(original + "\nVERSION=0.0.1\n", encoding="utf-8")
        result = subprocess.run(
            ["python3", "scripts/release.py", "check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "docs/deployment.md=0.0.1" in result.stderr
    finally:
        guarded.write_text(original, encoding="utf-8")


@pytest.mark.parametrize("output", [".", "..", "~", "/"])
def test_release_output_rejects_unsafe_deletion_targets(output: str) -> None:
    target = str(Path.home()) if output == "~" else output
    result = subprocess.run(
        [
            "python3",
            "scripts/release.py",
            "build",
            "--output",
            target,
            "--skip-desktop",
            "--skip-android",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_REF_NAME": "main", "GITHUB_REF_TYPE": "branch"},
    )
    assert result.returncode != 0
    assert "--output must be a descendant" in result.stderr


def test_release_output_rejects_dist_root() -> None:
    result = subprocess.run(
        ["python3", "scripts/release.py", "build", "--output", "dist"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_REF_NAME": "main", "GITHUB_REF_TYPE": "branch"},
    )
    assert result.returncode != 0
    assert "--output may not be the dist directory itself" in result.stderr


def test_installer_keeps_its_supply_chain_and_recovery_guarantees() -> None:
    installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
    release = (ROOT / "scripts/release.py").read_text(encoding="utf-8")
    # Dependencies come from the release's hash-locked file, never re-resolved.
    assert "uv export" not in installer
    assert "--require-hashes" in installer
    assert "--no-deps" in installer
    # Units are shipped artifacts, not text the installer writes itself.
    assert 'install -m 600 "$unit" "$BACKEND_UNIT"' in installer
    assert 'cat > "$BACKEND_UNIT"' not in installer
    # A failed upgrade must be able to put the previous release back.
    assert "restore_backend" in installer
    assert "authoritative" in installer
    # Without lingering the backend dies at logout on a headless server.
    assert "enable-linger" in installer
    assert '"uv",\n        "export"' in release


def test_all_external_actions_are_pinned_to_full_commit_shas() -> None:
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("- uses:") and "./" not in stripped:
                reference = stripped.split("@", 1)[1].split()[0]
                assert len(reference) == 40
                assert all(character in "0123456789abcdef" for character in reference)


def test_android_release_requires_expected_signer_identity() -> None:
    release = (ROOT / "scripts/release.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "DAX_ANDROID_CERT_SHA256" in release
    assert "Android signer certificate mismatch" in release
    assert "secrets.DAX_ANDROID_CERT_SHA256" in workflow


def test_installer_scripts_parse_and_versions_match() -> None:
    subprocess.run(["bash", "-n", "scripts/install.sh"], cwd=ROOT, check=True)
    subprocess.run(["bash", "-n", "scripts/install-service.sh"], cwd=ROOT, check=True)
    subprocess.run(["python3", "scripts/release.py", "check"], cwd=ROOT, check=True)
