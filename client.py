#!/usr/bin/env python3
"""
LEGACY SHIM - For backward compatibility

This file maintains compatibility with existing scripts that import client.
All code has been moved to src/autocoder/ package.

Please update your imports to use:
    from autocoder.agent.client import ClaudeSDKClient
    # or
    from autocoder.agent import ClaudeSDKClient
"""

# Re-export from the new location
from autocoder.agent.client import *

__all__ = ["ClaudeSDKClient"]
