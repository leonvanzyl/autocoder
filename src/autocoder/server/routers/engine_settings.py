"""
Engine Settings Router
======================

Per-project engine chain configuration stored in agent_system.db.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from autocoder.agent.registry import get_project_path
from autocoder.core.engine_settings import EngineSettings, parse_engine_settings, load_engine_settings, save_engine_settings


router = APIRouter(prefix="/api/engine-settings", tags=["engine-settings"])


def _project_dir(project: str | None) -> Path:
    if not project:
        raise HTTPException(status_code=400, detail="project is required")
    if not re.match(r"^[a-zA-Z0-9_-]{1,50}$", project):
        raise HTTPException(status_code=400, detail="Invalid project name")
    path = get_project_path(project)
    if not path:
        raise HTTPException(status_code=404, detail="Project not found in registry")
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")
    return resolved


@router.get("", response_model=EngineSettings)
async def get_engine_settings(project: str | None = Query(default=None)):
    project_dir = _project_dir(project)
    settings = load_engine_settings(str(project_dir))
    return settings


@router.put("", response_model=EngineSettings)
async def put_engine_settings(payload: dict, project: str | None = Query(default=None)):
    project_dir = _project_dir(project)
    try:
        settings = parse_engine_settings(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_engine_settings(str(project_dir), settings)
    return settings
