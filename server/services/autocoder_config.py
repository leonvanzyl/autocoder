"""
Autocoder Enhanced Configuration
================================

Centralized configuration system for all Autocoder features.
Extends the basic project_config.py with support for:
- Quality Gates
- Git Workflow
- Error Recovery
- CI/CD Integration
- Import Settings
- Completion Settings

Configuration is stored in {project_dir}/.autocoder/config.json.
"""

import copy
import json
import logging
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions for Configuration Schema
# =============================================================================


class QualityChecksConfig(TypedDict, total=False):
    """Configuration for individual quality checks."""
    lint: bool
    type_check: bool
    unit_tests: bool
    custom_script: str | None


class QualityGatesConfig(TypedDict, total=False):
    """Configuration for quality gates feature."""
    enabled: bool
    strict_mode: bool
    checks: QualityChecksConfig


class GitWorkflowConfig(TypedDict, total=False):
    """Configuration for git workflow feature."""
    mode: str  # "feature_branches" | "trunk" | "none"
    branch_prefix: str
    auto_merge: bool


class ErrorRecoveryConfig(TypedDict, total=False):
    """Configuration for error recovery feature."""
    max_retries: int
    skip_threshold: int
    escalate_threshold: int
    auto_clear_on_startup: bool


class CompletionConfig(TypedDict, total=False):
    """Configuration for completion behavior."""
    auto_stop_at_100: bool
    max_regression_cycles: int
    prompt_before_extra_cycles: bool


class EnvironmentConfig(TypedDict, total=False):
    """Configuration for a deployment environment."""
    url: str
    auto_deploy: bool


class CiCdConfig(TypedDict, total=False):
    """Configuration for CI/CD integration."""
    provider: str  # "github" | "gitlab" | "none"
    environments: dict[str, EnvironmentConfig]


class ImportConfig(TypedDict, total=False):
    """Configuration for project import feature."""
    default_feature_status: str  # "pending" | "passing"
    auto_detect_stack: bool


class SecurityScanningConfig(TypedDict, total=False):
    """Configuration for security scanning feature."""
    enabled: bool
    scan_dependencies: bool
    scan_secrets: bool
    scan_injection_patterns: bool
    fail_on_high_severity: bool


class LoggingConfig(TypedDict, total=False):
    """Configuration for enhanced logging feature."""
    enabled: bool
    level: str  # "debug" | "info" | "warn" | "error"
    structured_output: bool
    include_timestamps: bool
    max_log_file_size_mb: int


class AutocoderConfig(TypedDict, total=False):
    """Full Autocoder configuration schema."""
    version: str
    dev_command: str | None
    quality_gates: QualityGatesConfig
    git_workflow: GitWorkflowConfig
    error_recovery: ErrorRecoveryConfig
    completion: CompletionConfig
    ci_cd: CiCdConfig
    import_settings: ImportConfig
    security_scanning: SecurityScanningConfig
    logging: LoggingConfig


# =============================================================================
# Default Configuration Values
# =============================================================================


DEFAULT_CONFIG: AutocoderConfig = {
    "version": "1.0",
    "dev_command": None,
    "quality_gates": {
        "enabled": True,
        "strict_mode": True,
        "checks": {
            "lint": True,
            "type_check": True,
            "unit_tests": False,
            "custom_script": None,
        },
    },
    "git_workflow": {
        "mode": "none",
        "branch_prefix": "feature/",
        "auto_merge": False,
    },
    "error_recovery": {
        "max_retries": 3,
        "skip_threshold": 5,
        "escalate_threshold": 7,
        "auto_clear_on_startup": True,
    },
    "completion": {
        "auto_stop_at_100": True,
        "max_regression_cycles": 3,
        "prompt_before_extra_cycles": False,
    },
    "ci_cd": {
        "provider": "none",
        "environments": {},
    },
    "import_settings": {
        "default_feature_status": "pending",
        "auto_detect_stack": True,
    },
    "security_scanning": {
        "enabled": True,
        "scan_dependencies": True,
        "scan_secrets": True,
        "scan_injection_patterns": True,
        "fail_on_high_severity": False,
    },
    "logging": {
        "enabled": True,
        "level": "info",
        "structured_output": True,
        "include_timestamps": True,
        "max_log_file_size_mb": 10,
    },
}


# =============================================================================
# Configuration Loading and Saving
# =============================================================================


def _get_config_path(project_dir: Path) -> Path:
    """Get the path to the project config file."""
    return project_dir / ".autocoder" / "config.json"


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries.

    Values from override take precedence over base.
    Nested dicts are merged recursively.

    Args:
        base: Base dictionary with default values
        override: Dictionary with override values

    Returns:
        Merged dictionary
    """
    # Use deepcopy to prevent mutation of base dict's nested structures
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_autocoder_config(project_dir: Path) -> AutocoderConfig:
    """
    Load the full Autocoder configuration with defaults.

    Reads from .autocoder/config.json and merges with defaults.
    If the config file doesn't exist or is invalid, returns defaults.

    Args:
        project_dir: Path to the project directory

    Returns:
        Full configuration with all sections populated
    """
    config_path = _get_config_path(project_dir)

    if not config_path.exists():
        logger.debug("No config file found at %s, using defaults", config_path)
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)

        if not isinstance(user_config, dict):
            logger.warning(
                "Invalid config format in %s: expected dict, got %s",
                config_path, type(user_config).__name__
            )
            return copy.deepcopy(DEFAULT_CONFIG)

        # Merge user config with defaults
        merged = _deep_merge(DEFAULT_CONFIG, user_config)
        return merged

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse config at %s: %s", config_path, e)
        return copy.deepcopy(DEFAULT_CONFIG)
    except OSError as e:
        logger.warning("Failed to read config at %s: %s", config_path, e)
        return copy.deepcopy(DEFAULT_CONFIG)


def save_autocoder_config(project_dir: Path, config: AutocoderConfig) -> None:
    """
    Save the Autocoder configuration to disk.

    Creates the .autocoder directory if it doesn't exist.

    Args:
        project_dir: Path to the project directory
        config: Configuration to save

    Raises:
        OSError: If the file cannot be written
    """
    config_path = _get_config_path(project_dir)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.debug("Saved config to %s", config_path)
    except OSError as e:
        logger.error("Failed to save config to %s: %s", config_path, e)
        raise


def update_autocoder_config(project_dir: Path, updates: dict[str, Any]) -> AutocoderConfig:
    """
    Update specific configuration values.

    Loads current config, applies updates, and saves.

    Args:
        project_dir: Path to the project directory
        updates: Dictionary with values to update (can be nested)

    Returns:
        Updated configuration
    """
    config = load_autocoder_config(project_dir)
    merged = _deep_merge(config, updates)
    save_autocoder_config(project_dir, merged)
    return merged


# =============================================================================
# Convenience Getters for Specific Sections
# =============================================================================


def get_quality_gates_config(project_dir: Path) -> QualityGatesConfig:
    """Get quality gates configuration for a project."""
    config = load_autocoder_config(project_dir)
    return config.get("quality_gates", DEFAULT_CONFIG["quality_gates"])


def get_git_workflow_config(project_dir: Path) -> GitWorkflowConfig:
    """Get git workflow configuration for a project."""
    config = load_autocoder_config(project_dir)
    return config.get("git_workflow", DEFAULT_CONFIG["git_workflow"])


def get_error_recovery_config(project_dir: Path) -> ErrorRecoveryConfig:
    """Get error recovery configuration for a project."""
    config = load_autocoder_config(project_dir)
    return config.get("error_recovery", DEFAULT_CONFIG["error_recovery"])


def get_completion_config(project_dir: Path) -> CompletionConfig:
    """Get completion configuration for a project."""
    config = load_autocoder_config(project_dir)
    return config.get("completion", DEFAULT_CONFIG["completion"])


def get_security_scanning_config(project_dir: Path) -> SecurityScanningConfig:
    """Get security scanning configuration for a project."""
    config = load_autocoder_config(project_dir)
    return config.get("security_scanning", DEFAULT_CONFIG["security_scanning"])


def get_logging_config(project_dir: Path) -> LoggingConfig:
    """Get logging configuration for a project."""
    config = load_autocoder_config(project_dir)
    return config.get("logging", DEFAULT_CONFIG["logging"])


# =============================================================================
# Feature Enable/Disable Checks
# =============================================================================


def is_quality_gates_enabled(project_dir: Path) -> bool:
    """Check if quality gates are enabled for a project."""
    config = get_quality_gates_config(project_dir)
    return config.get("enabled", True)


def is_strict_quality_mode(project_dir: Path) -> bool:
    """Check if strict quality mode is enabled (blocks feature_mark_passing on failure)."""
    config = get_quality_gates_config(project_dir)
    return config.get("enabled", True) and config.get("strict_mode", True)


def is_security_scanning_enabled(project_dir: Path) -> bool:
    """Check if security scanning is enabled for a project."""
    config = get_security_scanning_config(project_dir)
    return config.get("enabled", True)


def is_auto_clear_on_startup_enabled(project_dir: Path) -> bool:
    """Check if auto-clear stuck features on startup is enabled."""
    config = get_error_recovery_config(project_dir)
    return config.get("auto_clear_on_startup", True)


def is_auto_stop_at_100_enabled(project_dir: Path) -> bool:
    """Check if agent should auto-stop when all features pass."""
    config = get_completion_config(project_dir)
    return config.get("auto_stop_at_100", True)


def get_git_workflow_mode(project_dir: Path) -> str:
    """Get the git workflow mode for a project."""
    config = get_git_workflow_config(project_dir)
    return config.get("mode", "none")
