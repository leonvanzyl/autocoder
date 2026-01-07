# Tests

This directory contains test files for the autonomous coding system.

## Test Files

### `test_security.py`
**Purpose:** Security testing for bash command validation

**What it tests:**
- `ALLOWED_COMMANDS` whitelist validation
- Command injection prevention
- Path traversal protection
- OS-level sandbox enforcement

**How to run:**
```bash
python tests/test_security.py
```

**Status:** ✅ Active - Run when modifying security.py

## Adding New Tests

When adding new functionality, create test files following this pattern:

```python
# test_<feature>.py
"""
Tests for <feature> functionality.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from <module> import <function>

def test_<function>_basic():
    """Test basic functionality."""
    result = <function>()
    assert result is not None

def test_<function>_edge_case():
    """Test edge cases."""
    result = <function>(edge_case_input)
    assert result == expected
```

## Test Coverage

Currently covered:
- ✅ Security validation
- ⏳ Knowledge base (needs automated tests)
- ⏳ Test framework detector (needs automated tests)
- ⏳ Orchestrator (needs automated tests)
- ⏳ Gatekeeper (needs automated tests)

## Running All Tests

```bash
# Run security tests
python tests/test_security.py

# Run with pytest (if installed)
pytest tests/

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## Notes

- Tests are kept minimal and focused
- Use direct imports for speed
- No external dependencies required
- Can run without full environment setup
