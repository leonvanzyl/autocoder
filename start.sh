#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "========================================"
echo "  Autonomous Coding Agent"
echo "========================================"
echo ""

# Check if Opencode Python SDK is available
if ! python -c "import opencode_ai" &> /dev/null; then
    echo "[ERROR] Opencode Python SDK not found"
    echo ""
    echo "Please install the SDK first:"
    echo "  pip install --pre opencode-ai"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "[OK] Opencode SDK available"

# Note: Opencode uses API keys or other auth mechanisms. Ensure OPENCODE_API_KEY is set.
if [ -n "${OPENCODE_API_KEY:-}" ]; then
    echo "[OK] OPENCODE_API_KEY found in environment"
else
    echo "[!] Opencode API key not configured"
    echo ""
    echo "Please set OPENCODE_API_KEY per https://opencode.ai/docs"
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

# Run the app
python start.py
