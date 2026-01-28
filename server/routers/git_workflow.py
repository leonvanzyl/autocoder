"""
Git Workflow Router
===================

REST API endpoints for git workflow management.

Endpoints:
- GET /api/git/status - Get current git status
- POST /api/git/start-feature - Start working on a feature (create branch)
- POST /api/git/complete-feature - Complete a feature (merge)
- POST /api/git/abort-feature - Abort a feature
- GET /api/git/branches - List feature branches
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/git", tags=["git-workflow"])


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry with validation."""
    from server.routers.design_tokens import validate_and_get_project_path

    # Use the validated path from design_tokens to prevent security issues
    return validate_and_get_project_path(project_name)


# ============================================================================
# Request/Response Models
# ============================================================================


class StartFeatureRequest(BaseModel):
    """Request to start a feature branch."""

    project_name: str = Field(..., description="Name of the registered project")
    feature_id: int = Field(..., description="Feature ID")
    feature_name: str = Field(..., description="Feature name for branch naming")


class CompleteFeatureRequest(BaseModel):
    """Request to complete a feature."""

    project_name: str = Field(..., description="Name of the registered project")
    feature_id: int = Field(..., description="Feature ID")


class AbortFeatureRequest(BaseModel):
    """Request to abort a feature."""

    project_name: str = Field(..., description="Name of the registered project")
    feature_id: int = Field(..., description="Feature ID")
    delete_branch: bool = Field(False, description="Whether to delete the branch")


class CommitRequest(BaseModel):
    """Request to commit changes."""

    project_name: str = Field(..., description="Name of the registered project")
    feature_id: int = Field(..., description="Feature ID")
    message: str = Field(..., description="Commit message")


class WorkflowResultResponse(BaseModel):
    """Response from workflow operations."""

    success: bool
    message: str
    branch_name: Optional[str] = None
    previous_branch: Optional[str] = None


class GitStatusResponse(BaseModel):
    """Response with git status information."""

    is_git_repo: bool
    mode: str
    current_branch: Optional[str] = None
    main_branch: Optional[str] = None
    is_on_feature_branch: bool = False
    current_feature_id: Optional[int] = None
    has_uncommitted_changes: bool = False
    feature_branches: list[str] = []
    feature_branch_count: int = 0


class BranchInfo(BaseModel):
    """Information about a branch."""

    name: str
    feature_id: Optional[int] = None
    is_feature_branch: bool = False
    is_current: bool = False


class BranchListResponse(BaseModel):
    """Response with list of branches."""

    branches: list[BranchInfo]
    count: int


# ============================================================================
# REST Endpoints
# ============================================================================


@router.get("/status/{project_name}", response_model=GitStatusResponse)
async def get_git_status(project_name: str):
    """
    Get current git workflow status for a project.

    Returns information about current branch, mode, and feature branches.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from git_workflow import get_workflow

        workflow = get_workflow(project_dir)
        status = workflow.get_status()

        return GitStatusResponse(**status)

    except Exception as e:
        logger.exception(f"Error getting git status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/start-feature", response_model=WorkflowResultResponse)
async def start_feature(request: StartFeatureRequest):
    """
    Start working on a feature (create and checkout branch).

    In feature_branches mode, creates a new branch like 'feature/42-user-can-login'.
    In trunk mode, this is a no-op.
    """
    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from git_workflow import get_workflow

        workflow = get_workflow(project_dir)
        result = workflow.start_feature(request.feature_id, request.feature_name)

        return WorkflowResultResponse(
            success=result.success,
            message=result.message,
            branch_name=result.branch_name,
            previous_branch=result.previous_branch,
        )

    except Exception as e:
        logger.exception(f"Error starting feature: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start feature: {str(e)}")


@router.post("/complete-feature", response_model=WorkflowResultResponse)
async def complete_feature(request: CompleteFeatureRequest):
    """
    Complete a feature (merge to main if auto_merge enabled).

    Commits any remaining changes and optionally merges the feature branch.
    """
    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from git_workflow import get_workflow

        workflow = get_workflow(project_dir)
        result = workflow.complete_feature(request.feature_id)

        return WorkflowResultResponse(
            success=result.success,
            message=result.message,
            branch_name=result.branch_name,
            previous_branch=result.previous_branch,
        )

    except Exception as e:
        logger.exception(f"Error completing feature: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete feature: {str(e)}")


@router.post("/abort-feature", response_model=WorkflowResultResponse)
async def abort_feature(request: AbortFeatureRequest):
    """
    Abort a feature (discard changes, optionally delete branch).

    Returns to main branch and discards uncommitted changes.
    """
    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from git_workflow import get_workflow

        workflow = get_workflow(project_dir)
        result = workflow.abort_feature(request.feature_id, request.delete_branch)

        return WorkflowResultResponse(
            success=result.success,
            message=result.message,
            branch_name=result.branch_name,
            previous_branch=result.previous_branch,
        )

    except Exception as e:
        logger.exception(f"Error aborting feature: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to abort feature: {str(e)}")


@router.post("/commit", response_model=WorkflowResultResponse)
async def commit_changes(request: CommitRequest):
    """
    Commit current changes for a feature.

    Adds all changes and commits with a structured message.
    """
    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from git_workflow import get_workflow

        workflow = get_workflow(project_dir)
        result = workflow.commit_feature_progress(request.feature_id, request.message)

        return WorkflowResultResponse(
            success=result.success,
            message=result.message,
        )

    except Exception as e:
        logger.exception(f"Error committing: {e}")
        raise HTTPException(status_code=500, detail=f"Commit failed: {str(e)}")


@router.get("/branches/{project_name}", response_model=BranchListResponse)
async def list_branches(project_name: str):
    """
    List all feature branches for a project.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from git_workflow import get_workflow

        workflow = get_workflow(project_dir)
        branches = workflow.list_feature_branches()

        return BranchListResponse(
            branches=[
                BranchInfo(
                    name=b.name,
                    feature_id=b.feature_id,
                    is_feature_branch=b.is_feature_branch,
                    is_current=b.is_current,
                )
                for b in branches
            ],
            count=len(branches),
        )

    except Exception as e:
        logger.exception(f"Error listing branches: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list branches: {str(e)}")
