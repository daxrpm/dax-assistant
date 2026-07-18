#!/usr/bin/env bash
# Production Linux installer and lifecycle manager for Dax Assistant.
#
# Usage:
#   ./scripts/install.sh install [options]
#   ./scripts/install.sh update
#   ./scripts/install.sh doctor
#   ./scripts/install.sh service
#   ./scripts/install.sh uninstall [--purge]

set -Eeuo pipefail
IFS=$'\n\t'

REPO_URL="${DAX_REPO_URL:-https://github.com/daxrpm/dax-assistant.git}"
COMMAND="install"
LANGUAGE="es"
VERSION=""
WITH_VOICE=1
WITH_SERVICE=1
WITH_MODELS=1
INSTALL_DEPS="ask"
ASSUME_YES=0
PURGE=0
DRY_RUN=0
INSTALL_DIR_EXPLICIT=0

[[ -n "${DAX_INSTALL_DIR:-}" ]] && INSTALL_DIR_EXPLICIT=1

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

APP_DIR="${DAX_INSTALL_DIR:-$XDG_DATA_HOME/dax-assistant/app}"
DATA_DIR="${DAX_DATA_DIR:-$XDG_DATA_HOME/dax-assistant}"
STATE_DIR="${DAX_STATE_DIR:-$XDG_STATE_HOME/dax-assistant}"
CACHE_DIR="${DAX_CACHE_DIR:-$XDG_CACHE_HOME/dax-assistant}"
MODELS_DIR="${DAX_MODELS_DIR:-$DATA_DIR/models}"
MEMORY_DIR="${DAX_MEMORY_DIR:-$STATE_DIR/memory}"
DATABASE_PATH="${DAX_DATABASE_PATH:-$STATE_DIR/dax.db}"
UNIT_DIR="$XDG_CONFIG_HOME/systemd/user"
UNIT_PATH="$UNIT_DIR/dax-assistant.service"
BACKUP_DIR="$STATE_DIR/backups"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
SOURCE_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ -t 1 ]]; then
    RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; BLUE=$'\033[0;34m'; YELLOW=$'\033[0;33m'; RESET=$'\033[0m'
else
    RED=""; GREEN=""; BLUE=""; YELLOW=""; RESET=""
fi

info() { printf '%s[INFO]%s %s\n' "$BLUE" "$RESET" "$*"; }
ok() { printf '%s[OK]%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '%s[WARN]%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
die() { printf '%s[ERROR]%s %s\n' "$RED" "$RESET" "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
Dax Assistant Linux installer

Commands:
  install              Install Dax and enable its user service (default)
  update               Back up state, update source, sync, and health-check
  doctor               Check service, storage, network, audio, and models
  service              Regenerate and restart the systemd user service
  uninstall            Remove app and unit, preserving state/models by default

Options:
  --yes                 Non-interactive defaults
  --language es|en      Voice language (default: es)
  --version REF         Git tag/branch/commit to install
  --install-dir PATH    Application source directory
  --no-voice            Install without local microphone/voice dependencies
  --skip-models         Do not download local voice models
  --no-service          Install without systemd integration
  --install-system-deps Install supported distro packages using sudo
  --skip-system-deps    Never invoke a system package manager
  --purge               With uninstall, also remove encrypted state and models
  --dry-run             Validate and print the resolved layout without changes
  -h, --help            Show this help

Environment overrides:
  DAX_INSTALL_DIR, DAX_DATA_DIR, DAX_STATE_DIR, DAX_MODELS_DIR,
  DAX_MEMORY_DIR, DAX_DATABASE_PATH, DAX_REPO_URL
EOF
}

if [[ $# -gt 0 && "$1" != -* ]]; then
    COMMAND="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|-y) ASSUME_YES=1 ;;
        --language) LANGUAGE="${2:-}"; shift ;;
        --version) VERSION="${2:-}"; shift ;;
        --install-dir) APP_DIR="${2:-}"; INSTALL_DIR_EXPLICIT=1; shift ;;
        --no-voice) WITH_VOICE=0; WITH_MODELS=0 ;;
        --skip-models) WITH_MODELS=0 ;;
        --no-service) WITH_SERVICE=0 ;;
        --install-system-deps) INSTALL_DEPS="yes" ;;
        --skip-system-deps) INSTALL_DEPS="no" ;;
        --purge) PURGE=1 ;;
        --dry-run) DRY_RUN=1 ;;
        --help|-h) usage; exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
    shift
done

[[ "$LANGUAGE" == "es" || "$LANGUAGE" == "en" ]] || die "--language must be es or en"
[[ " install update doctor service uninstall " == *" $COMMAND "* ]] || die "Unknown command: $COMMAND"
[[ "$(uname -s)" == "Linux" ]] || die "This installer supports Linux only"
[[ "$EUID" -ne 0 ]] || die "Run as your desktop user, not root"

if [[ "$INSTALL_DIR_EXPLICIT" -eq 0 && -f "$SOURCE_ROOT/pyproject.toml" ]]; then
    APP_DIR="$SOURCE_ROOT"
fi

APP_DIR="$(realpath -m "$APP_DIR")"
DATA_DIR="$(realpath -m "$DATA_DIR")"
STATE_DIR="$(realpath -m "$STATE_DIR")"
CACHE_DIR="$(realpath -m "$CACHE_DIR")"
MODELS_DIR="$(realpath -m "$MODELS_DIR")"
MEMORY_DIR="$(realpath -m "$MEMORY_DIR")"
DATABASE_PATH="$(realpath -m "$DATABASE_PATH")"
KEY_PATH="$(dirname "$DATABASE_PATH")/dax.key"

print_layout() {
    printf 'Application: %s\nState:       %s\nDatabase:    %s\nModels:      %s\nUnit:        %s\n' \
        "$APP_DIR" "$STATE_DIR" "$DATABASE_PATH" "$MODELS_DIR" "$UNIT_PATH"
}

if [[ "$DRY_RUN" -eq 1 ]]; then
    info "Dry run for '$COMMAND'"
    print_layout
    exit 0
fi

confirm() {
    local prompt="$1"
    [[ "$ASSUME_YES" -eq 1 ]] && return 0
    [[ -t 0 ]] || return 0
    read -r -p "$prompt [Y/n] " answer
    [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]
}

ensure_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

install_system_dependencies() {
    [[ "$INSTALL_DEPS" == "no" ]] && return 0
    if [[ "$INSTALL_DEPS" == "ask" ]] && ! confirm "Install Linux audio/build prerequisites with sudo?"; then
        return 0
    fi
    [[ -r /etc/os-release ]] || die "Cannot identify Linux distribution"
    # shellcheck disable=SC1091
    source /etc/os-release
    local family="${ID_LIKE:-$ID}"
    if [[ "$family" == *debian* || "$ID" == "ubuntu" || "$ID" == "debian" ]]; then
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl git build-essential libportaudio2 portaudio19-dev libsndfile1 espeak-ng
    elif [[ "$family" == *fedora* || "$family" == *rhel* || "$ID" == "fedora" ]]; then
        sudo dnf install -y ca-certificates curl git gcc gcc-c++ make portaudio portaudio-devel libsndfile espeak-ng
    elif [[ "$family" == *arch* || "$ID" == "arch" ]]; then
        sudo pacman -S --needed --noconfirm ca-certificates curl git base-devel portaudio libsndfile espeak-ng
    elif [[ "$family" == *suse* || "$ID" == "opensuse-tumbleweed" || "$ID" == "opensuse-leap" ]]; then
        sudo zypper --non-interactive install ca-certificates curl git gcc gcc-c++ make portaudio-devel libsndfile1 espeak-ng
    else
        die "Unsupported distro '$ID'. Install git, curl, a C compiler, PortAudio, libsndfile, and espeak-ng, then rerun with --skip-system-deps."
    fi
}

ensure_uv() {
    if ! command -v uv >/dev/null 2>&1; then
        ensure_command curl
        info "Installing uv from the official installer"
        curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    ensure_command uv
    uv python install 3.11
}

prepare_source() {
    ensure_command git
    if [[ -f "$APP_DIR/pyproject.toml" ]]; then
        grep -q '^name = "dax-assistant"' "$APP_DIR/pyproject.toml" || die "$APP_DIR is not Dax Assistant"
        return 0
    fi
    [[ ! -e "$APP_DIR" ]] || die "$APP_DIR exists but is not a Dax checkout"
    mkdir -p "$(dirname "$APP_DIR")"
    git clone --filter=blob:none "$REPO_URL" "$APP_DIR"
    touch "$APP_DIR/.dax-managed-install"
    if [[ -n "$VERSION" ]]; then
        git -C "$APP_DIR" fetch --tags --force
        git -C "$APP_DIR" checkout --detach "$VERSION"
    fi
}

sync_environment() {
    local args=(sync --frozen --no-dev --compile-bytecode --python 3.11)
    [[ "$WITH_VOICE" -eq 1 ]] && args+=(--extra voice)
    info "Installing locked Python environment"
    uv --directory "$APP_DIR" "${args[@]}"
    [[ -f "$APP_DIR/src/dax/web/static/index.html" ]] || die "Production web assets are missing from this release"
}

initialize_storage() {
    install -d -m 700 "$STATE_DIR" "$BACKUP_DIR" "$DATA_DIR" "$MODELS_DIR" "$MEMORY_DIR" "$CACHE_DIR"
    env \
        DAX_STORAGE__DATABASE_PATH="$DATABASE_PATH" \
        DAX_STORAGE__MODELS_PATH="$MODELS_DIR" \
        DAX_MEMORY_PATH="$MEMORY_DIR" \
        "$APP_DIR/.venv/bin/python" - "$LANGUAGE" <<'PY'
import sys
from dax.core.config import load_config
from dax.core.config_io import save_encrypted_config
from dax.storage.secrets import SecretStore

config = load_config(None)
object.__setattr__(config, "language_default", sys.argv[1])
object.__setattr__(config.voice, "stt_language", sys.argv[1])
store = SecretStore(config.storage.database_path)
save_encrypted_config(config, store)
PY
    chmod 600 "$DATABASE_PATH" "$KEY_PATH" 2>/dev/null || true
}

download_models() {
    [[ "$WITH_VOICE" -eq 1 && "$WITH_MODELS" -eq 1 ]] || return 0
    info "Downloading local voice models (several GB on first install)"
    env HF_HOME="$CACHE_DIR/huggingface" DAX_MODELS_DIR="$MODELS_DIR" \
        uv --directory "$APP_DIR" run python scripts/download_models.py \
        --language "$LANGUAGE" --models-dir "$MODELS_DIR"
}

systemd_escape_value() {
    local value="$1"
    printf '%s' "${value//%/%%}"
}

write_service() {
    ensure_command systemctl
    local app models memory database
    app="$(systemd_escape_value "$APP_DIR")"
    models="$(systemd_escape_value "$MODELS_DIR")"
    memory="$(systemd_escape_value "$MEMORY_DIR")"
    database="$(systemd_escape_value "$DATABASE_PATH")"
    install -d -m 700 "$UNIT_DIR"
    umask 077
    cat > "$UNIT_PATH" <<EOF
[Unit]
Description=Dax Personal AI Assistant
Documentation=https://github.com/daxrpm/dax-assistant
Wants=network-online.target
After=network-online.target graphical-session.target

[Service]
Type=simple
WorkingDirectory=$app
ExecStart=$app/.venv/bin/dax
Restart=on-failure
RestartSec=5s
TimeoutStopSec=30s
KillMode=mixed
UMask=0077
Environment=PYTHONUNBUFFERED=1
Environment="DAX_STORAGE__DATABASE_PATH=$database"
Environment="DAX_STORAGE__MODELS_PATH=$models"
Environment="DAX_MEMORY_PATH=$memory"
Environment="HF_HOME=$(systemd_escape_value "$CACHE_DIR")/huggingface"

NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
RestrictSUIDSGID=yes
LockPersonality=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemd-analyze --user verify "$UNIT_PATH" >/dev/null
}

enable_service() {
    write_service
    systemctl --user enable --now dax-assistant.service
}

health_check() {
    local attempts=30
    while (( attempts > 0 )); do
        if curl --fail --silent --max-time 2 http://127.0.0.1:8420/api/health >/dev/null; then
            return 0
        fi
        sleep 1
        attempts=$((attempts - 1))
    done
    return 1
}

backup_database() {
    [[ -f "$DATABASE_PATH" ]] || return 0
    install -d -m 700 "$BACKUP_DIR"
    local timestamp target
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    target="$BACKUP_DIR/dax-$timestamp.db"
    "$APP_DIR/.venv/bin/python" - "$DATABASE_PATH" "$target" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1])
destination = sqlite3.connect(sys.argv[2])
with destination:
    source.backup(destination)
source.close()
destination.close()
PY
    chmod 600 "$target"
    if [[ -f "$KEY_PATH" ]]; then
        install -m 600 "$KEY_PATH" "$BACKUP_DIR/dax-$timestamp.key"
    fi
    ok "Database backup: $target"
}

install_dax() {
    install_system_dependencies
    ensure_uv
    prepare_source
    sync_environment
    initialize_storage
    download_models
    if [[ "$WITH_SERVICE" -eq 1 ]]; then
        enable_service
        health_check || die "Service did not become healthy. Run: journalctl --user -u dax-assistant -n 100"
    fi
    ok "Dax Assistant installed"
    print_layout
    printf 'Web UI: http://127.0.0.1:8420\n'
}

update_dax() {
    [[ -d "$APP_DIR/.git" ]] || die "No managed Git checkout at $APP_DIR"
    [[ -z "$(git -C "$APP_DIR" status --porcelain --untracked-files=no)" ]] || die "Refusing to update a checkout with modified tracked files"
    ensure_uv
    backup_database
    local old_revision
    old_revision="$(git -C "$APP_DIR" rev-parse HEAD)"
    git -C "$APP_DIR" fetch --tags --prune origin
    if [[ -n "$VERSION" ]]; then
        git -C "$APP_DIR" checkout --detach "$VERSION"
    else
        git -C "$APP_DIR" pull --ff-only
    fi
    sync_environment
    write_service
    systemctl --user restart dax-assistant.service
    if ! health_check; then
        warn "Update health check failed; rolling source back to $old_revision"
        git -C "$APP_DIR" reset --keep "$old_revision"
        sync_environment
        systemctl --user restart dax-assistant.service
        die "Update rolled back. Inspect the journal before retrying."
    fi
    ok "Dax Assistant updated"
}

doctor() {
    local failures=0
    print_layout
    for command in git uv systemctl curl; do
        if command -v "$command" >/dev/null 2>&1; then ok "$command available"; else warn "$command missing"; failures=$((failures + 1)); fi
    done
    if [[ -x "$APP_DIR/.venv/bin/dax" ]]; then ok "Python environment ready"; else warn "Dax executable missing"; failures=$((failures + 1)); fi
    if [[ -f "$DATABASE_PATH" && "$(stat -c '%a' "$DATABASE_PATH")" == "600" ]]; then ok "Encrypted database permissions: 600"; else warn "Database missing or permissions are not 600"; failures=$((failures + 1)); fi
    if systemctl --user is-active --quiet dax-assistant.service; then ok "systemd service active"; else warn "systemd service inactive"; failures=$((failures + 1)); fi
    if health_check; then ok "Web health check passed"; else warn "Web health check failed"; failures=$((failures + 1)); fi
    if [[ "$WITH_VOICE" -eq 1 && -x "$APP_DIR/.venv/bin/python" ]]; then
        if "$APP_DIR/.venv/bin/python" - <<'PY'
import sounddevice as sd

devices = sd.query_devices()
assert any(d.get("max_input_channels", 0) > 0 for d in devices)
assert any(d.get("max_output_channels", 0) > 0 for d in devices)
PY
        then ok "Audio input and output detected"; else warn "Audio preflight failed in this user session"; failures=$((failures + 1)); fi
    fi
    (( failures == 0 )) || die "$failures doctor check(s) failed"
    ok "All checks passed"
}

uninstall_dax() {
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user disable --now dax-assistant.service 2>/dev/null || true
        rm -f "$UNIT_PATH"
        systemctl --user daemon-reload
    fi
    if [[ -f "$APP_DIR/.dax-managed-install" ]]; then
        safe_remove_tree "$APP_DIR"
    elif [[ "$APP_DIR" != "$SOURCE_ROOT" ]]; then
        warn "Keeping unmarked application directory: $APP_DIR"
    else
        warn "Keeping source checkout used for this local installation: $APP_DIR"
    fi
    if [[ "$PURGE" -eq 1 ]]; then
        confirm "Permanently delete encrypted state, keys, memories, models, and backups?" || die "Purge cancelled"
        safe_remove_tree "$STATE_DIR"
        [[ "$DATA_DIR" == "$STATE_DIR" ]] || safe_remove_tree "$DATA_DIR"
        [[ "$CACHE_DIR" == "$STATE_DIR" || "$CACHE_DIR" == "$DATA_DIR" ]] || safe_remove_tree "$CACHE_DIR"
    fi
    ok "Dax Assistant uninstalled"
}

safe_remove_tree() {
    local path="$1"
    [[ -n "$path" && "$path" != "/" && "$path" != "$HOME" ]] || \
        die "Refusing to remove unsafe path: $path"
    if [[ "$path" != "$HOME/"* ]]; then
        die "Refusing to remove path outside the current user's home: $path"
    fi
    if [[ -e "$path" ]]; then
        rm -rf "$path"
    fi
}

case "$COMMAND" in
    install) install_dax ;;
    update) update_dax ;;
    doctor) doctor ;;
    service) enable_service; health_check || die "Service health check failed"; ok "Service installed and healthy" ;;
    uninstall) uninstall_dax ;;
esac
