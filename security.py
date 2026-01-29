"""
Security Hooks for Autonomous Coding Agent
==========================================

Pre-tool-use hooks that validate bash commands for security.
Uses an allowlist approach - only explicitly permitted commands can run.
"""

import hashlib
import logging
import os
import re
import shlex
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, cast

import yaml

# Logger for security-related events (fallback parsing, validation failures, etc.)
logger = logging.getLogger(__name__)


# =============================================================================
# DENIED COMMANDS TRACKING
# =============================================================================
# Track denied commands for visibility and debugging.
# Uses a thread-safe deque with a max size to prevent memory leaks.
# =============================================================================

MAX_DENIED_COMMANDS = 100  # Keep last 100 denied commands


@dataclass
class DeniedCommand:
    """Record of a denied command."""
    timestamp: str
    command: str
    reason: str
    project_dir: Optional[str] = None


# Thread-safe storage for denied commands
_denied_commands: deque[DeniedCommand] = deque(maxlen=MAX_DENIED_COMMANDS)
_denied_commands_lock = threading.Lock()


def record_denied_command(command: str, reason: str, project_dir: Optional[Path] = None) -> None:
    """
    Record a denied command for later review.

    Args:
        command: The command that was denied
        reason: The reason it was denied
        project_dir: Optional project directory context
    """
    denied = DeniedCommand(
        timestamp=datetime.now(timezone.utc).isoformat(),
        command=command,
        reason=reason,
        project_dir=str(project_dir) if project_dir else None,
    )
    with _denied_commands_lock:
        _denied_commands.append(denied)

    # Redact sensitive data before logging to prevent secret leakage
    # Use deterministic hash for identification without exposing content
    command_hash = hashlib.sha256(command.encode('utf-8')).hexdigest()[:16]
    reason_hash = hashlib.sha256(reason.encode('utf-8')).hexdigest()[:16]

    logger.info(
        f"[SECURITY] Command denied - hash: {command_hash}, "
        f"length: {len(command)} chars, reason hash: {reason_hash}, "
        f"reason length: {len(reason)} chars"
    )


def get_denied_commands(limit: int = 50) -> list[dict[str, Any]]:
    """
    Get the most recent denied commands.

    Args:
        limit: Maximum number of commands to return (default 50)

    Returns:
        List of denied command records (most recent first)
    """
    with _denied_commands_lock:
        # Convert to list and reverse for most-recent-first
        commands = list(_denied_commands)[-limit:]
        commands.reverse()

        def redact_string(s: str, max_preview: int = 20) -> str:
            if len(s) <= max_preview * 2:
                return s
            return f"{s[:max_preview]}...{s[-max_preview:]}"

        return [
            {
                "timestamp": cmd.timestamp,
                "command": redact_string(cmd.command),
                "reason": redact_string(cmd.reason),
                "project_dir": cmd.project_dir,
            }
            for cmd in commands
        ]


def clear_denied_commands() -> int:
    """
    Clear all recorded denied commands.

    Returns:
        Number of commands that were cleared
    """
    with _denied_commands_lock:
        count = len(_denied_commands)
        _denied_commands.clear()
    logger.info(f"[SECURITY] Cleared {count} denied command records")
    return count


# Regex pattern for valid pkill process names (no regex metacharacters allowed)
# Matches alphanumeric names with dots, underscores, and hyphens
VALID_PROCESS_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

# =============================================================================
# DANGEROUS SHELL PATTERNS - Command Injection Prevention
# =============================================================================
# These patterns detect SPECIFIC dangerous attack vectors.
#
# IMPORTANT: We intentionally DO NOT block general shell features like:
# - $() command substitution (used in: node $(npm bin)/jest)
# - `` backticks (used in: VERSION=`cat package.json | jq .version`)
# - source (used in: source venv/bin/activate)
# - export with $ (used in: export PATH=$PATH:/usr/local/bin)
#
# These are commonly used in legitimate programming workflows and the existing
# allowlist system already provides strong protection by only allowing specific
# commands. We only block patterns that are ALMOST ALWAYS malicious.
# =============================================================================

DANGEROUS_SHELL_PATTERNS = [
    # Network download piped directly to shell interpreter
    # These are almost always malicious - legitimate use cases would save to file first
    (re.compile(r'curl\s+[^|]*\|\s*(?:ba)?sh', re.IGNORECASE), "curl piped to shell"),
    (re.compile(r'wget\s+[^|]*\|\s*(?:ba)?sh', re.IGNORECASE), "wget piped to shell"),
    (re.compile(r'curl\s+[^|]*\|\s*python', re.IGNORECASE), "curl piped to python"),
    (re.compile(r'wget\s+[^|]*\|\s*python', re.IGNORECASE), "wget piped to python"),
    (re.compile(r'curl\s+[^|]*\|\s*perl', re.IGNORECASE), "curl piped to perl"),
    (re.compile(r'wget\s+[^|]*\|\s*perl', re.IGNORECASE), "wget piped to perl"),
    (re.compile(r'curl\s+[^|]*\|\s*ruby', re.IGNORECASE), "curl piped to ruby"),
    (re.compile(r'wget\s+[^|]*\|\s*ruby', re.IGNORECASE), "wget piped to ruby"),

    # Null byte injection (can terminate strings early in C-based parsers)
    (re.compile(r'\\x00|\x00'), "null byte injection (hex or raw)"),
]


def pre_validate_command_safety(command: str) -> tuple[bool, str]:
    """
    Pre-validate a command string for dangerous shell patterns.

    This check runs BEFORE the allowlist check and blocks patterns that are
    almost always malicious (e.g., curl piped directly to shell).

    This function intentionally allows common shell features like $(), ``,
    source, and export because they are needed for legitimate programming
    workflows. The allowlist system provides the primary security layer.

    Args:
        command: The raw command string to validate

    Returns:
        Tuple of (is_safe, error_message). If is_safe is False, error_message
        describes the dangerous pattern that was detected.
    """
    if not command:
        return True, ""

    for pattern, description in DANGEROUS_SHELL_PATTERNS:
        if pattern.search(command):
            return False, f"Dangerous shell pattern detected: {description}"

    return True, ""

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
    # Note: docker-compose removed - commonly needed for local dev environments
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
    result: list[str] = []
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
    commands: list[str] = []

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
            # Security: Only use fallback if segment contains no chaining operators
            # This prevents allowlist bypass via malformed commands hiding chained operators
            if re.search(r'\|\||&&|\||&', segment):
                # Segment has operators but shlex failed - refuse to parse for safety
                continue

            # Try fallback extraction for single-command segments
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
    args: list[str] = []
    for token in tokens[1:]:
        if not token.startswith("-"):
            args.append(token)

    if not args:
        return False, "pkill requires a process name"

    # Validate every non-flag argument (pkill accepts multiple patterns on BSD)
    # This defensively ensures no disallowed process can be targeted
    targets: list[str] = []
    for arg in args:
        # For -f flag (full command line match), take the first word as process name
        # e.g., "pkill -f 'node server.js'" -> target is "node server.js", process is "node"
        t: str = arg.split()[0] if " " in arg else arg
        targets.append(t)

    disallowed: list[str] = [t for t in targets if t not in allowed_process_names]
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
    files: list[str] = []

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


def load_org_config() -> Optional[dict[str, Any]]:
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
            allowed_raw = cast(Any, config["allowed_commands"])
            if not isinstance(allowed_raw, list):
                logger.warning(f"Org config at {config_path}: 'allowed_commands' must be a list")
                return None
            allowed = cast(list[dict[str, Any]], allowed_raw)
            for i, cmd in enumerate(allowed):
                if not isinstance(cmd, dict):
                    logger.warning(f"Org config at {config_path}: allowed_commands[{i}] must be a dict")
                    return None
                if "name" not in cmd:
                    logger.warning(f"Org config at {config_path}: allowed_commands[{i}] missing 'name'")
                    return None
                # Validate that name is a non-empty string
                if not isinstance(cmd["name"], str) or cmd["name"].strip() == "":
                    logger.warning(f"Org config at {config_path}: allowed_commands[{i}] has invalid 'name'")
                    return None

        # Validate blocked_commands if present
        if "blocked_commands" in config:
            blocked_raw = cast(Any, config["blocked_commands"])
            if not isinstance(blocked_raw, list):
                logger.warning(f"Org config at {config_path}: 'blocked_commands' must be a list")
                return None
            blocked = cast(list[str], blocked_raw)
            for i, cmd in enumerate(blocked):
                if not isinstance(cmd, str):
                    logger.warning(f"Org config at {config_path}: blocked_commands[{i}] must be a string")
                    return None

        # Validate pkill_processes if present
        if "pkill_processes" in config:
            processes_raw = cast(Any, config["pkill_processes"])
            if not isinstance(processes_raw, list):
                logger.warning(f"Org config at {config_path}: 'pkill_processes' must be a list")
                return None
            processes = cast(list[Any], processes_raw)
            # Normalize and validate each process name against safe pattern
            normalized: list[str] = []
            for i, proc in enumerate(processes):
                if not isinstance(proc, str):
                    logger.warning(f"Org config at {config_path}: pkill_processes[{i}] must be a string")
                    return None
                proc = proc.strip()
                # Block empty strings and regex metacharacters
                if not proc or not VALID_PROCESS_NAME_PATTERN.fullmatch(proc):
                    logger.warning(f"Org config at {config_path}: pkill_processes[{i}] has invalid value '{proc}'")
                    return None
                normalized.append(proc)
            config["pkill_processes"] = normalized

        return cast(dict[str, Any], config)

    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse org config at {config_path}: {e}")
        return None
    except (IOError, OSError) as e:
        logger.warning(f"Failed to read org config at {config_path}: {e}")
        return None


def load_project_commands(project_dir: Path) -> Optional[dict[str, Any]]:
    """
    Load allowed commands from project-specific YAML config.

    Args:
        project_dir: Path to the project directory

    Returns:
        Dict with parsed YAML config, or None if file doesn't exist or is invalid
    """
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

        commands_raw = cast(Any, config["commands"] if "commands" in config else [])
        if not isinstance(commands_raw, list):
            logger.warning(f"Project config at {config_path}: 'commands' must be a list")
            return None
        commands = cast(list[dict[str, Any]], commands_raw)

        # Enforce 100 command limit
        if len(commands) > 100:
            logger.warning(f"Project config at {config_path} exceeds 100 command limit ({len(commands)} commands)")
            return None

        # Validate each command entry
        for i, cmd in enumerate(commands):
            if not isinstance(cmd, dict):
                logger.warning(f"Project config at {config_path}: commands[{i}] must be a dict")
                return None
            if "name" not in cmd:
                logger.warning(f"Project config at {config_path}: commands[{i}] missing 'name'")
                return None
            # Validate name is a non-empty string
            if not isinstance(cmd["name"], str) or cmd["name"].strip() == "":
                logger.warning(f"Project config at {config_path}: commands[{i}] has invalid 'name'")
                return None

        # Validate pkill_processes if present
        if "pkill_processes" in config:
            processes_raw = cast(Any, config["pkill_processes"])
            if not isinstance(processes_raw, list):
                logger.warning(f"Project config at {config_path}: 'pkill_processes' must be a list")
                return None
            processes = cast(list[Any], processes_raw)
            # Normalize and validate each process name against safe pattern
            normalized: list[str] = []
            for i, proc in enumerate(processes):
                if not isinstance(proc, str):
                    logger.warning(f"Project config at {config_path}: pkill_processes[{i}] must be a string")
                    return None
                proc = proc.strip()
                # Block empty strings and regex metacharacters
                if not proc or not VALID_PROCESS_NAME_PATTERN.fullmatch(proc):
                    logger.warning(f"Project config at {config_path}: pkill_processes[{i}] has invalid value '{proc}'")
                    return None
                normalized.append(proc)
            config["pkill_processes"] = normalized

        return cast(dict[str, Any], config)

    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse project config at {config_path}: {e}")
        return None
    except (IOError, OSError) as e:
        logger.warning(f"Failed to read project config at {config_path}: {e}")
        return None


def validate_project_command(cmd_config: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate a single command entry from project config.

    Args:
        cmd_config: Dict with command configuration (name, description, args)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(cmd_config, dict):  # type: ignore[misc]
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
        args_raw = cmd_config["args"]
        if not isinstance(args_raw, list):
            return False, "Args must be a list"
        args = cast(list[str], args_raw)
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
        org_blocked: Any = org_config.get("blocked_commands", [])
        blocked |= set(org_blocked)

        # Add org-level allowed commands
        for cmd_config in org_config.get("allowed_commands", []):
            if isinstance(cmd_config, dict) and "name" in cmd_config:
                allowed.add(cast(str, cmd_config["name"]))

    # Load project config and apply
    if project_dir:
        project_config = load_project_commands(project_dir)
        if project_config:
            # Add project-specific commands
            for cmd_config in project_config.get("commands", []):
                valid, error = validate_project_command(cmd_config)
                if valid:
                    allowed.add(cast(str, cmd_config["name"]))
                else:
                    # Log validation error for debugging
                    logger.debug(f"Project command validation failed: {error}")

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
    allowed, _blocked = get_effective_commands(project_dir)
    # _blocked is used in get_effective_commands for precedence logic
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
        org_processes_raw = org_config.get("pkill_processes", [])
        if isinstance(org_processes_raw, list):
            org_processes = cast(list[Any], org_processes_raw)
            processes |= {p for p in org_processes if isinstance(p, str) and p.strip()}

    # Add project-level pkill_processes
    if project_dir:
        project_config = load_project_commands(project_dir)
        if project_config:
            proj_processes_raw = project_config.get("pkill_processes", [])
            if isinstance(proj_processes_raw, list):
                proj_processes = cast(list[Any], proj_processes_raw)
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


async def bash_security_hook(
    input_data: dict[str, Any],
    tool_use_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Pre-tool-use hook that validates bash commands using an allowlist.

    Only commands in ALLOWED_COMMANDS and project-specific commands are permitted.

    Security layers (in order):
    1. Pre-validation: Block dangerous shell patterns (command substitution, etc.)
    2. Command extraction: Parse command into individual command names
    3. Blocklist check: Reject hardcoded dangerous commands
    4. Allowlist check: Only permit explicitly allowed commands
    5. Extra validation: Additional checks for sensitive commands (pkill, chmod)

    Args:
        input_data: Dict containing tool_name and tool_input
        tool_use_id: Optional tool use ID
        context: Optional context dict with 'project_dir' key

    Returns:
        Empty dict to allow, or {"decision": "block", "reason": "..."} to block
    """
    if input_data.get("tool_name") != "Bash":
        return {}

    command_raw: Any = input_data.get("tool_input", {}).get("command", "")
    command = str(command_raw) if command_raw else ""
    if not command:
        return {}

    # Get project directory from context early (needed for denied command recording)
    project_dir = None
    if context and isinstance(context, dict):  # type: ignore[misc]
        project_dir_str: Any = context.get("project_dir")
        if project_dir_str and isinstance(project_dir_str, str):
            project_dir = Path(project_dir_str)

    # SECURITY LAYER 1: Pre-validate for dangerous shell patterns
    # This runs BEFORE parsing to catch injection attempts that exploit parser edge cases
    is_safe, error_msg = pre_validate_command_safety(command)
    if not is_safe:
        reason = f"Command blocked: {error_msg}\nThis pattern can be used for command injection and is not allowed."
        record_denied_command(command, reason, project_dir)
        return {
            "decision": "block",
            "reason": reason,
        }

    # SECURITY LAYER 2: Extract all commands from the command string
    commands = extract_commands(command)

    if not commands:
        # Could not parse - fail safe by blocking
        reason = f"Could not parse command for security validation: {command}"
        record_denied_command(command, reason, project_dir)
        return {
            "decision": "block",
            "reason": reason,
        }

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
            reason = f"Command '{cmd}' is blocked at organization level and cannot be approved."
            record_denied_command(command, reason, project_dir)
            return {
                "decision": "block",
                "reason": reason,
            }

        # Check allowlist (with pattern matching)
        if not is_command_allowed(cmd, allowed_commands):
            # Provide helpful error message with config hint
            reason = f"Command '{cmd}' is not allowed.\n"
            reason += "To allow this command:\n"
            reason += "  1. Add to .autocoder/allowed_commands.yaml for this project, OR\n"
            reason += "  2. Request mid-session approval (the agent can ask)\n"
            reason += "Note: Some commands are blocked at org-level and cannot be overridden."
            record_denied_command(command, reason, project_dir)
            return {
                "decision": "block",
                "reason": reason,
            }

        # Additional validation for sensitive commands
        if cmd in COMMANDS_NEEDING_EXTRA_VALIDATION:
            # Find the specific segment containing this command
            cmd_segment = get_command_for_validation(cmd, segments)
            if not cmd_segment:
                cmd_segment = command  # Fallback to full command

            if cmd == "pkill":
                # Pass configured extra processes (beyond defaults)
                extra_procs = pkill_processes - DEFAULT_PKILL_PROCESSES
                allowed, reason = validate_pkill_command(cmd_segment, extra_procs if extra_procs else None)
                if not allowed:
                    record_denied_command(command, reason, project_dir)
                    return {"decision": "block", "reason": reason}
            elif cmd == "chmod":
                allowed, reason = validate_chmod_command(cmd_segment)
                if not allowed:
                    record_denied_command(command, reason, project_dir)
                    return {"decision": "block", "reason": reason}
            elif cmd == "init.sh":
                allowed, reason = validate_init_script(cmd_segment)
                if not allowed:
                    record_denied_command(command, reason, project_dir)
                    return {"decision": "block", "reason": reason}

    return {}
