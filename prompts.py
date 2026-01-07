#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that import prompts.
All code has been moved to src/autocoder/ package.

Please update your imports to use:
    from autocoder.agent.prompts import scaffold_project_prompts
    # or
    from autocoder.agent import scaffold_project_prompts
"""

# Re-export from the new location
from autocoder.agent.prompts import *

__all__ = ["scaffold_project_prompts", "has_project_prompts", "get_project_prompts_dir"]
