"""
Models Router
=============

API endpoints for model configuration and profiles.
"""

import sys
from pathlib import Path

from fastapi import APIRouter

# Add parent directory to path to import modules
root_dir = Path(__file__).parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from agent_types import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL_ID,
    DEFAULT_PROFILE_NAME,
    list_models,
    list_profiles,
)

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def get_models():
    """
    Get all available models with their configurations.

    Returns:
        List of model configurations with tiers and default model.
    """
    # Group models by tier
    tiers: dict[str, list[str]] = {"opus": [], "sonnet": [], "haiku": []}
    for model in AVAILABLE_MODELS:
        tier = model.tier.value
        if tier in tiers:
            tiers[tier].append(model.id)

    return {
        "models": list_models(),
        "tiers": tiers,
        "defaultModel": DEFAULT_MODEL_ID,
    }


@router.get("/profiles")
async def get_profiles():
    """
    Get all predefined model profiles.

    Returns:
        List of profiles with default profile name.
    """
    return {
        "profiles": list_profiles(),
        "defaultProfile": DEFAULT_PROFILE_NAME,
    }


@router.get("/{model_id}")
async def get_model(model_id: str):
    """
    Get a specific model configuration.

    Args:
        model_id: The model identifier.

    Returns:
        Model configuration or 404 if not found.
    """
    from fastapi import HTTPException

    from agent_types import get_model

    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    return model.to_dict()


@router.get("/profiles/{profile_name}")
async def get_profile(profile_name: str):
    """
    Get a specific model profile.

    Args:
        profile_name: The profile name.

    Returns:
        Profile configuration or 404 if not found.
    """
    from fastapi import HTTPException

    from agent_types import get_profile

    profile = get_profile(profile_name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_name}")

    return profile.to_dict()
