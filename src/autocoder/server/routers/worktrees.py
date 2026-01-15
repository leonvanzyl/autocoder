"""
Worktrees Router
================

API endpoints for inspecting and maintaining git worktrees and cleanup queues.

This primarily exists to expose the deferred cleanup queue used on Windows when
`node_modules` (native .node files) are locked and worktrees can't be deleted immediately.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autocoder.core.worktree_manager import WorktreeManager


router = APIRouter(prefix="/api/projects/{project_name}/worktrees", tags=["worktrees"])


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


def _cleanup_queue_path(project_dir: Path) -> Path:
    return (project_dir / ".autocoder" / "cleanup_queue.json").resolve()


class CleanupQueueItem(BaseModel):
    path: str
    attempts: int = 0
    next_try_at: float = 0.0
    added_at: float = 0.0
    reason: str = ""


class CleanupQueueResponse(BaseModel):
    queue_path: str
    items: list[CleanupQueueItem]


@router.get("/cleanup-queue", response_model=CleanupQueueResponse)
async def get_cleanup_queue(project_name: str):
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    mgr = WorktreeManager(str(project_dir))
    # Use internal format (float epoch); UI formats it.
    items = mgr._load_cleanup_queue()  # type: ignore[attr-defined]
    normalized: list[CleanupQueueItem] = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        normalized.append(
            CleanupQueueItem(
                path=str(it.get("path") or ""),
                attempts=int(it.get("attempts") or 0),
                next_try_at=float(it.get("next_try_at") or 0.0),
                added_at=float(it.get("added_at") or 0.0),
                reason=str(it.get("reason") or ""),
            )
        )
    return CleanupQueueResponse(queue_path=str(_cleanup_queue_path(project_dir)), items=normalized)


class ProcessCleanupQueueRequest(BaseModel):
    max_items: int = Field(default=5, ge=1, le=100)


class ProcessCleanupQueueResponse(BaseModel):
    processed: int
    remaining: int
    queue_path: str


@router.post("/cleanup-queue/process", response_model=ProcessCleanupQueueResponse)
async def process_cleanup_queue(project_name: str, req: ProcessCleanupQueueRequest):
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    mgr = WorktreeManager(str(project_dir))
    processed = int(mgr.process_cleanup_queue(max_items=int(req.max_items)) or 0)
    remaining = len(mgr._load_cleanup_queue())  # type: ignore[attr-defined]
    return ProcessCleanupQueueResponse(
        processed=processed,
        remaining=int(remaining),
        queue_path=str(_cleanup_queue_path(project_dir)),
    )


class ClearCleanupQueueRequest(BaseModel):
    confirm: bool = False


@router.post("/cleanup-queue/clear")
async def clear_cleanup_queue(project_name: str, req: ClearCleanupQueueRequest):
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()
    if not req.confirm:
        raise HTTPException(status_code=400, detail="confirm=true is required")

    path = _cleanup_queue_path(project_dir)
    # Don't delete the file; keep an empty list for easier debugging.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]\n", encoding="utf-8")
    return {"success": True, "queue_path": str(path), "cleared_at": datetime.now(tz=timezone.utc).isoformat()}

