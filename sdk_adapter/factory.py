"""
SDK Adapter Factory
===================

Factory function to create the appropriate SDK adapter
based on the AUTOFORGE_SDK environment variable.
"""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from sdk_adapter.protocols import SDKAdapter
from sdk_adapter.types import AdapterOptions

# Load .env file from project root (parent of sdk_adapter directory)
# This ensures AUTOFORGE_SDK is available regardless of current working directory
_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    # Fallback to current working directory
    load_dotenv()

# Environment variable for SDK selection
SDK_TYPE_VAR = "AUTOFORGE_SDK"

# Valid SDK types
SDKType = Literal["claude", "codex"]

# Default SDK
DEFAULT_SDK: SDKType = "claude"


def get_sdk_type() -> SDKType:
    """
    Get the SDK type from DB settings, falling back to environment variable.

    Priority:
        1. DB setting (sdk_type) from Settings UI
        2. AUTOFORGE_SDK environment variable
        3. Default: "claude"

    Returns:
        "claude" (default) or "codex".
    """
    # Check DB settings first
    try:
        import sys
        root = str(Path(__file__).parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from registry import get_setting
        db_value = get_setting("sdk_type")
        if db_value and db_value.lower() in ("claude", "codex"):
            return db_value.lower()  # type: ignore[return-value]
    except Exception:
        pass  # DB not available, fall back to env var

    # Fall back to environment variable
    raw_value = os.getenv(SDK_TYPE_VAR)
    sdk_type = (raw_value or DEFAULT_SDK).lower()

    if sdk_type not in ("claude", "codex"):
        print(f"   - Warning: Invalid AUTOFORGE_SDK='{sdk_type}', using default: {DEFAULT_SDK}")
        return DEFAULT_SDK

    return sdk_type  # type: ignore[return-value]


def create_adapter(options: AdapterOptions) -> SDKAdapter:
    """
    Factory function to create the appropriate SDK adapter.

    Uses AUTOFORGE_SDK environment variable to select:
    - "claude" (default): Claude Agent SDK
    - "codex": OpenAI Codex SDK

    Args:
        options: Unified adapter options.

    Returns:
        An SDK adapter implementing the SDKAdapter protocol.

    Raises:
        ImportError: If the selected SDK package is not installed.
        ValueError: If an unknown SDK type is specified.
    """
    sdk_type = get_sdk_type()

    if sdk_type == "claude":
        from sdk_adapter.claude_adapter import ClaudeAdapter

        return ClaudeAdapter(options)

    elif sdk_type == "codex":
        try:
            from sdk_adapter.codex_adapter import CodexAdapter

            return CodexAdapter(options)
        except ImportError as e:
            raise ImportError(
                "codex-sdk-py not installed. Install with: pip install codex-sdk-py\n"
                f"Original error: {e}"
            ) from e

    else:
        # Should not reach here due to get_sdk_type() validation
        raise ValueError(f"Unknown SDK type: {sdk_type}. Valid options: claude, codex")
