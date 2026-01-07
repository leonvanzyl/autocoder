#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that import from root.
All code has been moved to src/autocoder/ package.

Please update your imports to use:
    from autocoder.cli import main
    # or
    from autocoder import cli

Or use the new CLI commands:
    autocoder              # Interactive menu
    autocoder agent        # Run single agent
    autocoder parallel     # Run parallel agents
    autocoder-ui           # Launch web UI
"""

# Re-export the main function from the new location
from autocoder.cli import main

if __name__ == "__main__":
    main()
