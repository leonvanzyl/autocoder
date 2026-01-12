"""
Parallel (Per-Project) Router
============================

Endpoints for inspecting parallel worker state for a given project.

Note: starting/stopping agents is handled by the existing per-project agent router
(`/api/projects/{project_name}/agent/*`). This router focuses on observability.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from autocoder.core.database import get_database


router = APIRouter(prefix="/api/projects/{project_name}/parallel", tags=["parallel"])


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    from autocoder.agent.registry import get_project_path

    p = get_project_path(project_name)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")
    return Path(p)


def _validate_project_name(name: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_-]{1,50}$", name):
        raise HTTPException(status_code=400, detail="Invalid project name")
    return name


class ParallelAgentInfo(BaseModel):
    agent_id: str
    status: str
    last_ping: str | None = None
    pid: int | None = None
    worktree_path: str | None = None
    feature_id: int | None = None
    feature_name: str | None = None
    api_port: int | None = None
    web_port: int | None = None
    log_file_path: str | None = None


class ParallelAgentsStatusResponse(BaseModel):
    is_running: bool
    active_count: int
    agents: list[ParallelAgentInfo]


@router.get("/agents", response_model=ParallelAgentsStatusResponse)
async def get_parallel_agents(project_name: str, limit: int = 50):
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    limit = max(1, min(int(limit), 200))
    db = get_database(str(project_dir))

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
              ah.agent_id,
              ah.status,
              ah.last_ping,
              ah.pid,
              ah.worktree_path,
              ah.feature_id,
              f.name AS feature_name,
              ah.api_port,
              ah.web_port,
              ah.log_file_path
            FROM agent_heartbeats ah
            LEFT JOIN features f ON f.id = ah.feature_id
            ORDER BY ah.last_ping DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()

    agents = [
        ParallelAgentInfo(
            agent_id=row["agent_id"],
            status=row["status"],
            last_ping=row["last_ping"],
            pid=row["pid"],
            worktree_path=row["worktree_path"],
            feature_id=row["feature_id"],
            feature_name=row["feature_name"],
            api_port=row["api_port"],
            web_port=row["web_port"],
            log_file_path=row["log_file_path"],
        )
        for row in rows
    ]

    active_count = sum(1 for a in agents if a.status == "ACTIVE")
    return ParallelAgentsStatusResponse(
        is_running=active_count > 0,
        active_count=active_count,
        agents=agents,
    )
