#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that import security.
All code has been moved to src/autocoder/ package.

Please update your imports to use:
    from autocoder.agent.security import ALLOWED_COMMANDS, validate_bash_command
    # or
    from autocoder.agent import ALLOWED_COMMANDS, validate_bash_command
"""

# Re-export from the new location
from autocoder.agent.security import *

__all__ = ["ALLOWED_COMMANDS", "validate_bash_command"]
