"""
Parallel Agents Router
======================

API endpoints for parallel agent control (start/stop multiple agents).
Uses git worktrees for agent isolation.
"""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import (
    ParallelAgentStartRequest,
    ParallelAgentsStatus,
    ParallelAgentInfo,
    ParallelAgentActionResponse,
)


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


router = APIRouter(prefix="/api/projects/{project_name}/parallel-agents", tags=["parallel-agents"])

# Root directory for autocoder
ROOT_DIR = Path(__file__).parent.parent.parent


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name"
        )
    return name


def get_orchestrator(project_name: str):
    """Get or create the parallel agent orchestrator for a project."""
    from parallel_agents import get_orchestrator as _get_orchestrator

    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    return _get_orchestrator(project_name, project_dir, ROOT_DIR)


@router.get("/status", response_model=ParallelAgentsStatus)
async def get_parallel_agents_status(project_name: str):
    """Get the status of all parallel agents for a project."""
    orchestrator = get_orchestrator(project_name)

    # Run healthcheck
    await orchestrator.healthcheck()

    agents = []
    running_count = 0

    for agent_id, agent in orchestrator.agents.items():
        agents.append(ParallelAgentInfo(
            agent_id=agent_id,
            status=agent.status,
            pid=agent.process.pid if agent.process else None,
            started_at=agent.started_at,
            worktree_path=str(agent.worktree_path) if agent.worktree_path else None,
        ))
        if agent.status == "running":
            running_count += 1

    return ParallelAgentsStatus(
        agents=agents,
        total_running=running_count,
        max_agents=orchestrator.max_agents,
    )


@router.post("/start", response_model=ParallelAgentActionResponse)
async def start_parallel_agents(
    project_name: str,
    request: ParallelAgentStartRequest = ParallelAgentStartRequest(),
):
    """Start multiple parallel agents for a project."""
    orchestrator = get_orchestrator(project_name)

    results = await orchestrator.start_agents(
        num_agents=request.num_agents,
        yolo_mode=request.yolo_mode,
        max_iterations=request.max_iterations,
    )

    all_success = all(results.values())
    success_count = sum(1 for v in results.values() if v)

    return ParallelAgentActionResponse(
        success=all_success,
        agents=results,
        message=f"Started {success_count}/{request.num_agents} agents",
    )


@router.post("/stop", response_model=ParallelAgentActionResponse)
async def stop_all_parallel_agents(project_name: str):
    """Stop all parallel agents for a project."""
    orchestrator = get_orchestrator(project_name)

    # Get list of running agents before stopping
    running_agents = [
        aid for aid, agent in orchestrator.agents.items()
        if agent.status == "running"
    ]

    await orchestrator.stop_all_agents()

    # Build results dict
    results = {aid: True for aid in running_agents}

    return ParallelAgentActionResponse(
        success=True,
        agents=results,
        message=f"Stopped {len(running_agents)} agents",
    )


@router.post("/pause", response_model=ParallelAgentActionResponse)
async def pause_all_parallel_agents(project_name: str):
    """Pause all running parallel agents for a project."""
    orchestrator = get_orchestrator(project_name)

    running_agents = [
        aid for aid, agent in orchestrator.agents.items()
        if agent.status == "running"
    ]

    results = {}
    for aid in running_agents:
        success = await orchestrator.pause_agent(aid)
        results[aid] = success

    paused_count = sum(1 for v in results.values() if v)

    return ParallelAgentActionResponse(
        success=paused_count == len(running_agents),
        agents=results,
        message=f"Paused {paused_count}/{len(running_agents)} agents",
    )


@router.post("/resume", response_model=ParallelAgentActionResponse)
async def resume_all_parallel_agents(project_name: str):
    """Resume all paused parallel agents for a project."""
    orchestrator = get_orchestrator(project_name)

    paused_agents = [
        aid for aid, agent in orchestrator.agents.items()
        if agent.status == "paused"
    ]

    results = {}
    for aid in paused_agents:
        success = await orchestrator.resume_agent(aid)
        results[aid] = success

    resumed_count = sum(1 for v in results.values() if v)

    return ParallelAgentActionResponse(
        success=resumed_count == len(paused_agents),
        agents=results,
        message=f"Resumed {resumed_count}/{len(paused_agents)} agents",
    )


@router.post("/{agent_id}/start")
async def start_single_agent(
    project_name: str,
    agent_id: str,
    yolo_mode: bool = False,
):
    """Start a single parallel agent."""
    orchestrator = get_orchestrator(project_name)

    success = await orchestrator.start_agent(agent_id, yolo_mode=yolo_mode)

    agent = orchestrator.agents.get(agent_id)
    return {
        "success": success,
        "agent_id": agent_id,
        "status": agent.status if agent else "unknown",
    }


@router.post("/{agent_id}/stop")
async def stop_single_agent(project_name: str, agent_id: str):
    """Stop a single parallel agent."""
    orchestrator = get_orchestrator(project_name)

    success = await orchestrator.stop_agent(agent_id)

    return {
        "success": success,
        "agent_id": agent_id,
        "status": "stopped" if success else "unknown",
    }


@router.post("/{agent_id}/pause")
async def pause_single_agent(project_name: str, agent_id: str):
    """Pause a single parallel agent."""
    orchestrator = get_orchestrator(project_name)

    success = await orchestrator.pause_agent(agent_id)

    return {
        "success": success,
        "agent_id": agent_id,
        "status": "paused" if success else "unknown",
    }


@router.post("/{agent_id}/resume")
async def resume_single_agent(project_name: str, agent_id: str):
    """Resume a single parallel agent."""
    orchestrator = get_orchestrator(project_name)

    success = await orchestrator.resume_agent(agent_id)

    return {
        "success": success,
        "agent_id": agent_id,
        "status": "running" if success else "unknown",
    }


@router.post("/merge")
async def merge_all_worktrees(project_name: str):
    """Merge changes from all agent worktrees back to main branch."""
    orchestrator = get_orchestrator(project_name)

    results = await orchestrator.merge_all_worktrees()

    return {
        "success": all(results.values()),
        "agents": results,
        "message": f"Merged {sum(1 for v in results.values() if v)}/{len(results)} worktrees",
    }


@router.post("/cleanup")
async def cleanup_parallel_agents(project_name: str):
    """Stop all agents and clean up worktrees."""
    orchestrator = get_orchestrator(project_name)

    await orchestrator.cleanup()

    return {
        "success": True,
        "message": "All agents stopped and worktrees cleaned up",
    }
