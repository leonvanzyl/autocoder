"""
Agent Types Module
==================

Defines model configurations, agent types, and model profiles for the
autonomous coding agent system.

This module provides:
- ModelConfig: Configuration for individual AI models
- AgentType: Enum of different agent roles (initializer, coder, tester)
- ModelProfile: Predefined model configurations for different use cases
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelTier(str, Enum):
    """Model capability tiers."""
    OPUS = "opus"       # Highest capability, best for complex reasoning
    SONNET = "sonnet"   # Balanced capability and speed
    HAIKU = "haiku"     # Fast, efficient for simpler tasks


class AgentType(str, Enum):
    """Types of agents in the system."""
    INITIALIZER = "initializer"  # Creates features from app spec
    CODER = "coder"              # Implements features
    TESTER = "tester"            # Runs tests and validation
    REVIEWER = "reviewer"        # Code review and quality checks
    PLANNER = "planner"          # Architecture and planning


@dataclass
class ModelConfig:
    """Configuration for an AI model."""
    id: str                          # Model identifier (e.g., "claude-opus-4-5-20251101")
    name: str                        # Display name (e.g., "Claude Opus 4.5")
    tier: ModelTier                  # Capability tier
    context_window: int = 200000     # Max context tokens
    max_output_tokens: int = 16384   # Max output tokens
    supports_vision: bool = True     # Can process images
    supports_extended_thinking: bool = False  # Extended thinking capability
    cost_per_1k_input: float = 0.0   # Cost per 1K input tokens (USD)
    cost_per_1k_output: float = 0.0  # Cost per 1K output tokens (USD)
    description: str = ""            # Model description

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "tier": self.tier.value,
            "contextWindow": self.context_window,
            "maxOutputTokens": self.max_output_tokens,
            "supportsVision": self.supports_vision,
            "supportsExtendedThinking": self.supports_extended_thinking,
            "costPer1kInput": self.cost_per_1k_input,
            "costPer1kOutput": self.cost_per_1k_output,
            "description": self.description,
        }


@dataclass
class ModelProfile:
    """
    A profile defining which models to use for different agent types.

    Profiles allow users to configure model selection per task type,
    balancing cost, speed, and capability.
    """
    name: str                               # Profile name (e.g., "default", "budget", "premium")
    description: str                        # Profile description
    initializer_model: str                  # Model ID for initializer agent
    coder_model: str                        # Model ID for coding agent
    tester_model: str                       # Model ID for testing agent
    reviewer_model: str | None = None       # Model ID for reviewer (optional)
    planner_model: str | None = None        # Model ID for planner (optional)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_model_for_agent(self, agent_type: AgentType) -> str | None:
        """Get the model ID for a specific agent type."""
        mapping = {
            AgentType.INITIALIZER: self.initializer_model,
            AgentType.CODER: self.coder_model,
            AgentType.TESTER: self.tester_model,
            AgentType.REVIEWER: self.reviewer_model,
            AgentType.PLANNER: self.planner_model,
        }
        return mapping.get(agent_type)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "initializerModel": self.initializer_model,
            "coderModel": self.coder_model,
            "testerModel": self.tester_model,
            "reviewerModel": self.reviewer_model,
            "plannerModel": self.planner_model,
            "metadata": self.metadata,
        }


# =============================================================================
# Available Models (Single Source of Truth)
# =============================================================================

AVAILABLE_MODELS: list[ModelConfig] = [
    ModelConfig(
        id="claude-opus-4-5-20251101",
        name="Claude Opus 4.5",
        tier=ModelTier.OPUS,
        context_window=200000,
        max_output_tokens=16384,
        supports_vision=True,
        supports_extended_thinking=True,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        description="Most capable model, best for complex reasoning and coding tasks",
    ),
    ModelConfig(
        id="claude-sonnet-4-5-20250929",
        name="Claude Sonnet 4.5",
        tier=ModelTier.SONNET,
        context_window=200000,
        max_output_tokens=16384,
        supports_vision=True,
        supports_extended_thinking=True,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        description="Balanced performance and cost, great for most coding tasks",
    ),
    ModelConfig(
        id="claude-sonnet-4-20250514",
        name="Claude Sonnet 4",
        tier=ModelTier.SONNET,
        context_window=200000,
        max_output_tokens=16384,
        supports_vision=True,
        supports_extended_thinking=False,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        description="Previous generation Sonnet, reliable for standard tasks",
    ),
    ModelConfig(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        tier=ModelTier.SONNET,
        context_window=200000,
        max_output_tokens=8192,
        supports_vision=True,
        supports_extended_thinking=False,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        description="Claude 3.5 Sonnet, proven and stable",
    ),
    ModelConfig(
        id="claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        tier=ModelTier.HAIKU,
        context_window=200000,
        max_output_tokens=8192,
        supports_vision=True,
        supports_extended_thinking=False,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.004,
        description="Fast and efficient for simpler tasks and testing",
    ),
    ModelConfig(
        id="claude-3-haiku-20240307",
        name="Claude 3 Haiku",
        tier=ModelTier.HAIKU,
        context_window=200000,
        max_output_tokens=4096,
        supports_vision=True,
        supports_extended_thinking=False,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        description="Most cost-effective option for bulk operations",
    ),
]

# Index by model ID for quick lookup
MODELS_BY_ID: dict[str, ModelConfig] = {m.id: m for m in AVAILABLE_MODELS}

# List of valid model IDs
VALID_MODEL_IDS: list[str] = [m.id for m in AVAILABLE_MODELS]

# Default model
DEFAULT_MODEL_ID = "claude-opus-4-5-20251101"


# =============================================================================
# Predefined Model Profiles
# =============================================================================

PREDEFINED_PROFILES: list[ModelProfile] = [
    ModelProfile(
        name="default",
        description="Balanced profile using Opus for coding and Sonnet for testing",
        initializer_model="claude-opus-4-5-20251101",
        coder_model="claude-opus-4-5-20251101",
        tester_model="claude-sonnet-4-5-20250929",
        reviewer_model="claude-sonnet-4-5-20250929",
        planner_model="claude-opus-4-5-20251101",
    ),
    ModelProfile(
        name="premium",
        description="All Opus for maximum quality",
        initializer_model="claude-opus-4-5-20251101",
        coder_model="claude-opus-4-5-20251101",
        tester_model="claude-opus-4-5-20251101",
        reviewer_model="claude-opus-4-5-20251101",
        planner_model="claude-opus-4-5-20251101",
    ),
    ModelProfile(
        name="balanced",
        description="Sonnet for everything - good balance of cost and quality",
        initializer_model="claude-sonnet-4-5-20250929",
        coder_model="claude-sonnet-4-5-20250929",
        tester_model="claude-sonnet-4-5-20250929",
        reviewer_model="claude-sonnet-4-5-20250929",
        planner_model="claude-sonnet-4-5-20250929",
    ),
    ModelProfile(
        name="budget",
        description="Cost-effective using Haiku for testing",
        initializer_model="claude-sonnet-4-5-20250929",
        coder_model="claude-sonnet-4-5-20250929",
        tester_model="claude-3-5-haiku-20241022",
        reviewer_model="claude-3-5-haiku-20241022",
        planner_model="claude-sonnet-4-5-20250929",
    ),
    ModelProfile(
        name="economy",
        description="Maximum cost savings with older models",
        initializer_model="claude-3-5-sonnet-20241022",
        coder_model="claude-3-5-sonnet-20241022",
        tester_model="claude-3-haiku-20240307",
        reviewer_model="claude-3-haiku-20240307",
        planner_model="claude-3-5-sonnet-20241022",
    ),
]

# Index profiles by name
PROFILES_BY_NAME: dict[str, ModelProfile] = {p.name: p for p in PREDEFINED_PROFILES}

# Default profile
DEFAULT_PROFILE_NAME = "default"


def get_model(model_id: str) -> ModelConfig | None:
    """Get a model configuration by ID."""
    return MODELS_BY_ID.get(model_id)


def get_profile(profile_name: str) -> ModelProfile | None:
    """Get a model profile by name."""
    return PROFILES_BY_NAME.get(profile_name)


def get_default_model() -> ModelConfig:
    """Get the default model configuration."""
    return MODELS_BY_ID[DEFAULT_MODEL_ID]


def get_default_profile() -> ModelProfile:
    """Get the default model profile."""
    return PROFILES_BY_NAME[DEFAULT_PROFILE_NAME]


def list_models() -> list[dict[str, Any]]:
    """Get all available models as dictionaries."""
    return [m.to_dict() for m in AVAILABLE_MODELS]


def list_profiles() -> list[dict[str, Any]]:
    """Get all predefined profiles as dictionaries."""
    return [p.to_dict() for p in PREDEFINED_PROFILES]
