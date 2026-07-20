"""Release and installer contract tests."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _release_fixture(tmp_path: Path, *, arch: str = "x86_64") -> tuple[Path, Path]:
    artifacts = []
    for role, name, artifact_arch in (
        ("backend-wheel", "dax_assistant-0.1.0-py3-none-any.whl", "any"),
        ("backend-dependency-lock", "backend-requirements.txt", "any"),
        ("backend-service", "dax-assistant.service", "any"),
        ("node-service", "dax-assistant-node.service", "any"),
        ("desktop-rpm", "Dax-0.1.0-1.x86_64.rpm", arch),
        ("desktop-deb", "Dax_0.1.0_amd64.deb", arch),
        ("android-apk", "Dax-0.1.0.apk", "universal"),
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
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "version": "0.1.0",
                "commit": "a" * 40,
                "api_compatibility": {
                    "backend": "1",
                    "desktop": "1",
                    "android": "1",
                    "capability_node": "1",
                },
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )
    checksums = tmp_path / "SHA256SUMS"
    checksums.write_text(f"{_sha256(manifest)}  release-manifest.json\n", encoding="utf-8")
    return manifest, checksums


def _run_installer(
    tmp_path: Path,
    manifest: Path,
    checksums: Path,
    distro: str,
    *arguments: str,
    arch: str = "x86_64",
    check: bool = True,
    fail_attestation: bool = False,
    tag_commit: str = "a" * 40,
    provide_gh: bool = True,
    dry_run: bool = True,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    os_release = tmp_path / f"os-release-{distro}"
    if distro == "fedora":
        os_release.write_text('ID="fedora"\nID_LIKE="fedora"\n', encoding="utf-8")
    else:
        os_release.write_text('ID="debian"\nID_LIKE="debian"\n', encoding="utf-8")
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir(exist_ok=True)
    if provide_gh:
        gh = mock_bin / "gh"
        gh.write_text(
            "#!/usr/bin/env bash\n"
            'printf \'%s\\n\' "$*" >> "$DAX_MOCK_GH_LOG"\n'
            'if [[ "${DAX_MOCK_GH_FAIL:-0}" == 1 && "${1:-}" == attestation ]]; then exit 1; fi\n'
            'if [[ "${1:-}" == api ]]; then\n'
            "  printf '%s\\n' \"${DAX_MOCK_TAG_COMMIT:-"
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}"\n'
            "fi\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "XDG_DATA_HOME": str(tmp_path / "home/.local/share"),
        "XDG_STATE_HOME": str(tmp_path / "home/.local/state"),
        "XDG_CACHE_HOME": str(tmp_path / "home/.cache"),
        "XDG_CONFIG_HOME": str(tmp_path / "home/.config"),
        "DAX_OS_RELEASE_FILE": str(os_release),
        "DAX_UNAME_MACHINE": arch,
        "DAX_RELEASE_REPOSITORY": "daxrpm/dax-assistant",
        "DAX_MOCK_GH_LOG": str(tmp_path / "gh.log"),
        "DAX_MOCK_GH_FAIL": "1" if fail_attestation else "0",
        "DAX_MOCK_TAG_COMMIT": tag_commit,
        "DAX_GH_COMMAND": "gh" if provide_gh else "dax-missing-gh",
        "PATH": f"{mock_bin}{os.pathsep}{os.environ['PATH']}",
        **(extra_env or {}),
    }
    command = [
        "bash",
        "scripts/install.sh",
        "--manifest",
        str(manifest),
        "--checksums",
        str(checksums),
        "--yes",
        "--version",
        "0.1.0",
    ]
    if dry_run:
        command.append("--dry-run")
    command.extend(arguments)
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def test_installer_dry_run_selects_fedora_rpm_and_both_components(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(tmp_path, manifest, checksums, "fedora", "--both")
    assert "Distribution: rpm" in result.stdout
    assert "backend wheel" in result.stdout
    assert "desktop-rpm" not in result.stdout
    assert ".rpm" in result.stdout
    assert "Android" not in result.stdout


def test_installer_dry_run_selects_debian_deb(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(tmp_path, manifest, checksums, "debian", "--desktop-only")
    assert "Distribution: deb" in result.stdout
    assert "apt-get install desktop" in result.stdout
    assert ".deb" in result.stdout
    assert "backend wheel" not in result.stdout


def test_installer_rejects_manifest_hash_mismatch(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    checksums.write_text(f"{'0' * 64}  release-manifest.json\n", encoding="utf-8")
    result = _run_installer(tmp_path, manifest, checksums, "fedora", check=False)
    assert result.returncode != 0
    assert "SHA256 mismatch for release-manifest.json" in result.stderr


def test_installer_fails_closed_when_attestation_verification_fails(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path, manifest, checksums, "fedora", check=False, fail_attestation=True
    )
    assert result.returncode != 0
    assert "attestation verification failed for release-manifest.json" in result.stderr


def test_installer_fails_closed_when_gh_is_unavailable(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(tmp_path, manifest, checksums, "fedora", check=False, provide_gh=False)
    assert result.returncode != 0
    assert "gh is required for release attestation verification" in result.stderr


def test_installer_attestation_bypass_is_explicit_and_loud(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path,
        manifest,
        checksums,
        "fedora",
        "--insecure-skip-attestation",
        fail_attestation=True,
    )
    assert "[WARNING] INSECURE" in result.stderr
    assert "release-manifest.json" in result.stderr


def test_installer_attests_manifest_lock_units_and_installed_artifacts(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    _run_installer(tmp_path, manifest, checksums, "fedora", "--backend-only", "--with-node")
    calls = (tmp_path / "gh.log").read_text(encoding="utf-8")
    for name in (
        "release-manifest.json",
        "backend-requirements.txt",
        "dax-assistant.service",
        "dax-assistant-node.service",
        ".whl",
    ):
        assert name in calls
    assert calls.count("attestation verify") == 5


def test_installer_rejects_release_without_host_architecture(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path, arch="aarch64")
    result = _run_installer(tmp_path, manifest, checksums, "fedora", arch="x86_64", check=False)
    assert result.returncode != 0
    assert "release does not support x86_64/rpm" in result.stderr


def test_node_unit_is_never_auto_started(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path, manifest, checksums, "fedora", "--backend-only", "--with-node"
    )
    assert "without enabling or starting it" in result.stdout
    installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
    assert "enable --now dax-assistant-node" not in installer
    node_unit = (ROOT / "systemd/dax-assistant-node.service").read_text(encoding="utf-8")
    assert "ConditionPathExists=" in node_unit


def test_node_only_selects_runtime_without_backend_service(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(tmp_path, manifest, checksums, "fedora", "--node-only")
    calls = (tmp_path / "gh.log").read_text(encoding="utf-8")
    assert "capability-node runtime wheel" in result.stdout
    assert "without enabling or starting it" in result.stdout
    assert "dax-assistant-node.service" in calls
    assert "dax-assistant.service" not in calls
    assert ".rpm" not in result.stdout


def test_node_unit_uses_separate_runtime_from_authority() -> None:
    node_unit = (ROOT / "systemd/dax-assistant-node.service").read_text(encoding="utf-8")
    assert "/node-current/.venv/bin/dax edge run" in node_unit
    assert "/current/.venv/bin/dax edge run" not in node_unit


def test_node_only_install_never_installs_or_starts_an_authority(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    for name, content in {
        "sudo": "exit 0\n",
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
    }.items():
        path = mock_bin / name
        path.write_text(f"#!/usr/bin/env bash\n{content}", encoding="utf-8")
        path.chmod(0o755)

    systemctl_log = tmp_path / "systemctl.log"
    result = _run_installer(
        tmp_path,
        manifest,
        checksums,
        "fedora",
        "--node-only",
        dry_run=False,
        check=False,
        extra_env={"DAX_MOCK_SYSTEMCTL_LOG": str(systemctl_log)},
    )

    home = tmp_path / "home"
    assert result.returncode == 0, result.stderr
    assert not (home / ".config/systemd/user/dax-assistant.service").exists()
    assert (home / ".config/systemd/user/dax-assistant-node.service").exists()
    assert (home / ".local/share/dax-assistant/node-current").is_symlink()
    calls = systemctl_log.read_text(encoding="utf-8")
    assert "dax-assistant.service" not in calls
    assert "enable --now dax-assistant-node.service" not in calls


def test_manifest_version_is_bound_to_selected_tag(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path, manifest, checksums, "fedora", "--version", "0.2.0", check=False
    )
    assert result.returncode != 0
    assert "does not match --version 0.2.0" in result.stderr


def test_manifest_commit_is_bound_to_selected_tag(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    result = _run_installer(
        tmp_path, manifest, checksums, "fedora", check=False, tag_commit="b" * 40
    )
    assert result.returncode != 0
    assert "does not match tag v0.1.0" in result.stderr


def test_readiness_failure_restores_previous_backend_and_service(tmp_path: Path) -> None:
    manifest, checksums = _release_fixture(tmp_path)
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    for name, content in {
        "sudo": "exit 0\n",
        "systemctl": (
            'printf \'%s\\n\' "$*" >> "$DAX_MOCK_SYSTEMCTL_LOG"\n'
            'if [[ "$*" == *"is-active --quiet dax-assistant.service"* ]]; then exit 0; fi\n'
            'if [[ "$*" == *"is-enabled --quiet dax-assistant.service"* ]]; then exit 0; fi\n'
            'if [[ "$*" == *"is-active"* || "$*" == *"is-enabled"* ]]; then exit 1; fi\n'
            "exit 0\n"
        ),
        "uv": (
            'printf \'%s\\n\' "$*" >> "$DAX_MOCK_UV_LOG"\n'
            'if [[ "$1 $2" == "python find" ]]; then printf \'%s\\n\' /usr/bin/python3; fi\n'
            'if [[ "$1" == venv ]]; then mkdir -p "${@: -1}/bin"; fi\n'
            "exit 0\n"
        ),
    }.items():
        path = mock_bin / name
        path.write_text(f"#!/usr/bin/env bash\n{content}", encoding="utf-8")
        path.chmod(0o755)

    home = tmp_path / "home"
    previous = home / ".local/share/dax-assistant/releases/0.0.9"
    previous.mkdir(parents=True)
    current = previous.parent.parent / "current"
    current.symlink_to(previous)
    result = _run_installer(
        tmp_path,
        manifest,
        checksums,
        "fedora",
        "--backend-only",
        dry_run=False,
        check=False,
        extra_env={
            "DAX_READINESS_TIMEOUT_SECONDS": "0",
            "DAX_MOCK_SYSTEMCTL_LOG": str(tmp_path / "systemctl.log"),
            "DAX_MOCK_UV_LOG": str(tmp_path / "uv.log"),
        },
    )
    assert result.returncode != 0
    assert current.resolve() == previous
    assert "restored the previous current target and service" in result.stderr
    assert "restart dax-assistant.service" in (tmp_path / "systemctl.log").read_text()
    assert "--require-hashes" in (tmp_path / "uv.log").read_text()


def _run_mocked_backend_upgrade(
    tmp_path: Path,
    health: dict[str, object],
    *,
    service_active_after_restart: bool = True,
    deactivate_after_health: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    manifest, checksums = _release_fixture(tmp_path)
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    health_path = tmp_path / "health.json"
    health_path.write_text(json.dumps(health), encoding="utf-8")
    for name, content in {
        "sudo": "exit 0\n",
        "sleep": "exit 0\n",
        "curl": (
            'touch "$DAX_MOCK_HEALTH_CALLED"\n'
            'command cat "$DAX_MOCK_HEALTH_JSON"\n'
        ),
        "systemctl": (
            'printf \'%s\\n\' "$*" >> "$DAX_MOCK_SYSTEMCTL_LOG"\n'
            'if [[ "$*" == *"is-active --quiet dax-assistant-node.service"* || '
            '"$*" == *"is-enabled --quiet dax-assistant-node.service"* ]]; then exit 1; fi\n'
            'if [[ "$*" == *"is-active --quiet dax-assistant.service"* ]]; then\n'
            '  count=0\n'
            '  [[ ! -f "$DAX_MOCK_ACTIVE_COUNT" ]] || '
            'count="$(<"$DAX_MOCK_ACTIVE_COUNT")"\n'
            '  count=$((count + 1)); printf \'%s\' "$count" > "$DAX_MOCK_ACTIVE_COUNT"\n'
            '  [[ "$count" -eq 1 ]] && exit 0\n'
            '  [[ "$DAX_MOCK_SERVICE_ACTIVE" == 1 ]] || exit 1\n'
            '  [[ "$DAX_MOCK_DEACTIVATE_AFTER_HEALTH" != 1 || ! -f "$DAX_MOCK_HEALTH_CALLED" ]]\n'
            '  exit\n'
            'fi\n'
            'if [[ "$*" == *"is-enabled --quiet dax-assistant.service"* ]]; then exit 0; fi\n'
            "exit 0\n"
        ),
        "uv": (
            'if [[ "$1 $2" == "python find" ]]; then printf \'%s\\n\' /usr/bin/python3; fi\n'
            'if [[ "$1" == venv ]]; then mkdir -p "${@: -1}/bin"; fi\n'
            "exit 0\n"
        ),
    }.items():
        path = mock_bin / name
        path.write_text(f"#!/usr/bin/env bash\n{content}", encoding="utf-8")
        path.chmod(0o755)

    home = tmp_path / "home"
    previous = home / ".local/share/dax-assistant/releases/0.0.9"
    previous.mkdir(parents=True)
    current = previous.parent.parent / "current"
    current.symlink_to(previous)
    result = _run_installer(
        tmp_path,
        manifest,
        checksums,
        "fedora",
        "--backend-only",
        dry_run=False,
        check=False,
        extra_env={
            "DAX_READINESS_TIMEOUT_SECONDS": "1",
            "DAX_MOCK_SYSTEMCTL_LOG": str(tmp_path / "systemctl.log"),
            "DAX_MOCK_ACTIVE_COUNT": str(tmp_path / "active-count"),
            "DAX_MOCK_HEALTH_JSON": str(health_path),
            "DAX_MOCK_HEALTH_CALLED": str(tmp_path / "health-called"),
            "DAX_MOCK_SERVICE_ACTIVE": "1" if service_active_after_restart else "0",
            "DAX_MOCK_DEACTIVATE_AFTER_HEALTH": "1" if deactivate_after_health else "0",
        },
    )
    return result, current, previous


def test_upgrade_accepts_complete_health_contract_from_active_service(tmp_path: Path) -> None:
    result, current, previous = _run_mocked_backend_upgrade(
        tmp_path,
        {
            "status": "ok",
            "liveness": True,
            "readiness": True,
            "role": "authoritative",
            "api_protocol": "dax",
            "api_version": 1,
            "instance_id": "instance-1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert current.resolve() != previous


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("status", "starting"),
        ("liveness", False),
        ("readiness", False),
        ("role", "edge"),
        ("api_protocol", "foreign"),
        ("api_version", 2),
        ("instance_id", ""),
    ],
)
def test_upgrade_rejects_incomplete_health_contract(
    tmp_path: Path, field: str, invalid: object
) -> None:
    health: dict[str, object] = {
        "status": "ok",
        "liveness": True,
        "readiness": True,
        "role": "authoritative",
        "api_protocol": "dax",
        "api_version": 1,
        "instance_id": "instance-1",
    }
    health[field] = invalid

    result, current, previous = _run_mocked_backend_upgrade(
        tmp_path, health, deactivate_after_health=True
    )

    assert result.returncode != 0
    assert current.resolve() == previous
    assert "restored the previous current target and service" in result.stderr


def test_stale_health_listener_cannot_mask_failed_service_restart(tmp_path: Path) -> None:
    result, current, previous = _run_mocked_backend_upgrade(
        tmp_path,
        {
            "status": "ok",
            "liveness": True,
            "readiness": True,
            "role": "authoritative",
            "api_protocol": "dax",
            "api_version": 1,
            "instance_id": "stale-instance",
        },
        service_active_after_restart=False,
    )

    assert result.returncode != 0
    assert current.resolve() == previous
    assert not (tmp_path / "health-called").exists()
    assert "restart dax-assistant.service" in (tmp_path / "systemctl.log").read_text()


@pytest.mark.parametrize("output", [".", "..", "~", "/"])
def test_release_output_rejects_unsafe_deletion_targets(tmp_path: Path, output: str) -> None:
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
    )
    assert result.returncode != 0
    assert "--output may not be the dist directory itself" in result.stderr


def test_release_installer_uses_hash_lock_canonical_units_and_rollback() -> None:
    installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
    release = (ROOT / "scripts/release.py").read_text(encoding="utf-8")
    assert "uv export" not in installer
    assert "--require-hashes" in installer
    assert "--no-deps" in installer
    assert 'install -m 600 "$backend_asset" "$BACKEND_UNIT"' in installer
    assert 'cat > "$BACKEND_UNIT"' not in installer
    assert "previous_target" in installer
    assert "authoritative" in installer
    assert "restored the previous current target" in installer
    assert "is-active --quiet dax-assistant-node.service" in installer
    assert "is-enabled --quiet dax-assistant-node.service" in installer
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
