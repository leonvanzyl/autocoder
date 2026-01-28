"""
CI/CD Router
============

REST API endpoints for CI/CD workflow generation.

Endpoints:
- POST /api/cicd/generate - Generate CI/CD workflows
- GET /api/cicd/workflows - List existing workflows
- GET /api/cicd/preview - Preview workflow content
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cicd", tags=["cicd"])


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry."""
    from registry import get_project_path

    return get_project_path(project_name)


# ============================================================================
# Request/Response Models
# ============================================================================


class GenerateRequest(BaseModel):
    """Request to generate CI/CD workflows."""

    project_name: str = Field(..., description="Name of the registered project")
    provider: str = Field("github", description="CI provider (github, gitlab)")
    workflow_types: list[str] = Field(
        ["ci", "security", "deploy"],
        description="Types of workflows to generate",
    )
    save: bool = Field(True, description="Whether to save the workflow files")


class WorkflowInfo(BaseModel):
    """Information about a generated workflow."""

    name: str
    filename: str
    type: str
    path: Optional[str] = None


class GenerateResponse(BaseModel):
    """Response from workflow generation."""

    provider: str
    workflows: list[WorkflowInfo]
    output_dir: str
    message: str


class PreviewRequest(BaseModel):
    """Request to preview a workflow."""

    project_name: str = Field(..., description="Name of the registered project")
    workflow_type: str = Field("ci", description="Type of workflow (ci, security, deploy)")


class PreviewResponse(BaseModel):
    """Response with workflow preview."""

    workflow_type: str
    filename: str
    content: str


class WorkflowListResponse(BaseModel):
    """Response with list of existing workflows."""

    workflows: list[WorkflowInfo]
    count: int


# ============================================================================
# REST Endpoints
# ============================================================================


@router.post("/generate", response_model=GenerateResponse)
async def generate_workflows(request: GenerateRequest):
    """
    Generate CI/CD workflows for a project.

    Detects tech stack and generates appropriate workflow files.
    Supports GitHub Actions (and GitLab CI planned).
    """
    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    try:
        if request.provider == "github":
            from integrations.ci import generate_github_workflow

            workflows = []
            for wf_type in request.workflow_types:
                if wf_type not in ["ci", "security", "deploy"]:
                    continue

                workflow = generate_github_workflow(
                    project_dir,
                    workflow_type=wf_type,
                    save=request.save,
                )

                path = None
                if request.save:
                    path = str(project_dir / ".github" / "workflows" / workflow.filename)

                workflows.append(
                    WorkflowInfo(
                        name=workflow.name,
                        filename=workflow.filename,
                        type=wf_type,
                        path=path,
                    )
                )

            return GenerateResponse(
                provider="github",
                workflows=workflows,
                output_dir=str(project_dir / ".github" / "workflows"),
                message=f"Generated {len(workflows)} workflow(s)",
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported provider: {request.provider}",
            )

    except Exception as e:
        logger.exception(f"Error generating workflows: {e}")
        raise HTTPException(status_code=500, detail="Generation failed")


@router.post("/preview", response_model=PreviewResponse)
async def preview_workflow(request: PreviewRequest):
    """
    Preview a workflow without saving it.

    Returns the YAML content that would be generated.
    """
    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    if request.workflow_type not in ["ci", "security", "deploy"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workflow type: {request.workflow_type}",
        )

    try:
        from integrations.ci import generate_github_workflow

        workflow = generate_github_workflow(
            project_dir,
            workflow_type=request.workflow_type,
            save=False,
        )

        return PreviewResponse(
            workflow_type=request.workflow_type,
            filename=workflow.filename,
            content=workflow.to_yaml(),
        )

    except Exception as e:
        logger.exception(f"Error previewing workflow: {e}")
        raise HTTPException(status_code=500, detail="Preview failed")


@router.get("/workflows/{project_name}", response_model=WorkflowListResponse)
async def list_workflows(project_name: str):
    """
    List existing GitHub Actions workflows for a project.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    workflows_dir = project_dir / ".github" / "workflows"
    if not workflows_dir.exists():
        return WorkflowListResponse(workflows=[], count=0)

    workflows = []
    for file in workflows_dir.iterdir():
        if file.suffix not in (".yml", ".yaml"):
            continue
        # Determine workflow type from filename
        wf_type = "custom"
        if file.stem in ["ci", "security", "deploy"]:
            wf_type = file.stem

        workflows.append(
            WorkflowInfo(
                name=file.stem.title(),
                filename=file.name,
                type=wf_type,
                path=str(file),
            )
        )

    return WorkflowListResponse(
        workflows=workflows,
        count=len(workflows),
    )


@router.get("/workflows/{project_name}/{filename}")
async def get_workflow_content(project_name: str, filename: str):
    """
    Get the content of a specific workflow file.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    # Security: validate filename
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filename.endswith((".yml", ".yaml")):
        raise HTTPException(status_code=400, detail="Invalid workflow filename")

    workflow_path = project_dir / ".github" / "workflows" / filename
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        content = workflow_path.read_text()
        return {
            "filename": filename,
            "content": content,
        }
    except Exception as e:
        logger.exception(f"Error reading workflow {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error reading workflow")
