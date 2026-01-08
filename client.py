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

from security import bash_security_hook


def backup_existing_claude_settings(project_dir: Path) -> list[Path]:
    """Backup existing Claude settings that might conflict with autocoder.

    When importing projects that have their own .claude/ configuration,
    those settings can conflict with autocoder's sandbox permissions.
    This function backs up conflicting settings files.

    Args:
        project_dir: The project directory to check

    Returns:
        List of paths that were backed up (for later restoration)
    """
    backed_up = []
    claude_dir = project_dir / ".claude"

    if not claude_dir.exists():
        return backed_up

    # Settings files that can conflict with autocoder's permissions
    conflicting_files = [
        "settings.local.json",
        "settings.json",
    ]

    for filename in conflicting_files:
        settings_path = claude_dir / filename
        if settings_path.exists():
            backup_path = claude_dir / f"{filename}.autocoder_backup"
            # Remove existing backup if present (from previous failed run)
            if backup_path.exists():
                try:
                    backup_path.unlink()
                    print(f"   - Removed stale backup: {backup_path.name}")
                except OSError as e:
                    print(f"   - Warning: Could not remove stale backup {backup_path}: {e}")
                    # Use a unique backup name with timestamp instead of skipping
                    import time
                    backup_path = claude_dir / f"{filename}.autocoder_backup.{int(time.time())}"
            try:
                shutil.move(str(settings_path), str(backup_path))
                backed_up.append(backup_path)
                print(f"   - Backed up conflicting settings: {settings_path.name} -> {backup_path.name}")
            except OSError as e:
                print(f"   - Warning: Could not backup {settings_path}: {e}")

    return backed_up


def restore_claude_settings(backed_up_paths: list[Path]) -> None:
    """Restore Claude settings that were backed up.

    Args:
        backed_up_paths: List of backup paths returned by backup_existing_claude_settings
    """
    for backup_path in backed_up_paths:
        if backup_path.exists():
            # Handle both regular and timestamped backup names:
            # - Regular: settings.json.autocoder_backup -> settings.json
            # - Timestamped: settings.json.autocoder_backup.1234567890 -> settings.json
            name = backup_path.name
            if ".autocoder_backup." in name:
                # Timestamped backup: split on .autocoder_backup. and take left part
                original_name = name.split(".autocoder_backup.")[0]
            else:
                # Regular backup: just remove .autocoder_backup suffix
                original_name = name.replace(".autocoder_backup", "")
            original_path = backup_path.parent / original_name

            # Check if a new file was created at the original path during the run
            if original_path.exists():
                print(f"   - Warning: {original_path.name} was recreated during agent run, keeping both")
                # Keep the backup with a different name to preserve both versions
                archive_path = backup_path.parent / f"{original_name}.pre_autocoder"
                try:
                    shutil.move(str(backup_path), str(archive_path))
                    print(f"   - Archived original settings as: {archive_path.name}")
                except OSError as e:
                    print(f"   - Warning: Could not archive {backup_path}: {e}")
                continue

            try:
                shutil.move(str(backup_path), str(original_path))
                print(f"   - Restored settings: {original_path.name}")
            except OSError as e:
                print(f"   - Warning: Could not restore {backup_path}: {e}")

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

# Context MCP tools for analyzer mode documentation
CONTEXT_MCP_TOOLS = [
    "mcp__features__context_list",
    "mcp__features__context_read",
    "mcp__features__context_read_all",
    "mcp__features__context_write",
    "mcp__features__context_get_progress",
    "mcp__features__context_update_index",
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


def create_client(project_dir: Path, model: str, yolo_mode: bool = False) -> tuple["ClaudeSDKClient", list[Path]]:
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        yolo_mode: If True, skip Playwright MCP server for rapid prototyping

    Returns:
        Tuple of (ClaudeSDKClient, backed_up_paths) where backed_up_paths
        contains paths to settings files that were backed up and should be
        restored after the agent completes using restore_claude_settings().

    Security layers (defense in depth):
    1. Sandbox - OS-level bash command isolation prevents filesystem escape
    2. Permissions - File operations restricted to project_dir only
    3. Security hooks - Bash commands validated against an allowlist
       (see security.py for ALLOWED_COMMANDS)

    Note: Authentication is handled by start.bat/start.sh before this runs.
    The Claude SDK auto-detects credentials from ~/.claude/.credentials.json
    """
    # Backup any existing Claude settings that might conflict with autocoder
    backed_up_paths = backup_existing_claude_settings(project_dir)
    # Build allowed tools list based on mode
    # In YOLO mode, exclude Playwright tools for faster prototyping
    # Context tools are always included for analyzer mode documentation
    allowed_tools = [*BUILTIN_TOOLS, *FEATURE_MCP_TOOLS, *CONTEXT_MCP_TOOLS]
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
        # Allow Context MCP tools for analyzer mode documentation
        *CONTEXT_MCP_TOOLS,
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
        print("   - Warning: System Claude CLI not found, using bundled CLI")

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
        mcp_servers["playwright"] = {
            "command": "npx",
            "args": ["@playwright/mcp@latest", "--viewport-size", "1280x720"],
        }

    client = ClaudeSDKClient(
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

    return client, backed_up_paths
