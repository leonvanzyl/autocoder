#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that use start_ui.py.
Please update your scripts to use the new CLI:

    autocoder-ui

Or use the programmatic interface:
    from autocoder.server import start_server
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from autocoder.server import start_server

if __name__ == "__main__":
    start_server()
