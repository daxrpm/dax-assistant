#!/usr/bin/env bash
# Compatibility wrapper. The production installer owns unit generation.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/install.sh" service "$@"
