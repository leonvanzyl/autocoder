"""
Settings Router
===============

API endpoints for global settings management.
Settings are stored in the registry database and shared across all projects.
"""

import mimetypes
import sys

from fastapi import APIRouter

from ..schemas import (
    ModelInfo,
    ModelsResponse,
    ProviderInfo,
    ProvidersResponse,
    RoleModelAssignment,
    SettingsResponse,
    SettingsUpdate,
)
from ..services.chat_constants import ROOT_DIR

# Mimetype fix for Windows - must run before StaticFiles is mounted
mimetypes.add_type("text/javascript", ".js", True)

# Ensure root is on sys.path for registry import
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from registry import (
    API_PROVIDERS,
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    ROLE_MODEL_KEY_PREFIX,
    VALID_ROLES,
    get_all_role_models,
    get_all_settings,
    get_setting,
    set_setting,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _parse_yolo_mode(value: str | None) -> bool:
    """Parse YOLO mode string to boolean."""
    return (value or "false").lower() == "true"


@router.get("/providers", response_model=ProvidersResponse)
async def get_available_providers():
    """Get list of available API providers."""
    current = get_setting("api_provider", "claude") or "claude"
    providers = []
    for pid, pdata in API_PROVIDERS.items():
        providers.append(ProviderInfo(
            id=pid,
            name=pdata["name"],
            base_url=pdata.get("base_url"),
            models=[ModelInfo(id=m["id"], name=m["name"]) for m in pdata.get("models", [])],
            default_model=pdata.get("default_model", ""),
            requires_auth=pdata.get("requires_auth", False),
            tiers=pdata.get("tiers"),
        ))
    return ProvidersResponse(providers=providers, current=current)


@router.get("/models", response_model=ModelsResponse)
async def get_available_models():
    """Get list of available models.

    Returns models for the currently selected API provider.
    """
    current_provider = get_setting("api_provider", "claude") or "claude"
    provider = API_PROVIDERS.get(current_provider)

    if provider and current_provider != "claude":
        provider_models = provider.get("models", [])
        return ModelsResponse(
            models=[ModelInfo(id=m["id"], name=m["name"]) for m in provider_models],
            default=provider.get("default_model", ""),
        )

    # Default: return Claude models
    return ModelsResponse(
        models=[ModelInfo(id=m["id"], name=m["name"]) for m in AVAILABLE_MODELS],
        default=DEFAULT_MODEL,
    )


def _parse_int(value: str | None, default: int) -> int:
    """Parse integer setting with default fallback."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_bool(value: str | None, default: bool = False) -> bool:
    """Parse boolean setting with default fallback."""
    if value is None:
        return default
    return value.lower() == "true"


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get current global settings."""
    all_settings = get_all_settings()

    api_provider = all_settings.get("api_provider", "claude")

    glm_mode = api_provider == "glm"
    ollama_mode = api_provider == "ollama"

    role_models_dict = get_all_role_models()
    role_models = RoleModelAssignment(**role_models_dict)

    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", DEFAULT_MODEL),
        glm_mode=glm_mode,
        ollama_mode=ollama_mode,
        testing_agent_ratio=_parse_int(all_settings.get("testing_agent_ratio"), 1),
        playwright_headless=_parse_bool(all_settings.get("playwright_headless"), default=True),
        batch_size=_parse_int(all_settings.get("batch_size"), 3),
        api_provider=api_provider,
        api_base_url=all_settings.get("api_base_url"),
        api_has_auth_token=bool(all_settings.get("api_auth_token")),
        api_model=all_settings.get("api_model"),
        role_models=role_models,
    )


@router.patch("", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate):
    """Update global settings."""
    if update.yolo_mode is not None:
        set_setting("yolo_mode", "true" if update.yolo_mode else "false")

    if update.model is not None:
        set_setting("model", update.model)

    if update.testing_agent_ratio is not None:
        set_setting("testing_agent_ratio", str(update.testing_agent_ratio))

    if update.playwright_headless is not None:
        set_setting("playwright_headless", "true" if update.playwright_headless else "false")

    if update.batch_size is not None:
        set_setting("batch_size", str(update.batch_size))

    # API provider settings
    if update.api_provider is not None:
        old_provider = get_setting("api_provider", "claude")
        set_setting("api_provider", update.api_provider)

        # When provider changes, auto-set defaults for the new provider
        if update.api_provider != old_provider:
            provider = API_PROVIDERS.get(update.api_provider)
            if provider:
                # Auto-set base URL from provider definition
                if provider.get("base_url"):
                    set_setting("api_base_url", provider["base_url"])
                # Auto-set model to provider's default
                if provider.get("default_model") and update.api_model is None:
                    set_setting("api_model", provider["default_model"])

    if update.api_base_url is not None:
        set_setting("api_base_url", update.api_base_url)

    if update.api_auth_token is not None:
        set_setting("api_auth_token", update.api_auth_token)

    if update.api_model is not None:
        set_setting("api_model", update.api_model)

    # Per-role model overrides
    if update.role_models is not None:
        role_dict = update.role_models.model_dump()
        for role in VALID_ROLES:
            value = role_dict.get(role)
            if value is not None:
                key = f"{ROLE_MODEL_KEY_PREFIX}{role}"
                if value == "":
                    # Empty string clears the override (delete the setting)
                    set_setting(key, "")
                else:
                    set_setting(key, value)

    # Return updated settings
    all_settings = get_all_settings()
    api_provider = all_settings.get("api_provider", "claude")
    glm_mode = api_provider == "glm"
    ollama_mode = api_provider == "ollama"

    updated_role_models_dict = get_all_role_models()
    updated_role_models = RoleModelAssignment(**updated_role_models_dict)

    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", DEFAULT_MODEL),
        glm_mode=glm_mode,
        ollama_mode=ollama_mode,
        testing_agent_ratio=_parse_int(all_settings.get("testing_agent_ratio"), 1),
        playwright_headless=_parse_bool(all_settings.get("playwright_headless"), default=True),
        batch_size=_parse_int(all_settings.get("batch_size"), 3),
        api_provider=api_provider,
        api_base_url=all_settings.get("api_base_url"),
        api_has_auth_token=bool(all_settings.get("api_auth_token")),
        api_model=all_settings.get("api_model"),
        role_models=updated_role_models,
    )
