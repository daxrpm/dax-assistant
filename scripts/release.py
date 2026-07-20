#!/usr/bin/env python3
"""Build and describe immutable Dax release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "release.json"
VERSION_RE = r"[0-9]+\.[0-9]+\.[0-9]+"
REPOSITORY = os.environ.get("DAX_RELEASE_REPOSITORY", "daxrpm/dax-assistant")


def fail(message: str) -> None:
    raise SystemExit(f"release: {message}")


def metadata() -> dict[str, Any]:
    return json.loads(METADATA.read_text(encoding="utf-8"))


def extract(pattern: str, path: Path) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        fail(f"cannot read version from {path.relative_to(ROOT)}")
    return match.group(1)


def versions() -> dict[str, str]:
    return {
        "release.json": metadata()["version"],
        "pyproject.toml": extract(r'^version = "(' + VERSION_RE + r')"$', ROOT / "pyproject.toml"),
        "web/package.json": json.loads((ROOT / "web/package.json").read_text())["version"],
        "web/package-lock.json": json.loads((ROOT / "web/package-lock.json").read_text())[
            "version"
        ],
        "desktop/package.json": json.loads((ROOT / "desktop/package.json").read_text())["version"],
        "desktop/package-lock.json": json.loads((ROOT / "desktop/package-lock.json").read_text())[
            "version"
        ],
        "desktop/src-tauri/tauri.conf.json": json.loads(
            (ROOT / "desktop/src-tauri/tauri.conf.json").read_text()
        )["version"],
        "desktop/src-tauri/Cargo.toml": extract(
            r'^version = "(' + VERSION_RE + r')"$', ROOT / "desktop/src-tauri/Cargo.toml"
        ),
        "desktop/src-tauri/Cargo.lock": extract(
            r'name = "dax-desktop"\nversion = "(' + VERSION_RE + r')"',
            ROOT / "desktop/src-tauri/Cargo.lock",
        ),
        "android versionName": extract(
            r'versionName = "(' + VERSION_RE + r')"', ROOT / "android/app/build.gradle.kts"
        ),
    }


def version_code(version: str) -> int:
    major, minor, patch = (int(part) for part in version.split("."))
    if major > 2100 or minor > 999 or patch > 999:
        fail("version cannot be represented as an Android versionCode")
    return major * 1_000_000 + minor * 1_000 + patch


def check_versions() -> str:
    found = versions()
    expected = found["release.json"]
    mismatches = [f"{path}={value}" for path, value in found.items() if value != expected]
    android_code = int(extract(r"versionCode = ([0-9]+)", ROOT / "android/app/build.gradle.kts"))
    if android_code != version_code(expected):
        mismatches.append(
            f"android versionCode={android_code} (expected {version_code(expected)})"
        )
    if mismatches:
        fail("version mismatch: " + ", ".join(mismatches))
    print(expected)
    return expected


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        fail(f"could not synchronize {path.relative_to(ROOT)}")
    path.write_text(updated, encoding="utf-8")


def sync_versions(version: str) -> None:
    if not re.fullmatch(VERSION_RE, version):
        fail("version must be MAJOR.MINOR.PATCH")
    release = metadata()
    release["version"] = version
    METADATA.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    replace_once(
        ROOT / "pyproject.toml", r'^version = "' + VERSION_RE + r'"$', f'version = "{version}"'
    )
    for relative in (
        "web/package.json",
        "web/package-lock.json",
        "desktop/package.json",
        "desktop/package-lock.json",
    ):
        replace_once(
            ROOT / relative,
            r'^(  )"version": "' + VERSION_RE + r'",$',
            rf'\1"version": "{version}",',
        )
    for relative in ("web/package-lock.json", "desktop/package-lock.json"):
        replace_once(
            ROOT / relative,
            r'^(      )"version": "' + VERSION_RE + r'",$',
            rf'\1"version": "{version}",',
        )
    replace_once(
        ROOT / "desktop/src-tauri/tauri.conf.json",
        r'^(  )"version": "' + VERSION_RE + r'",$',
        rf'\1"version": "{version}",',
    )
    replace_once(
        ROOT / "desktop/src-tauri/Cargo.toml",
        r'^version = "' + VERSION_RE + r'"$',
        f'version = "{version}"',
    )
    replace_once(
        ROOT / "desktop/src-tauri/Cargo.lock",
        r'(name = "dax-desktop"\nversion = ")' + VERSION_RE + r'("\n)',
        rf"\g<1>{version}\2",
    )
    gradle = ROOT / "android/app/build.gradle.kts"
    replace_once(gradle, r"versionCode = [0-9]+", f"versionCode = {version_code(version)}")
    replace_once(gradle, r'versionName = "' + VERSION_RE + r'"', f'versionName = "{version}"')
    check_versions()


def run(*command: str, cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def copy_one(pattern: str, destination: Path, *, root: Path = ROOT) -> Path:
    matches = sorted(root.glob(pattern))
    if len(matches) != 1:
        fail(f"expected one {pattern} artifact, found {len(matches)}")
    target = destination / matches[0].name
    shutil.copy2(matches[0], target)
    return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    if machine in {"aarch64", "arm64"}:
        return "aarch64"
    fail(f"unsupported release architecture: {machine}")


def build(args: argparse.Namespace) -> None:
    version = check_versions()
    tag = f"v{version}"
    ref = os.environ.get("GITHUB_REF_NAME")
    if ref and ref != tag:
        fail(f"tag {ref} does not match release version {tag}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        fail("could not resolve a full release commit")

    output = Path(args.output).resolve()
    build_root = (ROOT / "dist").resolve()
    try:
        relative_output = output.relative_to(build_root)
    except ValueError:
        fail("--output must be a descendant of the repository dist directory")
    if not relative_output.parts:
        fail("--output may not be the dist directory itself")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    run("npm", "ci", cwd=ROOT / "web")
    run("npm", "run", "build", cwd=ROOT / "web")
    run("uv", "build", "--out-dir", str(output), cwd=ROOT)
    dependency_lock = output / "backend-requirements.txt"
    run(
        "uv",
        "export",
        "--frozen",
        "--no-dev",
        "--extra",
        "voice",
        "--no-emit-project",
        "--format",
        "requirements-txt",
        "--output-file",
        str(dependency_lock),
        cwd=ROOT,
    )
    lock_content = dependency_lock.read_text(encoding="utf-8")
    if "--hash=sha256:" not in lock_content:
        fail("uv export did not produce a hash-locked dependency file")

    artifacts: list[tuple[str, Path, str]] = []
    (output / ".gitignore").unlink(missing_ok=True)
    wheels = sorted(output.glob("*.whl"))
    sdists = sorted(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        counts = f"{len(wheels)} wheel(s) and {len(sdists)} sdist(s)"
        fail(f"expected one wheel and one sdist, found {counts}")
    artifacts.extend(
        (
            ("backend-wheel", wheels[0], "any"),
            ("backend-sdist", sdists[0], "any"),
            ("backend-dependency-lock", dependency_lock, "any"),
        )
    )

    if not args.skip_desktop:
        run("npm", "ci", cwd=ROOT / "desktop")
        run("npm", "run", "tauri", "build", "--", "--bundles", "rpm,deb", cwd=ROOT / "desktop")
        rpm = copy_one("desktop/src-tauri/target/release/bundle/rpm/*.rpm", output)
        deb = copy_one("desktop/src-tauri/target/release/bundle/deb/*.deb", output)
        artifacts.extend(
            (("desktop-rpm", rpm, normalized_arch()), ("desktop-deb", deb, normalized_arch()))
        )

    if not args.skip_android:
        required = (
            "DAX_ANDROID_KEYSTORE_PATH",
            "DAX_ANDROID_KEYSTORE_PASSWORD",
            "DAX_ANDROID_KEY_ALIAS",
            "DAX_ANDROID_KEY_PASSWORD",
            "DAX_ANDROID_CERT_SHA256",
        )
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            fail("Android production signing is required; missing " + ", ".join(missing))
        gradle = os.environ.get("GRADLE", "gradle")
        run(gradle, ":app:clean", ":app:assembleRelease", cwd=ROOT / "android")
        apk = copy_one("android/app/build/outputs/apk/release/app-release.apk", output)
        apksigner = shutil.which("apksigner")
        if not apksigner and os.environ.get("ANDROID_HOME"):
            candidates = sorted(Path(os.environ["ANDROID_HOME"]).glob("build-tools/*/apksigner"))
            apksigner = str(candidates[-1]) if candidates else None
        if not apksigner:
            fail("apksigner is required to verify the production APK signature")
        result = subprocess.run(
            [apksigner, "verify", "--verbose", "--print-certs", str(apk)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout, end="")
        match = re.search(
            r"Signer #1 certificate SHA-256 digest: ([0-9A-Fa-f:]+)",
            result.stdout + result.stderr,
        )
        actual_certificate = match.group(1).replace(":", "").lower() if match else ""
        expected_certificate = os.environ["DAX_ANDROID_CERT_SHA256"].replace(":", "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_certificate):
            fail("DAX_ANDROID_CERT_SHA256 must be a SHA-256 certificate fingerprint")
        if actual_certificate != expected_certificate:
            fail(
                "Android signer certificate mismatch: "
                f"expected {expected_certificate}, got {actual_certificate or 'unavailable'}"
            )
        artifacts.append(("android-apk", apk, "universal"))

    for role, source in (
        ("linux-installer", ROOT / "scripts/install.sh"),
        ("backend-service", ROOT / "systemd/dax-assistant.service"),
        ("node-service", ROOT / "systemd/dax-assistant-node.service"),
    ):
        target = output / source.name
        shutil.copy2(source, target)
        artifacts.append((role, target, "any"))

    base_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}"
    manifest = {
        "schema_version": 1,
        "version": version,
        "commit": commit,
        "api_compatibility": metadata()["api_compatibility"],
        "artifacts": [
            {
                "role": role,
                "name": path.name,
                "url": f"{base_url}/{path.name}",
                "arch": arch,
                "sha256": sha256(path),
                "size": path.stat().st_size,
            }
            for role, path, arch in sorted(artifacts)
        ],
    }
    manifest_path = output / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checksum_paths = sorted(path for path in output.iterdir() if path.name != "SHA256SUMS")
    (output / "SHA256SUMS").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in checksum_paths), encoding="utf-8"
    )
    print(f"Release {version}: {len(artifacts)} artifacts in {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="verify all product versions")
    sync = subparsers.add_parser("sync", help="synchronize all product versions")
    sync.add_argument("version")
    release = subparsers.add_parser("build", help="build release artifacts and manifest")
    release.add_argument("--output", default="dist/release")
    release.add_argument("--skip-desktop", action="store_true", help="local validation only")
    release.add_argument("--skip-android", action="store_true", help="local validation only")
    args = parser.parse_args()
    if args.command == "check":
        check_versions()
    elif args.command == "sync":
        sync_versions(args.version)
    else:
        build(args)


if __name__ == "__main__":
    main()
