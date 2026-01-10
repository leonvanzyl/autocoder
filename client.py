"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.
"""

import json
import os
import shutil
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import HookMatcher
from dotenv import load_dotenv

from security import bash_security_hook

# Load environment variables from .env file if present
load_dotenv()

# Default CLI command - can be overridden via CLI_COMMAND environment variable
# Common values: "claude" (default), "glm"
DEFAULT_CLI_COMMAND = "claude"

# Default Playwright headless mode - can be overridden via PLAYWRIGHT_HEADLESS env var
# When True, browser runs invisibly in background
# When False, browser window is visible (default - useful for monitoring agent progress)
DEFAULT_PLAYWRIGHT_HEADLESS = False


def get_cli_command() -> str:
    """
    Get the CLI command to use for the agent.

    Reads from CLI_COMMAND environment variable, defaults to 'claude'.
    This allows users to use alternative CLIs like 'glm'.
    """
    return os.getenv("CLI_COMMAND", DEFAULT_CLI_COMMAND)


def get_playwright_headless() -> bool:
    """
    Get the Playwright headless mode setting.

    Reads from PLAYWRIGHT_HEADLESS environment variable, defaults to False.
    Returns True for headless mode (invisible browser), False for visible browser.
    """
    value = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower()
    # Accept various truthy/falsy values
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
    # Core navigation & screenshots
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_navigate_back",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_snapshot",

    # Element interaction
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    "mcp__playwright__browser_fill_form",
    "mcp__playwright__browser_select_option",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_drag",
    "mcp__playwright__browser_press_key",

    # JavaScript & debugging
    "mcp__playwright__browser_evaluate",
    # "mcp__playwright__browser_run_code",  # REMOVED - causes Playwright MCP server crash
    "mcp__playwright__browser_console_messages",
    "mcp__playwright__browser_network_requests",

    # Browser management
    "mcp__playwright__browser_close",
    "mcp__playwright__browser_resize",
    "mcp__playwright__browser_tabs",
    "mcp__playwright__browser_wait_for",
    "mcp__playwright__browser_handle_dialog",
    "mcp__playwright__browser_file_upload",
    "mcp__playwright__browser_install",
]

# Laravel Boost MCP tools for Laravel development
# Note: Laravel Boost uses hyphens in tool names, not underscores
LARAVEL_BOOST_TOOLS = [
    "mcp__laravel_boost__database-query",
    "mcp__laravel_boost__database-schema",
    "mcp__laravel_boost__database-connections",
    "mcp__laravel_boost__list-routes",
    "mcp__laravel_boost__list-artisan-commands",
    "mcp__laravel_boost__read-log-entries",
    "mcp__laravel_boost__last-error",
    "mcp__laravel_boost__browser-logs",
    "mcp__laravel_boost__get-config",
    "mcp__laravel_boost__list-available-config-keys",
    "mcp__laravel_boost__list-available-env-vars",
    "mcp__laravel_boost__search-docs",
    "mcp__laravel_boost__tinker",
    "mcp__laravel_boost__get-absolute-url",
    "mcp__laravel_boost__application-info",
]

# Built-in tools
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "WebFetch",
    "WebSearch",
]


def create_client(
    project_dir: Path,
    model: str,
    yolo_mode: bool = False,
    is_laravel: bool = False,
):
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        yolo_mode: If True, skip Playwright MCP server for rapid prototyping
        is_laravel: If True, include Laravel Boost MCP server for Laravel development

    Returns:
        Configured ClaudeSDKClient (from claude_agent_sdk)

    Security layers (defense in depth):
    1. Sandbox - OS-level bash command isolation prevents filesystem escape
    2. Permissions - File operations restricted to project_dir only
    3. Security hooks - Bash commands validated against an allowlist
       (see security.py for ALLOWED_COMMANDS)

    Note: Authentication is handled by start.bat/start.sh before this runs.
    The Claude SDK auto-detects credentials from the Claude CLI configuration
    """
    # Build allowed tools list based on mode
    # In YOLO mode, exclude Playwright tools for faster prototyping
    allowed_tools = [*BUILTIN_TOOLS, *FEATURE_MCP_TOOLS]
    if not yolo_mode:
        allowed_tools.extend(PLAYWRIGHT_TOOLS)
    if is_laravel:
        allowed_tools.extend(LARAVEL_BOOST_TOOLS)

    # Build permissions list
    permissions_list = [
        # Allow all file operations within the project directory
        "Read(./**)",
        "Write(./**)",
        "Edit(./**)",
        "Glob(./**)",
        "Grep(./**)",
        # Bash permission granted here, but actual commands are validated
        # by the bash_security_hook (see security.py for allowed commands)
        "Bash(*)",
        # Allow web tools for documentation lookup
        "WebFetch",
        "WebSearch",
        # Allow Feature MCP tools for feature management
        *FEATURE_MCP_TOOLS,
    ]
    if not yolo_mode:
        # Allow Playwright MCP tools for browser automation (standard mode only)
        permissions_list.extend(PLAYWRIGHT_TOOLS)
    if is_laravel:
        # Allow Laravel Boost MCP tools for Laravel development
        permissions_list.extend(LARAVEL_BOOST_TOOLS)

    # Create comprehensive security settings
    # Note: Using relative paths ("./**") restricts access to project directory
    # since cwd is set to project_dir
    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "acceptEdits",  # Auto-approve edits within allowed directories
            "allow": permissions_list,
        },
    }

    # Ensure project directory exists before creating settings file
    project_dir.mkdir(parents=True, exist_ok=True)

    # Write settings to a file in the project directory
    settings_file = project_dir / ".claude_settings.json"
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    print(f"Created security settings at {settings_file}")
    print("   - Sandbox enabled (OS-level bash isolation)")
    print(f"   - Filesystem restricted to: {project_dir.resolve()}")
    print("   - Bash commands restricted to allowlist (see security.py)")

    # Build MCP server description for logging
    mcp_list = ["features (database)"]
    if not yolo_mode:
        mcp_list.append("playwright (browser)")
    if is_laravel:
        mcp_list.append("laravel_boost (Laravel tools)")
    if yolo_mode:
        print(f"   - MCP servers: {', '.join(mcp_list)} - YOLO MODE")
    else:
        print(f"   - MCP servers: {', '.join(mcp_list)}")
    if is_laravel:
        print("   - Framework: Laravel")
    print("   - Project settings enabled (skills, commands, CLAUDE.md)")
    print()

    # Use system CLI instead of bundled one (avoids Bun runtime crash on Windows)
    # CLI command is configurable via CLI_COMMAND environment variable
    cli_command = get_cli_command()
    system_cli = shutil.which(cli_command)
    if system_cli:
        print(f"   - Using system CLI: {system_cli}")
    else:
        print(f"   - Warning: System CLI '{cli_command}' not found, using bundled CLI")

    # Build MCP servers config - features is always included, playwright only in standard mode
    mcp_servers = {
        "features": {
            "command": sys.executable,  # Use the same Python that's running this script
            "args": ["-m", "mcp_server.feature_mcp"],
            "env": {
                # Inherit parent environment (PATH, ANTHROPIC_API_KEY, etc.)
                **os.environ,
                # Add custom variables
                "PROJECT_DIR": str(project_dir.resolve()),
                "PYTHONPATH": str(Path(__file__).parent.resolve()),
            },
        },
    }
    if not yolo_mode:
        # Include Playwright MCP server for browser automation (standard mode only)
        # Headless mode is configurable via PLAYWRIGHT_HEADLESS environment variable
        playwright_args = ["@playwright/mcp@latest", "--viewport-size", "1280x720"]
        if get_playwright_headless():
            playwright_args.append("--headless")
        mcp_servers["playwright"] = {
            "command": "npx",
            "args": playwright_args,
        }

    if is_laravel:
        # Include Laravel Boost MCP server for Laravel development
        mcp_servers["laravel_boost"] = {
            "command": "npx",
            "args": ["@anthropic/laravel-boost"],
            "env": {
                **os.environ,
                "PROJECT_DIR": str(project_dir.resolve()),
            },
        }

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            cli_path=system_cli,  # Use system CLI to avoid bundled Bun crash (exit code 3)
            system_prompt="You are an expert full-stack developer building a production-quality web application.",
            setting_sources=["project"],  # Enable skills, commands, and CLAUDE.md from project dir
            max_buffer_size=10 * 1024 * 1024,  # 10MB for large Playwright screenshots
            allowed_tools=allowed_tools,
            mcp_servers=mcp_servers,
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                ],
            },
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),  # Use absolute path
        )
    )
