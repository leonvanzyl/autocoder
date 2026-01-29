"""
Settings Module
===============

Hierarchical settings system for the Autocoder application.
Settings are resolved in order: project → app → built-in defaults.

This module provides:
- SettingsManager: Main class for reading/writing settings at all levels
- ProjectSettings: Settings specific to a project
- AppSettings: Application-wide settings
- Built-in defaults for all configuration options
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_types import DEFAULT_MODEL_ID, DEFAULT_PROFILE_NAME, VALID_MODEL_IDS

logger = logging.getLogger(__name__)


# =============================================================================
# Built-in Defaults
# =============================================================================

BUILT_IN_DEFAULTS: dict[str, Any] = {
    # Model settings
    "defaultModel": DEFAULT_MODEL_ID,
    "defaultProfile": DEFAULT_PROFILE_NAME,
    "coderModel": DEFAULT_MODEL_ID,
    "testerModel": "claude-sonnet-4-5-20250929",
    "initializerModel": DEFAULT_MODEL_ID,

    # Agent settings
    "maxConcurrency": 3,
    "yoloMode": False,
    "autoResume": True,
    "pauseOnError": True,

    # Testing settings
    "testingDirectory": "",  # Empty means use project directory
    "runRegressionTests": True,
    "testTimeout": 300,  # seconds

    # UI settings
    "theme": "system",
    "showDebugPanel": False,
    "celebrateOnComplete": True,

    # Git settings
    "autoCommit": False,
    "commitMessagePrefix": "[autocoder]",
    "createPullRequests": False,
}

# Settings that are project-specific only (not in app settings)
PROJECT_ONLY_SETTINGS = {
    "testingDirectory",
    "projectSpecificCommands",
}

# Settings file names
PROJECT_SETTINGS_FILE = ".autocoder/settings.json"
APP_SETTINGS_FILE = "settings.json"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ProjectSettings:
    """Settings specific to a project."""
    project_path: Path
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def settings_file(self) -> Path:
        """Path to the project settings file."""
        return self.project_path / PROJECT_SETTINGS_FILE

    def load(self) -> None:
        """Load settings from the project's settings file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
                logger.debug("Loaded project settings from %s", self.settings_file)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load project settings: %s", e)
                self.settings = {}
        else:
            self.settings = {}

    def save(self) -> None:
        """Save settings to the project's settings file."""
        # Ensure the .autocoder directory exists
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)
        logger.debug("Saved project settings to %s", self.settings_file)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        self.settings[key] = value

    def delete(self, key: str) -> bool:
        """Delete a setting. Returns True if deleted."""
        if key in self.settings:
            del self.settings[key]
            return True
        return False


@dataclass
class AppSettings:
    """Application-wide settings stored in ~/.autocoder/."""
    config_dir: Path = field(default_factory=lambda: Path.home() / ".autocoder")
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def settings_file(self) -> Path:
        """Path to the app settings file."""
        return self.config_dir / APP_SETTINGS_FILE

    def load(self) -> None:
        """Load settings from the app settings file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
                logger.debug("Loaded app settings from %s", self.settings_file)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load app settings: %s", e)
                self.settings = {}
        else:
            self.settings = {}

    def save(self) -> None:
        """Save settings to the app settings file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)
        logger.debug("Saved app settings to %s", self.settings_file)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        self.settings[key] = value

    def delete(self, key: str) -> bool:
        """Delete a setting. Returns True if deleted."""
        if key in self.settings:
            del self.settings[key]
            return True
        return False


# =============================================================================
# Settings Manager
# =============================================================================

class SettingsManager:
    """
    Manages hierarchical settings resolution.

    Settings are resolved in order:
    1. Project settings (highest priority)
    2. App settings
    3. Built-in defaults (lowest priority)
    """

    def __init__(self, project_path: Path | None = None):
        """
        Initialize the settings manager.

        Args:
            project_path: Optional path to a project for project-level settings.
        """
        self.app_settings = AppSettings()
        self.app_settings.load()

        self.project_settings: ProjectSettings | None = None
        if project_path:
            self.project_settings = ProjectSettings(project_path=Path(project_path))
            self.project_settings.load()

    def get(self, key: str) -> Any:
        """
        Get a setting value using hierarchical resolution.

        Resolution order: project → app → built-in default
        """
        # Check project settings first
        if self.project_settings and key in self.project_settings.settings:
            return self.project_settings.settings[key]

        # Check app settings
        if key in self.app_settings.settings:
            return self.app_settings.settings[key]

        # Return built-in default
        return BUILT_IN_DEFAULTS.get(key)

    def get_effective_settings(self) -> dict[str, Any]:
        """
        Get all effective settings with hierarchical resolution.

        Returns:
            Dictionary of all settings with their effective values.
        """
        effective = dict(BUILT_IN_DEFAULTS)

        # Apply app settings
        effective.update(self.app_settings.settings)

        # Apply project settings (highest priority)
        if self.project_settings:
            effective.update(self.project_settings.settings)

        return effective

    def set_project_setting(self, key: str, value: Any, save: bool = True) -> None:
        """
        Set a project-level setting.

        Args:
            key: Setting key
            value: Setting value
            save: Whether to save immediately (default True)
        """
        if not self.project_settings:
            raise ValueError("No project path configured")

        self.project_settings.set(key, value)
        if save:
            self.project_settings.save()

    def set_app_setting(self, key: str, value: Any, save: bool = True) -> None:
        """
        Set an app-level setting.

        Args:
            key: Setting key
            value: Setting value
            save: Whether to save immediately (default True)
        """
        # Don't allow project-only settings at app level
        if key in PROJECT_ONLY_SETTINGS:
            raise ValueError(f"Setting '{key}' is project-specific only")

        self.app_settings.set(key, value)
        if save:
            self.app_settings.save()

    def delete_project_setting(self, key: str, save: bool = True) -> bool:
        """
        Delete a project-level setting (fall back to app/default).

        Returns:
            True if deleted, False if not found
        """
        if not self.project_settings:
            return False

        deleted = self.project_settings.delete(key)
        if deleted and save:
            self.project_settings.save()
        return deleted

    def delete_app_setting(self, key: str, save: bool = True) -> bool:
        """
        Delete an app-level setting (fall back to default).

        Returns:
            True if deleted, False if not found
        """
        deleted = self.app_settings.delete(key)
        if deleted and save:
            self.app_settings.save()
        return deleted

    def get_setting_source(self, key: str) -> str:
        """
        Get the source of a setting's current value.

        Returns:
            "project", "app", or "default"
        """
        if self.project_settings and key in self.project_settings.settings:
            return "project"
        if key in self.app_settings.settings:
            return "app"
        return "default"

    def validate_model_setting(self, model_id: str) -> bool:
        """Check if a model ID is valid."""
        return model_id in VALID_MODEL_IDS

    def get_model_settings(self) -> dict[str, str]:
        """Get all model-related settings."""
        return {
            "defaultModel": self.get("defaultModel"),
            "coderModel": self.get("coderModel"),
            "testerModel": self.get("testerModel"),
            "initializerModel": self.get("initializerModel"),
            "defaultProfile": self.get("defaultProfile"),
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def get_app_settings() -> dict[str, Any]:
    """Get all app-level settings."""
    manager = SettingsManager()
    return manager.app_settings.settings


def get_project_settings(project_path: Path) -> dict[str, Any]:
    """Get all project-level settings."""
    settings = ProjectSettings(project_path=project_path)
    settings.load()
    return settings.settings


def get_effective_settings(project_path: Path | None = None) -> dict[str, Any]:
    """Get effective settings with hierarchical resolution."""
    manager = SettingsManager(project_path=project_path)
    return manager.get_effective_settings()


def get_testing_directory(project_path: Path) -> Path:
    """
    Get the testing directory for a project.

    Returns the configured testingDirectory if set and valid,
    otherwise returns the project directory itself.
    """
    manager = SettingsManager(project_path=project_path)
    testing_dir = manager.get("testingDirectory")

    if testing_dir:
        testing_path = Path(testing_dir)
        if testing_path.exists() and testing_path.is_dir():
            return testing_path

    return project_path


# Environment variable overrides
def get_env_override(key: str, default: Any = None) -> Any:
    """Get a setting from environment variable if set."""
    env_key = f"AUTOCODER_{key.upper()}"
    env_value = os.environ.get(env_key)
    if env_value is not None:
        # Try to parse as JSON for complex types
        try:
            return json.loads(env_value)
        except json.JSONDecodeError:
            return env_value
    return default
