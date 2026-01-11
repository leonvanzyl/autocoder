"""
Authentication Error Detection
==============================

Shared utilities for detecting Opencode authentication errors.
Used by both CLI (start.py) and server (process_manager.py) to provide
consistent error detection and messaging.
"""

import re

# Patterns that indicate authentication errors from Opencode or CLI wrappers
AUTH_ERROR_PATTERNS = [
    r"not\s+logged\s+in",
    r"not\s+authenticated",
    r"authentication\s+(failed|required|error)",
    r"login\s+required",
    r"please\s+(run\s+)?['\"]?opencode\s+login",
    r"unauthorized",
    r"invalid\s+(token|credential|api.?key)",
    r"expired\s+(token|session|credential)",
    r"could\s+not\s+authenticate",
    r"sign\s+in\s+(to|required)",
]


def is_auth_error(text: str) -> bool:
    """
    Check if text contains Opencode authentication error messages.

    Uses case-insensitive pattern matching against known error messages.

    Args:
        text: Output text to check

    Returns:
        True if any auth error pattern matches, False otherwise
    """
    if not text:
        return False
    text_lower = text.lower()
    for pattern in AUTH_ERROR_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


# CLI-style help message (for terminal output)
AUTH_ERROR_HELP_CLI = """
==================================================
  Authentication Error Detected
==================================================

Opencode requires an API key (set `OPENCODE_API_KEY` in your environment).

To fix this, set the environment variable:
  export OPENCODE_API_KEY=your_api_key_here

Then re-run the command.
==================================================
"""

# Server-style help message (for WebSocket streaming)
AUTH_ERROR_HELP_SERVER = """
================================================================================
  AUTHENTICATION ERROR DETECTED
================================================================================

Opencode requires an API key (set `OPENCODE_API_KEY` in your environment).

To fix this, set the environment variable:
  export OPENCODE_API_KEY=your_api_key_here

Then start the agent again if it was stopped.
================================================================================
"""


def print_auth_error_help() -> None:
    """Print helpful message when authentication error is detected (CLI version)."""
    print(AUTH_ERROR_HELP_CLI)
