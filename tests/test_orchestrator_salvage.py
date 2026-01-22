import subprocess
import tempfile
from pathlib import Path

import pytest

from autocoder.core.orchestrator import Orchestrator
import autocoder.core.orchestrator as orchestrator_module


def _init_git_repo(repo_path: Path) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=repo_path, capture_output=True, check=True)

    (repo_path / "README.md").write_text("# Test Repo", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True, check=True)


def _create_feature_branch_with_commit(repo_path: Path, branch: str) -> None:
    subprocess.run(["git", "checkout", "-b", branch], cwd=repo_path, capture_output=True, check=True)
    (repo_path / "A.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "A.txt"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "feat"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo_path, capture_output=True, check=True)


def test_salvage_dead_agent_marks_ready_for_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    If an agent is stale/dead but its branch has commits, salvage should submit it for Gatekeeper
    instead of resetting it for retry.
    """
    monkeypatch.setenv("AUTOCODER_SKIP_PORT_CHECK", "1")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        _init_git_repo(repo_path)

        branch = "feat/1"
        _create_feature_branch_with_commit(repo_path, branch)

        orch = Orchestrator(project_dir=str(repo_path), max_agents=0)

        feature_id = orch.database.create_feature(
            name="Test feature",
            description="x",
            category="backend",
        )
        assert orch.database.claim_feature(feature_id=feature_id, agent_id="agent-1", branch_name=branch)

        orch.database.register_agent(
            agent_id="agent-1",
            pid=999999,  # invalid
            worktree_path=str(repo_path / "worktrees" / "agent-1"),
            feature_id=feature_id,
        )
        with orch.database.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE agent_heartbeats SET last_ping = datetime('now', '-20 minutes') WHERE agent_id = ?",
                ("agent-1",),
            )
            conn.commit()

        orch._recover_crashed_agents()

        feature = orch.database.get_feature(feature_id)
        assert feature is not None
        assert feature["review_status"] == "READY_FOR_VERIFICATION"
        assert feature["branch_name"] == branch

        hb = orch.database.get_agent_heartbeat("agent-1")
        assert hb is not None
        assert hb["status"] == "COMPLETED"


def test_pid_guard_rejects_unexpected_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOCODER_SKIP_PORT_CHECK", "1")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        _init_git_repo(repo_path)

        orch = Orchestrator(project_dir=str(repo_path), max_agents=0)

        class _FakeProc:
            def __init__(self, pid: int):
                self._pid = pid

            def cmdline(self):
                return ["python", "not_a_worker.py"]

            def create_time(self):
                return 123.0

        monkeypatch.setattr(orchestrator_module.psutil, "Process", _FakeProc)

        assert orch._is_expected_worker_process(
            {
                "agent_id": "agent-1",
                "pid": 1234,
                "proc_create_time": 123.0,
                "started_at": "2026-01-01 00:00:00",
            }
        ) is False


def test_pid_guard_accepts_expected_worker_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOCODER_SKIP_PORT_CHECK", "1")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        _init_git_repo(repo_path)

        orch = Orchestrator(project_dir=str(repo_path), max_agents=0)

        class _FakeWorkerProc:
            def __init__(self, pid: int):
                self._pid = pid

            def cmdline(self):
                return ["python", "agent_worker.py", "--agent-id", "agent-1"]

            def create_time(self):
                return 1000.0

        monkeypatch.setattr(orchestrator_module.psutil, "Process", _FakeWorkerProc)

        assert (
            orch._is_expected_worker_process(
                {
                    "agent_id": "agent-1",
                    "pid": 1234,
                    "proc_create_time": 1000.0,
                    "started_at": "2026-01-01 00:00:00",
                }
            )
            is True
        )
