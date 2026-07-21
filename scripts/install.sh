#!/usr/bin/env bash
# Verified tagged-release installer for Dax on Fedora/RHEL and Debian/Ubuntu.

set -Eeuo pipefail
IFS=$'\n\t'

REPOSITORY="${DAX_RELEASE_REPOSITORY:-daxrpm/dax-assistant}"
GH_COMMAND="${DAX_GH_COMMAND:-gh}"
PIN_VERSION=""
MANIFEST_SOURCE=""
CHECKSUMS_SOURCE=""
COMPONENTS="both"
WITH_NODE=0
DRY_RUN=0
ASSUME_YES=0
INSECURE_SKIP_ATTESTATION=0
SOURCE_MODE=""
OS_RELEASE_FILE="${DAX_OS_RELEASE_FILE:-/etc/os-release}"
MACHINE="${DAX_UNAME_MACHINE:-$(uname -m)}"
SUPPORTED_API_VERSION=1

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_DIR="$XDG_DATA_HOME/dax-assistant"
STATE_DIR="$XDG_STATE_HOME/dax-assistant"
CACHE_DIR="$XDG_CACHE_HOME/dax-assistant"
RELEASES_DIR="$DATA_DIR/releases"
CURRENT_LINK="$DATA_DIR/current"
NODE_RELEASES_DIR="$DATA_DIR/node-releases"
NODE_CURRENT_LINK="$DATA_DIR/node-current"
UNIT_DIR="$XDG_CONFIG_HOME/systemd/user"
BACKEND_UNIT="$UNIT_DIR/dax-assistant.service"
NODE_UNIT="$UNIT_DIR/dax-assistant-node.service"
NODE_CREDENTIALS="$STATE_DIR/edge.json"
BACKUP_DIR="$STATE_DIR/backups"

TEMP_DIR=""
cleanup() { [[ -z "$TEMP_DIR" ]] || rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

info() { printf '[INFO] %s\n' "$*"; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
Dax verified Linux release installer

Usage:
  bash install.sh [install] [--backend-only|--desktop-only|--node-only|--both] [options]

Release options:
  --version VERSION       Pin an immutable release (for example 0.1.0)
  --manifest PATH|URL     Use an explicit release-manifest.json
  --checksums PATH|URL    SHA256SUMS authenticating the explicit manifest
  --backend-only          Install and start the authoritative backend only
  --desktop-only          Install the RPM/deb desktop client only
  --node-only             Install only the capability-node runtime and unit
  --both                  Install backend and desktop (default)
  --with-node             Also install the laptop capability-node unit; never enable/start it
  --dry-run               Download and verify assets, then print installation actions
  --yes                   Do not prompt
  --insecure-skip-attestation
                          UNSAFE: bypass GitHub artifact attestation verification

Development mode:
  --source PATH           Install the backend from an existing checkout with `uv sync`.
                          This mode never clones a branch and does not install desktop packages.

This Linux installer never downloads or installs the Android APK.
EOF
}

if [[ "${1:-}" == "install" ]]; then shift; fi
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) PIN_VERSION="${2:-}"; shift ;;
        --manifest) MANIFEST_SOURCE="${2:-}"; shift ;;
        --checksums) CHECKSUMS_SOURCE="${2:-}"; shift ;;
        --backend-only) COMPONENTS="backend" ;;
        --desktop-only) COMPONENTS="desktop" ;;
        --node-only) COMPONENTS="node"; WITH_NODE=1 ;;
        --both) COMPONENTS="both" ;;
        --with-node) WITH_NODE=1 ;;
        --source) SOURCE_MODE="${2:-}"; shift ;;
        --dry-run) DRY_RUN=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        --insecure-skip-attestation) INSECURE_SKIP_ATTESTATION=1 ;;
        --help|-h) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done

[[ "$(uname -s)" == "Linux" ]] || die "Linux is required"
[[ "$EUID" -ne 0 ]] || die "run as the desktop user, not root"
[[ "$PIN_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ || -z "$PIN_VERSION" ]] || die "--version must be MAJOR.MINOR.PATCH"
[[ "$WITH_NODE" -eq 0 || "$COMPONENTS" != "desktop" ]] || die "--with-node cannot be combined with --desktop-only; use --node-only"
[[ -z "$SOURCE_MODE" || "$COMPONENTS" == "backend" ]] || die "--source supports --backend-only only"
if [[ "$COMPONENTS" != "desktop" ]]; then
    [[ "$XDG_DATA_HOME" == "$HOME/.local/share" && "$XDG_STATE_HOME" == "$HOME/.local/state" && "$XDG_CACHE_HOME" == "$HOME/.cache" && "$XDG_CONFIG_HOME" == "$HOME/.config" ]] || die "backend installation uses the canonical user-systemd assets and requires the default XDG directories"
fi

case "$MACHINE" in
    x86_64|amd64) ARCH="x86_64" ;;
    aarch64|arm64) ARCH="aarch64" ;;
    *) die "unsupported architecture: $MACHINE" ;;
esac

[[ -r "$OS_RELEASE_FILE" ]] || die "cannot identify Linux distribution"
# shellcheck disable=SC1090
source "$OS_RELEASE_FILE"
FAMILY="${ID_LIKE:-${ID:-}}"
if [[ "${ID:-}" == "fedora" || "${ID:-}" == "rhel" || "$FAMILY" == *fedora* || "$FAMILY" == *rhel* ]]; then
    DISTRO="rpm"
elif [[ "${ID:-}" == "debian" || "${ID:-}" == "ubuntu" || "$FAMILY" == *debian* ]]; then
    DISTRO="deb"
else
    die "unsupported distribution: ${ID:-unknown}; use Fedora/RHEL or Debian/Ubuntu"
fi

print_layout() {
    printf 'Components:   %s\nArchitecture: %s\nDistribution: %s\nReleases:     %s\nState:        %s\nBackend unit: %s\nNode unit:    %s\n' \
        "$COMPONENTS" "$ARCH" "$DISTRO" "$RELEASES_DIR" "$STATE_DIR" "$BACKEND_UNIT" "$NODE_UNIT"
}

fetch() {
    local source="$1" destination="$2"
    case "$source" in
        https://*) curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error "$source" -o "$destination" ;;
        file://*) cp "${source#file://}" "$destination" ;;
        /*|./*|../*) cp "$source" "$destination" ;;
        *) die "refusing non-HTTPS URL: $source" ;;
    esac
}

verify_file() {
    local path="$1" expected="$2" actual
    actual="$(sha256sum "$path" | cut -d ' ' -f 1)"
    [[ "$actual" == "$expected" ]] || die "SHA256 mismatch for $(basename "$path"): expected $expected, got $actual"
}

verify_manifest_checksum() {
    local expected="" hash name
    while IFS=' ' read -r hash name; do
        [[ -n "$name" ]] || continue
        name="${name# }"
        name="${name#\*}"
        [[ "$name" != "release-manifest.json" ]] || expected="$hash"
    done < "$TEMP_DIR/SHA256SUMS"
    [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || die "SHA256SUMS has no release-manifest.json entry"
    verify_file "$TEMP_DIR/release-manifest.json" "$expected"
}

verify_attestation() {
    local path="$1"
    if [[ "$INSECURE_SKIP_ATTESTATION" -eq 1 ]]; then
        printf '[WARNING] INSECURE: skipping GitHub attestation verification for %s\n' "$(basename "$path")" >&2
        return
    fi
    command -v "$GH_COMMAND" >/dev/null 2>&1 || die "gh is required for release attestation verification; install GitHub CLI or explicitly accept the risk with --insecure-skip-attestation"
    "$GH_COMMAND" attestation verify "$path" --repo "$REPOSITORY" >/dev/null || die "GitHub attestation verification failed for $(basename "$path")"
}

write_selection() {
    python3 - "$TEMP_DIR/release-manifest.json" "$TEMP_DIR/selection.tsv" "$COMPONENTS" "$DISTRO" "$ARCH" "$PIN_VERSION" "$MANIFEST_SOURCE" "$WITH_NODE" "$REPOSITORY" <<'PY'
import json
import re
import sys
from pathlib import Path

manifest_path, output, components, distro, arch, pinned, source, with_node, repository = sys.argv[1:]
data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
if data.get("schema_version") != 1:
    raise SystemExit("unsupported release manifest schema")
version = data.get("version", "")
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
    raise SystemExit("invalid release version")
if pinned and version != pinned:
    raise SystemExit(f"manifest version {version} does not match --version {pinned}")
if not re.fullmatch(r"[0-9a-f]{40}", data.get("commit", "")):
    raise SystemExit("invalid release commit")
compat = data.get("api_compatibility", {})
if components == "both" and compat.get("backend") != compat.get("desktop"):
    raise SystemExit("backend and desktop API compatibility differ")
if not all(isinstance(compat.get(key), str) and compat[key] for key in ("backend", "desktop", "android", "capability_node")):
    raise SystemExit("incomplete API compatibility metadata")

wanted = []
if components in {"backend", "both", "node"}:
    wanted.extend(("backend-wheel", "backend-dependency-lock", "backend-service"))
    if components == "node":
        wanted.remove("backend-service")
if with_node == "1":
    wanted.append("node-service")
if components in {"desktop", "both"}:
    wanted.append("desktop-rpm" if distro == "rpm" else "desktop-deb")
found = {}
local_manifest = not source.startswith("https://")
for artifact in data.get("artifacts", []):
    role = artifact.get("role")
    if role not in wanted:
        continue
    name = artifact.get("name", "")
    url = artifact.get("url", "")
    artifact_arch = artifact.get("arch")
    digest = artifact.get("sha256", "")
    size = artifact.get("size")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", name) or Path(name).name != name:
        raise SystemExit(f"unsafe artifact name for {role}")
    release_base = f"https://github.com/{repository}/releases/download/v{version}/"
    if not url.startswith(release_base) and not (local_manifest and url.startswith("file://")):
        raise SystemExit(f"unsafe artifact URL for {role}")
    if artifact_arch not in {"any", arch}:
        continue
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or not isinstance(size, int) or size < 1:
        raise SystemExit(f"invalid integrity metadata for {role}")
    if role in found:
        raise SystemExit(f"ambiguous {role} artifact")
    found[role] = (name, url, artifact_arch, digest, size)
missing = [role for role in wanted if role not in found]
if missing:
    raise SystemExit(f"release does not support {arch}/{distro}: {', '.join(missing)} missing")
with Path(output).open("w", encoding="utf-8") as stream:
    stream.write(f"version\t{version}\n")
    stream.write(f"commit\t{data['commit']}\n")
    for role in wanted:
        stream.write(role + "\t" + "\t".join(str(value) for value in found[role]) + "\n")
PY
}

install_system_dependencies() {
    if [[ "$DISTRO" == "rpm" ]]; then
        sudo dnf install -y portaudio libsndfile espeak-ng
    else
        sudo apt-get update
        sudo apt-get install -y libportaudio2 libsndfile1 espeak-ng
    fi
}

backup_database() {
    local python="$1" database="$STATE_DIR/dax.db" target timestamp
    [[ -f "$database" ]] || return 0
    install -d -m 700 "$BACKUP_DIR"
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    target="$BACKUP_DIR/dax-$timestamp.db"
    "$python" - "$database" "$target" <<'PY'
import sqlite3
import sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
with target:
    source.backup(target)
source.close()
target.close()
PY
    chmod 600 "$target"
    [[ ! -f "$STATE_DIR/dax.key" ]] || install -m 600 "$STATE_DIR/dax.key" "$BACKUP_DIR/dax-$timestamp.key"
}

fixup_venv_shebangs() {
    local old_root="$1" new_root="$2"
    python3 - "$old_root" "$new_root" <<'PY'
import sys
from pathlib import Path

old_root, new_root = sys.argv[1], sys.argv[2]
old_shebang = f"#!{old_root}/.venv/bin/python\n".encode()
new_shebang = f"#!{new_root}/.venv/bin/python\n".encode()
bin_dir = Path(new_root) / ".venv" / "bin"
for script in bin_dir.iterdir():
    if not script.is_file():
        continue
    data = script.read_bytes()
    if data.startswith(old_shebang):
        script.write_bytes(new_shebang + data[len(old_shebang):])
PY
}

write_units() {
    local backend_asset="$1" node_asset="${2:-}"
    install -d -m 700 "$UNIT_DIR"
    install -m 600 "$backend_asset" "$BACKEND_UNIT"
    if [[ "$WITH_NODE" -eq 1 ]]; then
        [[ -n "$node_asset" ]] || die "release has no canonical node unit"
        install -m 600 "$node_asset" "$NODE_UNIT"
        systemctl --user disable dax-assistant-node.service >/dev/null 2>&1 || true
    fi
    systemctl --user daemon-reload
}

install_node() {
    local wheel="$1" dependency_lock="$2" node_asset="$3"
    local release_dir="$NODE_RELEASES_DIR/$RESOLVED_VERSION" managed_python
    command -v uv >/dev/null 2>&1 || die "uv is required to install the managed Python 3.11 runtime (https://docs.astral.sh/uv/)"
    systemctl --user is-active --quiet dax-assistant-node.service && die "dax-assistant-node.service is active; stop it explicitly before upgrading the node runtime"
    systemctl --user is-enabled --quiet dax-assistant-node.service && die "dax-assistant-node.service is enabled; disable it explicitly before upgrading the node runtime"
    install_system_dependencies
    uv python install 3.11
    managed_python="$(uv python find 3.11)"
    install -d -m 700 "$NODE_RELEASES_DIR" "$STATE_DIR" "$CACHE_DIR" "$DATA_DIR/models"
    rm -rf "$release_dir.new"
    install -d -m 700 "$release_dir.new"
    uv venv --python "$managed_python" "$release_dir.new/.venv"
    uv pip install --python "$release_dir.new/.venv/bin/python" --require-hashes -r "$dependency_lock"
    uv pip install --python "$release_dir.new/.venv/bin/python" --no-deps "$wheel"
    rm -rf "$release_dir"
    mv "$release_dir.new" "$release_dir"
    fixup_venv_shebangs "$release_dir.new" "$release_dir"
    install -d -m 700 "$UNIT_DIR"
    install -m 600 "$node_asset" "$NODE_UNIT"
    systemctl --user disable dax-assistant-node.service >/dev/null 2>&1 || true
    systemctl --user daemon-reload
    ln -sfn "$release_dir" "$NODE_CURRENT_LINK.new"
    mv -Tf "$NODE_CURRENT_LINK.new" "$NODE_CURRENT_LINK"
    info "Capability-node runtime installed without a backend. Enrol it from Dax Desktop, then explicitly enable and start dax-assistant-node.service."
}

rollback_backend() {
    local previous_target="$1" was_active="$2" was_enabled="$3"
    if [[ -n "$previous_target" ]]; then
        ln -sfn "$previous_target" "$CURRENT_LINK.new"
        mv -Tf "$CURRENT_LINK.new" "$CURRENT_LINK"
        if [[ "$was_active" -eq 1 ]]; then
            systemctl --user restart dax-assistant.service || true
        else
            systemctl --user stop dax-assistant.service || true
        fi
        [[ "$was_enabled" -eq 1 ]] || systemctl --user disable dax-assistant.service || true
    else
        systemctl --user disable --now dax-assistant.service || true
        rm -f "$CURRENT_LINK"
    fi
}

install_backend() {
    local wheel="$1" dependency_lock="$2" backend_asset="$3" node_asset="${4:-}"
    local release_dir="$RELEASES_DIR/$RESOLVED_VERSION" managed_python previous_target="" deadline ready=0
    local backend_was_active=0 backend_was_enabled=0
    command -v uv >/dev/null 2>&1 || die "uv is required to install the managed Python 3.11 runtime (https://docs.astral.sh/uv/)"
    if [[ "$WITH_NODE" -eq 1 ]] && systemctl --user is-active --quiet dax-assistant-node.service; then
        die "dax-assistant-node.service is active; stop it explicitly before replacing its selected runtime"
    fi
    if [[ "$WITH_NODE" -eq 1 ]] && systemctl --user is-enabled --quiet dax-assistant-node.service; then
        die "dax-assistant-node.service is enabled; disable it explicitly before replacing its selected runtime"
    fi
    install_system_dependencies
    uv python install 3.11
    managed_python="$(uv python find 3.11)"
    backup_database "$managed_python"
    install -d -m 700 "$RELEASES_DIR" "$STATE_DIR" "$CACHE_DIR" "$DATA_DIR/models" "$STATE_DIR/memory"
    [[ ! -L "$CURRENT_LINK" ]] || previous_target="$(readlink "$CURRENT_LINK")"
    if [[ -n "$previous_target" && "$(readlink -f "$CURRENT_LINK")" == "$release_dir" ]]; then
        die "backend release $RESOLVED_VERSION is already the current target"
    fi
    rm -rf "$release_dir.new"
    install -d -m 700 "$release_dir.new"
    uv venv --python "$managed_python" "$release_dir.new/.venv"
    uv pip install --python "$release_dir.new/.venv/bin/python" --require-hashes -r "$dependency_lock"
    uv pip install --python "$release_dir.new/.venv/bin/python" --no-deps "$wheel"
    rm -rf "$release_dir"
    mv "$release_dir.new" "$release_dir"
    fixup_venv_shebangs "$release_dir.new" "$release_dir"
    if systemctl --user is-active --quiet dax-assistant.service; then backend_was_active=1; fi
    if systemctl --user is-enabled --quiet dax-assistant.service; then backend_was_enabled=1; fi
    write_units "$backend_asset" "$node_asset"
    ln -sfn "$release_dir" "$CURRENT_LINK.new"
    mv -Tf "$CURRENT_LINK.new" "$CURRENT_LINK"
    if ! systemctl --user enable dax-assistant.service || ! systemctl --user restart dax-assistant.service; then
        rollback_backend "$previous_target" "$backend_was_active" "$backend_was_enabled"
        die "backend service activation failed; restored the previous current target and service"
    fi
    # 300s default: a fresh install's first startup fetches voice models (Whisper
    # STT, Piper TTS) from Hugging Face, which alone took ~64s over a home
    # connection in practice — comfortably past the old 60s deadline.
    deadline=$((SECONDS + ${DAX_READINESS_TIMEOUT_SECONDS:-300}))
    while (( SECONDS < deadline )); do
        if ! systemctl --user is-active --quiet dax-assistant.service; then
            break
        fi
        if curl --fail --silent --show-error http://127.0.0.1:8420/api/health | python3 -c 'import json,sys; value=json.load(sys.stdin); version=value.get("api_version"); instance_id=value.get("instance_id"); valid=value.get("status") == "ok" and value.get("liveness") is True and value.get("readiness") is True and value.get("role") == "authoritative" and value.get("api_protocol") == "dax" and type(version) is int and version == int(sys.argv[1]) and isinstance(instance_id, str) and bool(instance_id); raise SystemExit(0 if valid else 1)' "$SUPPORTED_API_VERSION" 2>/dev/null && systemctl --user is-active --quiet dax-assistant.service; then
            ready=1
            break
        fi
        sleep 2
    done
    if [[ "$ready" -ne 1 ]]; then
        rollback_backend "$previous_target" "$backend_was_active" "$backend_was_enabled"
        die "backend did not become authoritatively ready before the deadline; restored the previous current target and service"
    fi
    if [[ "$WITH_NODE" -eq 1 ]]; then
        ln -sfn "$release_dir" "$NODE_CURRENT_LINK.new"
        mv -Tf "$NODE_CURRENT_LINK.new" "$NODE_CURRENT_LINK"
        info "Node unit installed, disabled, and not started. Create a capability-node enrollment code on the authoritative backend, then run: $CURRENT_LINK/.venv/bin/dax edge enroll --server URL --code CODE --name NAME. After $NODE_CREDENTIALS exists, explicitly enable and start dax-assistant-node.service."
    fi
}

install_desktop() {
    local package="$1"
    if [[ "$DISTRO" == "rpm" ]]; then
        sudo dnf install -y "$package"
    else
        sudo apt-get install -y "$package"
    fi
}

install_source() {
    command -v uv >/dev/null 2>&1 || die "development --source mode requires an existing uv installation"
    [[ -f "$SOURCE_MODE/pyproject.toml" ]] || die "--source is not a Dax checkout"
    [[ -f "$SOURCE_MODE/src/dax/web/static/index.html" ]] || die "source checkout has no built web static assets"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        info "Development source mode; no release manifest or desktop package will be used"
        print_layout
        printf 'Would run: uv --directory %q sync --frozen --all-extras\n' "$SOURCE_MODE"
        return
    fi
    uv --directory "$SOURCE_MODE" sync --frozen --all-extras
    RESOLVED_VERSION="source"
    install -d -m 700 "$DATA_DIR"
    ln -sfn "$SOURCE_MODE" "$CURRENT_LINK.new"
    mv -Tf "$CURRENT_LINK.new" "$CURRENT_LINK"
    write_units "$SOURCE_MODE/systemd/dax-assistant.service"
    systemctl --user enable --now dax-assistant.service
}

if [[ -n "$SOURCE_MODE" ]]; then
    install_source
    exit 0
fi

for command in curl sha256sum python3; do command -v "$command" >/dev/null 2>&1 || die "required command not found: $command"; done
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dax-install.XXXXXXXX")"
if [[ -z "$MANIFEST_SOURCE" ]]; then
    if [[ -n "$PIN_VERSION" ]]; then RELEASE_BASE="https://github.com/$REPOSITORY/releases/download/v$PIN_VERSION"; else RELEASE_BASE="https://github.com/$REPOSITORY/releases/latest/download"; fi
    MANIFEST_SOURCE="$RELEASE_BASE/release-manifest.json"
    CHECKSUMS_SOURCE="$RELEASE_BASE/SHA256SUMS"
elif [[ -z "$CHECKSUMS_SOURCE" ]]; then
    die "--checksums is required with --manifest"
fi

fetch "$CHECKSUMS_SOURCE" "$TEMP_DIR/SHA256SUMS"
fetch "$MANIFEST_SOURCE" "$TEMP_DIR/release-manifest.json"
verify_attestation "$TEMP_DIR/release-manifest.json"
verify_manifest_checksum
write_selection

declare -A ARTIFACT_PATHS
while IFS=$'\t' read -r role name url _artifact_arch digest size; do
    if [[ "$role" == "version" ]]; then RESOLVED_VERSION="$name"; continue; fi
    if [[ "$role" == "commit" ]]; then RESOLVED_COMMIT="$name"; continue; fi
    target="$TEMP_DIR/$name"
    fetch "$url" "$target"
    verify_file "$target" "$digest"
    [[ "$(stat -c %s "$target")" == "$size" ]] || die "size mismatch for $name"
    verify_attestation "$target"
    ARTIFACT_PATHS[$role]="$target"
done < "$TEMP_DIR/selection.tsv"

if command -v "$GH_COMMAND" >/dev/null 2>&1; then
    TAG_COMMIT="$("$GH_COMMAND" api "repos/$REPOSITORY/commits/v$RESOLVED_VERSION" --jq .sha)" || die "could not resolve release tag v$RESOLVED_VERSION"
else
    TAG_COMMIT="$(curl --proto '=https' --tlsv1.2 --fail --silent --show-error "https://api.github.com/repos/$REPOSITORY/commits/v$RESOLVED_VERSION" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])')" || die "could not resolve release tag v$RESOLVED_VERSION"
fi
[[ "$TAG_COMMIT" == "$RESOLVED_COMMIT" ]] || die "manifest commit $RESOLVED_COMMIT does not match tag v$RESOLVED_VERSION ($TAG_COMMIT)"

info "Verified release $RESOLVED_VERSION before installation"
print_layout
if [[ "$DRY_RUN" -eq 1 ]]; then
    if [[ "$COMPONENTS" == "node" ]]; then
        printf 'Would install capability-node runtime wheel: %s\n' "${ARTIFACT_PATHS[backend-wheel]}"
    elif [[ "$COMPONENTS" != "desktop" ]]; then
        printf 'Would install backend wheel: %s\n' "${ARTIFACT_PATHS[backend-wheel]}"
    fi
    if [[ "$COMPONENTS" != "backend" && "$COMPONENTS" != "node" ]]; then
        printf 'Would run: sudo %s install desktop %s\n' "$([[ "$DISTRO" == "rpm" ]] && printf dnf || printf apt-get)" "${ARTIFACT_PATHS[desktop-$DISTRO]}"
    fi
    [[ "$WITH_NODE" -eq 0 ]] || printf 'Would install node unit without enabling or starting it; credentials: %s\n' "$NODE_CREDENTIALS"
    exit 0
fi

if [[ "$ASSUME_YES" -eq 0 && -t 0 ]]; then
    read -r -p "Install verified Dax $RESOLVED_VERSION ($COMPONENTS)? [Y/n] " answer
    [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]] || die "installation cancelled"
fi
if [[ "$COMPONENTS" == "node" ]]; then
    install_node \
        "${ARTIFACT_PATHS[backend-wheel]}" \
        "${ARTIFACT_PATHS[backend-dependency-lock]}" \
        "${ARTIFACT_PATHS[node-service]}"
elif [[ "$COMPONENTS" != "desktop" ]]; then
    install_backend \
        "${ARTIFACT_PATHS[backend-wheel]}" \
        "${ARTIFACT_PATHS[backend-dependency-lock]}" \
        "${ARTIFACT_PATHS[backend-service]}" \
        "${ARTIFACT_PATHS[node-service]:-}"
fi
[[ "$COMPONENTS" == "backend" || "$COMPONENTS" == "node" ]] || install_desktop "${ARTIFACT_PATHS[desktop-$DISTRO]}"
info "Dax $RESOLVED_VERSION installation complete. Android is distributed separately and was not installed."
