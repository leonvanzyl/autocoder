"""
Logs Router
===========

API endpoints for inspecting and pruning runtime log files for a project.

Currently targets parallel worker logs in `.autocoder/logs/*.log`.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autocoder.core.logs import prune_worker_logs, prune_gatekeeper_artifacts


router = APIRouter(prefix="/api/projects/{project_name}/logs", tags=["logs"])


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


def _logs_dir(project_dir: Path) -> Path:
    return (project_dir / ".autocoder" / "logs").resolve()


def _ensure_logs_path(logs_dir: Path, filename: str) -> Path:
    # Disallow path traversal and only allow .log files.
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not filename.endswith(".log"):
        raise HTTPException(status_code=400, detail="Only .log files are supported")
    p = (logs_dir / filename).resolve()
    if logs_dir not in p.parents:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return p


def _tail_lines(path: Path, *, max_lines: int = 400, max_bytes: int = 1024 * 1024) -> list[str]:
    """
    Read the last N lines of a file without loading the whole file.
    """
    max_lines = max(1, min(int(max_lines), 5000))
    max_bytes = max(1024, min(int(max_bytes), 10 * 1024 * 1024))

    try:
        size = path.stat().st_size
    except OSError:
        raise HTTPException(status_code=404, detail="Log file not found")

    # Fast path for small files.
    if size <= max_bytes:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raise HTTPException(status_code=500, detail="Failed to read log file")
        return text.splitlines()[-max_lines:]

    # Seek from end, accumulating blocks until enough newlines or byte cap.
    newline = b"\n"
    block = 64 * 1024
    data = b""
    read = 0
    try:
        with open(path, "rb") as f:
            offset = size
            while offset > 0 and read < max_bytes:
                step = min(block, offset, max_bytes - read)
                offset -= step
                f.seek(offset)
                chunk = f.read(step)
                data = chunk + data
                read += step
                if data.count(newline) >= max_lines + 5:
                    break
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to read log file")

    text = data.decode("utf-8", errors="replace")
    return text.splitlines()[-max_lines:]


class WorkerLogFile(BaseModel):
    name: str
    size_bytes: int
    modified_at: str


class WorkerLogsListResponse(BaseModel):
    directory: str
    files: list[WorkerLogFile]


@router.get("/worker", response_model=WorkerLogsListResponse)
async def list_worker_logs(project_name: str):
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()
    logs_dir = _logs_dir(project_dir)

    if not logs_dir.exists():
        return WorkerLogsListResponse(directory=str(logs_dir), files=[])

    files: list[WorkerLogFile] = []
    for p in logs_dir.glob("*.log"):
        try:
            st = p.stat()
        except OSError:
            continue
        files.append(
            WorkerLogFile(
                name=p.name,
                size_bytes=int(st.st_size),
                modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            )
        )

    files.sort(key=lambda f: f.modified_at, reverse=True)
    return WorkerLogsListResponse(directory=str(logs_dir), files=files)


class WorkerLogTailResponse(BaseModel):
    name: str
    size_bytes: int
    modified_at: str
    lines: list[str]


@router.get("/worker/{filename}", response_model=WorkerLogTailResponse)
async def get_worker_log(project_name: str, filename: str, tail: int = 400):
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()
    logs_dir = _logs_dir(project_dir)
    path = _ensure_logs_path(logs_dir, filename)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        st = path.stat()
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to stat log file")

    lines = _tail_lines(path, max_lines=tail)
    return WorkerLogTailResponse(
        name=path.name,
        size_bytes=int(st.st_size),
        modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        lines=lines,
    )


class PruneWorkerLogsRequest(BaseModel):
    keep_days: int = Field(default=7, ge=0, le=3650)
    keep_files: int = Field(default=200, ge=0, le=100000)
    max_mb: int = Field(default=200, ge=0, le=100000)
    dry_run: bool = False
    include_artifacts: bool = False


class PruneWorkerLogsResponse(BaseModel):
    deleted_files: int
    deleted_bytes: int
    kept_files: int
    kept_bytes: int


@router.post("/worker/prune", response_model=PruneWorkerLogsResponse)
async def prune_worker_logs_endpoint(project_name: str, req: PruneWorkerLogsRequest):
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    # Protect against accidental huge deletions in a shared environment.
    # Still allows the action, but requires explicit values if defaults are overridden.
    if req.keep_files == 0 and req.keep_days == 0 and req.max_mb == 0 and not req.dry_run:
        raise HTTPException(status_code=400, detail="Refusing to delete all logs without dry_run")

    logs_result = prune_worker_logs(
        project_dir,
        keep_days=req.keep_days,
        keep_files=req.keep_files,
        max_total_mb=req.max_mb,
        dry_run=req.dry_run,
    )
    artifacts_result = None
    if req.include_artifacts:
        artifacts_result = prune_gatekeeper_artifacts(
            project_dir,
            keep_days=req.keep_days,
            keep_files=req.keep_files,
            max_total_mb=req.max_mb,
            dry_run=req.dry_run,
        )
    return PruneWorkerLogsResponse(
        deleted_files=logs_result.deleted_files + (artifacts_result.deleted_files if artifacts_result else 0),
        deleted_bytes=logs_result.deleted_bytes + (artifacts_result.deleted_bytes if artifacts_result else 0),
        kept_files=logs_result.kept_files + (artifacts_result.kept_files if artifacts_result else 0),
        kept_bytes=logs_result.kept_bytes + (artifacts_result.kept_bytes if artifacts_result else 0),
    )


@router.delete("/worker/{filename}")
async def delete_worker_log(project_name: str, filename: str):
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()
    logs_dir = _logs_dir(project_dir)
    path = _ensure_logs_path(logs_dir, filename)

    if not path.exists():
        return {"success": True, "message": "Already deleted"}

    # Only delete files inside logs dir.
    try:
        path.unlink()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete log file: {e}")

    return {"success": True, "message": f"Deleted {filename}"}
