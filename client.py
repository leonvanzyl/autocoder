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
from claude_agent_sdk.types import HookContext, HookInput, HookMatcher, SyncHookJSONOutput
from dotenv import load_dotenv

from security import bash_security_hook

# Load environment variables from .env file if present
load_dotenv()

# Default Playwright headless mode - can be overridden via PLAYWRIGHT_HEADLESS env var
# When True, browser runs invisibly in background (default - saves CPU)
# When False, browser window is visible (useful for monitoring agent progress)
DEFAULT_PLAYWRIGHT_HEADLESS = True

# Default browser for Playwright - can be overridden via PLAYWRIGHT_BROWSER env var
# Options: chrome, firefox, webkit, msedge
# Firefox is recommended for lower CPU usage
DEFAULT_PLAYWRIGHT_BROWSER = "firefox"

# Environment variables to pass through to Claude CLI for API configuration
# These allow using alternative API endpoints (e.g., GLM via z.ai) without
# affecting the user's global Claude Code settings
API_ENV_VARS = [
    "ANTHROPIC_BASE_URL",              # Custom API endpoint (e.g., https://api.z.ai/api/anthropic)
    "ANTHROPIC_AUTH_TOKEN",            # API authentication token
    "API_TIMEOUT_MS",                  # Request timeout in milliseconds
    "ANTHROPIC_DEFAULT_SONNET_MODEL",  # Model override for Sonnet
    "ANTHROPIC_DEFAULT_OPUS_MODEL",    # Model override for Opus
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",   # Model override for Haiku
]


def get_playwright_headless() -> bool:
    """
    Get the Playwright headless mode setting.

    Reads from PLAYWRIGHT_HEADLESS environment variable, defaults to True.
    Returns True for headless mode (invisible browser), False for visible browser.
    """
    value = os.getenv("PLAYWRIGHT_HEADLESS", str(DEFAULT_PLAYWRIGHT_HEADLESS).lower()).lower()
    # Accept various truthy/falsy values
    return value in ("true", "1", "yes", "on")


def get_playwright_browser() -> str:
    """
    Get the browser to use for Playwright.

    Reads from PLAYWRIGHT_BROWSER environment variable, defaults to firefox.
    Options: chrome, firefox, webkit, msedge
    Firefox is recommended for lower CPU usage.
    """
    return os.getenv("PLAYWRIGHT_BROWSER", DEFAULT_PLAYWRIGHT_BROWSER).lower()


# Feature MCP tools for feature/test management
FEATURE_MCP_TOOLS = [
    # Core feature operations
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_by_id",  # Get assigned feature details
    "mcp__features__feature_get_summary",  # Lightweight: id, name, status, deps only
    "mcp__features__feature_mark_in_progress",
    "mcp__features__feature_claim_and_get",  # Atomic claim + get details
    "mcp__features__feature_mark_passing",
    "mcp__features__feature_mark_failing",  # Mark regression detected
    "mcp__features__feature_skip",
    "mcp__features__feature_create_bulk",
    "mcp__features__feature_create",
    "mcp__features__feature_clear_in_progress",
    "mcp__features__feature_release_testing",  # Release testing claim
    # Dependency management
    "mcp__features__feature_add_dependency",
    "mcp__features__feature_remove_dependency",
    "mcp__features__feature_set_dependencies",
    # Query tools
    "mcp__features__feature_get_ready",
    "mcp__features__feature_get_blocked",
    "mcp__features__feature_get_graph",
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
    agent_id: str | None = None,
):
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        yolo_mode: If True, skip Playwright MCP server for rapid prototyping
        agent_id: Optional unique identifier for browser isolation in parallel mode.
                  When provided, each agent gets its own browser profile.

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
    if yolo_mode:
        print("   - MCP servers: features (database) - YOLO MODE (no Playwright)")
    else:
        print("   - MCP servers: playwright (browser), features (database)")
    print("   - Project settings enabled (skills, commands, CLAUDE.md)")
    print()

    # Use system Claude CLI instead of bundled one (avoids Bun runtime crash on Windows)
    system_cli = shutil.which("claude")
    if system_cli:
        print(f"   - Using system CLI: {system_cli}")
    else:
        print("   - Warning: System 'claude' CLI not found, using bundled CLI")

    # Build MCP servers config - features is always included, playwright only in standard mode
    mcp_servers = {
        "features": {
            "command": sys.executable,  # Use the same Python that's running this script
            "args": ["-m", "mcp_server.feature_mcp"],
            "env": {
                # Only specify variables the MCP server needs
                # (subprocess inherits parent environment automatically)
                "PROJECT_DIR": str(project_dir.resolve()),
                "PYTHONPATH": str(Path(__file__).parent.resolve()),
            },
        },
    }
    if not yolo_mode:
        # Include Playwright MCP server for browser automation (standard mode only)
        # Browser and headless mode configurable via environment variables
        browser = get_playwright_browser()
        playwright_args = [
            "@playwright/mcp@latest",
            "--viewport-size", "1280x720",
            "--browser", browser,
        ]
        if get_playwright_headless():
            playwright_args.append("--headless")
        print(f"   - Browser: {browser} (headless={get_playwright_headless()})")

        # Browser isolation for parallel execution
        # Each agent gets its own isolated browser context to prevent tab conflicts
        if agent_id:
            # Use --isolated for ephemeral browser context
            # This creates a fresh, isolated context without persistent state
            # Note: --isolated and --user-data-dir are mutually exclusive
            playwright_args.append("--isolated")
            print(f"   - Browser isolation enabled for agent: {agent_id}")

        mcp_servers["playwright"] = {
            "command": "npx",
            "args": playwright_args,
        }

    # Build environment overrides for API endpoint configuration
    # These override system env vars for the Claude CLI subprocess,
    # allowing AutoCoder to use alternative APIs (e.g., GLM) without
    # affecting the user's global Claude Code settings
    sdk_env = {}
    for var in API_ENV_VARS:
        value = os.getenv(var)
        if value:
            sdk_env[var] = value

    if sdk_env:
        print(f"   - API overrides: {', '.join(sdk_env.keys())}")
        if "ANTHROPIC_BASE_URL" in sdk_env:
            print(f"   - GLM Mode: Using {sdk_env['ANTHROPIC_BASE_URL']}")

    # Create a wrapper for bash_security_hook that passes project_dir via context
    async def bash_hook_with_context(input_data, tool_use_id=None, context=None):
        """Wrapper that injects project_dir into context for security hook."""
        if context is None:
            context = {}
        context["project_dir"] = str(project_dir.resolve())
        return await bash_security_hook(input_data, tool_use_id, context)

    # PreCompact hook for logging and customizing context compaction
    # Compaction is handled automatically by Claude Code CLI when context approaches limits.
    # This hook allows us to log when compaction occurs and optionally provide custom instructions.
    async def pre_compact_hook(
        input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """
        Hook called before context compaction occurs.

        Compaction triggers:
        - "auto": Automatic compaction when context approaches token limits
        - "manual": User-initiated compaction via /compact command

        The hook can customize compaction via hookSpecificOutput:
        - customInstructions: String with focus areas for summarization
        """
        trigger = input_data.get("trigger", "auto")
        custom_instructions = input_data.get("custom_instructions")

        if trigger == "auto":
            print("[Context] Auto-compaction triggered (context approaching limit)")
        else:
            print("[Context] Manual compaction requested")

        if custom_instructions:
            print(f"[Context] Custom instructions: {custom_instructions}")

        # Return empty dict to allow compaction to proceed with default behavior
        # To customize, return:
        # {
        #     "hookSpecificOutput": {
        #         "hookEventName": "PreCompact",
        #         "customInstructions": "Focus on preserving file paths and test results"
        #     }
        # }
        return SyncHookJSONOutput()

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
                    HookMatcher(matcher="Bash", hooks=[bash_hook_with_context]),
                ],
                # PreCompact hook for context management during long sessions.
                # Compaction is automatic when context approaches token limits.
                # This hook logs compaction events and can customize summarization.
                "PreCompact": [
                    HookMatcher(hooks=[pre_compact_hook]),
                ],
            },
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),  # Use absolute path
            env=sdk_env,  # Pass API configuration overrides to CLI subprocess
            # Enable extended context beta for better handling of long sessions.
            # This provides up to 1M tokens of context with automatic compaction.
            # See: https://docs.anthropic.com/en/api/beta-headers
            betas=["context-1m-2025-08-07"],
            # Note on context management:
            # The Claude Agent SDK handles context management automatically through the
            # underlying Claude Code CLI. When context approaches limits, the CLI
            # automatically compacts/summarizes previous messages.
            #
            # The SDK does NOT expose explicit compaction_control or context_management
            # parameters. Instead, context is managed via:
            # 1. betas=["context-1m-2025-08-07"] - Extended context window
            # 2. PreCompact hook - Intercept and customize compaction behavior
            # 3. max_turns - Limit conversation turns (set to 1000 for long sessions)
            #
            # Future SDK versions may add explicit compaction controls. When available,
            # consider adding:
            # - compaction_control={"enabled": True, "context_token_threshold": 80000}
            # - context_management={"edits": [...]} for tool use clearing
        )
    )
