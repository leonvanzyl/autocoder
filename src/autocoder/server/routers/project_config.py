"""
Project Config Router
=====================

Read/write helpers for per-project `autocoder.yaml` (Gatekeeper verification commands + review config).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autocoder.agent.registry import get_project_path
from autocoder.core.project_config import load_project_config, infer_preset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_name}/config", tags=["config"])


def _validate_project_name(name: str) -> None:
    if not re.match(r"^[a-zA-Z0-9_-]{1,50}$", name):
        raise HTTPException(status_code=400, detail="Invalid project name")


def _project_dir(project_name: str) -> Path:
    _validate_project_name(project_name)
    p = get_project_path(project_name)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found in registry")
    d = Path(p).resolve()
    if not d.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")
    return d


class AutocoderYamlResponse(BaseModel):
    exists: bool
    path: str
    content: str
    inferred_preset: str | None = None
    resolved_commands: list[str] = Field(default_factory=list)


class AutocoderYamlUpdateRequest(BaseModel):
    content: str = Field(min_length=1)


@router.get("/autocoder", response_model=AutocoderYamlResponse)
async def get_autocoder_yaml(project_name: str) -> AutocoderYamlResponse:
    project_dir = _project_dir(project_name)
    path = project_dir / "autocoder.yaml"
    exists = path.exists()
    content = ""
    if exists:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read autocoder.yaml: {e}") from e

    inferred = infer_preset(project_dir)
    try:
        resolved = load_project_config(project_dir)
        resolved_names = sorted([k for k, v in (resolved.commands or {}).items() if v is not None])
    except Exception:
        resolved_names = []

    return AutocoderYamlResponse(
        exists=exists,
        path=str(path),
        content=content,
        inferred_preset=inferred,
        resolved_commands=resolved_names,
    )


@router.put("/autocoder", response_model=AutocoderYamlResponse)
async def put_autocoder_yaml(project_name: str, req: AutocoderYamlUpdateRequest) -> AutocoderYamlResponse:
    project_dir = _project_dir(project_name)
    path = project_dir / "autocoder.yaml"

    text = (req.content or "").replace("\r\n", "\n").strip() + "\n"
    try:
        parsed = yaml.safe_load(text) if text.strip() else {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}") from e
    if parsed is not None and not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="autocoder.yaml must contain a YAML mapping/object at top level")

    try:
        path.write_text(text, encoding="utf-8")
    except Exception as e:
        logger.exception("Failed to write autocoder.yaml")
        raise HTTPException(status_code=500, detail=f"Failed to write autocoder.yaml: {e}") from e

    inferred = infer_preset(project_dir)
    resolved = load_project_config(project_dir)
    resolved_names = sorted([k for k, v in (resolved.commands or {}).items() if v is not None])

    return AutocoderYamlResponse(
        exists=True,
        path=str(path),
        content=text,
        inferred_preset=inferred,
        resolved_commands=resolved_names,
    )

