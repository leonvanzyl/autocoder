import asyncio
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def test_patch_worker_implement_mode_marks_ready(tmp_path, monkeypatch):
    from autocoder.core.database import Database
    from autocoder import qa_worker

    repo = tmp_path / "repo"
    repo.mkdir()

    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    _run(["git", "checkout", "-b", "main"], repo)

    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "init"], repo)

    db = Database(str(repo / "agent_system.db"))
    feature_id = db.create_feature(name="feat", description="add implemented.txt", category="demo", priority=0)
    assert db.claim_feature(feature_id, "agent-1", "feat/1")

    _run(["git", "checkout", "-b", "feat/1"], repo)

    patch = "\n".join(
        [
            "diff --git a/implemented.txt b/implemented.txt",
            "new file mode 100644",
            "index 0000000..3b18e14",
            "--- /dev/null",
            "+++ b/implemented.txt",
            "@@ -0,0 +1 @@",
            "+ok",
            "",
        ]
    )

    def _stub_codex(*args, **kwargs):
        return True, patch, ""

    monkeypatch.setattr(qa_worker, "_run_codex", _stub_codex)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qa_worker.py",
            "--mode",
            "implement",
            "--project-dir",
            str(repo),
            "--agent-id",
            "agent-1",
            "--feature-id",
            str(feature_id),
            "--worktree-path",
            str(repo),
            "--provider",
            "codex_cli",
            "--max-iterations",
            "1",
            "--timeout-s",
            "30",
        ],
    )

    rc = asyncio.run(qa_worker.main())
    assert rc == 0

    assert (repo / "implemented.txt").read_text(encoding="utf-8") == "ok\n"

    f = db.get_feature(feature_id)
    assert f["review_status"] == "READY_FOR_VERIFICATION"

