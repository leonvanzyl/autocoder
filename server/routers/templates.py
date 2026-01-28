"""
Templates Router
================

REST API endpoints for project templates.

Endpoints:
- GET /api/templates - List all available templates
- GET /api/templates/{template_id} - Get template details
- POST /api/templates/preview - Preview app_spec.txt generation
- POST /api/templates/apply - Apply template to new project
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Setup sys.path for imports
# Compute project root and ensure it's in sys.path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from templates.library import generate_app_spec as generate_app_spec_lib
from templates.library import generate_features as generate_features_lib
from templates.library import get_template as get_template_lib
from templates.library import list_templates as list_templates_lib

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])


# ============================================================================
# Request/Response Models
# ============================================================================


class TechStackInfo(BaseModel):
    """Technology stack information."""

    frontend: Optional[str] = None
    backend: Optional[str] = None
    database: Optional[str] = None
    auth: Optional[str] = None
    styling: Optional[str] = None
    hosting: Optional[str] = None


class DesignTokensInfo(BaseModel):
    """Design tokens information."""

    colors: dict[str, str] = {}
    spacing: list[int] = []
    fonts: dict[str, str] = {}
    border_radius: dict[str, str] = {}


class TemplateInfo(BaseModel):
    """Template summary information."""

    id: str
    name: str
    description: str
    estimated_features: int
    tags: list[str] = []
    difficulty: str = "intermediate"


class TemplateDetail(BaseModel):
    """Full template details."""

    id: str
    name: str
    description: str
    tech_stack: TechStackInfo
    feature_categories: dict[str, list[str]]
    design_tokens: DesignTokensInfo
    estimated_features: int
    tags: list[str] = []
    difficulty: str = "intermediate"


class TemplateListResponse(BaseModel):
    """Response with list of templates."""

    templates: list[TemplateInfo]
    count: int


class PreviewRequest(BaseModel):
    """Request to preview app_spec.txt."""

    template_id: str = Field(..., description="Template identifier")
    app_name: str = Field(..., description="Application name")
    customizations: Optional[dict] = Field(None, description="Optional customizations")


class PreviewResponse(BaseModel):
    """Response with app_spec.txt preview."""

    template_id: str
    app_name: str
    app_spec_content: str
    feature_count: int


class ApplyRequest(BaseModel):
    """Request to apply template to a project."""

    template_id: str = Field(..., description="Template identifier")
    project_name: str = Field(..., description="Name for the new project")
    project_dir: str = Field(..., description="Directory for the project")
    customizations: Optional[dict] = Field(None, description="Optional customizations")


class ApplyResponse(BaseModel):
    """Response from applying template."""

    success: bool
    project_name: str
    project_dir: str
    app_spec_path: str
    feature_count: int
    message: str


# ============================================================================
# REST Endpoints
# ============================================================================


@router.get("", response_model=TemplateListResponse)
async def list_templates():
    """
    List all available templates.

    Returns basic information about each template.
    """
    try:
        templates = list_templates_lib()

        return TemplateListResponse(
            templates=[
                TemplateInfo(
                    id=t.id,
                    name=t.name,
                    description=t.description,
                    estimated_features=t.estimated_features,
                    tags=t.tags,
                    difficulty=t.difficulty,
                )
                for t in templates
            ],
            count=len(templates),
        )

    except Exception as e:
        logger.exception(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list templates")


@router.get("/{template_id}", response_model=TemplateDetail)
async def get_template(template_id: str):
    """
    Get detailed information about a specific template.
    """
    try:
        template = get_template_lib(template_id)

        if not template:
            raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

        return TemplateDetail(
            id=template.id,
            name=template.name,
            description=template.description,
            tech_stack=TechStackInfo(
                frontend=template.tech_stack.frontend,
                backend=template.tech_stack.backend,
                database=template.tech_stack.database,
                auth=template.tech_stack.auth,
                styling=template.tech_stack.styling,
                hosting=template.tech_stack.hosting,
            ),
            feature_categories=template.feature_categories,
            design_tokens=DesignTokensInfo(
                colors=template.design_tokens.colors,
                spacing=template.design_tokens.spacing,
                fonts=template.design_tokens.fonts,
                border_radius=template.design_tokens.border_radius,
            ),
            estimated_features=template.estimated_features,
            tags=template.tags,
            difficulty=template.difficulty,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting template: {e}")
        raise HTTPException(status_code=500, detail="Failed to get template")


@router.post("/preview", response_model=PreviewResponse)
async def preview_template(request: PreviewRequest):
    """
    Preview the app_spec.txt that would be generated from a template.

    Does not create any files - just returns the content.
    """
    try:
        template = get_template_lib(request.template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template not found: {request.template_id}")

        app_spec_content = generate_app_spec_lib(
            template,
            request.app_name,
            request.customizations,
        )

        features = generate_features_lib(template)

        return PreviewResponse(
            template_id=request.template_id,
            app_name=request.app_name,
            app_spec_content=app_spec_content,
            feature_count=len(features),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error previewing template: {e}")
        raise HTTPException(status_code=500, detail="Preview failed")


@router.post("/apply", response_model=ApplyResponse)
async def apply_template(request: ApplyRequest):
    """
    Apply a template to create a new project.

    Creates the project directory, prompts folder, and app_spec.txt.
    Does NOT register the project or create features - use the projects API for that.
    """
    try:
        template = get_template_lib(request.template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template not found: {request.template_id}")

        # Validate project_dir to prevent path traversal and absolute paths
        raw_path = request.project_dir
        if ".." in raw_path:
            raise HTTPException(status_code=400, detail="Invalid project directory: path traversal not allowed")

        # Reject absolute paths - require relative paths or user must provide full validated path
        raw_path_obj = Path(raw_path)
        if raw_path_obj.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid project directory: absolute paths not allowed")

        # Resolve relative to current working directory and verify it stays within bounds
        cwd = Path.cwd().resolve()
        project_dir = (cwd / raw_path).resolve()

        # Ensure resolved path is inside the working directory (no escape via symlinks etc.)
        try:
            project_dir.relative_to(cwd)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid project directory: path escapes working directory")

        # Create project directory
        prompts_dir = project_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        # Generate and save app_spec.txt
        app_spec_content = generate_app_spec_lib(
            template,
            request.project_name,
            request.customizations,
        )

        app_spec_path = prompts_dir / "app_spec.txt"
        with open(app_spec_path, "w", encoding="utf-8") as f:
            f.write(app_spec_content)

        features = generate_features_lib(template)

        return ApplyResponse(
            success=True,
            project_name=request.project_name,
            project_dir=str(project_dir),
            app_spec_path=str(app_spec_path),
            feature_count=len(features),
            message=f"Template '{template.name}' applied successfully. Register the project and run the initializer to create features.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error applying template: {e}")
        raise HTTPException(status_code=500, detail="Apply failed")


@router.get("/{template_id}/features")
async def get_template_features(template_id: str):
    """
    Get the features that would be created from a template.

    Returns features in bulk_create format.
    """
    try:
        template = get_template_lib(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

        features = generate_features_lib(template)

        return {
            "template_id": template_id,
            "features": features,
            "count": len(features),
            "by_category": {
                category: len(feature_names)
                for category, feature_names in template.feature_categories.items()
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting template features: {e}")
        raise HTTPException(status_code=500, detail="Failed to get features")
