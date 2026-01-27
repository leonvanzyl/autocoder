"""
Design Tokens API Router
========================

REST API endpoints for design tokens management.

Endpoints:
- GET /api/design-tokens/{project_name} - Get current design tokens
- PUT /api/design-tokens/{project_name} - Update design tokens
- POST /api/design-tokens/{project_name}/generate - Generate token files
- GET /api/design-tokens/{project_name}/preview/{format} - Preview generated output
- POST /api/design-tokens/{project_name}/validate - Validate tokens
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from design_tokens import DesignTokens, DesignTokensManager
from registry import get_project_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/design-tokens", tags=["design-tokens"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ColorTokens(BaseModel):
    """Color token configuration."""

    primary: Optional[str] = "#3B82F6"
    secondary: Optional[str] = "#6366F1"
    accent: Optional[str] = "#F59E0B"
    success: Optional[str] = "#10B981"
    warning: Optional[str] = "#F59E0B"
    error: Optional[str] = "#EF4444"
    info: Optional[str] = "#3B82F6"
    neutral: Optional[str] = "#6B7280"


class TypographyTokens(BaseModel):
    """Typography token configuration."""

    font_family: Optional[dict] = None
    font_size: Optional[dict] = None
    font_weight: Optional[dict] = None
    line_height: Optional[dict] = None


class BorderTokens(BaseModel):
    """Border token configuration."""

    radius: Optional[dict] = None
    width: Optional[dict] = None


class AnimationTokens(BaseModel):
    """Animation token configuration."""

    duration: Optional[dict] = None
    easing: Optional[dict] = None


class DesignTokensRequest(BaseModel):
    """Request to update design tokens."""

    colors: Optional[dict] = None
    spacing: Optional[list[int]] = None
    typography: Optional[dict] = None
    borders: Optional[dict] = None
    shadows: Optional[dict] = None
    animations: Optional[dict] = None


class DesignTokensResponse(BaseModel):
    """Response with design tokens."""

    colors: dict
    spacing: list[int]
    typography: dict
    borders: dict
    shadows: dict
    animations: dict


class GenerateResponse(BaseModel):
    """Response from token generation."""

    generated_files: dict
    contrast_issues: Optional[list[dict]] = None
    message: str


class PreviewResponse(BaseModel):
    """Preview of generated output."""

    format: str
    content: str


class ValidateResponse(BaseModel):
    """Validation results."""

    valid: bool
    issues: list[dict]


# ============================================================================
# Helper Functions
# ============================================================================


def get_project_dir(project_name: str) -> Path:
    """Get project directory from name or path."""
    project_path = get_project_path(project_name)
    if project_path:
        return Path(project_path)

    path = Path(project_name)
    if path.exists() and path.is_dir():
        return path

    raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/{project_name}", response_model=DesignTokensResponse)
async def get_design_tokens(project_name: str):
    """
    Get current design tokens for a project.

    Returns the design tokens from config file or defaults.
    """
    project_dir = get_project_dir(project_name)

    try:
        manager = DesignTokensManager(project_dir)
        tokens = manager.load()

        return DesignTokensResponse(
            colors=tokens.colors,
            spacing=tokens.spacing,
            typography=tokens.typography,
            borders=tokens.borders,
            shadows=tokens.shadows,
            animations=tokens.animations,
        )
    except Exception as e:
        logger.error(f"Error getting design tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_name}", response_model=DesignTokensResponse)
async def update_design_tokens(project_name: str, request: DesignTokensRequest):
    """
    Update design tokens for a project.

    Saves tokens to .autocoder/design-tokens.json.
    """
    project_dir = get_project_dir(project_name)

    try:
        manager = DesignTokensManager(project_dir)
        current = manager.load()

        # Update only provided fields
        if request.colors:
            current.colors.update(request.colors)
        if request.spacing:
            current.spacing = request.spacing
        if request.typography:
            current.typography.update(request.typography)
        if request.borders:
            current.borders.update(request.borders)
        if request.shadows:
            current.shadows.update(request.shadows)
        if request.animations:
            current.animations.update(request.animations)

        manager.save(current)

        return DesignTokensResponse(
            colors=current.colors,
            spacing=current.spacing,
            typography=current.typography,
            borders=current.borders,
            shadows=current.shadows,
            animations=current.animations,
        )
    except Exception as e:
        logger.error(f"Error updating design tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/generate", response_model=GenerateResponse)
async def generate_token_files(project_name: str, output_dir: Optional[str] = None):
    """
    Generate token files for a project.

    Creates:
    - tokens.css - CSS custom properties
    - _tokens.scss - SCSS variables
    - tailwind.tokens.js - Tailwind config (if Tailwind detected)
    """
    project_dir = get_project_dir(project_name)

    try:
        manager = DesignTokensManager(project_dir)

        if output_dir:
            result = manager.generate_all(project_dir / output_dir)
        else:
            result = manager.generate_all()

        contrast_issues = result.pop("contrast_issues", None)

        return GenerateResponse(
            generated_files=result,
            contrast_issues=contrast_issues,
            message=f"Generated {len(result)} token files",
        )
    except Exception as e:
        logger.error(f"Error generating token files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/preview/{format}", response_model=PreviewResponse)
async def preview_tokens(project_name: str, format: str):
    """
    Preview generated output without writing to disk.

    Args:
        project_name: Project name
        format: Output format (css, scss, tailwind)
    """
    project_dir = get_project_dir(project_name)

    valid_formats = ["css", "scss", "tailwind"]
    if format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Valid formats: {', '.join(valid_formats)}",
        )

    try:
        manager = DesignTokensManager(project_dir)
        tokens = manager.load()

        if format == "css":
            content = manager.generate_css(tokens)
        elif format == "scss":
            content = manager.generate_scss(tokens)
        elif format == "tailwind":
            content = manager.generate_tailwind_config(tokens)
        else:
            content = ""

        return PreviewResponse(format=format, content=content)
    except Exception as e:
        logger.error(f"Error previewing tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/validate", response_model=ValidateResponse)
async def validate_tokens(project_name: str):
    """
    Validate design tokens for accessibility and consistency.

    Checks:
    - Color contrast ratios
    - Color format validity
    - Spacing scale consistency
    """
    project_dir = get_project_dir(project_name)

    try:
        manager = DesignTokensManager(project_dir)
        tokens = manager.load()

        issues = []

        # Validate colors
        import re

        hex_pattern = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
        for name, value in tokens.colors.items():
            if not hex_pattern.match(value):
                issues.append(
                    {
                        "type": "color_format",
                        "field": f"colors.{name}",
                        "value": value,
                        "message": "Invalid hex color format",
                    }
                )

        # Check contrast
        contrast_issues = manager.validate_contrast(tokens)
        for ci in contrast_issues:
            issues.append(
                {
                    "type": "contrast",
                    "field": f"colors.{ci['color']}",
                    "value": ci["value"],
                    "message": ci["issue"],
                    "suggestion": ci.get("suggestion"),
                }
            )

        # Validate spacing scale
        if tokens.spacing:
            for i in range(1, len(tokens.spacing)):
                if tokens.spacing[i] <= tokens.spacing[i - 1]:
                    issues.append(
                        {
                            "type": "spacing_scale",
                            "field": "spacing",
                            "value": tokens.spacing,
                            "message": f"Spacing scale should be increasing: {tokens.spacing[i-1]} >= {tokens.spacing[i]}",
                        }
                    )

        return ValidateResponse(valid=len(issues) == 0, issues=issues)
    except Exception as e:
        logger.error(f"Error validating tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_name}/reset")
async def reset_tokens(project_name: str):
    """
    Reset design tokens to defaults.
    """
    project_dir = get_project_dir(project_name)

    try:
        manager = DesignTokensManager(project_dir)
        tokens = DesignTokens.default()
        manager.save(tokens)

        return {"reset": True, "message": "Design tokens reset to defaults"}
    except Exception as e:
        logger.error(f"Error resetting tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))
