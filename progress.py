#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that import progress.
All code has been moved to src/autocoder/ package.

Please update your imports to use:
    from autocoder.agent.progress import ProgressTracker
    # or
    from autocoder.agent import ProgressTracker
"""

# Re-export from the new location
from autocoder.agent.progress import *

__all__ = ["ProgressTracker"]
