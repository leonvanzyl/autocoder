#!/usr/bin/env python3
"""
E2E Fixture: Parallel Mini Project
=================================

Creates a small Python repo + 3 dependent features and runs AutoCoder parallel mode end-to-end:

  claim -> worktrees -> worker -> Gatekeeper verify/merge -> DONE

This fixture is intentionally tiny but exercises:
- dependency-aware claiming (features 2/3 depend on 1)
- per-feature planner artifact (optional; controlled by env)
- controller preflight (optional; controlled by env)
- Gatekeeper temp-worktree verification + merge

Usage:
  python scripts/e2e_parallel_mini.py --out-dir "G:/Apps/autocoder-e2e-fixtures" --timeout-s 1200
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from autocoder.core.database import Database  # noqa: E402
from autocoder.core.orchestrator import Orchestrator  # noqa: E402


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _ensure_git_identity(repo: Path) -> None:
    _run(["git", "config", "user.email", "e2e@example.com"], repo)
    _run(["git", "config", "user.name", "AutoCoder E2E"], repo)


def _safe_remove_dir(path: Path) -> None:
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
        return
    except Exception:
        pass

    quarantine_root = path.parent / ".quarantine"
    quarantine_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = quarantine_root / f"{path.name}-{stamp}"
    try:
        path.rename(target)
    except Exception:
        # Last resort: leave it in place.
        return


def create_fixture(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], project_dir)
    _ensure_git_identity(project_dir)

    (project_dir / "autocoder.yaml").write_text(
        """
# autocoder.yaml - deterministic verification for e2e fixture
commands:
  test:
    command: "python -m pytest -q"
    timeout: 120
  acceptance:
    command: "python -c \\"import pathlib; assert pathlib.Path('AFFILIATE.md').exists()\\""
    timeout: 30
""".lstrip(),
        encoding="utf-8",
    )
    (project_dir / "pyproject.toml").write_text(
        """
[project]
name = "autocoder_e2e_parallel_fixture"
version = "0.0.0"
requires-python = ">=3.10"
""".lstrip(),
        encoding="utf-8",
    )
    (project_dir / "README.md").write_text(
        """
# AutoCoder E2E Parallel Fixture

Minimal project used to validate parallel mode end-to-end.
""".lstrip(),
        encoding="utf-8",
    )
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests" / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    _run(["git", "add", "."], project_dir)
    _run(["git", "commit", "-m", "init e2e fixture"], project_dir)


def seed_features(project_dir: Path) -> None:
    db_path = project_dir / "agent_system.db"
    if db_path.exists():
        db_path.unlink()
    db = Database(str(db_path))
    fid1 = int(
        db.create_feature(
            "Create AFFILIATE.md",
            "Add a short affiliate disclosure + game summary file AFFILIATE.md",
            "content",
        )
    )
    db.create_feature(
        "Add app.py helper",
        "Create app.py with function get_game_slug() returning 'fortune-of-dragons' and add a pytest asserting it.",
        "backend",
        depends_on=[fid1],
    )
    db.create_feature(
        "Update README with run instructions",
        "Update README.md with a short section explaining the purpose of AFFILIATE.md and how to run tests.",
        "docs",
        depends_on=[fid1],
    )


def run_parallel(project_dir: Path, *, parallel: int, preset: str, timeout_s: int) -> int:
    # Ensure core safety defaults if the caller didn't set them.
    os.environ.setdefault("AUTOCODER_REQUIRE_GATEKEEPER", "1")
    # Keep fixture fast/deterministic by default. Users can override by exporting env vars.
    os.environ.setdefault("AUTOCODER_CONTROLLER_ENABLED", "0")
    os.environ.setdefault("AUTOCODER_PLANNER_ENABLED", "0")
    # Deterministic worker for fixtures (no LLM required).
    os.environ.setdefault("AUTOCODER_E2E_DUMMY_WORKER", "1")

    orch = Orchestrator(str(project_dir), max_agents=int(parallel), model_preset=str(preset))

    start = time.time()
    # Orchestrator is async; keep a hard wall-clock timeout.
    try:
        import asyncio

        asyncio.run(asyncio.wait_for(orch.run_parallel_agents(), timeout=float(timeout_s)))
    except Exception as e:
        elapsed = time.time() - start
        print(f"E2E ERROR after {elapsed:.1f}s: {e}")
        return 2

    db = Database(str(project_dir / "agent_system.db"))
    rows = []
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id,status,passes FROM features ORDER BY id")
        rows = [dict(r) for r in cur.fetchall()]
    ok = all(str(r.get("status") or "").upper() == "DONE" and bool(r.get("passes")) for r in rows)
    if ok:
        print("E2E SUCCESS: all features DONE and passing")
        return 0
    print("E2E FAILED: not all features are DONE/passing")
    print(rows)
    return 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(Path.cwd() / "autocoder-e2e-fixtures"))
    ap.add_argument("--timeout-s", type=int, default=1200)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--preset", default="balanced")
    args = ap.parse_args()

    root = Path(args.out_dir).resolve()
    project_dir = root / "parallel-mini"
    if project_dir.exists():
        _safe_remove_dir(project_dir)
    create_fixture(project_dir)
    seed_features(project_dir)
    return run_parallel(project_dir, parallel=int(args.parallel), preset=str(args.preset), timeout_s=int(args.timeout_s))


if __name__ == "__main__":
    raise SystemExit(main())
