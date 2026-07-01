#!/usr/bin/env bash
# Dax Assistant — One-command installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/daxrpm/dax-assistant/main/scripts/install.sh | bash
#
# Or locally:
#   ./scripts/install.sh
#
# What it does:
#   1. Checks prerequisites (Python 3.11+, uv, node, audio)
#   2. Clones the repo (or uses current directory)
#   3. Installs Python dependencies via uv
#   4. Installs frontend dependencies and builds the web UI
#   5. Downloads ML models (TTS voices, wake word)
#   6. Creates default config if missing
#   7. Optionally installs systemd user service

set -euo pipefail

REPO_URL="https://github.com/daxrpm/dax-assistant.git"
INSTALL_DIR="${DAX_INSTALL_DIR:-$HOME/.local/share/dax-assistant}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

echo ""
echo "  ██████╗  █████╗ ██╗  ██╗"
echo "  ██╔══██╗██╔══██╗╚██╗██╔╝"
echo "  ██║  ██║███████║ ╚███╔╝ "
echo "  ██║  ██║██╔══██║ ██╔██╗ "
echo "  ██████╔╝██║  ██║██╔╝ ██╗"
echo "  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝"
echo "  Voice-first Personal AI Assistant"
echo ""

# --- Step 1: Check prerequisites ---

info "Checking prerequisites..."

# Python 3.11+
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    ok "Python $PY_VERSION found"
else
    fail "Python 3.11+ is required. Install it first."
fi

# uv
if command -v uv &>/dev/null; then
    ok "uv $(uv --version 2>/dev/null | head -1) found"
else
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    ok "uv installed"
fi

# Node.js (for MCP servers and frontend build)
if command -v node &>/dev/null; then
    ok "Node.js $(node --version) found"
else
    warn "Node.js not found. MCP servers via npx won't work."
    warn "Install with: curl -fsSL https://fnm.vercel.app/install | bash"
fi

# Audio (PulseAudio/PipeWire)
if command -v pactl &>/dev/null || command -v pw-cli &>/dev/null; then
    ok "Audio system detected"
else
    warn "No PulseAudio/PipeWire detected. Voice features may not work."
fi

# --- Step 2: Get the code ---

if [ -f "pyproject.toml" ] && grep -q "dax-assistant" pyproject.toml 2>/dev/null; then
    info "Running from dax-assistant directory"
    INSTALL_DIR="$(pwd)"
else
    info "Cloning dax-assistant to $INSTALL_DIR..."
    if [ -d "$INSTALL_DIR" ]; then
        warn "Directory exists, pulling latest..."
        git -C "$INSTALL_DIR" pull --ff-only
    else
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
fi

cd "$INSTALL_DIR"

# --- Step 3: Install Python dependencies ---

info "Installing Python dependencies..."
uv sync --extra voice --extra test --extra dev 2>&1 | tail -3
ok "Python dependencies installed"

# --- Step 4: Build frontend ---

if [ -d "web" ] && [ -f "web/package.json" ]; then
    info "Building web UI..."
    cd web
    npm install --silent 2>&1 | tail -1
    npm run build 2>&1 | tail -3
    cd ..
    ok "Web UI built"
else
    warn "No web/ directory found, skipping frontend build"
fi

# --- Step 5: Choose primary language ---

echo ""
info "Primary language for the voice assistant?"
echo "  1) Español (es)"
echo "  2) English (en)"
read -p "Select [1/2] (default 1): " -r LANG_SEL
case "${LANG_SEL:-1}" in
    2) DAX_LANG="en" ;;
    *) DAX_LANG="es" ;;
esac
ok "Primary language: $DAX_LANG"

# --- Step 6: Download ML models (language-aware) ---

info "Downloading ML models (Kokoro + Piper TTS, Whisper STT, wake word)..."
info "This includes large models (~2 GB) and may take several minutes."
uv run python scripts/download_models.py --language "$DAX_LANG" 2>&1 \
    | grep -E "(Downloading|Caching|done|ready|already|Done)"
ok "Models downloaded"

# --- Step 7: Create + configure config ---

if [ ! -f "config/dax.toml" ]; then
    info "Creating default config..."
    mkdir -p config
    cp config/dax.toml.example config/dax.toml 2>/dev/null || true
    ok "Config created at config/dax.toml"
else
    ok "Config already exists at config/dax.toml"
fi

info "Pinning voice language to '$DAX_LANG' in config..."
uv run python - "$DAX_LANG" <<'PY'
import pathlib
import sys
import tomllib

import tomli_w

lang = sys.argv[1]
path = pathlib.Path("config/dax.toml")
data = tomllib.loads(path.read_text()) if path.exists() else {}
voice = data.setdefault("voice", {})
voice["stt_language"] = lang  # pin language → no more "ru" mis-detection
voice.setdefault("tts_engine", "kokoro")
path.write_text(tomli_w.dumps(data))
print(f"Configured voice for '{lang}'")
PY
ok "Voice configured"

# --- Step 8: Verify ---

info "Verifying installation..."
uv run python -c "from dax.app import DaxApp; print('Import OK')" 2>/dev/null
ok "Installation verified"

# --- Step 9: Optional systemd service ---

echo ""
read -p "Install as systemd user service? (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    bash scripts/install-service.sh
    ok "Service installed"
fi

# --- Done ---

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Dax Assistant installed successfully!"
echo ""
echo "  Start:   uv run python -m dax"
echo "  Web UI:  http://localhost:8420"
echo "  Config:  config/dax.toml"
echo ""
echo "  Configure your services in the web UI:"
echo "  - MCP servers (shell, nextcloud, home assistant, spotify)"
echo "  - LLM provider (Ollama, Gemini)"
echo "  - WhatsApp (Evolution API)"
echo "  - Voice settings (wake word, STT, TTS)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
