#!/bin/bash
# Autonomous Coder UI Launcher for Unix/Linux/macOS
# This script launches the web UI for the autonomous coding agent.

echo ""
echo "===================================="
echo "  Autonomous Coder UI"
echo "===================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Run the Python launcher
$PYTHON_CMD "$SCRIPT_DIR/start_ui.py" "$@"
