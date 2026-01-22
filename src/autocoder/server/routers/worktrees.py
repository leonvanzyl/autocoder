"""
Worktrees Router
================

API endpoints for inspecting and maintaining git worktrees and cleanup queues.

This primarily exists to expose the deferred cleanup queue used on Windows when
`node_modules` (native .node files) are locked and worktrees can't be deleted immediately.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import time
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


def _load_cleanup_queue_file(project_dir: Path) -> list[dict]:
    path = _cleanup_queue_path(project_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save_cleanup_queue_file(project_dir: Path, items: list[dict]) -> None:
    path = _cleanup_queue_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _rmtree_force(path: Path) -> None:
    def onerror(func, p, excinfo):  # type: ignore[no-untyped-def]
        try:
            os.chmod(p, stat.S_IWRITE)
        except Exception:
            pass
        try:
            func(p)
        except Exception:
            pass

    shutil.rmtree(path, onerror=onerror)


def _process_cleanup_queue(project_dir: Path, *, max_items: int) -> int:
    """
    Best-effort deletion of deferred-cleanup directories.

    This intentionally does NOT require the project to be a git repo: cleanup queues can exist
    even when worktrees were never created (or when users are just cleaning up a directory).
    """
    items = _load_cleanup_queue_file(project_dir)
    if not items:
        return 0

    now = time.time()
    processed = 0
    remaining: list[dict] = []

    def backoff_s(attempts: int) -> float:
        # 5s, 10s, 20s, ... up to 10 minutes
        return float(min(600, 5 * (2 ** max(0, attempts))))

    for item in items:
        if processed >= max_items:
            remaining.append(item)
            continue

        try:
            next_try_at = float(item.get("next_try_at", 0.0))
        except Exception:
            next_try_at = 0.0
        if next_try_at and next_try_at > now:
            remaining.append(item)
            continue

        p = Path(str(item.get("path") or ""))
        if not p.exists():
            processed += 1
            continue

        try:
            _rmtree_force(p)
            processed += 1
            continue
        except Exception as e:
            attempts = int(item.get("attempts") or 0) + 1
            item["attempts"] = attempts
            item["last_error"] = str(e)
            item["next_try_at"] = now + backoff_s(attempts)
            remaining.append(item)
            processed += 1

    _save_cleanup_queue_file(project_dir, remaining)
    return processed


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

    # Use internal format (float epoch); UI formats it.
    # IMPORTANT: do not require a git repo here; a project can exist without `.git`.
    try:
        mgr = WorktreeManager(str(project_dir))
        items = mgr._load_cleanup_queue()  # type: ignore[attr-defined]
    except Exception:
        # Project may not be a git repo (or WorktreeManager may fail); fall back to plain JSON queue.
        items = _load_cleanup_queue_file(project_dir)
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

    try:
        mgr = WorktreeManager(str(project_dir))
        processed = int(mgr.process_cleanup_queue(max_items=int(req.max_items)) or 0)
        remaining = len(mgr._load_cleanup_queue())  # type: ignore[attr-defined]
    except Exception:
        processed = int(_process_cleanup_queue(project_dir, max_items=int(req.max_items)) or 0)
        remaining = len(_load_cleanup_queue_file(project_dir))
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
