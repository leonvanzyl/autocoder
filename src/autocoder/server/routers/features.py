"""
Features Router
===============

API endpoints for feature/test case management.

This UI layer uses the unified project database: `agent_system.db`.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from autocoder.core.database import get_database
from ..schemas import FeatureCreate, FeatureListResponse, FeatureResponse, FeatureUpdate


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_name}/features", tags=["features"])


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    from autocoder.agent.registry import get_project_path

    p = get_project_path(project_name)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")
    return Path(p)


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r"^[a-zA-Z0-9_-]{1,50}$", name):
        raise HTTPException(status_code=400, detail="Invalid project name")
    return name


def _parse_steps(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(s) for s in raw]
    if isinstance(raw, str):
        if not raw.strip():
            return []
        try:
            decoded = json.loads(raw)
        except Exception:
            return []
        if isinstance(decoded, list):
            return [str(s) for s in decoded]
    return []


def _is_retry_eligible(next_attempt_at: object) -> bool:
    if not next_attempt_at:
        return True
    s = str(next_attempt_at).strip()
    if not s:
        return True
    # SQLite timestamps are typically `YYYY-MM-DD HH:MM:SS` or ISO-ish.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt <= datetime.now()
        except Exception:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # Naive compare fallback
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt <= datetime.now()
    except Exception:
        # If unparseable, be conservative.
        return False


def _feature_to_response(row: dict, *, deps: list[dict[str, object]] | None = None) -> FeatureResponse:
    status = (row.get("status") or "").upper()
    dep_rows = deps or []
    waiting_on = [int(d["id"]) for d in dep_rows if str(d.get("status") or "").upper() != "DONE" and d.get("id")]
    ready = bool(
        status == "PENDING"
        and not waiting_on
        and _is_retry_eligible(row.get("next_attempt_at"))
    )
    return FeatureResponse(
        id=int(row["id"]),
        priority=int(row.get("priority") or 0),
        category=str(row.get("category") or ""),
        name=str(row.get("name") or ""),
        description=str(row.get("description") or ""),
        steps=_parse_steps(row.get("steps")),
        status=status or "PENDING",
        passes=bool(row.get("passes")) or status == "DONE",
        in_progress=status == "IN_PROGRESS",
        attempts=int(row.get("attempts") or 0),
        last_error=(str(row.get("last_error")) if row.get("last_error") is not None else None),
        last_artifact_path=(str(row.get("last_artifact_path")) if row.get("last_artifact_path") is not None else None),
        depends_on=[int(x) for x in (row.get("depends_on") or [])],
        ready=ready,
        waiting_on=waiting_on,
    )


def _get_next_priority(project_dir: Path) -> int:
    db = get_database(str(project_dir))
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(priority), 0) FROM features")
        max_priority = int(cursor.fetchone()[0] or 0)
    return max_priority + 1


@router.get("", response_model=FeatureListResponse)
async def list_features(project_name: str):
    """
    List all features for a project organized by status.

    Returns features in three lists:
    - pending: status=PENDING (and BLOCKED)
    - in_progress: status=IN_PROGRESS
    - done: status=DONE (passes=true)
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db = get_database(str(project_dir))

    try:
        pending_rows = db.get_features_by_status("PENDING")
        blocked_rows = db.get_features_by_status("BLOCKED")
        in_progress_rows = db.get_features_by_status("IN_PROGRESS")
        done_rows = db.get_features_by_status("DONE")

        dep_map = db.get_dependency_statuses([int(r["id"]) for r in pending_rows])

        return FeatureListResponse(
            pending=[
                _feature_to_response(r, deps=dep_map.get(int(r["id"]), [])) for r in pending_rows
            ]
            + [_feature_to_response(r) for r in blocked_rows],
            in_progress=[_feature_to_response(r) for r in in_progress_rows],
            done=[_feature_to_response(r) for r in done_rows],
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error in list_features")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.post("", response_model=FeatureResponse)
async def create_feature(project_name: str, feature: FeatureCreate):
    """Create a new feature/test case manually."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db = get_database(str(project_dir))

    try:
        priority = feature.priority if feature.priority is not None else _get_next_priority(project_dir)
        feature_id = db.create_feature(
            name=feature.name,
            description=feature.description,
            category=feature.category,
            steps=json.dumps(feature.steps),
            priority=int(priority),
        )
        row = db.get_feature(int(feature_id))
        if not row:
            raise HTTPException(status_code=500, detail="Failed to load created feature")
        return _feature_to_response(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create feature")
        raise HTTPException(status_code=500, detail="Failed to create feature")


@router.get("/{feature_id}", response_model=FeatureResponse)
async def get_feature(project_name: str, feature_id: int):
    """Get details of a specific feature."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db = get_database(str(project_dir))

    try:
        row = db.get_feature(int(feature_id))
        if not row:
            raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")
        return _feature_to_response(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error in get_feature")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.patch("/{feature_id}", response_model=FeatureResponse)
async def update_feature(project_name: str, feature_id: int, update: FeatureUpdate):
    """
    Update a feature's details.

    Only non-completed features can be edited (PENDING/IN_PROGRESS/BLOCKED).
    This is useful when the agent is stuck or instructions need correction.
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db = get_database(str(project_dir))

    try:
        row = db.get_feature(int(feature_id))
        if not row:
            raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

        status = str(row.get("status") or "").upper()
        if bool(row.get("passes")) or status == "DONE":
            raise HTTPException(status_code=400, detail="Cannot edit a completed feature")

        payload = update.model_dump(exclude_none=True)
        if not payload:
            raise HTTPException(status_code=400, detail="No updates provided")

        steps = payload.get("steps")
        steps_json = json.dumps(steps) if steps is not None else None

        updated = db.update_feature_details(
            int(feature_id),
            category=payload.get("category"),
            name=payload.get("name"),
            description=payload.get("description"),
            steps=steps_json,
            priority=payload.get("priority"),
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")
        return _feature_to_response(updated)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update feature")
        raise HTTPException(status_code=500, detail="Failed to update feature")


@router.delete("/{feature_id}")
async def delete_feature(project_name: str, feature_id: int):
    """Delete a feature."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db = get_database(str(project_dir))

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM branches WHERE feature_id = ?", (int(feature_id),))
            cursor.execute("UPDATE agent_heartbeats SET feature_id = NULL WHERE feature_id = ?", (int(feature_id),))
            cursor.execute("DELETE FROM features WHERE id = ?", (int(feature_id),))
            conn.commit()
            if cursor.rowcount <= 0:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")
        return {"success": True, "message": f"Feature {feature_id} deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete feature")
        raise HTTPException(status_code=500, detail="Failed to delete feature")


@router.patch("/{feature_id}/skip")
async def skip_feature(project_name: str, feature_id: int):
    """
    Mark a feature as skipped by moving it to the end of the priority queue.

    This doesn't delete the feature; it increases priority so it will be processed last.
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db = get_database(str(project_dir))

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM features WHERE id = ?", (int(feature_id),))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            cursor.execute("SELECT COALESCE(MAX(priority), 0) FROM features")
            max_priority = int(cursor.fetchone()[0] or 0)
            new_priority = max_priority + 1000

            cursor.execute(
                "UPDATE features SET priority = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_priority, int(feature_id)),
            )
            conn.commit()

        return {"success": True, "message": f"Feature {feature_id} moved to end of queue"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to skip feature")
        raise HTTPException(status_code=500, detail="Failed to skip feature")
