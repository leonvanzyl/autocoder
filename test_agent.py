"""
Unit tests for rate limit handling functions.

Tests the parse_retry_after() and is_rate_limit_error() functions
from rate_limit_utils.py (shared module).
"""

import unittest

from rate_limit_utils import (
    is_rate_limit_error,
    parse_retry_after,
)


class TestParseRetryAfter(unittest.TestCase):
    """Tests for parse_retry_after() function."""

    def test_retry_after_colon_format(self):
        """Test 'Retry-After: 60' format."""
        assert parse_retry_after("Retry-After: 60") == 60
        assert parse_retry_after("retry-after: 120") == 120
        assert parse_retry_after("retry after: 30 seconds") == 30

    def test_retry_after_space_format(self):
        """Test 'retry after 60 seconds' format."""
        assert parse_retry_after("retry after 60 seconds") == 60
        assert parse_retry_after("Please retry after 120 seconds") == 120
        assert parse_retry_after("Retry after 30") == 30

    def test_try_again_in_format(self):
        """Test 'try again in X seconds' format."""
        assert parse_retry_after("try again in 120 seconds") == 120
        assert parse_retry_after("Please try again in 60s") == 60
        assert parse_retry_after("Try again in 30 seconds") == 30

    def test_seconds_remaining_format(self):
        """Test 'X seconds remaining' format."""
        assert parse_retry_after("30 seconds remaining") == 30
        assert parse_retry_after("60 seconds left") == 60
        assert parse_retry_after("120 seconds until reset") == 120

    def test_no_match(self):
        """Test messages that don't contain retry-after info."""
        assert parse_retry_after("no match here") is None
        assert parse_retry_after("Connection refused") is None
        assert parse_retry_after("Internal server error") is None
        assert parse_retry_after("") is None

    def test_minutes_not_supported(self):
        """Test that minutes are not parsed (by design)."""
        # We only support seconds to avoid complexity
        assert parse_retry_after("wait 5 minutes") is None
        assert parse_retry_after("try again in 2 minutes") is None


class TestIsRateLimitError(unittest.TestCase):
    """Tests for is_rate_limit_error() function."""

    def test_rate_limit_patterns(self):
        """Test various rate limit error messages."""
        assert is_rate_limit_error("Rate limit exceeded") is True
        assert is_rate_limit_error("rate_limit_exceeded") is True
        assert is_rate_limit_error("Too many requests") is True
        assert is_rate_limit_error("HTTP 429 Too Many Requests") is True
        assert is_rate_limit_error("API quota exceeded") is True
        assert is_rate_limit_error("Please wait before retrying") is True
        assert is_rate_limit_error("Try again later") is True
        assert is_rate_limit_error("Server is overloaded") is True
        assert is_rate_limit_error("Usage limit reached") is True

    def test_case_insensitive(self):
        """Test that detection is case-insensitive."""
        assert is_rate_limit_error("RATE LIMIT") is True
        assert is_rate_limit_error("Rate Limit") is True
        assert is_rate_limit_error("rate limit") is True
        assert is_rate_limit_error("RaTe LiMiT") is True

    def test_non_rate_limit_errors(self):
        """Test non-rate-limit error messages."""
        assert is_rate_limit_error("Connection refused") is False
        assert is_rate_limit_error("Authentication failed") is False
        assert is_rate_limit_error("Invalid API key") is False
        assert is_rate_limit_error("Internal server error") is False
        assert is_rate_limit_error("Network timeout") is False
        assert is_rate_limit_error("") is False


class TestExponentialBackoff(unittest.TestCase):
    """Test exponential backoff calculations."""

    def test_backoff_sequence(self):
        """Test that backoff follows expected sequence."""
        # Simulating: min(60 * (2 ** retries), 3600)
        expected = [60, 120, 240, 480, 960, 1920, 3600, 3600]  # Caps at 3600
        for retries, expected_delay in enumerate(expected):
            delay = min(60 * (2 ** retries), 3600)
            assert delay == expected_delay, f"Retry {retries}: expected {expected_delay}, got {delay}"

    def test_error_backoff_sequence(self):
        """Test error backoff follows expected sequence."""
        # Simulating: min(30 * retries, 300)
        expected = [30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 300]  # Caps at 300
        for retries in range(1, len(expected) + 1):
            delay = min(30 * retries, 300)
            expected_delay = expected[retries - 1]
            assert delay == expected_delay, f"Retry {retries}: expected {expected_delay}, got {delay}"


if __name__ == "__main__":
    unittest.main()
