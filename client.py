"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import HookContext, HookInput, HookMatcher, SyncHookJSONOutput
from dotenv import load_dotenv

from security import SENSITIVE_DIRECTORIES, bash_security_hook

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

# Extra read paths for cross-project file access (read-only)
# Set EXTRA_READ_PATHS environment variable with comma-separated absolute paths
# Example: EXTRA_READ_PATHS=/Volumes/Data/dev,/Users/shared/libs
EXTRA_READ_PATHS_VAR = "EXTRA_READ_PATHS"

# Sensitive directories that should never be allowed via EXTRA_READ_PATHS.
# Delegates to the canonical SENSITIVE_DIRECTORIES set in security.py so that
# this blocklist and the filesystem browser API share a single source of truth.
EXTRA_READ_PATHS_BLOCKLIST = SENSITIVE_DIRECTORIES

def convert_model_for_vertex(model: str) -> str:
    """
    Convert model name format for Vertex AI compatibility.

    Vertex AI uses @ to separate model name from version (e.g., claude-sonnet-4-5@20250929)
    while the Anthropic API uses - (e.g., claude-sonnet-4-5-20250929).
    Models without a date suffix (e.g., claude-opus-4-6) pass through unchanged.

    Args:
        model: Model name in Anthropic format (with hyphens)

    Returns:
        Model name in Vertex AI format (with @ before date) if Vertex AI is enabled,
        otherwise returns the model unchanged.
    """
    # Only convert if Vertex AI is enabled
    if os.getenv("CLAUDE_CODE_USE_VERTEX") != "1":
        return model

    # Pattern: claude-{name}-{version}-{date} -> claude-{name}-{version}@{date}
    # Example: claude-sonnet-4-5-20250929 -> claude-sonnet-4-5@20250929
    # The date is always 8 digits at the end
    match = re.match(r'^(claude-.+)-(\d{8})$', model)
    if match:
        base_name, date = match.groups()
        return f"{base_name}@{date}"

    # If already in @ format or doesn't match expected pattern, return as-is
    return model


def get_playwright_headless() -> bool:
    """
    Get the Playwright headless mode setting.

    Reads from PLAYWRIGHT_HEADLESS environment variable, defaults to True.
    Returns True for headless mode (invisible browser), False for visible browser.
    """
    value = os.getenv("PLAYWRIGHT_HEADLESS", str(DEFAULT_PLAYWRIGHT_HEADLESS).lower()).strip().lower()
    truthy = {"true", "1", "yes", "on"}
    falsy = {"false", "0", "no", "off"}
    if value not in truthy | falsy:
        print(f"   - Warning: Invalid PLAYWRIGHT_HEADLESS='{value}', defaulting to {DEFAULT_PLAYWRIGHT_HEADLESS}")
        return DEFAULT_PLAYWRIGHT_HEADLESS
    return value in truthy


# Valid browsers supported by Playwright MCP
VALID_PLAYWRIGHT_BROWSERS = {"chrome", "firefox", "webkit", "msedge"}


def get_playwright_browser() -> str:
    """
    Get the browser to use for Playwright.

    Reads from PLAYWRIGHT_BROWSER environment variable, defaults to firefox.
    Options: chrome, firefox, webkit, msedge
    Firefox is recommended for lower CPU usage.
    """
    value = os.getenv("PLAYWRIGHT_BROWSER", DEFAULT_PLAYWRIGHT_BROWSER).strip().lower()
    if value not in VALID_PLAYWRIGHT_BROWSERS:
        print(f"   - Warning: Invalid PLAYWRIGHT_BROWSER='{value}', "
              f"valid options: {', '.join(sorted(VALID_PLAYWRIGHT_BROWSERS))}. "
              f"Defaulting to {DEFAULT_PLAYWRIGHT_BROWSER}")
        return DEFAULT_PLAYWRIGHT_BROWSER
    return value


def get_extra_read_paths() -> list[Path]:
    """
    Get extra read-only paths from EXTRA_READ_PATHS environment variable.

    Parses comma-separated absolute paths and validates each one:
    - Must be an absolute path
    - Must exist and be a directory
    - Cannot be or contain sensitive directories (e.g., .ssh, .aws)

    Returns:
        List of validated, canonicalized Path objects.
    """
    raw_value = os.getenv(EXTRA_READ_PATHS_VAR, "").strip()
    if not raw_value:
        return []

    validated_paths: list[Path] = []
    home_dir = Path.home()

    for path_str in raw_value.split(","):
        path_str = path_str.strip()
        if not path_str:
            continue

        # Parse and canonicalize the path
        try:
            path = Path(path_str).resolve()
        except (OSError, ValueError) as e:
            print(f"   - Warning: Invalid EXTRA_READ_PATHS path '{path_str}': {e}")
            continue

        # Must be absolute (resolve() makes it absolute, but check original input)
        if not Path(path_str).is_absolute():
            print(f"   - Warning: EXTRA_READ_PATHS requires absolute paths, skipping: {path_str}")
            continue

        # Must exist
        if not path.exists():
            print(f"   - Warning: EXTRA_READ_PATHS path does not exist, skipping: {path_str}")
            continue

        # Must be a directory
        if not path.is_dir():
            print(f"   - Warning: EXTRA_READ_PATHS path is not a directory, skipping: {path_str}")
            continue

        # Check against sensitive directory blocklist
        is_blocked = False
        for sensitive in EXTRA_READ_PATHS_BLOCKLIST:
            sensitive_path = (home_dir / sensitive).resolve()
            try:
                # Block if path IS the sensitive dir or is INSIDE it
                if path == sensitive_path or path.is_relative_to(sensitive_path):
                    print(f"   - Warning: EXTRA_READ_PATHS blocked sensitive path: {path_str}")
                    is_blocked = True
                    break
                # Also block if sensitive dir is INSIDE the requested path
                if sensitive_path.is_relative_to(path):
                    print(f"   - Warning: EXTRA_READ_PATHS path contains sensitive directory ({sensitive}): {path_str}")
                    is_blocked = True
                    break
            except (OSError, ValueError):
                # is_relative_to can raise on some edge cases
                continue

        if is_blocked:
            continue

        validated_paths.append(path)

    return validated_paths


# Per-agent-type MCP tool lists.
# Only expose the tools each agent type actually needs, reducing tool schema
# overhead and preventing agents from calling tools meant for other roles.
#
# Tools intentionally omitted from ALL agent lists (UI/orchestrator only):
#   feature_get_ready, feature_get_blocked, feature_get_graph,
#   feature_remove_dependency
#
# The ghost tool "feature_release_testing" was removed entirely -- it was
# listed here but never implemented in mcp_server/feature_mcp.py.

CODING_AGENT_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_by_id",
    "mcp__features__feature_get_summary",
    "mcp__features__feature_claim_and_get",
    "mcp__features__feature_mark_in_progress",
    "mcp__features__feature_mark_passing",
    "mcp__features__feature_mark_failing",
    "mcp__features__feature_skip",
    "mcp__features__feature_clear_in_progress",
]

TESTING_AGENT_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_by_id",
    "mcp__features__feature_get_summary",
    "mcp__features__feature_mark_passing",
    "mcp__features__feature_mark_failing",
]

INITIALIZER_AGENT_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_create_bulk",
    "mcp__features__feature_create",
    "mcp__features__feature_add_dependency",
    "mcp__features__feature_set_dependencies",
]

# Union of all agent tool lists -- used for permissions (all tools remain
# *permitted* so the MCP server can respond, but only the agent-type-specific
# list is included in allowed_tools, which controls what the LLM sees).
ALL_FEATURE_MCP_TOOLS = sorted(
    set(CODING_AGENT_TOOLS) | set(TESTING_AGENT_TOOLS) | set(INITIALIZER_AGENT_TOOLS)
)

# Playwright MCP tools for browser automation.
# Full set of tools for comprehensive UI testing including drag-and-drop,
# hover menus, file uploads, tab management, etc.
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
    "mcp__playwright__browser_press_key",
    "mcp__playwright__browser_drag",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_file_upload",

    # JavaScript & debugging
    "mcp__playwright__browser_evaluate",
    # "mcp__playwright__browser_run_code",  # REMOVED - causes Playwright MCP server crash
    "mcp__playwright__browser_console_messages",
    "mcp__playwright__browser_network_requests",

    # Browser management
    "mcp__playwright__browser_resize",
    "mcp__playwright__browser_wait_for",
    "mcp__playwright__browser_handle_dialog",
    "mcp__playwright__browser_install",
    "mcp__playwright__browser_close",
    "mcp__playwright__browser_tabs",
]

# Built-in tools available to agents.
# WebFetch and WebSearch are included so coding agents can look up current
# documentation for frameworks and libraries they are implementing.
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


def should_use_playwright(testing_mode: str, feature_category: str | None, yolo_mode: bool) -> bool:
    """
    Determine if Playwright tools should be included based on testing mode and feature category.

    Args:
        testing_mode: Testing mode - "full" or "smart"
        feature_category: Category of the feature (e.g., "API", "UI", "Database")
        yolo_mode: Whether YOLO mode is enabled (overrides everything)

    Returns:
        True if Playwright tools should be included, False otherwise
    """
    # YOLO mode always disables Playwright
    if yolo_mode:
        return False

    # "smart" mode only uses Playwright for UI features
    if testing_mode == "smart":
        if feature_category:
            category_lower = feature_category.lower()
            # Exclude for API/backend features
            api_keywords = ["api", "backend", "database", "db", "server", "endpoint", "service"]
            if any(kw in category_lower for kw in api_keywords):
                return False
        # Default: use Playwright (for UI features or unknown categories)
        return True

    # "full" mode (default) always uses Playwright
    return True


def create_client(
    project_dir: Path,
    model: str,
    yolo_mode: bool = False,
    agent_id: str | None = None,
    agent_type: str = "coding",
    testing_mode: str = "full",
    feature_category: str | None = None,
):
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        yolo_mode: If True, skip Playwright MCP server for rapid prototyping
        agent_id: Optional unique identifier for browser isolation in parallel mode.
                  When provided, each agent gets its own browser profile.
        agent_type: One of "coding", "testing", or "initializer". Controls which
                    MCP tools are exposed and the max_turns limit.
        testing_mode: Testing mode - "full" (always Playwright), "smart" (UI only)
        feature_category: Category of the feature being worked on (for smart mode)

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
    # Select the feature MCP tools appropriate for this agent type
    feature_tools_map = {
        "coding": CODING_AGENT_TOOLS,
        "testing": TESTING_AGENT_TOOLS,
        "initializer": INITIALIZER_AGENT_TOOLS,
    }
    feature_tools = feature_tools_map.get(agent_type, CODING_AGENT_TOOLS)

    # Select max_turns based on agent type:
    #   - coding/initializer: 300 turns (complex multi-step implementation)
    #   - testing: 100 turns (focused verification of a single feature)
    max_turns_map = {
        "coding": 300,
        "testing": 100,
        "initializer": 300,
    }
    max_turns = max_turns_map.get(agent_type, 300)

    # Determine if Playwright should be used
    use_playwright = should_use_playwright(testing_mode, feature_category, yolo_mode)

    # Build allowed tools list based on mode and agent type.
    allowed_tools = [*BUILTIN_TOOLS, *feature_tools]
    if use_playwright:
        allowed_tools.extend(PLAYWRIGHT_TOOLS)

    # Build permissions list.
    # We permit ALL feature MCP tools at the security layer (so the MCP server
    # can respond if called), but the LLM only *sees* the agent-type-specific
    # subset via allowed_tools above.
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
        # Allow web tools for looking up framework/library documentation
        "WebFetch(*)",
        "WebSearch(*)",
        # Allow Feature MCP tools for feature management
        *ALL_FEATURE_MCP_TOOLS,
    ]

    # Add extra read paths from environment variable (read-only access)
    # Paths are validated, canonicalized, and checked against sensitive blocklist
    extra_read_paths = get_extra_read_paths()
    for path in extra_read_paths:
        # Add read-only permissions for each validated path
        permissions_list.append(f"Read({path}/**)")
        permissions_list.append(f"Glob({path}/**)")
        permissions_list.append(f"Grep({path}/**)")

    if use_playwright:
        # Allow Playwright MCP tools for browser automation
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
    from autoforge_paths import get_claude_settings_path
    settings_file = get_claude_settings_path(project_dir)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    print(f"Created security settings at {settings_file}")
    print("   - Sandbox enabled (OS-level bash isolation)")
    print(f"   - Filesystem restricted to: {project_dir.resolve()}")
    if extra_read_paths:
        print(f"   - Extra read paths (validated): {', '.join(str(p) for p in extra_read_paths)}")
    print("   - Bash commands restricted to allowlist (see security.py)")
    if not use_playwright:
        reason = "YOLO MODE" if yolo_mode else f"testing_mode={testing_mode}"
        if testing_mode == "smart" and feature_category:
            reason += f", category={feature_category}"
        print(f"   - MCP servers: features (database) - NO Playwright ({reason})")
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
    if use_playwright:
        # Include Playwright MCP server for browser automation
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
            "env": {
                "NODE_COMPILE_CACHE": "",  # Disable V8 compile caching to prevent .node file accumulation in %TEMP%
            },
        }

    # Build environment overrides for API endpoint configuration
    # Uses get_effective_sdk_env() which reads provider settings from the database,
    # ensuring UI-configured alternative providers (GLM, Ollama, Kimi, Custom) propagate
    # correctly to the Claude CLI subprocess
    from registry import get_effective_sdk_env
    sdk_env = get_effective_sdk_env()

    # Detect alternative API mode (Ollama, GLM, or Vertex AI)
    base_url = sdk_env.get("ANTHROPIC_BASE_URL", "")
    is_vertex = sdk_env.get("CLAUDE_CODE_USE_VERTEX") == "1"
    is_alternative_api = bool(base_url) or is_vertex
    is_ollama = "localhost:11434" in base_url or "127.0.0.1:11434" in base_url
    model = convert_model_for_vertex(model)
    if sdk_env:
        print(f"   - API overrides: {', '.join(sdk_env.keys())}")
        if is_vertex:
            project_id = sdk_env.get("ANTHROPIC_VERTEX_PROJECT_ID", "unknown")
            region = sdk_env.get("CLOUD_ML_REGION", "unknown")
            print(f"   - Vertex AI Mode: Using GCP project '{project_id}' with model '{model}' in region '{region}'")
        elif is_ollama:
            print("   - Ollama Mode: Using local models")
        elif "ANTHROPIC_BASE_URL" in sdk_env:
            print(f"   - GLM Mode: Using {sdk_env['ANTHROPIC_BASE_URL']}")

    # Create a wrapper for bash_security_hook that passes project_dir via context
    async def bash_hook_with_context(input_data, tool_use_id=None, context=None):
        """Wrapper that injects project_dir into context for security hook."""
        if context is None:
            context = {}
        context["project_dir"] = str(project_dir.resolve())
        return await bash_security_hook(input_data, tool_use_id, context)

    # PreCompact hook for logging and customizing context compaction.
    # Compaction is handled automatically by Claude Code CLI when context approaches limits.
    # This hook provides custom instructions that guide the summarizer to preserve
    # critical workflow state while discarding verbose/redundant content.
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

        Returns custom instructions that guide the compaction summarizer to:
        1. Preserve critical workflow state (feature ID, modified files, test results)
        2. Discard verbose content (screenshots, long grep outputs, repeated reads)
        """
        trigger = input_data.get("trigger", "auto")
        custom_instructions = input_data.get("custom_instructions")

        if trigger == "auto":
            print("[Context] Auto-compaction triggered (context approaching limit)")
        else:
            print("[Context] Manual compaction requested")

        if custom_instructions:
            print(f"[Context] Custom instructions provided: {custom_instructions}")

        # Build compaction instructions that preserve workflow-critical context
        # while discarding verbose content that inflates token usage.
        #
        # The summarizer receives these instructions and uses them to decide
        # what to keep vs. discard during context compaction.
        compaction_guidance = "\n".join([
            "## PRESERVE (critical workflow state)",
            "- Current feature ID, feature name, and feature status (pending/in_progress/passing/failing)",
            "- List of all files created or modified during this session, with their paths",
            "- Last test/lint/type-check results: command run, pass/fail status, and key error messages",
            "- Current step in the workflow (e.g., implementing, testing, fixing lint errors)",
            "- Any dependency information (which features block this one)",
            "- Git operations performed (commits, branches created)",
            "- MCP tool call results (feature_claim_and_get, feature_mark_passing, etc.)",
            "- Key architectural decisions made during this session",
            "",
            "## DISCARD (verbose content safe to drop)",
            "- Full screenshot base64 data (just note that a screenshot was taken and what it showed)",
            "- Long grep/find/glob output listings (summarize to: searched for X, found Y relevant files)",
            "- Repeated file reads of the same file (keep only the latest read or a summary of changes)",
            "- Full file contents from Read tool (summarize to: read file X, key sections were Y)",
            "- Verbose npm/pip install output (just note: dependencies installed successfully/failed)",
            "- Full lint/type-check output when passing (just note: lint passed with no errors)",
            "- Browser console message dumps (summarize to: N errors found, key error was X)",
            "- Redundant tool result confirmations ([Done] markers)",
        ])

        print("[Context] Applying custom compaction instructions (preserve workflow state, discard verbose content)")

        # The SDK's HookSpecificOutput union type does not yet include a
        # PreCompactHookSpecificOutput variant, but the CLI protocol accepts
        # {"hookEventName": "PreCompact", "customInstructions": "..."}.
        # The dict is serialized to JSON and sent to the CLI process directly,
        # so the runtime behavior is correct despite the type mismatch.
        return SyncHookJSONOutput(
            hookSpecificOutput={  # type: ignore[typeddict-item]
                "hookEventName": "PreCompact",
                "customInstructions": compaction_guidance,
            }
        )

    # PROMPT CACHING: The Claude Code CLI applies cache_control breakpoints internally.
    # Our system_prompt benefits from automatic caching without explicit configuration.
    # If explicit cache_control is needed, the SDK would need to accept content blocks
    # with cache_control fields (not currently supported in v0.1.x).
    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            cli_path=system_cli,  # Use system CLI to avoid bundled Bun crash (exit code 3)
            system_prompt="You are an expert full-stack developer building a production-quality web application.",
            setting_sources=["project"],  # Enable skills, commands, and CLAUDE.md from project dir
            max_buffer_size=10 * 1024 * 1024,  # 10MB for large Playwright screenshots
            allowed_tools=allowed_tools,
            mcp_servers=mcp_servers,  # type: ignore[arg-type]  # SDK accepts dict config at runtime
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
            max_turns=max_turns,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),  # Use absolute path
            env=sdk_env,  # Pass API configuration overrides to CLI subprocess
            # Enable extended context beta for better handling of long sessions.
            # This provides up to 1M tokens of context with automatic compaction.
            # See: https://docs.anthropic.com/en/api/beta-headers
            # Disabled for alternative APIs (Ollama, GLM, Vertex AI) as they don't support this beta.
            betas=[] if is_alternative_api else ["context-1m-2025-08-07"],
            # Note on context management:
            # The Claude Agent SDK handles context management automatically through the
            # underlying Claude Code CLI. When context approaches limits, the CLI
            # automatically compacts/summarizes previous messages.
            #
            # The SDK does NOT expose explicit compaction_control or context_management
            # parameters. Instead, context is managed via:
            # 1. betas=["context-1m-2025-08-07"] - Extended context window
            # 2. PreCompact hook - Intercept and customize compaction behavior
            # 3. max_turns - Limit conversation turns (per agent type: coding=300, testing=100)
            #
            # Future SDK versions may add explicit compaction controls. When available,
            # consider adding:
            # - compaction_control={"enabled": True, "context_token_threshold": 80000}
            # - context_management={"edits": [...]} for tool use clearing
        )
    )
