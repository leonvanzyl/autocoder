"""
Deploy Router
=============

API endpoints for deployment workflow management.
"""

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add parent directory to path
root_dir = Path(__file__).parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from deploy_agent import (
    DeployAgent,
    DeploymentConfig,
    DeploymentEnvironment,
    DeploymentStatus,
    DeploymentStrategy,
)
from registry import get_project_path

router = APIRouter(prefix="/api/deploy", tags=["deployments"])


class DeployRequest(BaseModel):
    """Request to start a deployment."""

    environment: str = Field(..., description="Target environment (development, staging, production, preview)")
    strategy: str = Field(default="direct", description="Deployment strategy")
    branch: str = Field(default="main", description="Git branch to deploy")
    commit_sha: str | None = Field(default=None, description="Specific commit SHA to deploy")
    deploy_command: str | None = Field(default=None, description="Custom deployment command")
    pre_deploy_checks: list[str] = Field(default_factory=list, description="Pre-deployment check commands")
    post_deploy_checks: list[str] = Field(default_factory=list, description="Post-deployment check commands")
    rollback_command: str | None = Field(default=None, description="Rollback command")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DeployResponse(BaseModel):
    """Response from a deployment operation."""

    success: bool
    deployment_id: int | None = None
    message: str = ""
    duration_ms: int = 0
    logs: list[str] = []


def _get_project_path(project_name: str) -> Path:
    """Get project path or raise 404."""
    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    return project_path


def _parse_environment(env_str: str) -> DeploymentEnvironment:
    """Parse environment string to enum."""
    try:
        return DeploymentEnvironment(env_str.lower())
    except ValueError:
        valid = [e.value for e in DeploymentEnvironment]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid environment '{env_str}'. Valid options: {valid}",
        )


def _parse_strategy(strategy_str: str) -> DeploymentStrategy:
    """Parse strategy string to enum."""
    try:
        return DeploymentStrategy(strategy_str.lower())
    except ValueError:
        valid = [s.value for s in DeploymentStrategy]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy '{strategy_str}'. Valid options: {valid}",
        )


def _parse_status(status_str: str | None) -> DeploymentStatus | None:
    """Parse status string to enum."""
    if not status_str:
        return None
    try:
        return DeploymentStatus(status_str.lower())
    except ValueError:
        valid = [s.value for s in DeploymentStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status_str}'. Valid options: {valid}",
        )


@router.post("/{project_name}/start")
async def start_deployment(project_name: str, request: DeployRequest) -> DeployResponse:
    """
    Start a new deployment.

    Args:
        project_name: The project name
        request: Deployment configuration

    Returns:
        DeployResponse with deployment status
    """
    project_path = _get_project_path(project_name)
    agent = DeployAgent(project_path)

    config = DeploymentConfig(
        environment=_parse_environment(request.environment),
        strategy=_parse_strategy(request.strategy),
        branch=request.branch,
        commit_sha=request.commit_sha,
        deploy_command=request.deploy_command,
        pre_deploy_checks=request.pre_deploy_checks,
        post_deploy_checks=request.post_deploy_checks,
        rollback_command=request.rollback_command,
        metadata={**request.metadata, "rollback_command": request.rollback_command},
    )

    result = agent.start_deployment(config)

    return DeployResponse(
        success=result.success,
        deployment_id=result.deployment_id,
        message=result.message,
        duration_ms=result.duration_ms,
        logs=result.logs,
    )


@router.get("/{project_name}/deployments")
async def list_deployments(
    project_name: str,
    environment: str | None = None,
    status: str | None = None,
    limit: int = 20,
):
    """
    List deployments for a project.

    Args:
        project_name: The project name
        environment: Optional environment filter
        status: Optional status filter
        limit: Maximum number of results

    Returns:
        List of deployments
    """
    project_path = _get_project_path(project_name)
    agent = DeployAgent(project_path)

    env = _parse_environment(environment) if environment else None
    stat = _parse_status(status)

    deployments = agent.list_deployments(
        environment=env,
        status=stat,
        limit=min(limit, 100),
    )

    return {"deployments": deployments}


@router.get("/{project_name}/deployments/{deployment_id}")
async def get_deployment(project_name: str, deployment_id: int):
    """
    Get a specific deployment.

    Args:
        project_name: The project name
        deployment_id: The deployment ID

    Returns:
        Deployment details
    """
    project_path = _get_project_path(project_name)
    agent = DeployAgent(project_path)

    deployment = agent.get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail=f"Deployment #{deployment_id} not found")

    return deployment


@router.get("/{project_name}/deployments/{deployment_id}/checks")
async def get_deployment_checks(project_name: str, deployment_id: int):
    """
    Get checks for a deployment.

    Args:
        project_name: The project name
        deployment_id: The deployment ID

    Returns:
        List of deployment checks
    """
    project_path = _get_project_path(project_name)
    agent = DeployAgent(project_path)

    checks = agent.get_deployment_checks(deployment_id)
    return {"checks": checks}


@router.post("/{project_name}/deployments/{deployment_id}/rollback")
async def rollback_deployment(project_name: str, deployment_id: int) -> DeployResponse:
    """
    Rollback a deployment.

    Args:
        project_name: The project name
        deployment_id: The deployment ID

    Returns:
        DeployResponse with rollback status
    """
    project_path = _get_project_path(project_name)
    agent = DeployAgent(project_path)

    result = agent.rollback(deployment_id)

    return DeployResponse(
        success=result.success,
        deployment_id=result.deployment_id,
        message=result.message,
        duration_ms=result.duration_ms,
        logs=result.logs,
    )


@router.post("/{project_name}/deployments/{deployment_id}/cancel")
async def cancel_deployment(project_name: str, deployment_id: int) -> DeployResponse:
    """
    Cancel a pending or in-progress deployment.

    Args:
        project_name: The project name
        deployment_id: The deployment ID

    Returns:
        DeployResponse with cancellation status
    """
    project_path = _get_project_path(project_name)
    agent = DeployAgent(project_path)

    result = agent.cancel_deployment(deployment_id)

    return DeployResponse(
        success=result.success,
        deployment_id=result.deployment_id,
        message=result.message,
    )


@router.get("/{project_name}/environments")
async def get_environment_status(project_name: str):
    """
    Get status of all deployment environments.

    Args:
        project_name: The project name

    Returns:
        Environment status information
    """
    project_path = _get_project_path(project_name)
    agent = DeployAgent(project_path)

    return agent.get_environment_status()
