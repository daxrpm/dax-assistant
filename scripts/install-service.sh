#!/usr/bin/env bash
# Install Dax Assistant as a systemd user service.
#
# Usage: ./scripts/install-service.sh
#
# After installation:
#   systemctl --user start dax-assistant
#   systemctl --user status dax-assistant
#   journalctl --user -u dax-assistant -f

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_FILE="$PROJECT_DIR/systemd/dax-assistant.service"
TARGET_DIR="$HOME/.config/systemd/user"

echo "Installing Dax Assistant systemd user service..."

# Create user systemd directory
mkdir -p "$TARGET_DIR"

# Copy and adjust the service file for user service
sed \
    -e '/^User=/d' \
    -e '/^Group=/d' \
    -e '/^SupplementaryGroups=/d' \
    -e 's|^WantedBy=.*|WantedBy=default.target|' \
    "$SERVICE_FILE" > "$TARGET_DIR/dax-assistant.service"

# Reload systemd
systemctl --user daemon-reload

echo "Service installed at $TARGET_DIR/dax-assistant.service"
echo ""
echo "Commands:"
echo "  systemctl --user start dax-assistant    # Start"
echo "  systemctl --user stop dax-assistant     # Stop"
echo "  systemctl --user enable dax-assistant   # Auto-start on login"
echo "  systemctl --user status dax-assistant   # Check status"
echo "  journalctl --user -u dax-assistant -f   # View logs"
