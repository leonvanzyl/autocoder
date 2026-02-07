"""
Settings Router
===============

API endpoints for global settings management.
Settings are stored in the registry database and shared across all projects.
"""

import asyncio
import logging
import mimetypes
import shutil
import sys

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from ..schemas import ModelInfo, ModelsResponse, ProviderInfo, ProvidersResponse, SettingsResponse, SettingsUpdate

logger = logging.getLogger(__name__)
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


def _build_settings_response(all_settings: dict[str, str]) -> SettingsResponse:
    """Build SettingsResponse from settings dict (shared by GET and PATCH)."""
    api_provider = all_settings.get("api_provider", "claude")
    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", DEFAULT_MODEL),
        glm_mode=api_provider == "glm",
        ollama_mode=api_provider == "ollama",
        testing_agent_ratio=_parse_int(all_settings.get("testing_agent_ratio"), 1),
        playwright_headless=_parse_bool(all_settings.get("playwright_headless"), default=True),
        batch_size=_parse_int(all_settings.get("batch_size"), 3),
        api_provider=api_provider,
        api_base_url=all_settings.get("api_base_url"),
        api_has_auth_token=bool(all_settings.get(f"api_auth_token.{api_provider}") or all_settings.get("api_auth_token")),
        api_model=all_settings.get("api_model"),
    )


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get current global settings."""
    return _build_settings_response(get_all_settings())


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
        current_provider = get_setting("api_provider", "claude")
        set_setting(f"api_auth_token.{current_provider}", update.api_auth_token)
        set_setting("api_auth_token", update.api_auth_token)

    if update.api_model is not None:
        set_setting("api_model", update.api_model)

    return _build_settings_response(get_all_settings())


# =============================================================================
# Test Connection
# =============================================================================


class TestConnectionResponse(BaseModel):
    success: bool
    message: str


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_provider_connection():
    """Test connectivity to the current API provider."""
    all_settings = get_all_settings()
    provider_id = all_settings.get("api_provider", "claude")

    if provider_id == "claude":
        return await _test_claude()

    provider = API_PROVIDERS.get(provider_id)
    if not provider:
        return TestConnectionResponse(success=False, message=f"Unknown provider: {provider_id}")

    base_url = all_settings.get("api_base_url") or provider.get("base_url")
    if not base_url:
        return TestConnectionResponse(success=False, message="No base URL configured")

    auth_token = all_settings.get(f"api_auth_token.{provider_id}") or all_settings.get("api_auth_token")
    if provider.get("requires_auth") and not auth_token:
        return TestConnectionResponse(success=False, message="No API key configured")

    return await _test_http_provider(provider_id, base_url, auth_token, provider)


async def _test_claude() -> TestConnectionResponse:
    """Test Claude CLI availability."""
    claude_path = shutil.which("claude")
    if not claude_path:
        return TestConnectionResponse(success=False, message="Claude CLI not found in PATH")
    try:
        proc = await asyncio.create_subprocess_exec(
            claude_path, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        version = stdout.decode().strip() if stdout else "unknown"
        return TestConnectionResponse(success=True, message=f"Claude CLI: {version}")
    except asyncio.TimeoutError:
        return TestConnectionResponse(success=False, message="Claude CLI timed out")
    except Exception as e:
        return TestConnectionResponse(success=False, message=f"Claude CLI error: {e}")


async def _test_http_provider(
    provider_id: str, base_url: str, auth_token: str | None, provider: dict,  # type: ignore[type-arg]
) -> TestConnectionResponse:
    """Test an HTTP-based API provider by sending a minimal messages request."""
    base = base_url.rstrip("/")
    # Try multiple paths - different providers use different API structures
    candidate_paths = ["/v1/messages", "/messages", "/chat/completions", ""]

    auth_env_var = provider.get("auth_env_var", "ANTHROPIC_AUTH_TOKEN")
    headers: dict[str, str] = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if auth_token:
        if auth_env_var == "ANTHROPIC_API_KEY":
            headers["x-api-key"] = auth_token
        else:
            headers["authorization"] = f"Bearer {auth_token}"

    model = provider.get("default_model") or "test"
    body = {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for path in candidate_paths:
                url = base + path
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code == 404:
                    continue  # Try next path
                if resp.status_code == 200:
                    return TestConnectionResponse(success=True, message=f"Connected to {provider_id}")
                if resp.status_code == 401:
                    return TestConnectionResponse(success=False, message="Authentication failed - check API key")
                if resp.status_code == 403:
                    return TestConnectionResponse(success=False, message="Access denied - check API key permissions")
                # Some providers return errors but still prove connectivity
                try:
                    data = resp.json()
                    err_type = data.get("error", {}).get("type", "")
                    if err_type in ("invalid_request_error", "not_found_error", "overloaded_error"):
                        return TestConnectionResponse(success=True, message=f"Connected to {provider_id}")
                except Exception:
                    pass
                # Got a non-404 response, so connectivity works even if there's an error
                return TestConnectionResponse(success=False, message=f"HTTP {resp.status_code}: {resp.text[:200]}")

        # All paths returned 404
        return TestConnectionResponse(success=False, message=f"No valid endpoint found at {base_url}")
    except httpx.ConnectError:
        return TestConnectionResponse(success=False, message=f"Cannot connect to {base_url}")
    except httpx.TimeoutException:
        return TestConnectionResponse(success=False, message="Connection timed out")
    except Exception as e:
        logger.warning("Test connection error for %s: %s", provider_id, e)
        return TestConnectionResponse(success=False, message=f"Error: {e}")
