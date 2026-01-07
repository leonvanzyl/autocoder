"""
Model Selection Settings System
================================

Flexible configuration for AI model usage across the autonomous coding system.
Supports CLI, UI, and programmatic configuration.

Presets:
- quality: Opus for everything (maximum quality, highest cost)
- balanced: Opus + Haiku (recommended for Pro)
- economy: Opus critical + Sonnet standard + Haiku simple
- cheap: Sonnet + Haiku (skip Opus)
- experimental: All models with AI auto-selection

Usage:
    # CLI
    python agent.py --preset balanced
    python agent.py --models opus,haiku

    # UI
    Settings → Model Selection → Choose preset or custom

    # Programmatic
    from model_settings import ModelSettings
    settings = ModelSettings.load()
    settings.set_preset("balanced")
    model = settings.select_model(feature)
"""

import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Literal, Optional


class ModelPreset(str, Enum):
    """Predefined model configurations"""
    QUALITY = "quality"          # Opus only
    BALANCED = "balanced"        # Opus + Haiku (recommended)
    ECONOMY = "economy"          # Opus + Sonnet + Haiku
    CHEAP = "cheap"              # Sonnet + Haiku (no Opus)
    EXPERIMENTAL = "experimental" # All models with smart AI


ModelName = Literal["opus", "sonnet", "haiku"]
FeatureCategory = Literal["frontend", "backend", "database", "testing", "documentation", "infrastructure"]


@dataclass
class ModelMapping:
    """Model mapping for feature categories"""
    frontend: ModelName = "opus"
    backend: ModelName = "opus"
    database: ModelName = "opus"
    testing: ModelName = "haiku"
    documentation: ModelName = "haiku"
    infrastructure: ModelName = "opus"


@dataclass
class ModelSettings:
    """Configuration for model selection across the system"""

    # Available models (in order of preference)
    available_models: list[ModelName] = field(default_factory=lambda: ["opus", "haiku"])

    # Current preset
    preset: str = "balanced"

    # Per-category model mapping
    category_mapping: dict[FeatureCategory, ModelName] = field(default_factory=dict)

    # Fallback model if selection fails
    fallback_model: ModelName = "opus"

    # Auto-detect simple tasks for cheaper models
    auto_detect_simple: bool = True

    # Simple task keywords (trigger cheapest available model)
    simple_keywords: list[str] = field(default_factory=lambda: [
        "test", "testing", "unit test", "integration test",
        "documentation", "doc", "comment", "readme",
        "format", "lint", "style", "formatting",
        "simple", "basic", "crud", "read-only",
        "display", "show", "list", "get"
    ])

    # Complex task keywords (trigger best available model)
    complex_keywords: list[str] = field(default_factory=lambda: [
        "architecture", "scalability", "performance",
        "security", "authentication", "authorization", "payment",
        "integration", "api", "infrastructure",
        "complex", "difficult", "optimize", "refactor",
        "production", "critical", "error handling"
    ])

    def __post_init__(self):
        """Validate settings after initialization"""
        # Ensure available_models is subset of valid models
        valid_models = {"opus", "sonnet", "haiku"}
        self.available_models = [m for m in self.available_models if m in valid_models]

        if not self.available_models:
            self.available_models = ["opus"]  # Fallback

        # Set default category mapping if not provided
        if not self.category_mapping:
            self._apply_preset_mapping()

    def _apply_preset_mapping(self):
        """Apply category mapping based on current preset"""
        if self.preset == "quality":
            mapping = {cat: "opus" for cat in FeatureCategory.__args__}

        elif self.preset == "balanced":
            mapping = {
                "frontend": "opus",
                "backend": "opus",
                "database": "opus",
                "testing": "haiku",
                "documentation": "haiku",
                "infrastructure": "opus"
            }

        elif self.preset == "economy":
            mapping = {
                "frontend": "sonnet",
                "backend": "opus",
                "database": "opus",
                "testing": "haiku",
                "documentation": "haiku",
                "infrastructure": "sonnet"
            }

        elif self.preset == "cheap":
            mapping = {
                "frontend": "sonnet",
                "backend": "sonnet",
                "database": "sonnet",
                "testing": "haiku",
                "documentation": "haiku",
                "infrastructure": "sonnet"
            }

        else:  # experimental
            mapping = {cat: "opus" for cat in FeatureCategory.__args__}

        self.category_mapping = mapping

    def select_model(self, feature: dict) -> ModelName:
        """Select best model for a feature

        Args:
            feature: Feature dict with keys: category, description, name

        Returns:
            Model name (opus, sonnet, or haiku)
        """
        category = feature.get("category", "").lower()
        description = feature.get("description", "").lower()
        name = feature.get("name", "").lower()

        # 1. Check category mapping first (explicit override)
        if category in self.category_mapping:
            mapped_model = self.category_mapping[category]
            if mapped_model in self.available_models:
                return mapped_model

        # 2. Auto-detect simple tasks (if enabled)
        if self.auto_detect_simple:
            combined_text = f"{description} {name}"
            if any(keyword in combined_text for keyword in self.simple_keywords):
                # Return cheapest available model
                return self.available_models[-1]

        # 3. Auto-detect complex tasks
        if self.auto_detect_simple:
            combined_text = f"{description} {name}"
            if any(keyword in combined_text for keyword in self.complex_keywords):
                # Return best available model
                return self.available_models[0]

        # 4. Default to best available model
        return self.available_models[0]

    def set_preset(self, preset: str):
        """Apply a preset configuration

        Args:
            preset: One of 'quality', 'balanced', 'economy', 'cheap', 'experimental'
        """
        if preset not in [p.value for p in ModelPreset]:
            raise ValueError(f"Invalid preset: {preset}. Must be one of: {[p.value for p in ModelPreset]}")

        self.preset = preset

        # Update available models based on preset
        preset_configs = {
            "quality": ["opus"],
            "balanced": ["opus", "haiku"],
            "economy": ["opus", "sonnet", "haiku"],
            "cheap": ["sonnet", "haiku"],
            "experimental": ["opus", "sonnet", "haiku"]
        }

        self.available_models = preset_configs[preset]
        self._apply_preset_mapping()

    def set_custom_models(self, models: list[ModelName]):
        """Set custom model availability

        Args:
            models: List of model names (e.g., ["opus", "haiku"])
        """
        valid_models = {"opus", "sonnet", "haiku"}
        self.available_models = [m for m in models if m in valid_models]

        if not self.available_models:
            raise ValueError("At least one valid model must be specified")

        # Determine preset from custom configuration
        sorted_models = sorted(self.available_models,
                             key=lambda m: {"opus": 3, "sonnet": 2, "haiku": 1}[m],
                             reverse=True)

        if sorted_models == ["opus"]:
            self.preset = "quality"
        elif sorted_models == ["opus", "haiku"]:
            self.preset = "balanced"
        elif sorted_models == ["sonnet", "haiku"]:
            self.preset = "cheap"
        else:
            self.preset = "custom"

        self._apply_preset_mapping()

    def save(self, path: Optional[Path] = None):
        """Save settings to JSON file

        Args:
            path: Path to save settings (defaults to ~/.autocoder/model_settings.json)
        """
        if path is None:
            config_dir = Path.home() / ".autocoder"
            config_dir.mkdir(parents=True, exist_ok=True)
            path = config_dir / "model_settings.json"

        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'ModelSettings':
        """Load settings from JSON file

        Args:
            path: Path to load settings from (defaults to ~/.autocoder/model_settings.json)

        Returns:
            ModelSettings instance
        """
        if path is None:
            config_dir = Path.home() / ".autocoder"
            path = config_dir / "model_settings.json"

        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)
            return cls(**data)

        # Return default settings if file doesn't exist
        return cls()

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "preset": self.preset,
            "available_models": self.available_models,
            "category_mapping": self.category_mapping,
            "fallback_model": self.fallback_model,
            "auto_detect_simple": self.auto_detect_simple,
            "simple_keywords": self.simple_keywords,
            "complex_keywords": self.complex_keywords
        }


# Global settings instance
_global_settings: Optional[ModelSettings] = None


def get_settings() -> ModelSettings:
    """Get global model settings instance"""
    global _global_settings
    if _global_settings is None:
        _global_settings = ModelSettings.load()
    return _global_settings


def reset_settings():
    """Reset global settings to defaults"""
    global _global_settings
    _global_settings = None


# CLI argument parsing helpers
def parse_models_arg(models_arg: str) -> list[ModelName]:
    """Parse --models CLI argument

    Args:
        models_arg: Comma-separated model names (e.g., "opus,haiku")

    Returns:
        List of validated model names

    Examples:
        >>> parse_models_arg("opus,haiku")
        ["opus", "haiku"]
        >>> parse_models_arg("all")
        ["opus", "sonnet", "haiku"]
    """
    if models_arg.lower() == "all":
        return ["opus", "sonnet", "haiku"]

    models = [m.strip().lower() for m in models_arg.split(",")]
    valid_models = {"opus", "sonnet", "haiku"}

    validated = [m for m in models if m in valid_models]

    if not validated:
        raise ValueError(f"No valid models found in: {models_arg}")

    return validated


def get_preset_info() -> dict:
    """Get information about all presets"""
    return {
        "quality": {
            "name": "Quality (Opus Only)",
            "description": "Maximum quality, highest cost. Opus for everything.",
            "models": ["opus"],
            "best_for": "Critical production systems, complex architectures"
        },
        "balanced": {
            "name": "Balanced (Recommended for Pro)",
            "description": "Opus for features, Haiku for tests/docs. Best value.",
            "models": ["opus", "haiku"],
            "best_for": "Most Pro users, optimal quality/cost balance"
        },
        "economy": {
            "name": "Economy (Three-Tier)",
            "description": "Opus critical + Sonnet standard + Haiku simple",
            "models": ["opus", "sonnet", "haiku"],
            "best_for": "Cost optimization with quality where it matters"
        },
        "cheap": {
            "name": "Cheap (No Opus)",
            "description": "Sonnet for features, Haiku for tests/docs",
            "models": ["sonnet", "haiku"],
            "best_for": "Budget-conscious, non-critical projects"
        },
        "experimental": {
            "name": "Experimental (AI Selection)",
            "description": "All models with intelligent auto-selection",
            "models": ["opus", "sonnet", "haiku"],
            "best_for": "Testing and experimentation"
        }
    }


def get_full_model_id(model_name: ModelName) -> str:
    """Convert short model name to full Claude model ID

    Args:
        model_name: Short model name (opus, sonnet, or haiku)

    Returns:
        Full Claude model ID for use with Claude SDK

    Examples:
        >>> get_full_model_id("opus")
        "claude-opus-4-5-20251101"
        >>> get_full_model_id("sonnet")
        "claude-sonnet-4-5-20250929"
        >>> get_full_model_id("haiku")
        "claude-haiku-4-20250919"
    """
    model_ids = {
        "opus": "claude-opus-4-5-20251101",
        "sonnet": "claude-sonnet-4-5-20250929",
        "haiku": "claude-haiku-4-20250919"
    }
    return model_ids.get(model_name, model_ids["opus"])


if __name__ == "__main__":
    # Demo: Show preset information
    print("=== Model Selection Presets ===\n")
    for preset, info in get_preset_info().items():
        print(f"📦 {preset.upper()}")
        print(f"   Name: {info['name']}")
        print(f"   Description: {info['description']}")
        print(f"   Models: {', '.join(info['models'])}")
        print(f"   Best For: {info['best_for']}")
        print()

    # Demo: Test model selection
    print("\n=== Model Selection Examples ===\n")

    settings = ModelSettings()
    settings.set_preset("balanced")

    test_features = [
        {"category": "testing", "name": "Unit Tests", "description": "Add unit tests for user model"},
        {"category": "backend", "name": "Auth System", "description": "Implement JWT authentication"},
        {"category": "frontend", "name": "User List", "description": "Display list of users"},
        {"category": "database", "name": "Schema Design", "description": "Design database schema for scaling"},
    ]

    for feature in test_features:
        model = settings.select_model(feature)
        print(f"Feature: {feature['name']}")
        print(f"Category: {feature['category']}")
        print(f"Selected Model: {model.upper()}")
        print()
