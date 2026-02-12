"""
Security Hooks for Autonomous Coding Agent
==========================================

Pre-tool-use hooks that validate bash commands for security.
Uses an allowlist approach - only explicitly permitted commands can run.
"""

import logging
import os
import re
import shlex
from pathlib import Path
from typing import Optional

import yaml

# Logger for security-related events (fallback parsing, validation failures, etc.)
logger = logging.getLogger(__name__)

# Regex pattern for valid pkill process names (no regex metacharacters allowed)
# Matches alphanumeric names with dots, underscores, and hyphens
VALID_PROCESS_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

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
    # Browser automation
    "playwright-cli",  # Playwright CLI for browser testing; validated separately
}

# Commands that need additional validation even when in the allowlist
COMMANDS_NEEDING_EXTRA_VALIDATION = {"pkill", "chmod", "init.sh", "playwright-cli"}

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

# Sensitive directories (relative to home) that should never be exposed.
# Used by both the EXTRA_READ_PATHS validator (client.py) and the filesystem
# browser API (server/routers/filesystem.py) to block credential/key directories.
# This is the single source of truth -- import from here in both places.
#
# SENSITIVE_DIRECTORIES is the union of the previous filesystem browser blocklist
# (filesystem.py) and the previous EXTRA_READ_PATHS blocklist (client.py).
# Some entries are new to each consumer -- this is intentional for defense-in-depth.
SENSITIVE_DIRECTORIES = {
    ".ssh",
    ".aws",
    ".azure",
    ".kube",
    ".gnupg",
    ".gpg",
    ".password-store",
    ".docker",
    ".config/gcloud",
    ".config/gh",
    ".npmrc",
    ".pypirc",
    ".netrc",
    ".terraform",
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


def _extract_primary_command(segment: str) -> str | None:
    """
    Fallback command extraction when shlex fails.

    Extracts the first word that looks like a command, handling cases
    like complex docker exec commands with nested quotes.

    Args:
        segment: The command segment to parse

    Returns:
        The primary command name, or None if extraction fails
    """
    # Remove leading whitespace
    segment = segment.lstrip()

    if not segment:
        return None

    # Skip env var assignments at start (VAR=value cmd)
    words = segment.split()
    while words and "=" in words[0] and not words[0].startswith("="):
        words = words[1:]

    if not words:
        return None

    # Extract first token (the command)
    first_word = words[0]

    # Match valid command characters (alphanumeric, dots, underscores, hyphens, slashes)
    match = re.match(r"^([a-zA-Z0-9_./-]+)", first_word)
    if match:
        cmd = match.group(1)
        return os.path.basename(cmd)

    return None


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
            # Try fallback extraction instead of blocking entirely
            fallback_cmd = _extract_primary_command(segment)
            if fallback_cmd:
                logger.debug(
                    "shlex fallback used: segment=%r -> command=%r",
                    segment,
                    fallback_cmd,
                )
                commands.append(fallback_cmd)
            else:
                logger.debug(
                    "shlex fallback failed: segment=%r (no command extracted)",
                    segment,
                )
            continue

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


# Default pkill process names (hardcoded baseline, always available)
DEFAULT_PKILL_PROCESSES = {
    "node",
    "npm",
    "npx",
    "vite",
    "next",
}


def validate_pkill_command(
    command_string: str,
    extra_processes: Optional[set[str]] = None
) -> tuple[bool, str]:
    """
    Validate pkill commands - only allow killing dev-related processes.

    Uses shlex to parse the command, avoiding regex bypass vulnerabilities.

    Args:
        command_string: The pkill command to validate
        extra_processes: Optional set of additional process names to allow
                        (from org/project config pkill_processes)

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    # Merge default processes with any extra configured processes
    allowed_process_names = DEFAULT_PKILL_PROCESSES.copy()
    if extra_processes:
        allowed_process_names |= extra_processes

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

    # Validate every non-flag argument (pkill accepts multiple patterns on BSD)
    # This defensively ensures no disallowed process can be targeted
    targets = []
    for arg in args:
        # For -f flag (full command line match), take the first word as process name
        # e.g., "pkill -f 'node server.js'" -> target is "node server.js", process is "node"
        t = arg.split()[0] if " " in arg else arg
        targets.append(t)

    disallowed = [t for t in targets if t not in allowed_process_names]
    if not disallowed:
        return True, ""
    return False, f"pkill only allowed for processes: {sorted(allowed_process_names)}"


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


def validate_playwright_command(command_string: str) -> tuple[bool, str]:
    """
    Validate playwright-cli commands - block dangerous subcommands.

    Blocks `run-code` (arbitrary Node.js execution) and `eval` (arbitrary JS
    evaluation) which bypass the security sandbox.

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse playwright-cli command"

    if not tokens:
        return False, "Empty command"

    BLOCKED_SUBCOMMANDS = {"run-code", "eval"}

    # Find the subcommand: first non-flag token after 'playwright-cli'
    for token in tokens[1:]:
        if token.startswith("-"):
            continue  # skip flags like -s=agent-1
        if token in BLOCKED_SUBCOMMANDS:
            return False, f"playwright-cli '{token}' is not allowed"
        break  # first non-flag token is the subcommand

    return True, ""


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


def _validate_command_list(commands: list, config_path: Path, field_name: str) -> bool:
    """
    Validate a list of command entries from a YAML config.

    Each entry must be a dict with a non-empty string 'name' field.
    Used by both load_org_config() and load_project_commands() to avoid
    duplicating the same validation logic.

    Args:
        commands: List of command entries to validate
        config_path: Path to the config file (for log messages)
        field_name: Name of the YAML field being validated (e.g., 'allowed_commands', 'commands')

    Returns:
        True if all entries are valid, False otherwise
    """
    if not isinstance(commands, list):
        logger.warning(f"Config at {config_path}: '{field_name}' must be a list")
        return False
    for i, cmd in enumerate(commands):
        if not isinstance(cmd, dict):
            logger.warning(f"Config at {config_path}: {field_name}[{i}] must be a dict")
            return False
        if "name" not in cmd:
            logger.warning(f"Config at {config_path}: {field_name}[{i}] missing 'name'")
            return False
        if not isinstance(cmd["name"], str) or cmd["name"].strip() == "":
            logger.warning(f"Config at {config_path}: {field_name}[{i}] has invalid 'name'")
            return False
    return True


def _validate_pkill_processes(config: dict, config_path: Path) -> Optional[list[str]]:
    """
    Validate and normalize pkill_processes from a YAML config.

    Each entry must be a non-empty string matching VALID_PROCESS_NAME_PATTERN
    (alphanumeric, dots, underscores, hyphens only -- no regex metacharacters).
    Used by both load_org_config() and load_project_commands().

    Args:
        config: Parsed YAML config dict that may contain 'pkill_processes'
        config_path: Path to the config file (for log messages)

    Returns:
        Normalized list of process names, or None if validation fails.
        Returns an empty list if 'pkill_processes' is not present.
    """
    if "pkill_processes" not in config:
        return []

    processes = config["pkill_processes"]
    if not isinstance(processes, list):
        logger.warning(f"Config at {config_path}: 'pkill_processes' must be a list")
        return None

    normalized = []
    for i, proc in enumerate(processes):
        if not isinstance(proc, str):
            logger.warning(f"Config at {config_path}: pkill_processes[{i}] must be a string")
            return None
        proc = proc.strip()
        if not proc or not VALID_PROCESS_NAME_PATTERN.fullmatch(proc):
            logger.warning(f"Config at {config_path}: pkill_processes[{i}] has invalid value '{proc}'")
            return None
        normalized.append(proc)
    return normalized


def get_org_config_path() -> Path:
    """
    Get the organization-level config file path.

    Returns:
        Path to ~/.autoforge/config.yaml (falls back to ~/.autocoder/config.yaml)
    """
    new_path = Path.home() / ".autoforge" / "config.yaml"
    if new_path.exists():
        return new_path
    # Backward compatibility: check old location
    old_path = Path.home() / ".autocoder" / "config.yaml"
    if old_path.exists():
        return old_path
    return new_path


def load_org_config() -> Optional[dict]:
    """
    Load organization-level config from ~/.autoforge/config.yaml.

    Falls back to ~/.autocoder/config.yaml for backward compatibility.

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
            logger.warning(f"Org config at {config_path} is empty")
            return None

        # Validate structure
        if not isinstance(config, dict):
            logger.warning(f"Org config at {config_path} must be a YAML dictionary")
            return None

        if "version" not in config:
            logger.warning(f"Org config at {config_path} missing required 'version' field")
            return None

        # Validate allowed_commands if present
        if "allowed_commands" in config:
            if not _validate_command_list(config["allowed_commands"], config_path, "allowed_commands"):
                return None

        # Validate blocked_commands if present
        if "blocked_commands" in config:
            blocked = config["blocked_commands"]
            if not isinstance(blocked, list):
                logger.warning(f"Org config at {config_path}: 'blocked_commands' must be a list")
                return None
            for i, cmd in enumerate(blocked):
                if not isinstance(cmd, str):
                    logger.warning(f"Org config at {config_path}: blocked_commands[{i}] must be a string")
                    return None

        # Validate pkill_processes if present
        normalized = _validate_pkill_processes(config, config_path)
        if normalized is None:
            return None
        if normalized:
            config["pkill_processes"] = normalized

        return config

    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse org config at {config_path}: {e}")
        return None
    except (IOError, OSError) as e:
        logger.warning(f"Failed to read org config at {config_path}: {e}")
        return None


def load_project_commands(project_dir: Path) -> Optional[dict]:
    """
    Load allowed commands from project-specific YAML config.

    Args:
        project_dir: Path to the project directory

    Returns:
        Dict with parsed YAML config, or None if file doesn't exist or is invalid
    """
    # Check new location first, fall back to old for backward compatibility
    config_path = project_dir.resolve() / ".autoforge" / "allowed_commands.yaml"
    if not config_path.exists():
        config_path = project_dir.resolve() / ".autocoder" / "allowed_commands.yaml"

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            logger.warning(f"Project config at {config_path} is empty")
            return None

        # Validate structure
        if not isinstance(config, dict):
            logger.warning(f"Project config at {config_path} must be a YAML dictionary")
            return None

        if "version" not in config:
            logger.warning(f"Project config at {config_path} missing required 'version' field")
            return None

        commands = config.get("commands", [])

        # Enforce 100 command limit
        if isinstance(commands, list) and len(commands) > 100:
            logger.warning(f"Project config at {config_path} exceeds 100 command limit ({len(commands)} commands)")
            return None

        # Validate each command entry using shared helper
        if not _validate_command_list(commands, config_path, "commands"):
            return None

        # Validate pkill_processes if present
        normalized = _validate_pkill_processes(config, config_path)
        if normalized is None:
            return None
        if normalized:
            config["pkill_processes"] = normalized

        return config

    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse project config at {config_path}: {e}")
        return None
    except (IOError, OSError) as e:
        logger.warning(f"Failed to read project config at {config_path}: {e}")
        return None


def validate_project_command(cmd_config: dict) -> tuple[bool, str]:
    """
    Validate a single command entry from project config.

    Checks that the command has a valid name and is not in any blocklist.
    Called during hierarchy resolution to gate each project command before
    it is added to the effective allowed set.

    Args:
        cmd_config: Dict with command configuration (name, description)

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


def get_effective_pkill_processes(project_dir: Optional[Path]) -> set[str]:
    """
    Get effective pkill process names after hierarchy resolution.

    Merges processes from:
    1. DEFAULT_PKILL_PROCESSES (hardcoded baseline)
    2. Org config pkill_processes
    3. Project config pkill_processes

    Args:
        project_dir: Path to the project directory, or None

    Returns:
        Set of allowed process names for pkill
    """
    # Start with default processes
    processes = DEFAULT_PKILL_PROCESSES.copy()

    # Add org-level pkill_processes
    org_config = load_org_config()
    if org_config:
        org_processes = org_config.get("pkill_processes", [])
        if isinstance(org_processes, list):
            processes |= {p for p in org_processes if isinstance(p, str) and p.strip()}

    # Add project-level pkill_processes
    if project_dir:
        project_config = load_project_commands(project_dir)
        if project_config:
            proj_processes = project_config.get("pkill_processes", [])
            if isinstance(proj_processes, list):
                processes |= {p for p in proj_processes if isinstance(p, str) and p.strip()}

    return processes


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

    # Get effective pkill processes (includes org/project config)
    pkill_processes = get_effective_pkill_processes(project_dir)

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
            error_msg += "  1. Add to .autoforge/allowed_commands.yaml for this project, OR\n"
            error_msg += "  2. Request mid-session approval (the agent can ask)\n"
            error_msg += "Note: Some commands are blocked at org-level and cannot be overridden."
            return {
                "decision": "block",
                "reason": error_msg,
            }

        # Additional validation for sensitive commands
        if cmd in COMMANDS_NEEDING_EXTRA_VALIDATION:
            # Find the specific segment containing this command by searching
            # each segment's extracted commands for a match
            cmd_segment = ""
            for segment in segments:
                if cmd in extract_commands(segment):
                    cmd_segment = segment
                    break
            if not cmd_segment:
                cmd_segment = command  # Fallback to full command

            if cmd == "pkill":
                # Pass configured extra processes (beyond defaults)
                extra_procs = pkill_processes - DEFAULT_PKILL_PROCESSES
                allowed, reason = validate_pkill_command(cmd_segment, extra_procs if extra_procs else None)
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
            elif cmd == "playwright-cli":
                allowed, reason = validate_playwright_command(cmd_segment)
                if not allowed:
                    return {"decision": "block", "reason": reason}

    return {}
