#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that use orchestrator_demo.py.
Please update your scripts to use the new CLI:

    autocoder parallel --project-dir my-app --parallel 3 --preset balanced

Or use the programmatic interface:
    from autocoder.core import Orchestrator
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Re-export from the new location
from autocoder.cli import main

if __name__ == "__main__":
    # Redirect to run parallel mode
    sys.argv.insert(1, "parallel")
    main()
