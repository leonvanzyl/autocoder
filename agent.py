#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that import from root.
All code has been moved to src/autocoder/ package.

Please update your imports to use:
    from autocoder.agent import run_autonomous_agent
    # or
    from autocoder import agent
"""

# Re-export everything from the new location
from autocoder.agent.agent import *

__all__ = ["run_autonomous_agent"]
