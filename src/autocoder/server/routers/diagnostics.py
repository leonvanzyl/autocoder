"""
Diagnostics Router
==================

Runs deterministic end-to-end fixture tests from the Web UI.

Currently supported:
- QA provider pipeline fixture (Gatekeeper reject -> QA sub-agent -> Gatekeeper merge)
- Parallel mini project fixture (parallel run on a tiny repo)
"""

from __future__ import annotations

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..settings_store import load_advanced_settings


router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


def _find_repo_root_with_scripts() -> Path | None:
    here = Path(__file__).resolve()
    for base in here.parents:
        if (base / "scripts" / "e2e_qa_provider.py").exists() or (base / "scripts" / "e2e_parallel_mini.py").exists():
            return base
    return None


def _default_fixtures_dir() -> Path:
    repo_root = _find_repo_root_with_scripts()
    if repo_root:
        return (repo_root / "dev_archive" / "e2e-fixtures").resolve()
    # Fallback: ~/.autocoder/e2e-fixtures
    return (Path.home() / ".autocoder" / "e2e-fixtures").resolve()


def _effective_out_dir() -> Path:
    s = load_advanced_settings()
    configured = (s.diagnostics_fixtures_dir or "").strip()
    default_dir = _default_fixtures_dir()
    return Path(configured).expanduser().resolve() if configured else default_dir


class QAProviderRunRequest(BaseModel):
    fixture: str = Field(default="node", pattern="^(node|python)$")
    provider: str = Field(default="multi_cli", pattern="^(claude|codex_cli|gemini_cli|multi_cli)$")
    timeout_s: int = Field(default=240, ge=30, le=3600)


class QAProviderRunResponse(BaseModel):
    success: bool
    exit_code: int
    out_dir: str
    log_path: str
    output_tail: str


@router.get("/fixtures-dir")
async def get_fixtures_dir():
    s = load_advanced_settings()
    configured = (s.diagnostics_fixtures_dir or "").strip()
    default_dir = _default_fixtures_dir()
    effective = Path(configured).expanduser().resolve() if configured else default_dir
    return {
        "default_dir": str(default_dir),
        "configured_dir": configured,
        "effective_dir": str(effective),
    }


class DiagnosticsRun(BaseModel):
    name: str
    path: str
    size_bytes: int
    modified_at: str


@router.get("/runs", response_model=list[DiagnosticsRun])
async def list_runs(limit: int = 25):
    limit = max(1, min(200, int(limit)))
    out_dir = _effective_out_dir()
    runs_dir = out_dir / "diagnostics_runs"
    if not runs_dir.exists():
        return []

    items: list[DiagnosticsRun] = []
    for p in sorted(runs_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        st = p.stat()
        items.append(
            DiagnosticsRun(
                name=p.name,
                path=str(p),
                size_bytes=int(st.st_size),
                modified_at=datetime.fromtimestamp(st.st_mtime).isoformat(),
            )
        )
    return items


@router.get("/runs/{name}/tail")
async def tail_run(name: str, max_chars: int = 8000):
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid name")
    max_chars = max(200, min(200000, int(max_chars)))
    out_dir = _effective_out_dir()
    runs_dir = out_dir / "diagnostics_runs"
    path = (runs_dir / name).resolve()
    if not str(path).startswith(str(runs_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "name": name,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "tail": text[-max_chars:],
    }


@router.post("/e2e/qa-provider/run", response_model=QAProviderRunResponse)
async def run_qa_provider(req: QAProviderRunRequest):
    repo_root = _find_repo_root_with_scripts()
    if not repo_root:
        raise HTTPException(status_code=500, detail="Cannot locate repo root (scripts/e2e_qa_provider.py missing)")

    script = repo_root / "scripts" / "e2e_qa_provider.py"
    if not script.exists():
        raise HTTPException(status_code=500, detail="e2e_qa_provider.py not found")

    settings = load_advanced_settings()
    out_dir = _effective_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    runs_dir = out_dir / "diagnostics_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = runs_dir / f"qa-provider-{req.fixture}-{req.provider}-{stamp}.log"

    cmd = [
        sys.executable,
        str(script),
        "--out-dir",
        str(out_dir),
        "--fixture",
        req.fixture,
        "--provider",
        req.provider,
        "--timeout-s",
        str(int(req.timeout_s)),
    ]

    # Apply UI persisted advanced settings as env vars, same as ProcessManager does.
    env = os.environ.copy()
    advanced_env = settings.to_env()
    for k, v in advanced_env.items():
        env.setdefault(k, v)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=int(req.timeout_s) + 30,
        )
    except subprocess.TimeoutExpired:
        log_path.write_text("Timed out running diagnostics\n", encoding="utf-8")
        raise HTTPException(status_code=504, detail="Diagnostics run timed out")

    combined = (proc.stdout or "") + ("\n" if proc.stdout else "") + (proc.stderr or "")
    with log_path.open("w", encoding="utf-8", errors="replace") as f:
        f.write(combined)

    tail = combined[-8000:]
    success = proc.returncode == 0 and "E2E SUCCESS" in combined
    return QAProviderRunResponse(
        success=bool(success),
        exit_code=int(proc.returncode),
        out_dir=str(out_dir),
        log_path=str(log_path),
        output_tail=tail,
    )


class ParallelMiniRunRequest(BaseModel):
    parallel: int = Field(default=3, ge=1, le=5)
    preset: str = Field(default="balanced", max_length=64)
    timeout_s: int = Field(default=1200, ge=60, le=7200)


class ParallelMiniRunResponse(BaseModel):
    success: bool
    exit_code: int
    out_dir: str
    log_path: str
    output_tail: str


@router.post("/e2e/parallel-mini/run", response_model=ParallelMiniRunResponse)
async def run_parallel_mini(req: ParallelMiniRunRequest):
    repo_root = _find_repo_root_with_scripts()
    if not repo_root:
        raise HTTPException(status_code=500, detail="Cannot locate repo root (scripts missing)")

    script = repo_root / "scripts" / "e2e_parallel_mini.py"
    if not script.exists():
        raise HTTPException(status_code=500, detail="e2e_parallel_mini.py not found")

    settings = load_advanced_settings()
    out_dir = _effective_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    runs_dir = out_dir / "diagnostics_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = runs_dir / f"parallel-mini-{stamp}.log"

    cmd = [
        sys.executable,
        str(script),
        "--out-dir",
        str(out_dir),
        "--timeout-s",
        str(int(req.timeout_s)),
        "--parallel",
        str(int(req.parallel)),
        "--preset",
        str(req.preset),
    ]

    env = os.environ.copy()
    advanced_env = settings.to_env()
    for k, v in advanced_env.items():
        env.setdefault(k, v)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=int(req.timeout_s) + 60,
        )
    except subprocess.TimeoutExpired:
        log_path.write_text("Timed out running diagnostics\n", encoding="utf-8")
        raise HTTPException(status_code=504, detail="Diagnostics run timed out")

    combined = (proc.stdout or "") + ("\n" if proc.stdout else "") + (proc.stderr or "")
    with log_path.open("w", encoding="utf-8", errors="replace") as f:
        f.write(combined)

    tail = combined[-8000:]
    success = proc.returncode == 0 and "E2E SUCCESS" in combined
    return ParallelMiniRunResponse(
        success=bool(success),
        exit_code=int(proc.returncode),
        out_dir=str(out_dir),
        log_path=str(log_path),
        output_tail=tail,
    )
