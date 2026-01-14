"""
Generate Router
==============

REST endpoint for generating spec/plan artifacts using external model CLIs (Codex/Gemini)
with optional synthesis.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

import anyio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autocoder.agent.registry import get_project_path
from autocoder.generation.multi_model import MultiModelGenerateConfig, generate_multi_model_artifact


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["generate"])


def validate_project_name(name: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_-]{1,50}$", name))


class GenerateRequest(BaseModel):
    kind: Literal["spec", "plan"] = "spec"
    prompt: str = Field(min_length=1)

    agents: str = ""  # csv: codex,gemini
    synthesizer: Literal["", "none", "claude", "codex", "gemini"] = ""
    no_synthesize: bool = False
    timeout_s: int = Field(default=0, ge=0, le=36000)

    out: str = ""  # optional absolute path


class GenerateResponse(BaseModel):
    output_path: str
    drafts_dir: str


@router.post("/{project_name}", response_model=GenerateResponse)
async def generate_for_project(project_name: str, req: GenerateRequest) -> GenerateResponse:
    if not validate_project_name(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")

    project_dir = get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found in registry")
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Resolve prompt and config
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    agents = [a.strip().lower() for a in (req.agents or "").replace(";", ",").split(",") if a.strip()]
    agents = [a for a in agents if a in {"codex", "gemini"}]

    cfg = MultiModelGenerateConfig.from_env(
        agents=agents or None,
        synthesizer=(req.synthesizer if req.synthesizer else None),  # type: ignore[arg-type]
        timeout_s=(req.timeout_s if req.timeout_s and req.timeout_s > 0 else None),
    )

    out_path = Path(req.out).resolve() if req.out else None

    def _run() -> dict[str, str]:
        return generate_multi_model_artifact(
            project_dir=project_dir,
            kind=req.kind,
            user_prompt=prompt,
            cfg=cfg,
            output_path=out_path,
            synthesize=not bool(req.no_synthesize),
        )

    try:
        result = await anyio.to_thread.run_sync(_run)
    except Exception as e:
        logger.exception("Generate failed")
        raise HTTPException(status_code=500, detail=f"Generate failed: {e}") from e

    return GenerateResponse(output_path=result["output_path"], drafts_dir=result["drafts_dir"])

