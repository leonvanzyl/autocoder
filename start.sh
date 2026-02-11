#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "========================================"
echo "  AutoForge - Autonomous Coding Agent"
echo "========================================"
echo ""

# Check if Claude CLI is installed
if ! command -v claude &> /dev/null; then
    echo "[ERROR] Claude CLI not found"
    echo ""
    echo "Please install Claude CLI first:"
    echo "  curl -fsSL https://claude.ai/install.sh | bash"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "[OK] Claude CLI found"

# Note: Claude CLI no longer stores credentials in ~/.claude/.credentials.json
# We can't reliably check auth status without making an API call, so we just
# verify the CLI is installed and remind the user to login if needed
if [ -d "$HOME/.claude" ]; then
    echo "[OK] Claude CLI directory found"
    echo "     (If you're not logged in, run: claude login)"
else
    echo "[!] Claude CLI not configured"
    echo ""
    echo "Please run 'claude login' to authenticate before continuing."
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to exit..."
fi

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
    else
        echo "Creating virtual environment..."
    fi
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        echo "Please ensure the venv module is installed:"
        echo "  Ubuntu/Debian: sudo apt install python3-venv"
        echo "  Or try: python3 -m ensurepip"
        exit 1
    fi
fi

# Activate the virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment"
    echo "The venv may be corrupted. Try: rm -rf venv && ./start.sh"
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

# Run the app
python start.py
