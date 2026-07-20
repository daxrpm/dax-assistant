#!/usr/bin/env bash
# Development-only compatibility wrapper. Tagged installs configure services directly.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(dirname "$SCRIPT_DIR")"
exec "$SCRIPT_DIR/install.sh" --source "$SOURCE_ROOT" --backend-only "$@"
