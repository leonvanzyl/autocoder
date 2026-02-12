#!/usr/bin/env bash
set -e  # Exit on error

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# AutoForge UI Launcher for Unix/Linux/macOS
# This script launches the web UI for the autonomous coding agent.

echo ""
echo "===================================="
echo "  AutoForge UI"
echo "===================================="
echo ""

# Check if Claude CLI is installed
if ! command -v claude &> /dev/null; then
    echo "[!] Claude CLI not found"
    echo ""
    echo "    The agent requires Claude CLI to work."
    echo "    Install it from: https://claude.ai/download"
    echo ""
    echo "    After installing, run: claude login"
    echo ""
else
    echo "[OK] Claude CLI found"
    # Note: Claude CLI no longer stores credentials in ~/.claude/.credentials.json
    # We can't reliably check auth status without making an API call
    if [ -d "$HOME/.claude" ]; then
        echo "     (If you're not logged in, run: claude login)"
    else
        echo "[!] Claude CLI not configured - run 'claude login' first"
    fi
fi
echo ""

# Check if Python is available and meet version requirements
PYTHON_CMD=""
for cmd in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python not found"
    echo "Please install Python 3.11+ from https://python.org"
    exit 1
fi

# Verify Python version is 3.11+
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "ERROR: Python 3.11+ required (found $PYTHON_VERSION)"
    echo "Please upgrade Python or install a newer version"
    exit 1
fi

echo "[OK] Using Python $PYTHON_VERSION ($PYTHON_CMD)"
echo ""

# Check if venv exists with correct structure for this platform
# Windows venvs have Scripts/, Linux/macOS have bin/
if [ ! -f "venv/bin/activate" ]; then
    if [ -d "venv" ]; then
        echo "[INFO] Detected incompatible virtual environment (possibly created on Windows)"
        echo "[INFO] Recreating virtual environment for this platform..."
        rm -rf venv
        if [ -d "venv" ]; then
            echo "[ERROR] Failed to remove existing virtual environment"
            echo "Please manually delete the 'venv' directory and try again:"
            echo "  rm -rf venv"
            exit 1
        fi
    fi
    echo "Creating virtual environment..."
    if ! $PYTHON_CMD -m venv venv; then
        echo "[ERROR] Failed to create virtual environment"
        echo "Please ensure the venv module is installed:"
        echo "  Ubuntu/Debian: sudo apt install python3-venv"
        echo "  Fedora/RHEL: sudo dnf install python3-venv"
        echo "  Or try: $PYTHON_CMD -m ensurepip"
        exit 1
    fi
    echo "[OK] Virtual environment created"
fi

# Detect package manager preference (uv > pip3 > pip)
PKG_MGR=""
if command -v uv &> /dev/null; then
    PKG_MGR="uv"
    echo "[OK] Using uv package manager"
elif command -v pip3 &> /dev/null; then
    PKG_MGR="pip3"
    echo "[OK] Using pip3 package manager"
elif command -v pip &> /dev/null; then
    PKG_MGR="pip"
    echo "[OK] Using pip package manager"
else
    echo "[ERROR] No package manager found (pip, pip3, or uv required)"
    exit 1
fi
echo ""

# Activate the virtual environment
if [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
else
    echo "[ERROR] Virtual environment activation script not found"
    echo "The venv may be corrupted. Try: rm -rf venv && ./start_ui.sh"
    exit 1
fi

# Install dependencies based on package manager
echo "Installing dependencies..."
if [ "$PKG_MGR" = "uv" ]; then
    if ! uv pip install -r requirements.txt --quiet; then
        echo "[ERROR] Failed to install dependencies with uv"
        echo "Try manually: uv pip install -r requirements.txt"
        exit 1
    fi
else
    # Upgrade pip to avoid warnings (only for pip/pip3)
    echo "Ensuring pip is up to date..."
    $PKG_MGR install --upgrade pip --quiet 2>&1 | grep -v "Requirement already satisfied" || true

    if ! $PKG_MGR install -r requirements.txt --quiet; then
        echo "[ERROR] Failed to install dependencies"
        echo "Try manually: source venv/bin/activate && $PKG_MGR install -r requirements.txt"
        exit 1
    fi
fi

echo ""
echo "Starting AutoForge UI server..."
echo ""

# Ensure playwright-cli is available for browser automation
if ! command -v playwright-cli &> /dev/null; then
    echo "Installing playwright-cli for browser automation..."
    npm install -g @playwright/cli --quiet 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "Note: Could not install playwright-cli. Install manually: npm install -g @playwright/cli"
    fi
fi

# Run the Python launcher
exec $PYTHON_CMD start_ui.py "$@"
