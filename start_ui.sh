#!/bin/bash
cd "$(dirname "$0")"
# AutoCoder UI Launcher for Unix/Linux/macOS
# This script launches the web UI for the autonomous coding agent.

echo ""
echo "===================================="
echo "  AutoCoder UI"
echo "===================================="
echo ""

# Check if Opencode Python SDK is available
if ! python -c "import opencode_ai" &> /dev/null; then
    echo "[!] Opencode Python SDK not found"
    echo ""
    echo "    The agent requires the Opencode SDK to be installed."
    echo "    Install it with: pip install --pre opencode-ai"
    echo ""
else
    echo "[OK] Opencode SDK available"
fi

# Note: Opencode uses API keys for authentication
if [ -n "${OPENCODE_API_KEY:-}" ]; then
    echo "[OK] OPENCODE_API_KEY found in environment"
else
    echo "[!] Opencode API key not configured - set OPENCODE_API_KEY"
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

# Run the Python launcher
python start_ui.py "$@"
