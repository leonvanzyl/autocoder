#!/bin/bash
cd "$(dirname "$0")"
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

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python not found"
        echo "Please install Python from https://python.org"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

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
    else
        echo "Creating virtual environment..."
    fi
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        echo "Please ensure the venv module is installed:"
        echo "  Ubuntu/Debian: sudo apt install python3-venv"
        echo "  Or try: $PYTHON_CMD -m ensurepip"
        exit 1
    fi
fi

# Activate the virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment"
    echo "The venv may be corrupted. Try: rm -rf venv && ./start_ui.sh"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Ensure playwright-cli is available for browser automation
if ! command -v playwright-cli &> /dev/null; then
    echo "Installing playwright-cli for browser automation..."
    npm install -g @playwright/cli --quiet 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "Note: Could not install playwright-cli. Install manually: npm install -g @playwright/cli"
    fi
fi

# Run the Python launcher
python start_ui.py "$@"
