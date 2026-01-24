"""
Security Hooks for Autonomous Coding Agent
==========================================

Pre-tool-use hooks that validate bash commands for security.
Uses an allowlist approach - only explicitly permitted commands can run.
"""

import os
import shlex
from pathlib import Path
from typing import Optional

import yaml

# Allowed commands for development tasks
# Minimal set needed for the autonomous coding demo
ALLOWED_COMMANDS = {
    # File inspection
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "grep",
    # File operations (agent uses SDK tools for most file ops, but cp/mkdir needed occasionally)
    "cp",
    "mkdir",
    "chmod",  # For making scripts executable; validated separately
    # Directory
    "pwd",
    # Output
    "echo",
    # Node.js development
    "npm",
    "npx",
    "pnpm",  # Project uses pnpm
    "node",
    # Version control
    "git",
    # Docker (for PostgreSQL)
    "docker",
    # Process management
    "ps",
    "lsof",
    "sleep",
    "kill",  # Kill by PID
    "pkill",  # For killing dev servers; validated separately
    # Network/API testing
    "curl",
    # File operations
    "mv",
    "rm",  # Use with caution
    "touch",
    # Shell scripts
    "sh",
    "bash",
    # Script execution
    "init.sh",  # Init scripts; validated separately
}

# Commands that need additional validation even when in the allowlist
COMMANDS_NEEDING_EXTRA_VALIDATION = {"pkill", "chmod", "init.sh"}

# Commands that are NEVER allowed, even with user approval
# These commands can cause permanent system damage or security breaches
BLOCKED_COMMANDS = {
    # Disk operations
    "dd",
    "mkfs",
    "fdisk",
    "parted",
    # System control
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "init",
    # Ownership changes
    "chown",
    "chgrp",
    # System services
    "systemctl",
    "service",
    "launchctl",
    # Network security
    "iptables",
    "ufw",
}

# Commands that trigger emphatic warnings but CAN be approved (Phase 3)
# For now, these are blocked like BLOCKED_COMMANDS until Phase 3 implements approval
DANGEROUS_COMMANDS = {
    # Privilege escalation
    "sudo",
    "su",
    "doas",
    # Cloud CLIs (can modify production infrastructure)
    "aws",
    "gcloud",
    "az",
    # Container and orchestration
    "kubectl",
    "docker-compose",
}


def split_command_segments(command_string: str) -> list[str]:
    """
    Split a compound command into individual command segments.

    Handles command chaining (&&, ||, ;) but not pipes (those are single commands).

    Args:
        command_string: The full shell command

    Returns:
        List of individual command segments
    """
    import re

    # Split on && and || while preserving the ability to handle each segment
    # This regex splits on && or || that aren't inside quotes
    segments = re.split(r"\s*(?:&&|\|\|)\s*", command_string)

    # Further split on semicolons
    result = []
    for segment in segments:
        sub_segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', segment)
        for sub in sub_segments:
            sub = sub.strip()
            if sub:
                result.append(sub)

    return result


def extract_commands(command_string: str) -> list[str]:
    """
    Extract command names from a shell command string.

    Handles pipes, command chaining (&&, ||, ;), and subshells.
    Returns the base command names (without paths).

    Args:
        command_string: The full shell command

    Returns:
        List of command names found in the string
    """
    commands = []

    # shlex doesn't treat ; as a separator, so we need to pre-process
    import re

    # Split on semicolons that aren't inside quotes (simple heuristic)
    # This handles common cases like "echo hello; ls"
    segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', command_string)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        try:
            tokens = shlex.split(segment)
        except ValueError:
            # Malformed command (unclosed quotes, etc.)
            # Return empty to trigger block (fail-safe)
            return []

        if not tokens:
            continue

        # Track when we expect a command vs arguments
        expect_command = True

        for token in tokens:
            # Shell operators indicate a new command follows
            if token in ("|", "||", "&&", "&"):
                expect_command = True
                continue

            # Skip shell keywords that precede commands
            if token in (
                "if",
                "then",
                "else",
                "elif",
                "fi",
                "for",
                "while",
                "until",
                "do",
                "done",
                "case",
                "esac",
                "in",
                "!",
                "{",
                "}",
            ):
                continue

            # Skip flags/options
            if token.startswith("-"):
                continue

            # Skip variable assignments (VAR=value)
            if "=" in token and not token.startswith("="):
                continue

            if expect_command:
                # Extract the base command name (handle paths like /usr/bin/python)
                cmd = os.path.basename(token)
                commands.append(cmd)
                expect_command = False

    return commands


def validate_pkill_command(command_string: str) -> tuple[bool, str]:
    """
    Validate pkill commands - only allow killing dev-related processes.

    Uses shlex to parse the command, avoiding regex bypass vulnerabilities.

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    # Allowed process names for pkill
    allowed_process_names = {
        "node",
        "npm",
        "npx",
        "vite",
        "next",
    }

    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse pkill command"

    if not tokens:
        return False, "Empty pkill command"

    # Separate flags from arguments
    args = []
    for token in tokens[1:]:
        if not token.startswith("-"):
            args.append(token)

    if not args:
        return False, "pkill requires a process name"

    # The target is typically the last non-flag argument
    target = args[-1]

    # For -f flag (full command line match), extract the first word as process name
    # e.g., "pkill -f 'node server.js'" -> target is "node server.js", process is "node"
    if " " in target:
        target = target.split()[0]

    if target in allowed_process_names:
        return True, ""
    return False, f"pkill only allowed for dev processes: {allowed_process_names}"


def validate_chmod_command(command_string: str) -> tuple[bool, str]:
    """
    Validate chmod commands - only allow making files executable with +x.

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse chmod command"

    if not tokens or tokens[0] != "chmod":
        return False, "Not a chmod command"

    # Look for the mode argument
    # Valid modes: +x, u+x, a+x, etc. (anything ending with +x for execute permission)
    mode = None
    files = []

    for token in tokens[1:]:
        if token.startswith("-"):
            # Skip flags like -R (we don't allow recursive chmod anyway)
            return False, "chmod flags are not allowed"
        elif mode is None:
            mode = token
        else:
            files.append(token)

    if mode is None:
        return False, "chmod requires a mode"

    if not files:
        return False, "chmod requires at least one file"

    # Only allow +x variants (making files executable)
    # This matches: +x, u+x, g+x, o+x, a+x, ug+x, etc.
    import re

    if not re.match(r"^[ugoa]*\+x$", mode):
        return False, f"chmod only allowed with +x mode, got: {mode}"

    return True, ""


def validate_init_script(command_string: str) -> tuple[bool, str]:
    """
    Validate init.sh script execution - only allow ./init.sh.

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse init script command"

    if not tokens:
        return False, "Empty command"

    # The command should be exactly ./init.sh (possibly with arguments)
    script = tokens[0]

    # Allow ./init.sh or paths ending in /init.sh
    if script == "./init.sh" or script.endswith("/init.sh"):
        return True, ""

    return False, f"Only ./init.sh is allowed, got: {script}"


def get_command_for_validation(cmd: str, segments: list[str]) -> str:
    """
    Find the specific command segment that contains the given command.

    Args:
        cmd: The command name to find
        segments: List of command segments

    Returns:
        The segment containing the command, or empty string if not found
    """
    for segment in segments:
        segment_commands = extract_commands(segment)
        if cmd in segment_commands:
            return segment
    return ""


def matches_pattern(command: str, pattern: str) -> bool:
    """
    Check if a command matches a pattern.

    Supports:
    - Exact match: "swift"
    - Prefix wildcard: "swift*" matches "swift", "swiftc", "swiftformat"
    - Local script paths: "./scripts/build.sh" or "scripts/test.sh"

    Args:
        command: The command to check
        pattern: The pattern to match against

    Returns:
        True if command matches pattern
    """
    # Reject bare wildcards - security measure to prevent matching everything
    if pattern == "*":
        return False

    # Exact match
    if command == pattern:
        return True

    # Prefix wildcard (e.g., "swift*" matches "swiftc", "swiftlint")
    if pattern.endswith("*"):
        prefix = pattern[:-1]
        # Also reject if prefix is empty (would be bare "*")
        if not prefix:
            return False
        return command.startswith(prefix)

    # Path patterns (./scripts/build.sh, scripts/test.sh, etc.)
    if "/" in pattern:
        # Extract the script name from the pattern
        pattern_name = os.path.basename(pattern)
        return command == pattern or command == pattern_name or command.endswith("/" + pattern_name)

    return False


def get_org_config_path() -> Path:
    """
    Get the organization-level config file path.

    Returns:
        Path to ~/.autocoder/config.yaml
    """
    return Path.home() / ".autocoder" / "config.yaml"


def load_org_config() -> Optional[dict]:
    """
    Load organization-level config from ~/.autocoder/config.yaml.

    Returns:
        Dict with parsed org config, or None if file doesn't exist or is invalid
    """
    config_path = get_org_config_path()

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            return None

        # Validate structure
        if not isinstance(config, dict):
            return None

        if "version" not in config:
            return None

        # Validate allowed_commands if present
        if "allowed_commands" in config:
            allowed = config["allowed_commands"]
            if not isinstance(allowed, list):
                return None
            for cmd in allowed:
                if not isinstance(cmd, dict):
                    return None
                if "name" not in cmd:
                    return None
                # Validate that name is a non-empty string
                if not isinstance(cmd["name"], str) or cmd["name"].strip() == "":
                    return None

        # Validate blocked_commands if present
        if "blocked_commands" in config:
            blocked = config["blocked_commands"]
            if not isinstance(blocked, list):
                return None
            for cmd in blocked:
                if not isinstance(cmd, str):
                    return None

        return config

    except (yaml.YAMLError, IOError, OSError):
        return None


def load_project_commands(project_dir: Path) -> Optional[dict]:
    """
    Load allowed commands from project-specific YAML config.

    Args:
        project_dir: Path to the project directory

    Returns:
        Dict with parsed YAML config, or None if file doesn't exist or is invalid
    """
    config_path = project_dir / ".autocoder" / "allowed_commands.yaml"

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            return None

        # Validate structure
        if not isinstance(config, dict):
            return None

        if "version" not in config:
            return None

        commands = config.get("commands", [])
        if not isinstance(commands, list):
            return None

        # Enforce 100 command limit
        if len(commands) > 100:
            return None

        # Validate each command entry
        for cmd in commands:
            if not isinstance(cmd, dict):
                return None
            if "name" not in cmd:
                return None
            # Validate name is a string
            if not isinstance(cmd["name"], str):
                return None

        return config

    except (yaml.YAMLError, IOError, OSError):
        return None


def validate_project_command(cmd_config: dict) -> tuple[bool, str]:
    """
    Validate a single command entry from project config.

    Args:
        cmd_config: Dict with command configuration (name, description, args)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(cmd_config, dict):
        return False, "Command must be a dict"

    if "name" not in cmd_config:
        return False, "Command must have 'name' field"

    name = cmd_config["name"]
    if not isinstance(name, str) or not name:
        return False, "Command name must be a non-empty string"

    # Reject bare wildcard - security measure to prevent matching all commands
    if name == "*":
        return False, "Bare wildcard '*' is not allowed (security risk: matches all commands)"

    # Check if command is in the blocklist or dangerous commands
    base_cmd = os.path.basename(name.rstrip("*"))
    if base_cmd in BLOCKED_COMMANDS:
        return False, f"Command '{name}' is in the blocklist and cannot be allowed"
    if base_cmd in DANGEROUS_COMMANDS:
        return False, f"Command '{name}' is in the blocklist and cannot be allowed"

    # Description is optional
    if "description" in cmd_config and not isinstance(cmd_config["description"], str):
        return False, "Description must be a string"

    # Args validation (Phase 1 - just check structure)
    if "args" in cmd_config:
        args = cmd_config["args"]
        if not isinstance(args, list):
            return False, "Args must be a list"
        for arg in args:
            if not isinstance(arg, str):
                return False, "Each arg must be a string"

    return True, ""


def get_effective_commands(project_dir: Optional[Path]) -> tuple[set[str], set[str]]:
    """
    Get effective allowed and blocked commands after hierarchy resolution.

    Hierarchy (highest to lowest priority):
    1. BLOCKED_COMMANDS (hardcoded) - always blocked
    2. Org blocked_commands - cannot be unblocked
    3. Org allowed_commands - adds to global
    4. Project allowed_commands - adds to global + org

    Args:
        project_dir: Path to the project directory, or None

    Returns:
        Tuple of (allowed_commands, blocked_commands)
    """
    # Start with global allowed commands
    allowed = ALLOWED_COMMANDS.copy()
    blocked = BLOCKED_COMMANDS.copy()

    # Add dangerous commands to blocked (Phase 3 will add approval flow)
    blocked |= DANGEROUS_COMMANDS

    # Load org config and apply
    org_config = load_org_config()
    if org_config:
        # Add org-level blocked commands (cannot be overridden)
        org_blocked = org_config.get("blocked_commands", [])
        blocked |= set(org_blocked)

        # Add org-level allowed commands
        for cmd_config in org_config.get("allowed_commands", []):
            if isinstance(cmd_config, dict) and "name" in cmd_config:
                allowed.add(cmd_config["name"])

    # Load project config and apply
    if project_dir:
        project_config = load_project_commands(project_dir)
        if project_config:
            # Add project-specific commands
            for cmd_config in project_config.get("commands", []):
                valid, error = validate_project_command(cmd_config)
                if valid:
                    allowed.add(cmd_config["name"])

    # Remove blocked commands from allowed (blocklist takes precedence)
    allowed -= blocked

    return allowed, blocked


def get_project_allowed_commands(project_dir: Optional[Path]) -> set[str]:
    """
    Get the set of allowed commands for a project.

    Uses hierarchy resolution from get_effective_commands().

    Args:
        project_dir: Path to the project directory, or None

    Returns:
        Set of allowed command names (including patterns)
    """
    allowed, blocked = get_effective_commands(project_dir)
    return allowed


def is_command_allowed(command: str, allowed_commands: set[str]) -> bool:
    """
    Check if a command is allowed (supports patterns).

    Args:
        command: The command to check
        allowed_commands: Set of allowed commands (may include patterns)

    Returns:
        True if command is allowed
    """
    # Check exact match first
    if command in allowed_commands:
        return True

    # Check pattern matches
    for pattern in allowed_commands:
        if matches_pattern(command, pattern):
            return True

    return False


async def bash_security_hook(input_data, tool_use_id=None, context=None):
    """
    Pre-tool-use hook that validates bash commands using an allowlist.

    Only commands in ALLOWED_COMMANDS and project-specific commands are permitted.

    Args:
        input_data: Dict containing tool_name and tool_input
        tool_use_id: Optional tool use ID
        context: Optional context dict with 'project_dir' key

    Returns:
        Empty dict to allow, or {"decision": "block", "reason": "..."} to block
    """
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return {}

    # Extract all commands from the command string
    commands = extract_commands(command)

    if not commands:
        # Could not parse - fail safe by blocking
        return {
            "decision": "block",
            "reason": f"Could not parse command for security validation: {command}",
        }

    # Get project directory from context
    project_dir = None
    if context and isinstance(context, dict):
        project_dir_str = context.get("project_dir")
        if project_dir_str:
            project_dir = Path(project_dir_str)

    # Get effective commands using hierarchy resolution
    allowed_commands, blocked_commands = get_effective_commands(project_dir)

    # Split into segments for per-command validation
    segments = split_command_segments(command)

    # Check each command against the blocklist and allowlist
    for cmd in commands:
        # Check blocklist first (highest priority)
        if cmd in blocked_commands:
            return {
                "decision": "block",
                "reason": f"Command '{cmd}' is blocked at organization level and cannot be approved.",
            }

        # Check allowlist (with pattern matching)
        if not is_command_allowed(cmd, allowed_commands):
            # Provide helpful error message with config hint
            error_msg = f"Command '{cmd}' is not allowed.\n"
            error_msg += "To allow this command:\n"
            error_msg += "  1. Add to .autocoder/allowed_commands.yaml for this project, OR\n"
            error_msg += "  2. Request mid-session approval (the agent can ask)\n"
            error_msg += "Note: Some commands are blocked at org-level and cannot be overridden."
            return {
                "decision": "block",
                "reason": error_msg,
            }

        # Additional validation for sensitive commands
        if cmd in COMMANDS_NEEDING_EXTRA_VALIDATION:
            # Find the specific segment containing this command
            cmd_segment = get_command_for_validation(cmd, segments)
            if not cmd_segment:
                cmd_segment = command  # Fallback to full command

            if cmd == "pkill":
                allowed, reason = validate_pkill_command(cmd_segment)
                if not allowed:
                    return {"decision": "block", "reason": reason}
            elif cmd == "chmod":
                allowed, reason = validate_chmod_command(cmd_segment)
                if not allowed:
                    return {"decision": "block", "reason": reason}
            elif cmd == "init.sh":
                allowed, reason = validate_init_script(cmd_segment)
                if not allowed:
                    return {"decision": "block", "reason": reason}

    return {}
