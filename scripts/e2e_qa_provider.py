#!/usr/bin/env python3
"""
E2E Fixture: QA Provider Pipeline
================================

Creates a minimal git repo + agent_system.db state that deterministically triggers:

  Gatekeeper reject -> QA sub-agent spawn -> patch/commit -> Gatekeeper approve+merge

This avoids relying on a full "feature implementation" agent to create failures.

Usage (Windows / macOS / Linux):
  python scripts/e2e_qa_provider.py --out-dir "G:/Apps/autocoder-e2e-fixtures" --engines '["codex_cli","gemini_cli","claude_patch"]'
"""

from __future__ import annotations

import argparse
import contextlib
import json
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

from autocoder.core.orchestrator import Orchestrator  # noqa: E402
from autocoder.core.database import Database  # noqa: E402
from autocoder.core.engine_settings import EngineSettings, save_engine_settings  # noqa: E402


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _ensure_git_identity(repo: Path) -> None:
    _run(["git", "config", "user.email", "e2e@example.com"], repo)
    _run(["git", "config", "user.name", "AutoCoder E2E"], repo)


def create_fixture(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], project_dir)
    _ensure_git_identity(project_dir)
    _run(["git", "checkout", "-b", "main"], project_dir)

    (project_dir / "autocoder.yaml").write_text(
        """
preset: null
commands:
  test:
    command: "node test.js"
    timeout: 30
""".lstrip(),
        encoding="utf-8",
    )
    (project_dir / "test.js").write_text('console.log("ok"); process.exit(0)\n', encoding="utf-8")
    _run(["git", "add", "."], project_dir)
    _run(["git", "commit", "-m", "init passing"], project_dir)

    # Feature branch introduces deterministic failure (exit 1).
    _run(["git", "checkout", "-b", "feat/1"], project_dir)
    (project_dir / "test.js").write_text('console.log("fail"); process.exit(1)\n', encoding="utf-8")
    _run(["git", "add", "test.js"], project_dir)
    _run(["git", "commit", "-m", "break tests"], project_dir)
    _run(["git", "checkout", "main"], project_dir)

    # Seed DB to look like a worker finished and submitted for Gatekeeper verification.
    db_path = project_dir / "agent_system.db"
    if db_path.exists():
        db_path.unlink()
    db = Database(str(db_path))
    feature_id = int(db.create_feature("E2E: QA engine chain fixes Gatekeeper failure", "Deterministic failure", "testing"))

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE features
            SET status = 'IN_PROGRESS',
                assigned_agent_id = ?,
                branch_name = ?,
                review_status = 'READY_FOR_VERIFICATION',
                passes = FALSE
            WHERE id = ?
            """,
            ("seed-agent", "feat/1", feature_id),
        )
        conn.commit()

    db.register_agent(
        agent_id="seed-agent",
        pid=0,
        worktree_path="",
        feature_id=feature_id,
        api_port=5000,
        web_port=5173,
        log_file_path="",
    )
    db.mark_agent_completed("seed-agent")

    (project_dir / ".autocoder").mkdir(parents=True, exist_ok=True)
    (project_dir / ".autocoder" / "fixture.json").write_text(
        json.dumps({"feature_id": feature_id, "branch_name": "feat/1"}, indent=2),
        encoding="utf-8",
    )

def create_fixture_python(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], project_dir)
    _ensure_git_identity(project_dir)
    _run(["git", "checkout", "-b", "main"], project_dir)

    # Use a venv with system site packages so pytest is available without downloading wheels.
    (project_dir / "autocoder.yaml").write_text(
        """
preset: null
commands:
  setup:
    command: "{PY} -m venv --system-site-packages .venv"
    timeout: 60
  test:
    command: "{VENV_PY} -m pytest -q"
    timeout: 60
""".lstrip(),
        encoding="utf-8",
    )
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    _run(["git", "add", "."], project_dir)
    _run(["git", "commit", "-m", "init passing"], project_dir)

    # Feature branch introduces deterministic failure.
    _run(["git", "checkout", "-b", "feat/1"], project_dir)
    (project_dir / "tests" / "test_ok.py").write_text("def test_ok():\n    assert False\n", encoding="utf-8")
    _run(["git", "add", "tests/test_ok.py"], project_dir)
    _run(["git", "commit", "-m", "break tests"], project_dir)
    _run(["git", "checkout", "main"], project_dir)

    db_path = project_dir / "agent_system.db"
    if db_path.exists():
        db_path.unlink()
    db = Database(str(db_path))
    feature_id = int(db.create_feature("E2E: QA engine chain fixes pytest failure", "Deterministic pytest failure", "testing"))

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE features
            SET status = 'IN_PROGRESS',
                assigned_agent_id = ?,
                branch_name = ?,
                review_status = 'READY_FOR_VERIFICATION',
                passes = FALSE
            WHERE id = ?
            """,
            ("seed-agent", "feat/1", feature_id),
        )
        conn.commit()

    db.register_agent(
        agent_id="seed-agent",
        pid=0,
        worktree_path="",
        feature_id=feature_id,
        api_port=5000,
        web_port=5173,
        log_file_path="",
    )
    db.mark_agent_completed("seed-agent")

    (project_dir / ".autocoder").mkdir(parents=True, exist_ok=True)
    (project_dir / ".autocoder" / "fixture.json").write_text(
        json.dumps({"feature_id": feature_id, "branch_name": "feat/1"}, indent=2),
        encoding="utf-8",
    )

def _parse_engines(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        data = None
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        v = item.strip().lower()
        if v in {"codex_cli", "gemini_cli", "claude_patch"}:
            out.append(v)
    # de-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for v in out:
        if v in seen:
            continue
        seen.add(v)
        deduped.append(v)
    return deduped


def run_e2e(project_dir: Path, *, engines: list[str], timeout_s: int) -> int:
    os.environ["AUTOCODER_REQUIRE_GATEKEEPER"] = "1"
    os.environ["AUTOCODER_QA_SUBAGENT_ENABLED"] = "1"
    os.environ.setdefault("AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS", "2")
    os.environ.setdefault("AUTOCODER_QA_FIX_ENABLED", "1")
    os.environ.setdefault("AUTOCODER_QA_MAX_SESSIONS", "3")

    settings = EngineSettings.defaults()
    settings.chains["qa_fix"] = settings.chains["qa_fix"].model_copy(update={"engines": engines})
    save_engine_settings(str(project_dir), settings)

    orch = Orchestrator(str(project_dir), max_agents=0, model_preset="custom")
    # Reserve the synthetic seed-agent port allocation to avoid noisy warnings when releasing.
    with contextlib.suppress(Exception):
        orch.port_allocator.reserve_ports("seed-agent", 5000, 5173)
    db = Database(str(project_dir / "agent_system.db"))
    fixture = json.loads((project_dir / ".autocoder" / "fixture.json").read_text(encoding="utf-8"))
    feature_id = int(fixture.get("feature_id") or 1)

    start = time.time()
    while time.time() - start < timeout_s:
        orch._recover_completed_agents()
        row = db.get_feature(feature_id) or {}
        status = str(row.get("status") or "").upper()
        if status == "DONE" or bool(row.get("passes")):
            print("E2E SUCCESS: feature merged and marked passing")
            return 0
        if status == "BLOCKED":
            print("E2E FAILED: feature BLOCKED")
            print(row.get("last_error") or "")
            return 2
        time.sleep(2)

    print("E2E TIMEOUT")
    row = db.get_feature(feature_id) or {}
    print(row.get("status"), row.get("last_error"))
    return 3


def _safe_remove_dir(path: Path) -> None:
    """
    Best-effort removal on Windows where file locks can occur.

    If deletion fails, quarantine the directory instead of crashing.
    """
    if not path.exists():
        return
    for _ in range(5):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            time.sleep(0.5)
        except OSError:
            time.sleep(0.5)

    quarantine_root = path.parent / ".quarantine"
    quarantine_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = quarantine_root / f"{path.name}-{stamp}"
    path.rename(target)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(Path.cwd() / "autocoder-e2e-fixtures"))
    ap.add_argument("--fixture", default="node", choices=["node", "python"])
    ap.add_argument("--engines", default='["codex_cli","gemini_cli","claude_patch"]')
    ap.add_argument("--timeout-s", type=int, default=180)
    args = ap.parse_args()

    root = Path(args.out_dir).resolve()
    project_dir = root / ("qa-provider-python" if args.fixture == "python" else "qa-provider-node")
    if project_dir.exists():
        _safe_remove_dir(project_dir)
    if args.fixture == "python":
        create_fixture_python(project_dir)
    else:
        create_fixture(project_dir)

    engines = _parse_engines(args.engines)
    if not engines:
        print("No valid engines provided; expected JSON list with codex_cli/gemini_cli/claude_patch", file=sys.stderr)
        return 4

    if "codex_cli" in engines and shutil.which("codex") is None:
        print("codex CLI not found; install it or remove codex_cli from --engines", file=sys.stderr)
        return 4
    if "gemini_cli" in engines and shutil.which("gemini") is None:
        print("gemini CLI not found; install it or remove gemini_cli from --engines", file=sys.stderr)
        return 4
    if "claude_patch" in engines:
        credentials_path = Path.home() / ".claude" / ".credentials.json"
        has_claude = bool(shutil.which("claude") or credentials_path.exists() or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
        if not has_claude:
            print("claude CLI/credentials not found; install Claude Code or set credentials", file=sys.stderr)
            return 4

    return run_e2e(project_dir, engines=engines, timeout_s=int(args.timeout_s))


if __name__ == "__main__":
    raise SystemExit(main())
