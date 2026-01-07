"""
Model Settings API Router
==========================

REST API endpoints for managing AI model selection settings.

Endpoints:
- GET /model-settings - Get current model settings
- PUT /model-settings - Update model settings
- POST /model-settings/preset - Apply a preset configuration
- GET /model-settings/presets - List available presets
"""

import os
from pathlib import Path
from typing import List, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autocoder.core.model_settings import ModelSettings, get_preset_info, parse_models_arg

router = APIRouter(prefix="/model-settings", tags=["model-settings"])


# Pydantic models for API
class ModelSettingsResponse(BaseModel):
    """Model settings response"""
    preset: str
    available_models: List[str]
    category_mapping: dict
    fallback_model: str
    auto_detect_simple: bool


class UpdateSettingsRequest(BaseModel):
    """Request to update model settings"""
    preset: str | None = Field(None, description="Preset name (quality, balanced, economy, cheap, experimental)")
    available_models: List[str] | None = Field(None, description="List of available models (opus, sonnet, haiku)")
    auto_detect_simple: bool | None = Field(None, description="Enable auto-detection of simple tasks")


class ApplyPresetRequest(BaseModel):
    """Request to apply a preset"""
    preset: str = Field(..., description="Preset name to apply")


class PresetInfo(BaseModel):
    """Information about a preset"""
    name: str
    description: str
    models: List[str]
    best_for: str


class PresetsResponse(BaseModel):
    """Response with all presets"""
    presets: dict[str, PresetInfo]


def get_global_settings() -> ModelSettings:
    """Get or create global model settings"""
    settings_file = Path.home() / ".autocoder" / "model_settings.json"
    return ModelSettings.load(settings_file) if settings_file.exists() else ModelSettings()


def save_global_settings(settings: ModelSettings):
    """Save global model settings"""
    settings_file = Path.home() / ".autocoder" / "model_settings.json"
    settings.save(settings_file)


@router.get("", response_model=ModelSettingsResponse)
async def get_model_settings():
    """Get current model settings

    Returns the current model selection configuration including preset,
    available models, and category mappings.
    """
    settings = get_global_settings()
    return ModelSettingsResponse(
        preset=settings.preset,
        available_models=settings.available_models,
        category_mapping=settings.category_mapping,
        fallback_model=settings.fallback_model,
        auto_detect_simple=settings.auto_detect_simple
    )


@router.put("")
async def update_model_settings(request: UpdateSettingsRequest):
    """Update model settings

    Update the model configuration. Can specify preset, available models,
    or auto-detect setting. Changes are persisted to disk.
    """
    settings = get_global_settings()

    # Update available models if provided
    if request.available_models is not None:
        try:
            settings.set_custom_models(request.available_models)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Update preset if provided
    elif request.preset is not None:
        try:
            settings.set_preset(request.preset)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Update auto-detect if provided
    if request.auto_detect_simple is not None:
        settings.auto_detect_simple = request.auto_detect_simple

    # Save settings
    save_global_settings(settings)

    return {
        "success": True,
        "settings": ModelSettingsResponse(
            preset=settings.preset,
            available_models=settings.available_models,
            category_mapping=settings.category_mapping,
            fallback_model=settings.fallback_model,
            auto_detect_simple=settings.auto_detect_simple
        )
    }


@router.post("/preset")
async def apply_preset(request: ApplyPresetRequest):
    """Apply a preset configuration

    Applies a predefined preset configuration (quality, balanced, economy, cheap, experimental).
    This resets all settings to the preset's defaults.
    """
    settings = get_global_settings()

    try:
        settings.set_preset(request.preset)
        save_global_settings(settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": f"Applied preset: {request.preset}",
        "settings": ModelSettingsResponse(
            preset=settings.preset,
            available_models=settings.available_models,
            category_mapping=settings.category_mapping,
            fallback_model=settings.fallback_model,
            auto_detect_simple=settings.auto_detect_simple
        )
    }


@router.get("/presets", response_model=PresetsResponse)
async def list_presets():
    """List all available presets

    Returns information about all available model selection presets
    including their names, descriptions, and best use cases.
    """
    presets_info = get_preset_info()

    return PresetsResponse(
        presets={
            preset: PresetInfo(
                name=info["name"],
                description=info["description"],
                models=info["models"],
                best_for=info["best_for"]
            )
            for preset, info in presets_info.items()
        }
    )


@router.post("/test")
async def test_model_selection(feature: dict):
    """Test model selection for a feature

    Given a feature (with category, description, name), returns which model
    would be selected based on current settings. Useful for previewing model selection.
    """
    settings = get_global_settings()
    selected_model = settings.select_model(feature)

    return {
        "feature": feature,
        "selected_model": selected_model,
        "settings": {
            "preset": settings.preset,
            "available_models": settings.available_models
        }
    }
