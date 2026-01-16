"""
Worktree Manager
================

Manages git worktrees for isolated agent workspaces.

Each agent gets their own worktree (isolated copy of the repo) where they
can work safely without affecting the main codebase or other agents.

Key Features:
- Creates isolated worktrees for each agent
- Manages feature branches within worktrees
- Cleans up worktrees when done
- Handles crash recovery (force delete if needed)

Disk Space: Worktrees share the .git directory, so overhead is minimal
(only the working files are duplicated, not the git history)
"""

import os
import subprocess
import shutil
import json
import stat
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class WorktreeManager:
    """Manages git worktrees for parallel agent isolation."""

    def __init__(self, project_dir: str, worktrees_base_dir: Optional[str] = None):
        """
        Initialize the worktree manager.

        Args:
            project_dir: Path to the main project (must be a git repo)
            worktrees_base_dir: Base directory for worktrees (default: project_dir/worktrees)
        """
        self.project_dir = Path(project_dir).resolve()
        self.worktrees_base_dir = Path(
            worktrees_base_dir or self.project_dir / "worktrees"
        ).resolve()

        # Ensure worktrees directory exists
        self.worktrees_base_dir.mkdir(parents=True, exist_ok=True)

        # Verify project is a git repository
        if not (self.project_dir / ".git").exists():
            raise ValueError(f"Not a git repository: {self.project_dir}")

        # Windows path edge-cases: enable long path support for this repo (local config).
        # This avoids failures when Node/Next creates deep node_modules trees in worktrees.
        if os.name == "nt":
            try:
                subprocess.run(
                    ["git", "config", "core.longpaths", "true"],
                    cwd=self.project_dir,
                    check=False,
                    capture_output=True,
                )
            except Exception:
                pass

        # Backwards-compatible attribute name (used by older tests)
        self.repo_path = str(self.project_dir)

        logger.info(f"WorktreeManager initialized: {self.project_dir}")
        logger.info(f"Worktrees base: {self.worktrees_base_dir}")

    def _autocoder_dir(self) -> Path:
        d = self.project_dir / ".autocoder"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _cleanup_queue_path(self) -> Path:
        return self._autocoder_dir() / "cleanup_queue.json"

    def _load_cleanup_queue(self) -> list[dict]:
        path = self._cleanup_queue_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def _save_cleanup_queue(self, items: list[dict]) -> None:
        path = self._cleanup_queue_path()
        path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def _enqueue_cleanup(self, path: Path, *, reason: str) -> None:
        items = self._load_cleanup_queue()
        p = str(path)
        now = time.time()
        for item in items:
            if item.get("path") == p:
                item["reason"] = reason
                return self._save_cleanup_queue(items)
        items.append(
            {
                "path": p,
                "attempts": 0,
                "next_try_at": now,
                "added_at": now,
                "reason": reason,
            }
        )
        self._save_cleanup_queue(items)

    @staticmethod
    def _rmtree_force(path: Path) -> None:
        def onerror(func, p, excinfo):  # type: ignore[no-untyped-def]
            try:
                os.chmod(p, stat.S_IWRITE)
            except Exception:
                pass
            try:
                func(p)
            except Exception:
                pass

        shutil.rmtree(path, onerror=onerror)

    def process_cleanup_queue(self, *, max_items: int = 2) -> int:
        """
        Best-effort deletion of deferred-cleanup directories.

        This mitigates Windows file locking (e.g. native `.node` modules) by retrying later.
        """
        items = self._load_cleanup_queue()
        if not items:
            return 0
        now = time.time()
        processed = 0
        remaining: list[dict] = []

        def backoff_s(attempts: int) -> float:
            # 5s, 10s, 20s, ... up to 10 minutes
            return float(min(600, 5 * (2 ** max(0, attempts))))

        for item in items:
            if processed >= max_items:
                remaining.append(item)
                continue
            try:
                next_try_at = float(item.get("next_try_at", 0.0))
            except Exception:
                next_try_at = 0.0
            if next_try_at and next_try_at > now:
                remaining.append(item)
                continue

            p = Path(str(item.get("path") or ""))
            if not p.exists():
                processed += 1
                continue
            try:
                self._rmtree_force(p)
                processed += 1
                continue
            except Exception as e:
                attempts = int(item.get("attempts") or 0) + 1
                item["attempts"] = attempts
                item["last_error"] = str(e)
                item["next_try_at"] = now + backoff_s(attempts)
                remaining.append(item)
                processed += 1

        self._save_cleanup_queue(remaining)
        return processed

    def create_worktree(
        self,
        agent_id: str,
        feature_id: Optional[int] = None,
        feature_name: Optional[str] = None,
        branch_name: Optional[str] = None,
    ) -> dict | str:
        """
        Create a new isolated worktree for an agent.

        Args:
            agent_id: Agent identifier (e.g., "agent-1")
            feature_id: Feature ID from database
            feature_name: Human-readable feature name
            branch_name: Optional explicit branch name to use

        Returns:
            Dictionary with worktree details:
            {
                "worktree_path": "/path/to/worktrees/agent-1",
                "branch_name": "feat/feature-123-20250107-143022",
                "relative_path": "worktrees/agent-1"
            }

        Raises:
            subprocess.CalledProcessError: If git worktree creation fails
        """
        legacy_return_path_only = False
        if feature_id is None and feature_name is None:
            # Backwards-compatible calling convention used by older tests:
            # create_worktree("feature-1") -> returns worktree_path string.
            legacy_return_path_only = True
            feature_id = 0
            feature_name = agent_id
            if branch_name is None:
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                branch_name = f"feat/{agent_id}-{timestamp}"

        # Create branch name with timestamp for uniqueness (unless provided)
        if branch_name is None:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            branch_name = f"feat/feature-{feature_id}-{timestamp}"

        # Sanitize feature name for directory name
        safe_agent_id = agent_id.replace("/", "-").replace("\\", "-")
        worktree_path = self.worktrees_base_dir / safe_agent_id

        # Clean up existing worktree if it exists (crash recovery)
        if worktree_path.exists():
            logger.warning(f"Worktree already exists, removing: {worktree_path}")
            self.delete_worktree(agent_id, force=True)

        # Create the worktree
        logger.info(f"Creating worktree: {worktree_path}")
        logger.info(f"Branch: {branch_name}")

        def branch_exists(name: str) -> bool:
            try:
                subprocess.run(
                    ["git", "rev-parse", "--verify", name],
                    cwd=self.project_dir,
                    check=True,
                    capture_output=True,
                )
                return True
            except subprocess.CalledProcessError:
                return False

        # Prefer creating feature branches from main/master rather than whatever the repo is currently on.
        base_ref: Optional[str] = None
        for candidate in ("main", "master"):
            try:
                subprocess.run(
                    ["git", "rev-parse", "--verify", candidate],
                    cwd=self.project_dir,
                    check=True,
                    capture_output=True,
                )
                base_ref = candidate
                break
            except subprocess.CalledProcessError:
                continue

        try:
            # Git worktree add command:
            # - If branch already exists, attach worktree to it (resume).
            # - Otherwise, create a new branch from base_ref.
            cmd: list[str] = ["git", "worktree", "add", str(worktree_path)]
            if branch_exists(branch_name):
                cmd.append(branch_name)
            else:
                cmd.extend(["-b", branch_name])
                if base_ref:
                    cmd.append(base_ref)
            subprocess.run(
                cmd,
                cwd=self.project_dir,
                check=True,
                capture_output=True,
                text=True
            )

            logger.info(f"✅ Worktree created successfully")

            result = {
                "worktree_path": str(worktree_path),
                "branch_name": branch_name,
                "relative_path": worktree_path.relative_to(self.project_dir.parent),
                "created_at": datetime.now().isoformat()
            }

            return result["worktree_path"] if legacy_return_path_only else result

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create worktree: {e.stderr}")
            raise

    def delete_worktree(self, agent_id: str, force: bool = False) -> bool:
        """
        Delete a worktree and remove the git worktree registration.

        Args:
            agent_id: Agent identifier
            force: Force deletion even if worktree has uncommitted changes

        Returns:
            True if deleted, False if worktree didn't exist
        """
        safe_agent_id = agent_id.replace("/", "-").replace("\\", "-")
        worktree_path = self.worktrees_base_dir / safe_agent_id

        if not worktree_path.exists():
            # This can happen during repeated cleanup attempts or when a worker never created its worktree.
            if force:
                logger.debug(f"Worktree does not exist: {worktree_path}")
            else:
                logger.warning(f"Worktree does not exist: {worktree_path}")
            return False

        try:
            # Remove the worktree using git
            logger.info(f"Removing worktree: {worktree_path}")

            subprocess.run(
                [
                    "git",
                    "worktree",
                    "remove",
                    *(["-f"] if force else []),
                    str(worktree_path),
                ],
                cwd=self.project_dir,
                check=True,
                capture_output=True,
                text=True
            )

            # Force delete directory if git command failed
            if worktree_path.exists():
                if force:
                    logger.warning(f"Force deleting directory: {worktree_path}")
                    try:
                        self._rmtree_force(worktree_path)
                    except Exception as e:
                        logger.warning(f"Deferred cleanup for locked worktree: {e}")
                        self._enqueue_cleanup(worktree_path, reason="force-delete failed after git worktree remove")
                        return True
                else:
                    logger.error(f"Directory still exists after git worktree remove")
                    return False

            logger.info(f"✅ Worktree deleted successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove worktree: {e.stderr}")

            # Try force cleanup
            if force:
                logger.warning("Attempting force cleanup...")
                try:
                    # Prune worktrees
                    subprocess.run(
                        ["git", "worktree", "prune"],
                        cwd=self.project_dir,
                        check=True,
                        capture_output=True
                    )
                    # Delete directory
                    if worktree_path.exists():
                        try:
                            self._rmtree_force(worktree_path)
                        except Exception as cleanup_error:
                            logger.warning(f"Deferred cleanup for locked worktree: {cleanup_error}")
                            self._enqueue_cleanup(worktree_path, reason="force-cleanup failed after prune")
                            return True
                    logger.info("✅ Force cleanup successful")
                    return True
                except Exception as cleanup_error:
                    logger.error(f"Force cleanup failed: {cleanup_error}")
                    if worktree_path.exists():
                        self._enqueue_cleanup(worktree_path, reason="force-cleanup failed")
                    return False

            return False

    def remove_worktree(self, agent_id: str) -> bool:
        """Backwards-compatible alias for delete_worktree()."""
        return self.delete_worktree(agent_id, force=True)

    def list_worktrees(self) -> list[dict]:
        """
        List all active worktrees.

        Returns:
            List of worktree info dictionaries
        """
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.project_dir,
                check=True,
                capture_output=True,
                text=True
            )

            worktrees = []
            current_worktree = {}

            for line in result.stdout.strip().split("\n"):
                if not line:
                    if current_worktree:
                        worktrees.append(current_worktree)
                        current_worktree = {}
                    continue

                parts = line.split(" ", 1)
                if len(parts) != 2:
                    continue

                key, value = parts
                current_worktree[key] = value

            if current_worktree:
                worktrees.append(current_worktree)

            return worktrees

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list worktrees: {e.stderr}")
            return []

    def get_worktree_path(self, agent_id: str) -> Optional[Path]:
        """
        Get the worktree path for a specific agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Path to worktree, or None if not found
        """
        safe_agent_id = agent_id.replace("/", "-").replace("\\", "-")
        worktree_path = self.worktrees_base_dir / safe_agent_id

        if worktree_path.exists():
            return worktree_path

        return None

    def is_worktree_clean(self, agent_id: str) -> bool:
        """
        Check if a worktree has uncommitted changes.

        Args:
            agent_id: Agent identifier

        Returns:
            True if worktree is clean (no uncommitted changes)
        """
        worktree_path = self.get_worktree_path(agent_id)

        if not worktree_path:
            return False

        try:
            # Check git status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True
            )

            # Empty output = clean
            return len(result.stdout.strip()) == 0

        except subprocess.CalledProcessError:
            return False

    def commit_checkpoint(
        self,
        agent_id: str,
        message: str,
        allow_dirty: bool = False
    ) -> bool:
        """
        Create a checkpoint commit in the agent's worktree.

        Checkpoints are frequent commits that allow rollback if the agent
        goes sideways later in the feature.

        Args:
            agent_id: Agent identifier
            message: Commit message (should describe what's working)
            allow_dirty: Allow committing even with untracked files

        Returns:
            True if commit succeeded
        """
        worktree_path = self.get_worktree_path(agent_id)

        if not worktree_path:
            logger.error(f"Worktree not found for agent: {agent_id}")
            return False

        try:
            # Add all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=worktree_path,
                check=True,
                capture_output=True
            )

            # Commit
            commit_message = f"Checkpoint: {message}"

            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True
            )

            logger.info(f"✅ Checkpoint committed in {agent_id}: {message}")
            return True

        except subprocess.CalledProcessError as e:
            # If nothing to commit, that's okay
            if "nothing to commit" in e.stdout.lower():
                logger.debug(f"No changes to commit in {agent_id}")
                return True

            logger.error(f"Failed to commit checkpoint: {e.stderr}")
            return False

    def rollback_to_last_checkpoint(self, agent_id: str, steps: int = 1) -> bool:
        """
        Rollback worktree to last checkpoint commit.

        Use this when agent goes sideways and you want to revert
        to the last known good state.

        Args:
            agent_id: Agent identifier
            steps: Number of commits to rollback (default: 1)

        Returns:
            True if rollback succeeded
        """
        worktree_path = self.get_worktree_path(agent_id)

        if not worktree_path:
            logger.error(f"Worktree not found for agent: {agent_id}")
            return False

        try:
            # Reset to previous commit
            subprocess.run(
                ["git", "reset", "--hard", f"HEAD~{steps}"],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True
            )

            logger.info(f"✅ Rolled back {agent_id} by {steps} checkpoint(s)")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to rollback: {e.stderr}")
            return False

    def push_branch(self, agent_id: str, branch_name: str) -> bool:
        """
        Push the feature branch to remote repository.

        This makes the branch available for the Gatekeeper to review.

        Args:
            agent_id: Agent identifier
            branch_name: Branch name to push

        Returns:
            True if push succeeded
        """
        worktree_path = self.get_worktree_path(agent_id)

        if not worktree_path:
            logger.error(f"Worktree not found for agent: {agent_id}")
            return False

        try:
            # Push branch to origin
            subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True
            )

            logger.info(f"✅ Branch pushed: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to push branch: {e.stderr}")
            return False


def test_worktree_manager():
    """Test the worktree manager with a real repository."""
    import tempfile

    # Create a test repo
    with tempfile.TemporaryDirectory() as tmpdir:
        test_repo = Path(tmpdir) / "test_repo"
        test_repo.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=test_repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_repo,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_repo,
            check=True
        )

        # Create initial commit
        (test_repo / "README.md").write_text("# Test Repo\n")
        subprocess.run(["git", "add", "."], cwd=test_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=test_repo,
            check=True
        )

        # Test worktree manager
        manager = WorktreeManager(str(test_repo))

        # Create worktree
        result = manager.create_worktree("agent-1", 123, "Test Feature")
        print(f"Created worktree: {result}")

        # Check worktree exists
        worktree_path = manager.get_worktree_path("agent-1")
        print(f"Worktree path: {worktree_path}")
        assert worktree_path.exists()

        # Create checkpoint
        (worktree_path / "test.txt").write_text("Test content")
        manager.commit_checkpoint("agent-1", "Added test file")

        # List worktrees
        worktrees = manager.list_worktrees()
        print(f"Active worktrees: {len(worktrees)}")

        # Delete worktree
        manager.delete_worktree("agent-1")
        assert not manager.get_worktree_path("agent-1").exists()

        print("✅ All tests passed!")


if __name__ == "__main__":
    test_worktree_manager()
