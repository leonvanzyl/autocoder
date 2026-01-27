"""
Rate Limit Utilities
====================

Shared utilities for detecting and handling API rate limits.
Used by both agent.py (production) and test_agent.py (tests).
"""

import re
from typing import Optional

# Rate limit detection patterns (used in both exception messages and response text)
RATE_LIMIT_PATTERNS = [
    "limit reached",
    "rate limit",
    "rate_limit",
    "too many requests",
    "quota exceeded",
    "please wait",
    "try again later",
    "429",
    "overloaded",
]


def parse_retry_after(error_message: str) -> Optional[int]:
    """
    Extract retry-after seconds from various error message formats.

    Handles common formats:
    - "Retry-After: 60"
    - "retry after 60 seconds"
    - "try again in 5 seconds"
    - "30 seconds remaining"

    Args:
        error_message: The error message to parse

    Returns:
        Seconds to wait, or None if not parseable.
    """
    patterns = [
        r"retry.?after[:\s]+(\d+)\s*(?:seconds?)?",
        r"try again in\s+(\d+)\s*(?:seconds?|s\b)",
        r"(\d+)\s*seconds?\s*(?:remaining|left|until)",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def is_rate_limit_error(error_message: str) -> bool:
    """
    Detect if an error message indicates a rate limit.

    Checks against common rate limit patterns from various API providers.

    Args:
        error_message: The error message to check

    Returns:
        True if the message indicates a rate limit, False otherwise.
    """
    error_lower = error_message.lower()
    return any(pattern in error_lower for pattern in RATE_LIMIT_PATTERNS)
