"""
Opencode Client Configuration
=============================

Functions for creating and configuring the Opencode client adapter.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from opencode_adapter import OpencodeClient

# Load environment variables from .env file if present
load_dotenv()

# Default Playwright headless mode - can be overridden via PLAYWRIGHT_HEADLESS env var
DEFAULT_PLAYWRIGHT_HEADLESS = False


def get_playwright_headless() -> bool:
    """Get the Playwright headless mode setting."""
    value = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower()
    return value in ("true", "1", "yes", "on")


# Feature MCP tools for feature/test management
FEATURE_MCP_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_next",
    "mcp__features__feature_get_for_regression",
    "mcp__features__feature_mark_in_progress",
    "mcp__features__feature_mark_passing",
    "mcp__features__feature_skip",
    "mcp__features__feature_create_bulk",
]

# Playwright MCP tools for browser automation
PLAYWRIGHT_TOOLS = [
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    "mcp__playwright__browser_fill_form",
    "mcp__playwright__browser_select_option",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_evaluate",
    "mcp__playwright__browser_console_messages",
    "mcp__playwright__browser_network_requests",
]

# Built-in tools
BUILTIN_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebFetch", "WebSearch"]


def create_client(project_dir: Path, model: str, yolo_mode: bool = False):
    """Create an Opencode client adapter and write project settings file.

    The Opencode SDK is a REST client; we use an adapter to provide a
    minimal interface compatible with the rest of the codebase.
    """
    # Build allowed tools list based on mode
    allowed_tools = [*BUILTIN_TOOLS, *FEATURE_MCP_TOOLS]
    if not yolo_mode:
        allowed_tools.extend(PLAYWRIGHT_TOOLS)

    # Build permissions list
    permissions_list = [
        "Read(./**)",
        "Write(./**)",
        "Edit(./**)",
        "Glob(./**)",
        "Grep(./**)",
        "Bash(*)",
        "WebFetch",
        "WebSearch",
        *FEATURE_MCP_TOOLS,
    ]
    if not yolo_mode:
        permissions_list.extend(PLAYWRIGHT_TOOLS)

    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {"defaultMode": "acceptEdits", "allow": permissions_list},
    }

    project_dir.mkdir(parents=True, exist_ok=True)

    settings_file = project_dir / ".opencode_settings.json"
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    print(f"Created security settings at {settings_file}")
    print("   - Sandbox enabled (OS-level bash isolation)")
    print(f"   - Filesystem restricted to: {project_dir.resolve()}")
    print("   - Bash commands restricted to allowlist (see security.py)")
    if yolo_mode:
        print("   - MCP servers: features (database) - YOLO MODE (no Playwright)")
    else:
        print("   - MCP servers: playwright (browser), features (database)")
    print("   - Project settings enabled (skills, commands, OPENCODE.md)")
    print()

    # Build MCP servers config
    mcp_servers = {
        "features": {
            "command": sys.executable,
            "args": ["-m", "mcp_server.feature_mcp"],
            "env": {**os.environ, "PROJECT_DIR": str(project_dir.resolve()), "PYTHONPATH": str(Path(__file__).parent.resolve())},
        }
    }

    if not yolo_mode:
        playwright_args = ["@playwright/mcp@latest", "--viewport-size", "1280x720"]
        if get_playwright_headless():
            playwright_args.append("--headless")
        mcp_servers["playwright"] = {"command": "npx", "args": playwright_args}

    # Return an Opencode adapter instance
    return OpencodeClient(project_dir, model, yolo_mode=yolo_mode)
