"""
E2E Dummy Worker
================

Deterministic worker used by E2E fixtures to exercise the parallel orchestration pipeline without
calling any LLMs.

This script is only used when `AUTOCODER_E2E_DUMMY_WORKER=1` is set by a fixture runner.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
from pathlib import Path

from autocoder.core.database import get_database


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _ensure_git_identity(repo: Path) -> None:
    with contextlib.suppress(Exception):
        _run(["git", "config", "user.email", "e2e@example.com"], repo)
        _run(["git", "config", "user.name", "AutoCoder E2E"], repo)


def _write_feature_changes(worktree: Path, feature_id: int, feature_name: str) -> None:
    name = (feature_name or "").lower()
    if "affiliate" in name:
        (worktree / "AFFILIATE.md").write_text(
            "# Affiliate Disclosure\n\nThis is a demo fixture project.\n",
            encoding="utf-8",
        )
        return
    if "app.py" in name or "helper" in name:
        (worktree / "app.py").write_text(
            "def get_game_slug() -> str:\n    return 'fortune-of-dragons'\n",
            encoding="utf-8",
        )
        tests = worktree / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        (tests / "test_app.py").write_text(
            "from app import get_game_slug\n\n\ndef test_get_game_slug():\n    assert get_game_slug() == 'fortune-of-dragons'\n",
            encoding="utf-8",
        )
        return
    if "readme" in name or "instructions" in name:
        readme = worktree / "README.md"
        existing = readme.read_text(encoding="utf-8", errors="replace") if readme.exists() else ""
        existing = existing.rstrip() + "\n\n## Running\n\n- `python -m pytest -q`\n- `AFFILIATE.md` is required by acceptance checks.\n"
        readme.write_text(existing + "\n", encoding="utf-8")
        return

    # Fallback: create a marker file so Gatekeeper sees a change.
    (worktree / f"FEATURE_{feature_id}.txt").write_text("ok\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--feature-id", type=int, required=True)
    ap.add_argument("--worktree-path", required=True)
    # Accept orchestrator/worker common flags for compatibility; ignored for this dummy worker.
    ap.add_argument("--model", default="")
    ap.add_argument("--max-iterations", type=int, default=0)
    ap.add_argument("--yolo", action="store_true")
    ap.add_argument("--heartbeat-seconds", type=int, default=0)
    ap.add_argument("--api-port", type=int, default=5000)
    ap.add_argument("--web-port", type=int, default=5173)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    worktree = Path(args.worktree_path).resolve()

    # Keep behavior aligned with real workers.
    os.environ["AUTOCODER_API_PORT"] = str(args.api_port)
    os.environ["AUTOCODER_WEB_PORT"] = str(args.web_port)
    os.environ["PORT"] = str(args.api_port)
    os.environ["VITE_PORT"] = str(args.web_port)
    os.environ["AUTOCODER_REQUIRE_GATEKEEPER"] = "1"

    db = get_database(str(project_dir))
    feature = db.get_feature(int(args.feature_id)) or {}
    feature_name = str(feature.get("name") or "")

    _ensure_git_identity(worktree)
    _write_feature_changes(worktree, int(args.feature_id), feature_name)

    _run(["git", "add", "."], worktree)
    _run(["git", "commit", "-m", f"e2e: implement feature {args.feature_id}"], worktree)

    # Submit for Gatekeeper verification.
    db.mark_feature_ready_for_verification(int(args.feature_id))
    db.mark_agent_completed(args.agent_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
