#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that import registry.
All code has been moved to src/autocoder/ package.

Please update your imports to use:
    from autocoder.agent.registry import get_project_path
    # or
    from autocoder.agent import get_project_path
"""

# Re-export from the new location
from autocoder.agent.registry import *

__all__ = ["register_project", "get_project_path", "list_registered_projects"]
