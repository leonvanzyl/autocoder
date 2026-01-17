#!/bin/bash
# AutoCoder UI Launcher for Unix/Linux/macOS

# Load .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo ""
if [ -n "${AUTOCODER_UI_BANNER}" ] && [ "${AUTOCODER_UI_BANNER}" != "0" ]; then
  echo "===================================="
  echo "  AUTOCODER // WEB UI"
  echo "  Modded by Gabi (Booplex)"
  echo "===================================="
fi
UI_PORT="${AUTOCODER_UI_PORT:-8888}"
echo ""
echo "  Opening http://127.0.0.1:${UI_PORT}  (set AUTOCODER_OPEN_UI=0 to disable)"
if [ -n "${AUTOCODER_UI_BANNER}" ] && [ "${AUTOCODER_UI_BANNER}" = "0" ]; then
  echo "  Banner suppressed via AUTOCODER_UI_BANNER=0"
fi
echo ""

# Run autocoder-ui command
if ! command -v autocoder-ui &> /dev/null; then
    echo "[ERROR] autocoder-ui command not found"
    echo ""
    echo "Please install the package first:"
    echo "  pip install -e '.[dev]'"
    echo ""
    exit 1
fi

autocoder-ui
