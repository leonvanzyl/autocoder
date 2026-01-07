"""
Parallel Agents API Router
===========================

REST API endpoints for managing parallel agent execution.

Endpoints:
- POST /parallel-agents/start - Start parallel agents
- POST /parallel-agents/stop - Stop running agents
- GET /parallel-agents/status - Get agent status
- PUT /parallel-agents/config - Update parallel configuration
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from model_settings import ModelSettings

router = APIRouter(prefix="/parallel-agents", tags=["parallel-agents"])


# Global state for tracking running agents
_running_managers: Dict[str, "AgentManager"] = {}
_agent_status: Dict[str, List[dict]] = {}


# Pydantic models
class StartAgentsRequest(BaseModel):
    """Request to start parallel agents"""
    project_dir: str = Field(..., description="Path to project directory")
    parallel_count: int = Field(default=3, ge=1, le=5, description="Number of parallel agents")
    preset: str | None = Field(None, description="Model selection preset")
    models: List[str] | None = Field(None, description="Custom model list")


class AgentStatus(BaseModel):
    """Status of a single agent"""
    agent_id: str
    feature_id: int
    feature_name: str
    status: str  # running, completed, failed
    model_used: str
    progress: int


class ParallelAgentsStatus(BaseModel):
    """Status of all parallel agents"""
    project_dir: str
    parallel_count: int
    running_agents: List[AgentStatus]
    completed_count: int
    failed_count: int
    is_running: bool


class ConfigUpdate(BaseModel):
    """Parallel configuration update"""
    parallel_count: int = Field(ge=1, le=5, description="Number of parallel agents")
    preset: str | None = None
    models: List[str] | None = None


async def run_agents_async(project_dir: str, parallel_count: int, settings: ModelSettings):
    """Run agents in background (async wrapper)"""
    # This will be implemented when we integrate with agent_manager
    # For now, just simulate
    status_key = f"{project_dir}:{parallel_count}"
    _agent_status[status_key] = []

    # Simulate agent work
    for i in range(parallel_count):
        _agent_status[status_key].append({
            "agent_id": f"agent-{i+1}",
            "feature_id": i+1,
            "feature_name": f"Feature {i+1}",
            "status": "running",
            "model_used": settings.available_models[0],
            "progress": 0
        })

    # In real implementation, this would call agent_manager
    # manager = AgentManager(project_dir, parallel_count, settings)
    # await manager.run_parallel()


@router.post("/start")
async def start_agents(request: StartAgentsRequest, background_tasks: BackgroundTasks):
    """Start parallel agents for a project

    Spawns the specified number of parallel agents to work on features.
    Returns immediately with agent IDs, agents run in background.
    """
    project_path = Path(request.project_dir).resolve()

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {request.project_dir}")

    if not (project_path / "features.db").exists():
        raise HTTPException(status_code=404, detail="Features database not found. Initialize project first.")

    # Load model settings
    settings = ModelSettings.load()
    if request.preset:
        settings.set_preset(request.preset)
    elif request.models:
        settings.set_custom_models(request.models)

    # Check if already running
    status_key = f"{str(project_path)}:{request.parallel_count}"
    if status_key in _agent_status:
        raise HTTPException(status_code=400, detail="Agents already running for this project")

    # Start agents in background
    background_tasks.add_task(run_agents_async, str(project_path), request.parallel_count, settings)

    return {
        "success": True,
        "message": f"Started {request.parallel_count} parallel agents",
        "project_dir": str(project_path),
        "parallel_count": request.parallel_count,
        "model_preset": settings.preset,
        "available_models": settings.available_models
    }


@router.post("/stop")
async def stop_agents(project_dir: str):
    """Stop running parallel agents

    Gracefully stops all running agents for a project.
    """
    project_path = Path(project_dir).resolve()

    # Find and stop agents
    keys_to_remove = []
    for key in _agent_status.keys():
        if key.startswith(str(project_path)):
            keys_to_remove.append(key)

    if not keys_to_remove:
        raise HTTPException(status_code=404, detail="No running agents found for this project")

    for key in keys_to_remove:
        # In real implementation, would call manager._shutdown_agents()
        del _agent_status[key]

    return {
        "success": True,
        "message": f"Stopped agents for {len(keys_to_remove)} configuration(s)"
    }


@router.get("/status", response_model=ParallelAgentsStatus)
async def get_agent_status(project_dir: str, parallel_count: Optional[int] = None):
    """Get status of running agents

    Returns the current status of all running agents including
    which features they're working on and their progress.
    """
    project_path = Path(project_dir).resolve()

    # Find matching status
    if parallel_count:
        status_key = f"{str(project_path)}:{parallel_count}"
        if status_key not in _agent_status:
            return ParallelAgentsStatus(
                project_dir=str(project_path),
                parallel_count=parallel_count,
                running_agents=[],
                completed_count=0,
                failed_count=0,
                is_running=False
            )

        agents = _agent_status[status_key]
        completed = sum(1 for a in agents if a["status"] == "completed")
        failed = sum(1 for a in agents if a["status"] == "failed")

        return ParallelAgentsStatus(
            project_dir=str(project_path),
            parallel_count=parallel_count,
            running_agents=[AgentStatus(**a) for a in agents],
            completed_count=completed,
            failed_count=failed,
            is_running=True
        )

    # Return aggregated status for all configurations
    all_agents = []
    for key, agents in _agent_status.items():
        if key.startswith(str(project_path)):
            all_agents.extend(agents)

    completed = sum(1 for a in all_agents if a["status"] == "completed")
    failed = sum(1 for a in all_agents if a["status"] == "failed")

    # Determine parallel count from first match
    parallel_count = 0
    for key in _agent_status.keys():
        if key.startswith(str(project_path)):
            parallel_count = int(key.split(":")[-1])
            break

    return ParallelAgentsStatus(
        project_dir=str(project_path),
        parallel_count=parallel_count,
        running_agents=[AgentStatus(**a) for a in all_agents],
        completed_count=completed,
        failed_count=failed,
        is_running=len(all_agents) > 0
    )


@router.put("/config")
async def update_config(project_dir: str, config: ConfigUpdate):
    """Update parallel agent configuration

    Update the number of parallel agents or model settings for a project.
    Changes take effect on next agent start.
    """
    project_path = Path(project_dir).resolve()

    # Load settings
    settings = ModelSettings.load()

    # Apply updates
    if config.preset:
        settings.set_preset(config.preset)
    elif config.models:
        settings.set_custom_models(config.models)

    # Save settings
    settings.save()

    return {
        "success": True,
        "message": "Configuration updated",
        "config": {
            "parallel_count": config.parallel_count,
            "model_preset": settings.preset,
            "available_models": settings.available_models
        }
    }


@router.get("/presets")
async def get_presets():
    """Get available model presets

    Returns list of available presets and their configurations.
    """
    from model_settings import get_preset_info

    presets = get_preset_info()

    return {
        "presets": [
            {
                "id": preset_id,
                "name": info["name"],
                "models": info["models"],
                "best_for": info["best_for"],
                "description": info["description"]
            }
            for preset_id, info in presets.items()
        ]
    }
