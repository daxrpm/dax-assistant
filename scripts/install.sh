#!/usr/bin/env bash
#
# Dax installer for Linux.
#
# Run it with no arguments: it asks what to install, installs it, creates your
# account, and prints the address to give your other devices. Pass flags and it
# does the same without asking.
#
#   bash install.sh                    choose interactively
#   bash install.sh --backend --yes    unattended
#   bash install.sh status|list|rollback|uninstall
#
# Every download is authenticated by SHA-256 against the release manifest, and
# the manifest against the release's SHA256SUMS over TLS. If the GitHub CLI is
# installed and logged in, build provenance is checked too — but it is never
# required. Needing `gh auth login` to install a program is a barrier, not
# security.

set -Eeuo pipefail

REPOSITORY="${DAX_RELEASE_REPOSITORY:-daxrpm/dax-assistant}"
SUPPORTED_API_VERSION=1
READINESS_TIMEOUT="${DAX_READINESS_TIMEOUT_SECONDS:-300}"
KEEP_RELEASES="${DAX_KEEP_RELEASES:-3}"
BACKEND_PORT=8420

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
BACKUP_DIR="$STATE_DIR/backups"

# `systemctl --user` talks to the per-user systemd manager over its D-Bus
# socket. A graphical login exports XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS;
# an SSH session or a bare TTY often does not, and systemctl then fails with
# "Failed to connect to user scope bus ... Operation not permitted". Point both
# at the well-known runtime path so unit operations work from any session.
if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
    XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export XDG_RUNTIME_DIR
fi
if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -S "$XDG_RUNTIME_DIR/bus" ]]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
fi

COMMAND="install"
WANT_BACKEND=0
WANT_DESKTOP=0
WANT_NODE=0
SELECTION_GIVEN=0
PIN_VERSION=""
ASSUME_YES=0
DRY_RUN=0
PURGE_STATE=0
REQUIRE_ATTESTATION=0
SKIP_ACCOUNT=0
ROLLBACK_VERSION=""
SOURCE_DIR=""
MANIFEST_SOURCE=""
CHECKSUMS_SOURCE=""
VERSION=""
UV=""
OS_RELEASE_FILE="${DAX_OS_RELEASE_FILE:-/etc/os-release}"
MACHINE="${DAX_UNAME_MACHINE:-$(uname -m)}"

TEMP_DIR=""
cleanup() { [[ -z "$TEMP_DIR" ]] || rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

# ---------------------------------------------------------------- presentation

if [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-dumb}" != "dumb" ]]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
    RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'
    BLUE=$'\033[34m'; CYAN=$'\033[36m'
else
    BOLD=""; DIM=""; RESET=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; CYAN=""
fi

INTERACTIVE=0
[[ -t 0 && -t 1 ]] && INTERACTIVE=1

step() { printf '\n%s==>%s %s%s%s\n' "$BLUE" "$RESET" "$BOLD" "$*" "$RESET"; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
note() { printf '  %s·%s %s\n' "$DIM" "$RESET" "$*"; }
warn() { printf '  %s!%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
die()  { printf '\n%sError:%s %s\n\n' "$RED" "$RESET" "$*" >&2; exit 1; }

usage() {
    cat <<EOF
${BOLD}Dax installer${RESET}

  bash install.sh [COMMAND] [OPTIONS]

${BOLD}Commands${RESET}
  install             Install or upgrade (default)
  status              What is installed, and whether it is running
  list                Installed releases
  rollback [VERSION]  Switch the backend to an installed release and restart
  uninstall           Remove services, units, and releases

${BOLD}What to install${RESET} (omit to be asked)
  --backend           The server: SQLite, config, conversations, LLM routing
  --desktop           The desktop client (RPM or deb)
  --node              Capability-node runtime; installed stopped
  --all               Backend and desktop

${BOLD}Options${RESET}
  --version VERSION   Pin a release instead of taking the newest
  --yes, -y           Never prompt; installs backend and desktop if unspecified
  --dry-run           Download and verify, then stop without changing anything
  --no-account        Skip first-run account creation
  --require-attestation
                      Fail unless GitHub build provenance verifies
  --keep N            Keep the N newest backend releases (default $KEEP_RELEASES)
  --purge             With uninstall: also delete the database and secret key
  --source PATH       Development: install the backend from a checkout
  -h, --help          This text

Environment: DAX_RELEASE_REPOSITORY, DAX_KEEP_RELEASES,
DAX_READINESS_TIMEOUT_SECONDS, NO_COLOR.

Android is distributed separately and is never installed from here.
EOF
}

# --------------------------------------------------------------- argument pass

case "${1:-}" in
    install|status|list|rollback|uninstall) COMMAND="$1"; shift ;;
    -h|--help) usage; exit 0 ;;
esac

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend) WANT_BACKEND=1; SELECTION_GIVEN=1 ;;
        --desktop) WANT_DESKTOP=1; SELECTION_GIVEN=1 ;;
        --node)    WANT_NODE=1;    SELECTION_GIVEN=1 ;;
        --all)     WANT_BACKEND=1; WANT_DESKTOP=1; SELECTION_GIVEN=1 ;;
        --version) PIN_VERSION="${2:-}"; shift ;;
        --manifest) MANIFEST_SOURCE="${2:-}"; shift ;;
        --checksums) CHECKSUMS_SOURCE="${2:-}"; shift ;;
        --keep)    KEEP_RELEASES="${2:-}"; shift ;;
        --source)  SOURCE_DIR="${2:-}"; shift ;;
        --yes|-y)  ASSUME_YES=1 ;;
        --dry-run) DRY_RUN=1 ;;
        --purge)   PURGE_STATE=1 ;;
        --no-account) SKIP_ACCOUNT=1 ;;
        --require-attestation) REQUIRE_ATTESTATION=1 ;;
        -h|--help) usage; exit 0 ;;
        -*) die "unknown option: $1  (try --help)" ;;
        *)
            [[ "$COMMAND" == "rollback" && -z "$ROLLBACK_VERSION" ]] \
                || die "unexpected argument: $1"
            ROLLBACK_VERSION="$1"
            ;;
    esac
    shift
done

[[ "$(uname -s)" == "Linux" ]] || die "this installer is for Linux"
[[ "$EUID" -ne 0 ]] || die "run as your own user, not root; Dax installs into your home directory"
[[ "$PURGE_STATE" -eq 0 || "$COMMAND" == "uninstall" ]] \
    || die "--purge only applies to uninstall"
[[ -z "$PIN_VERSION" || "$PIN_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || die "--version expects a release like 0.2.0, got '$PIN_VERSION'"
[[ -z "$ROLLBACK_VERSION" || "$ROLLBACK_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || die "rollback expects a release like 0.2.0, got '$ROLLBACK_VERSION'"
[[ "$KEEP_RELEASES" =~ ^[1-9][0-9]*$ ]] \
    || die "--keep expects a positive number, got '$KEEP_RELEASES'"

# ------------------------------------------------------------------- utilities

have() { command -v "$1" >/dev/null 2>&1; }

confirm() {
    local prompt="$1" reply
    [[ "$ASSUME_YES" -eq 1 ]] && return 0
    [[ "$INTERACTIVE" -eq 1 ]] || die "$prompt — refusing to assume without a terminal; pass --yes"
    printf '  %s?%s %s [y/N] ' "$YELLOW" "$RESET" "$prompt"
    read -r reply
    [[ "$reply" =~ ^[Yy]$ ]]
}

# Interactive multi-select: arrows or j/k move, space toggles, enter confirms.
# Number keys also toggle, so a terminal that swallows escape sequences never
# turns this into a dead end.
choose_components() {
    local labels=(
        "Backend            the server; every client connects to it"
        "Desktop client     the app for this machine"
        "Capability node    lend this machine's tools to a backend elsewhere"
    )
    local picked=(1 0 0) cursor=0 key rest index
    local count=${#labels[@]} i

    printf '\n  %sWhat should I install?%s\n' "$BOLD" "$RESET"
    printf '  %s↑↓ move · space toggle · enter confirm · q quit%s\n\n' "$DIM" "$RESET"

    printf '\033[?25l'
    local drawn=0
    while true; do
        [[ "$drawn" -eq 0 ]] || printf '\033[%dA' "$count"
        drawn=1
        for (( i = 0; i < count; i++ )); do
            local mark="[ ]" pointer="  " colour=""
            [[ "${picked[$i]}" -eq 1 ]] && mark="[${GREEN}x${RESET}]"
            if [[ "$i" -eq "$cursor" ]]; then
                pointer="${CYAN}❯${RESET} "
                colour="$BOLD"
            fi
            printf '\033[2K  %s%s %s%s%s\n' "$pointer" "$mark" "$colour" "${labels[$i]}" "$RESET"
        done

        IFS= read -rsn1 key || break
        case "$key" in
            $'\x1b')
                rest=""
                read -rsn2 -t 0.05 rest || true
                case "$rest" in
                    "[A") (( cursor = (cursor - 1 + count) % count )) ;;
                    "[B") (( cursor = (cursor + 1) % count )) ;;
                esac
                ;;
            k) (( cursor = (cursor - 1 + count) % count )) ;;
            j) (( cursor = (cursor + 1) % count )) ;;
            " ") picked[cursor]=$(( 1 - picked[cursor] )) ;;
            [1-9])
                index=$(( key - 1 ))
                (( index < count )) && picked[index]=$(( 1 - picked[index] ))
                ;;
            "") break ;;
            q|$'\x03') printf '\033[?25h'; die "cancelled" ;;
        esac
    done
    printf '\033[?25h'

    WANT_BACKEND="${picked[0]}"
    WANT_DESKTOP="${picked[1]}"
    WANT_NODE="${picked[2]}"
}

# The address other devices should use. Clients accept cleartext only to a
# private literal, so a name like `home-server` is deliberately not offered:
# it would be rejected on the other end.
lan_address() {
    local address=""
    if have ip; then
        address=$(ip -4 -oneline route get 1.1.1.1 2>/dev/null \
            | sed -n 's/.*[[:space:]]src[[:space:]]\([0-9.]*\).*/\1/p' | head -1)
    fi
    case "$address" in
        10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[01].*) printf '%s' "$address" ;;
        *) printf '' ;;
    esac
}

# Remote sources are HTTPS only. Local paths are accepted so a mirrored or
# air-gapped release can be installed from disk via --manifest.
fetch() {
    case "$1" in
        https://*)
            curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
                --retry 3 --retry-delay 1 --output "$2" "$1" || die "download failed: $1"
            ;;
        file://*) cp "${1#file://}" "$2" || die "cannot read $1" ;;
        /*) cp "$1" "$2" || die "cannot read $1" ;;
        *) die "refusing a source that is neither HTTPS nor a local path: $1" ;;
    esac
}

# ------------------------------------------------------------------ dependency

ensure_base_tools() {
    local missing=()
    local tool
    for tool in curl sha256sum python3 systemctl; do
        have "$tool" || missing+=("$tool")
    done
    [[ ${#missing[@]} -eq 0 ]] || die "missing required commands: ${missing[*]}"
}

ensure_uv() {
    if have uv; then UV=$(command -v uv); return; fi
    if [[ -x "$HOME/.local/bin/uv" ]]; then UV="$HOME/.local/bin/uv"; return; fi

    step "Installing uv"
    note "uv provides the Python 3.11 runtime and virtualenv the backend needs."
    confirm "Download uv from astral.sh and install it into ~/.local/bin?" \
        || die "uv is required; install it yourself from https://docs.astral.sh/uv/ and re-run"
    curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
        https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 \
        || die "could not install uv automatically; install it from https://docs.astral.sh/uv/"
    [[ -x "$HOME/.local/bin/uv" ]] || die "uv did not install into ~/.local/bin"
    UV="$HOME/.local/bin/uv"
    ok "uv installed"
}

package_kind() {
    local identity=""
    if [[ -r "$OS_RELEASE_FILE" ]]; then
        # Sourced in a subshell so the file's variables never leak into ours.
        # shellcheck disable=SC1090  # the path is a test seam, not a constant
        identity=$(. "$OS_RELEASE_FILE" && printf '%s %s' "${ID:-}" "${ID_LIKE:-}")
    fi
    case " $identity " in
        *fedora*|*rhel*|*centos*) printf 'rpm' ;;
        *debian*|*ubuntu*) printf 'deb' ;;
        *) printf '' ;;
    esac
}

# Without lingering, the user's systemd manager shuts down when the last session
# ends, taking the backend with it. On a headless server that means Dax dies the
# moment you log out of SSH — an "always-on" backend that is only on while you
# are watching it.
ensure_linger() {
    local state
    state=$(loginctl show-user "$USER" --property=Linger --value 2>/dev/null) || return 0
    [[ "$state" != "yes" ]] || return 0

    if loginctl enable-linger "$USER" >/dev/null 2>&1; then
        ok "enabled lingering so the backend keeps running after you log out"
        return 0
    fi
    if sudo -n loginctl enable-linger "$USER" >/dev/null 2>&1; then
        ok "enabled lingering so the backend keeps running after you log out"
        return 0
    fi
    warn "Could not enable lingering. The backend will stop when you log out."
    warn "Fix it with: sudo loginctl enable-linger $USER"
}

audio_libraries_present() {
    have espeak-ng || return 1
    local cache
    cache=$(ldconfig -p 2>/dev/null) || return 1
    [[ "$cache" == *libportaudio.so* ]] || return 1
    [[ "$cache" == *libsndfile.so* ]] || return 1
}

# Voice capture and synthesis link against these; the wheel cannot vendor them.
install_audio_libraries() {
    # Checked before asking, because escalating to root for packages that are
    # already installed is exactly the friction that makes an installer painful.
    if audio_libraries_present; then
        note "audio libraries already present"
        return 0
    fi

    local kind; kind=$(package_kind)
    step "Installing audio libraries"
    note "PortAudio, libsndfile, and espeak-ng back the voice pipeline."
    note "This is the one step that needs administrator rights."
    if [[ "$kind" == "rpm" ]]; then
        sudo dnf install -y portaudio libsndfile espeak-ng \
            || die "could not install the audio libraries"
    elif [[ "$kind" == "deb" ]]; then
        sudo apt-get update -qq || die "could not refresh the package lists"
        sudo apt-get install -y libportaudio2 libsndfile1 espeak-ng \
            || die "could not install the audio libraries"
    else
        warn "Unrecognised distribution; install portaudio, libsndfile and espeak-ng yourself."
        return 0
    fi
    ok "audio libraries present"
}

# --------------------------------------------------------------- release fetch

resolve_release() {
    TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/dax-install.XXXXXXXX")
    local base
    if [[ -n "$MANIFEST_SOURCE" ]]; then
        [[ -n "$CHECKSUMS_SOURCE" ]] || die "--manifest also needs --checksums"
    elif [[ -n "$PIN_VERSION" ]]; then
        base="https://github.com/$REPOSITORY/releases/download/v$PIN_VERSION"
        MANIFEST_SOURCE="$base/release-manifest.json"
        CHECKSUMS_SOURCE="$base/SHA256SUMS"
    else
        base="https://github.com/$REPOSITORY/releases/latest/download"
        MANIFEST_SOURCE="$base/release-manifest.json"
        CHECKSUMS_SOURCE="$base/SHA256SUMS"
    fi

    step "Fetching release"
    fetch "$CHECKSUMS_SOURCE" "$TEMP_DIR/SHA256SUMS"
    fetch "$MANIFEST_SOURCE" "$TEMP_DIR/release-manifest.json"

    # The manifest carries a digest for every artifact, so authenticating the
    # manifest authenticates the entire release.
    ( cd "$TEMP_DIR" \
        && grep ' release-manifest.json$' SHA256SUMS | sha256sum --check --status ) \
        || die "release-manifest.json does not match the release SHA256SUMS"

    local local_manifest=0
    [[ "$MANIFEST_SOURCE" == https://* ]] || local_manifest=1

    VERSION=$(python3 - "$TEMP_DIR/release-manifest.json" "$SUPPORTED_API_VERSION" \
              "${PIN_VERSION:-}" "$REPOSITORY" "$local_manifest" <<'PY'
import json, re, sys
manifest = json.load(open(sys.argv[1]))
supported, pinned, repository = sys.argv[2], sys.argv[3], sys.argv[4]
local_manifest = sys.argv[5] == "1"

if manifest.get("schema_version") != 1:
    raise SystemExit("unsupported release manifest schema; upgrade this installer")
version = manifest.get("version", "")
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
    raise SystemExit("release manifest has no valid version")
if pinned and pinned != version:
    raise SystemExit(f"asked for {pinned} but the manifest describes {version}")
if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("commit", "")):
    raise SystemExit("release manifest has no valid commit")

compatibility = manifest.get("api_compatibility", {})
if compatibility.get("backend") != supported:
    raise SystemExit(
        f"release {version} speaks backend API {compatibility.get('backend')}, "
        f"this installer supports {supported}"
    )

# An artifact URL is where a download comes from, so a manifest fetched from a
# release may only point back into that same release. A manifest handed over
# from local disk is already as trusted as the files beside it, so it may name
# them directly — that is what makes a mirrored or air-gapped install possible.
expected = f"https://github.com/{repository}/releases/download/v{version}/"
for artifact in manifest.get("artifacts", []):
    name, url = artifact.get("name", ""), artifact.get("url", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", name):
        raise SystemExit(f"unsafe artifact name: {name!r}")
    permitted = url.startswith(expected) or (
        local_manifest and url.startswith(("file://", "/"))
    )
    if not permitted or not url.endswith("/" + name):
        raise SystemExit(f"artifact {name} points outside release v{version}")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact.get("sha256", "")):
        raise SystemExit(f"artifact {name} has no valid digest")
    if not isinstance(artifact.get("size"), int) or artifact["size"] < 1:
        raise SystemExit(f"artifact {name} has no valid size")
print(version)
PY
    ) || exit 1

    ok "Dax $VERSION"
    verify_provenance "$TEMP_DIR/release-manifest.json"
}

verify_provenance() {
    local file="$1"
    # Build provenance attests a published release artifact. A manifest handed
    # over from local disk was never published, so there is nothing to attest.
    if [[ "$MANIFEST_SOURCE" != https://* ]]; then
        [[ "$REQUIRE_ATTESTATION" -eq 0 ]] \
            || die "--require-attestation cannot apply to a local --manifest"
        note "Local manifest: provenance does not apply; digests verified against it."
        return 0
    fi
    if ! have gh || ! gh auth status >/dev/null 2>&1; then
        [[ "$REQUIRE_ATTESTATION" -eq 0 ]] \
            || die "--require-attestation needs the GitHub CLI, authenticated"
        note "Provenance not checked (no authenticated gh); digests verified over TLS."
        return 0
    fi
    if gh attestation verify "$file" --repo "$REPOSITORY" >/dev/null 2>&1; then
        ok "GitHub build provenance verified"
    elif [[ "$REQUIRE_ATTESTATION" -eq 1 ]]; then
        die "build provenance did not verify for $(basename "$file")"
    else
        warn "Build provenance did not verify; continuing on digests alone."
    fi
}

# Download one artifact by role, verify size and digest, echo its path.
artifact_path() {
    local role="$1" arch="${2:-any}" line name url sha size destination
    line=$(python3 - "$TEMP_DIR/release-manifest.json" "$role" "$arch" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1]))
role, arch = sys.argv[2], sys.argv[3]
for artifact in manifest["artifacts"]:
    if artifact["role"] == role and artifact["arch"] in (arch, "any"):
        print("\t".join([artifact["name"], artifact["url"],
                         artifact["sha256"], str(artifact["size"])]))
        break
PY
    )
    [[ -n "$line" ]] || return 1

    IFS=$'\t' read -r name url sha size <<<"$line"
    destination="$TEMP_DIR/$name"
    [[ -f "$destination" ]] || fetch "$url" "$destination"

    local actual
    actual=$(stat -c %s "$destination")
    [[ "$actual" == "$size" ]] || die "$name is $actual bytes, the manifest says $size"
    actual=$(sha256sum "$destination" | cut -d' ' -f1)
    [[ "$actual" == "$sha" ]] || die "$name failed its SHA-256 check"

    printf '%s' "$destination"
}

# --------------------------------------------------------------- service state

unit_active()  { systemctl --user is-active --quiet "$1"; }
unit_enabled() { systemctl --user is-enabled --quiet "$1" 2>/dev/null; }

# True when the per-user systemd manager is reachable. When it is not — an SSH
# or `su` session with no running user manager — every `systemctl --user` call
# fails to connect, and unit operations must be skipped rather than aborted on.
user_bus_up() { systemctl --user show-environment >/dev/null 2>&1; }

backend_ready() {
    curl --fail --silent --max-time 5 "http://127.0.0.1:$BACKEND_PORT/api/health" 2>/dev/null \
        | python3 -c '
import json, sys
try:
    health = json.load(sys.stdin)
except ValueError:
    sys.exit(1)
sys.exit(0 if (
    health.get("status") == "ok"
    and health.get("role") == "authoritative"
    and health.get("api_protocol") == "dax"
    and health.get("api_version") == int(sys.argv[1])
    and health.get("liveness") is True
    and health.get("readiness") is True
    and isinstance(health.get("instance_id"), str)
    and health["instance_id"]
) else 1)
' "$SUPPORTED_API_VERSION"
}

# A first start downloads Whisper and Piper voice models, which is why the
# default deadline is minutes rather than seconds.
wait_for_backend() {
    local deadline=$((SECONDS + READINESS_TIMEOUT)) i=0 started=$SECONDS
    local frames='|/-+'
    while (( SECONDS < deadline )); do
        unit_active dax-assistant.service || { [[ "$INTERACTIVE" -eq 1 ]] && printf '\r\033[2K'; return 1; }
        if backend_ready; then
            [[ "$INTERACTIVE" -eq 1 ]] && printf '\r\033[2K'
            return 0
        fi
        if [[ "$INTERACTIVE" -eq 1 ]]; then
            printf '\r\033[2K  %s%s%s starting up, this can take a few minutes on a first install (%ss)' \
                "$CYAN" "${frames:i++%4:1}" "$RESET" "$((SECONDS - started))"
        fi
        sleep 2
    done
    [[ "$INTERACTIVE" -eq 1 ]] && printf '\r\033[2K'
    return 1
}

# ------------------------------------------------------------- installed state

installed_versions() {
    local directory="$1" entry version
    [[ -d "$directory" ]] || return 0
    for entry in "$directory"/*; do
        [[ -d "$entry" ]] || continue
        version=$(basename "$entry")
        [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] && printf '%s\n' "$version"
    done | sort -t. -k1,1nr -k2,2nr -k3,3nr
}

active_version() {
    local target
    [[ -L "$1" ]] || return 0
    target=$(readlink -f "$1") || return 0
    [[ -n "$target" ]] || return 0
    basename "$target"
}

# Keep the newest few releases. The active backend and whatever the node runs
# are never deletion candidates, whatever their age.
prune_releases() {
    local active node_active kept=0 version
    active=$(active_version "$CURRENT_LINK")
    node_active=$(active_version "$NODE_CURRENT_LINK")
    while read -r version; do
        [[ -n "$version" ]] || continue
        if [[ "$version" == "$active" ]] || (( kept < KEEP_RELEASES )); then
            kept=$((kept + 1))
            continue
        fi
        [[ "$version" == "$node_active" ]] && continue
        rm -rf "${RELEASES_DIR:?}/$version"
        note "removed superseded release $version"
    done < <(installed_versions "$RELEASES_DIR")
}

backup_database() {
    [[ -f "$STATE_DIR/dax.db" ]] || return 0
    local stamp destination
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    destination="$BACKUP_DIR/dax-$stamp.db"
    install -d -m 700 "$BACKUP_DIR"
    # sqlite3's backup API is the only safe copy of a live WAL database.
    # Failing here is fatal on purpose: this backup is the entire safety net for
    # an upgrade or a rollback, and continuing without one silently removes it.
    python3 - "$STATE_DIR/dax.db" "$destination" <<'PY' || {
import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
with target:
    source.backup(target)
source.close()
target.close()
PY
        rm -f "$destination"
        die "could not back up $STATE_DIR/dax.db; refusing to continue without a backup"
    }
    chmod 600 "$destination"
    # The database is useless without the key that decrypts its secrets.
    [[ ! -f "$STATE_DIR/dax.key" ]] \
        || install -m 600 "$STATE_DIR/dax.key" "$BACKUP_DIR/dax-$stamp.key"
    note "database backed up to $destination"
}

restore_backend() {
    local target="$1" was_active="$2" was_enabled="$3"
    if [[ -n "$target" && -e "$target" ]]; then
        ln -sfn "$target" "$CURRENT_LINK.new"
        mv -Tf "$CURRENT_LINK.new" "$CURRENT_LINK"
    else
        rm -f "$CURRENT_LINK"
    fi
    systemctl --user daemon-reload
    [[ "$was_enabled" -eq 1 ]] \
        || systemctl --user disable dax-assistant.service >/dev/null 2>&1 || true
    if [[ "$was_active" -eq 1 ]]; then
        systemctl --user restart dax-assistant.service >/dev/null 2>&1 || true
    else
        systemctl --user stop dax-assistant.service >/dev/null 2>&1 || true
    fi
}

# ------------------------------------------------------------------- installs

build_runtime() {
    local target="$1" wheel="$2" requirements="$3" python
    "$UV" python install 3.11 >/dev/null 2>&1 || die "could not provision Python 3.11"
    python=$("$UV" python find 3.11) || die "could not locate the managed Python 3.11"

    # Built directly at its final path: a venv records absolute paths in its
    # scripts, so creating it elsewhere and moving it produces broken shebangs.
    rm -rf "$target"
    install -d -m 700 "$target"
    "$UV" venv --python "$python" "$target/.venv" >/dev/null 2>&1 \
        || die "could not create the Python environment"
    "$UV" pip install --quiet --python "$target/.venv/bin/python" \
        --require-hashes --requirement "$requirements" \
        || die "dependency installation failed"
    "$UV" pip install --quiet --python "$target/.venv/bin/python" --no-deps "$wheel" \
        || die "installing the Dax wheel failed"
}

install_backend() {
    local target="$RELEASES_DIR/$VERSION" wheel requirements unit
    wheel=$(artifact_path backend-wheel) || die "could not obtain the backend wheel for $VERSION"
    requirements=$(artifact_path backend-dependency-lock) \
        || die "could not obtain the dependency lock for $VERSION"
    unit=$(artifact_path backend-service) || die "could not obtain the backend service unit for $VERSION"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        note "would install backend $VERSION into $target"
        return 0
    fi

    install_audio_libraries
    ensure_linger

    step "Installing the backend"
    local previous="" was_active=0 was_enabled=0
    [[ ! -L "$CURRENT_LINK" ]] || previous=$(readlink "$CURRENT_LINK")
    unit_active dax-assistant.service && was_active=1
    unit_enabled dax-assistant.service && was_enabled=1

    install -d -m 700 "$RELEASES_DIR" "$STATE_DIR" "$CACHE_DIR" \
        "$DATA_DIR/models" "$STATE_DIR/memory"
    backup_database
    build_runtime "$target" "$wheel" "$requirements"
    ok "runtime built at $target"

    ln -sfn "$target" "$CURRENT_LINK.new"
    mv -Tf "$CURRENT_LINK.new" "$CURRENT_LINK"

    install -d -m 700 "$UNIT_DIR"
    install -m 600 "$unit" "$BACKEND_UNIT"
    systemctl --user daemon-reload
    systemctl --user enable dax-assistant.service >/dev/null 2>&1 \
        || die "could not enable dax-assistant.service"
    systemctl --user restart dax-assistant.service \
        || { restore_backend "$previous" "$was_active" "$was_enabled"
             die "dax-assistant.service failed to start; the previous release was restored"; }

    if ! wait_for_backend; then
        warn "the backend did not become ready; restoring the previous release"
        restore_backend "$previous" "$was_active" "$was_enabled"
        die "backend $VERSION never became ready. See: journalctl --user -u dax-assistant -n 50"
    fi
    ok "backend $VERSION is running and ready"
    prune_releases
}

install_node() {
    local target="$NODE_RELEASES_DIR/$VERSION" wheel requirements unit
    wheel=$(artifact_path backend-wheel) || die "could not obtain the node wheel for $VERSION"
    requirements=$(artifact_path backend-dependency-lock) \
        || die "could not obtain the dependency lock for $VERSION"
    unit=$(artifact_path node-service) || die "could not obtain the node service unit for $VERSION"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        note "would install capability node $VERSION into $target"
        return 0
    fi

    # Replacing the runtime under a running node would swap the code beneath an
    # live connection, so require an explicit stop first.
    unit_active dax-assistant-node.service \
        && die "dax-assistant-node.service is running; stop it before replacing its runtime"

    [[ "$WANT_BACKEND" -eq 1 ]] || install_audio_libraries

    step "Installing the capability node"
    install -d -m 700 "$NODE_RELEASES_DIR"
    build_runtime "$target" "$wheel" "$requirements"

    ln -sfn "$target" "$NODE_CURRENT_LINK.new"
    mv -Tf "$NODE_CURRENT_LINK.new" "$NODE_CURRENT_LINK"
    install -d -m 700 "$UNIT_DIR"
    install -m 600 "$unit" "$NODE_UNIT"
    systemctl --user daemon-reload
    # Left stopped on purpose: a node has nothing to connect to until it is
    # enrolled, and enrolling needs an already-authenticated client.
    systemctl --user disable dax-assistant-node.service >/dev/null 2>&1 || true
    ok "node runtime installed, stopped until you enrol it"
}

install_desktop() {
    local kind arch package
    kind=$(package_kind)
    [[ -n "$kind" ]] \
        || die "unrecognised distribution; download the RPM or deb from https://github.com/$REPOSITORY/releases"
    arch="$MACHINE"
    [[ "$arch" == "x86_64" ]] \
        || die "the desktop package is published for x86_64 only; this machine is $arch"

    package=$(artifact_path "desktop-$kind" "$arch") \
        || die "could not obtain the desktop $kind package for $VERSION"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        note "would install $(basename "$package")"
        return 0
    fi

    step "Installing the desktop client"
    note "This needs administrator rights to install a system package."
    if [[ "$kind" == "rpm" ]]; then
        sudo dnf install -y "$package" || die "desktop package installation failed"
    else
        sudo apt-get install -y "$package" || die "desktop package installation failed"
    fi
    ok "desktop client installed; launch Dax from your application menu"
}

install_from_source() {
    [[ -f "$SOURCE_DIR/pyproject.toml" ]] || die "--source is not a Dax checkout: $SOURCE_DIR"
    [[ -f "$SOURCE_DIR/src/dax/web/static/index.html" ]] \
        || die "this checkout has no built web assets; run 'npm run build' in web/ first"

    step "Installing the backend from $SOURCE_DIR"
    warn "Source mode is for development. It is not a verified release."
    if [[ "$DRY_RUN" -eq 1 ]]; then
        note "would run: uv sync --frozen --all-extras in $SOURCE_DIR"
        return 0
    fi
    "$UV" --directory "$SOURCE_DIR" sync --frozen --all-extras || die "uv sync failed"
    install -d -m 700 "$DATA_DIR" "$UNIT_DIR"
    ln -sfn "$SOURCE_DIR" "$CURRENT_LINK.new"
    mv -Tf "$CURRENT_LINK.new" "$CURRENT_LINK"
    install -m 600 "$SOURCE_DIR/systemd/dax-assistant.service" "$BACKEND_UNIT"
    systemctl --user daemon-reload
    systemctl --user enable --now dax-assistant.service
    wait_for_backend || warn "the backend has not reported ready yet"
    ok "source backend installed"
}

# ------------------------------------------------------------------- account

create_account() {
    local dax="$CURRENT_LINK/.venv/bin/dax" configured
    [[ -x "$dax" ]] || return 0

    configured=$(curl --fail --silent --max-time 5 \
        "http://127.0.0.1:$BACKEND_PORT/api/auth/status" 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin).get("configured"))' 2>/dev/null) \
        || return 0
    if [[ "$configured" == "True" ]]; then
        note "this backend already has an account"
        return 0
    fi

    step "Creating your account"
    if [[ "$INTERACTIVE" -eq 0 ]]; then
        warn "No terminal to prompt on. Run '$dax claim' on this machine to set the password."
        return 0
    fi
    # The first account can only be created from the backend's own machine, so
    # an unclaimed backend cannot be taken over by whoever reaches it first.
    note "Only this machine can create the first account, which is why it happens here."
    "$dax" claim \
        || warn "account not created; run '$dax claim' here when you are ready"
}

# ------------------------------------------------------------------ reporting

print_next_steps() {
    local address; address=$(lan_address)
    printf '\n  %s%sDone.%s\n\n' "$BOLD" "$GREEN" "$RESET"

    if [[ "$WANT_BACKEND" -eq 1 ]]; then
        printf '  %sOn this machine%s\n    http://127.0.0.1:%s\n' "$BOLD" "$RESET" "$BACKEND_PORT"
        if [[ -n "$address" ]]; then
            printf '\n  %sFrom your other devices%s\n    %shttp://%s:%s%s\n' \
                "$BOLD" "$RESET" "$CYAN" "$address" "$BACKEND_PORT" "$RESET"
            printf '    %sEnter that exact address in the desktop app and on your phone.%s\n' \
                "$DIM" "$RESET"
        else
            printf '\n  %sNo private LAN address was found, so other devices will need\n' "$DIM"
            printf '  HTTPS through a reverse proxy or a VPN to reach this backend.%s\n' "$RESET"
        fi
        printf '\n  %sLogs%s    journalctl --user -u dax-assistant -f\n' "$DIM" "$RESET"
        printf '  %sState%s   bash install.sh status\n' "$DIM" "$RESET"
    fi
    if [[ "$WANT_NODE" -eq 1 ]]; then
        printf '\n  %sThe node is installed but stopped.%s Enrol it from the desktop app\n' \
            "$BOLD" "$RESET"
        printf '  under Settings → Access → Devices, then start it.\n'
    fi
    printf '\n'
}

# ------------------------------------------------------------------- commands

command_status() {
    local version node_version address
    version=$(active_version "$CURRENT_LINK")
    node_version=$(active_version "$NODE_CURRENT_LINK")
    printf '\n'

    if [[ -n "$version" ]]; then
        printf '  %sBackend%s  %s\n' "$BOLD" "$RESET" "$version"
        if ! unit_active dax-assistant.service; then
            printf '           %sstopped%s\n' "$RED" "$RESET"
        elif backend_ready; then
            printf '           %srunning, ready%s\n' "$GREEN" "$RESET"
        else
            printf '           %srunning, not ready yet%s\n' "$YELLOW" "$RESET"
        fi
        printf '           http://127.0.0.1:%s\n' "$BACKEND_PORT"
        address=$(lan_address)
        [[ -n "$address" ]] && printf '           http://%s:%s\n' "$address" "$BACKEND_PORT"
    else
        printf '  %sBackend%s  not installed\n' "$BOLD" "$RESET"
    fi

    if [[ -n "$node_version" ]]; then
        printf '\n  %sNode%s     %s' "$BOLD" "$RESET" "$node_version"
        if unit_active dax-assistant-node.service; then
            printf ' (%srunning%s)\n' "$GREEN" "$RESET"
        else
            printf ' (stopped)\n'
        fi
    fi
    printf '\n'
}

command_list() {
    local active version found=0 node_active
    active=$(active_version "$CURRENT_LINK")
    printf '\n  %sBackend releases%s  %s\n' "$BOLD" "$RESET" "$RELEASES_DIR"
    while read -r version; do
        [[ -n "$version" ]] || continue
        found=1
        if [[ "$version" == "$active" ]]; then
            printf '    %s❯ %s  active%s\n' "$GREEN" "$version" "$RESET"
        else
            printf '      %s\n' "$version"
        fi
    done < <(installed_versions "$RELEASES_DIR")
    [[ "$found" -eq 1 ]] || printf '      %snone%s\n' "$DIM" "$RESET"

    node_active=$(active_version "$NODE_CURRENT_LINK")
    if [[ -n "$node_active" ]]; then
        printf '\n  %sNode releases%s  %s\n' "$BOLD" "$RESET" "$NODE_RELEASES_DIR"
        while read -r version; do
            [[ -n "$version" ]] || continue
            if [[ "$version" == "$node_active" ]]; then
                printf '    %s❯ %s  active%s\n' "$GREEN" "$version" "$RESET"
            else
                printf '      %s\n' "$version"
            fi
        done < <(installed_versions "$NODE_RELEASES_DIR")
    fi
    printf '\n'
}

command_rollback() {
    local active target was_active=0 was_enabled=0 previous=""
    active=$(active_version "$CURRENT_LINK")
    if [[ -n "$ROLLBACK_VERSION" ]]; then
        target="$ROLLBACK_VERSION"
        [[ -d "$RELEASES_DIR/$target" ]] \
            || die "release $target is not installed; see: bash install.sh list"
        [[ "$target" != "$active" ]] || die "release $target is already active"
    else
        target=$(installed_versions "$RELEASES_DIR" | grep -v -x -- "$active" | head -1)
        [[ -n "$target" ]] || die "no other installed release to roll back to"
    fi
    [[ -x "$RELEASES_DIR/$target/.venv/bin/python" ]] \
        || die "release $target has no usable environment"
    [[ -f "$BACKEND_UNIT" ]] || die "no backend unit installed; nothing to roll back"

    printf '\n'
    warn "Schema migrations run forward only. If $active migrated the database, $target"
    warn "may be unable to open it. A backup and its key are written first."
    confirm "Roll the backend back from ${active:-nothing} to $target?" || die "cancelled"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        note "would point $CURRENT_LINK at $RELEASES_DIR/$target and restart"
        return 0
    fi

    unit_active dax-assistant.service && was_active=1
    unit_enabled dax-assistant.service && was_enabled=1
    [[ ! -L "$CURRENT_LINK" ]] || previous=$(readlink "$CURRENT_LINK")
    backup_database

    ln -sfn "$RELEASES_DIR/$target" "$CURRENT_LINK.new"
    mv -Tf "$CURRENT_LINK.new" "$CURRENT_LINK"
    if ! systemctl --user restart dax-assistant.service || ! wait_for_backend; then
        warn "release $target did not become ready; returning to $active"
        restore_backend "$previous" "$was_active" "$was_enabled"
        die "rollback to $target failed; the previous release was restored"
    fi
    ok "the backend is now running $target"
}

command_uninstall() {
    printf '\n'
    if [[ "$PURGE_STATE" -eq 1 ]]; then
        warn "--purge deletes $STATE_DIR: the database, the secret key, node"
        warn "credentials, and every backup. Encrypted settings and API keys"
        warn "cannot be recovered without that key. This is irreversible."
    else
        note "The database, key, and backups in $STATE_DIR are kept."
    fi
    confirm "Remove Dax from this machine?" || die "cancelled"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        note "would stop both services and remove the units, $RELEASES_DIR and $NODE_RELEASES_DIR"
        [[ "$PURGE_STATE" -eq 1 ]] && note "would also delete $STATE_DIR"
        return 0
    fi

    local unit
    if user_bus_up; then
        for unit in dax-assistant.service dax-assistant-node.service; do
            systemctl --user disable --now "$unit" >/dev/null 2>&1 || true
        done
        rm -f "$BACKEND_UNIT" "$NODE_UNIT"
        systemctl --user daemon-reload >/dev/null 2>&1 || true
    else
        warn "the per-user systemd manager is not reachable from this shell,"
        warn "so services cannot be stopped here. Removing the unit files anyway."
        warn "If a service is still running, from a login/graphical session run:"
        warn "  systemctl --user disable --now dax-assistant.service dax-assistant-node.service"
        rm -f "$BACKEND_UNIT" "$NODE_UNIT"
    fi
    rm -f "$CURRENT_LINK" "$NODE_CURRENT_LINK"
    rm -rf "${RELEASES_DIR:?}" "${NODE_RELEASES_DIR:?}" "${CACHE_DIR:?}"
    ok "services, units, and releases removed"

    if [[ "$PURGE_STATE" -eq 1 ]]; then
        rm -rf "${STATE_DIR:?}" "${DATA_DIR:?}"
        ok "all state removed"
    else
        note "state kept at $STATE_DIR; voice models kept at $DATA_DIR/models"
    fi
    note "The desktop package is managed by your distribution:"
    note "  sudo dnf remove Dax   ·   sudo apt-get remove dax"
    printf '\n'
}

command_install() {
    printf '\n%s%s  Dax%s  ·  self-hosted assistant\n' "$BOLD" "$CYAN" "$RESET"

    if [[ "$SELECTION_GIVEN" -eq 0 ]]; then
        if [[ "$INTERACTIVE" -eq 1 && "$ASSUME_YES" -eq 0 ]]; then
            choose_components
        else
            WANT_BACKEND=1
            WANT_DESKTOP=1
        fi
    fi
    (( WANT_BACKEND + WANT_DESKTOP + WANT_NODE > 0 )) || die "nothing selected to install"

    ensure_base_tools
    # The desktop package is a distro package; only the Python components need uv.
    (( WANT_BACKEND + WANT_NODE > 0 )) && ensure_uv

    # The units reference canonical XDG paths, so a relocated home layout would
    # produce a service that cannot find its own runtime.
    if (( WANT_BACKEND + WANT_NODE > 0 )); then
        [[ "$XDG_DATA_HOME" == "$HOME/.local/share" \
            && "$XDG_STATE_HOME" == "$HOME/.local/state" \
            && "$XDG_CONFIG_HOME" == "$HOME/.config" ]] \
            || die "backend and node installs require the default XDG directories"
    fi

    if [[ -n "$SOURCE_DIR" ]]; then
        install_from_source
        print_next_steps
        return 0
    fi

    resolve_release
    [[ "$WANT_BACKEND" -eq 1 ]] && install_backend
    [[ "$WANT_NODE" -eq 1 ]] && install_node
    [[ "$WANT_DESKTOP" -eq 1 ]] && install_desktop

    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '\n'
        ok "dry run complete: everything verified, nothing installed"
        return 0
    fi

    [[ "$WANT_BACKEND" -eq 1 && "$SKIP_ACCOUNT" -eq 0 ]] && create_account
    print_next_steps
}

case "$COMMAND" in
    install)   command_install ;;
    status)    command_status ;;
    list)      command_list ;;
    rollback)  command_rollback ;;
    uninstall) command_uninstall ;;
esac
