"""
Git Worktree Manager
====================

Manages git worktrees for parallel agent execution.
Each worker operates in its own worktree with isolated branches.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WorktreeManager:
    """Manages git worktrees for parallel workers."""

    def __init__(self, project_dir: Path, worker_count: int):
        """
        Initialize the worktree manager.

        Args:
            project_dir: Root project directory (must be a git repo)
            worker_count: Number of workers to create worktrees for
        """
        self.project_dir = project_dir
        self.worker_count = worker_count
        self.worktree_base = project_dir / ".worktrees"
        self._created_worktrees: list[Path] = []
        self._created_branches: list[str] = []
        self._target_branch: Optional[str] = None  # Captured at startup

    async def _run_git(
        self,
        *args: str,
        cwd: Optional[Path] = None,
        check: bool = True
    ) -> asyncio.subprocess.Process:
        """
        Run a git command asynchronously.

        Uses create_subprocess_exec (safe, no shell injection).

        Args:
            *args: Git command arguments
            cwd: Working directory (defaults to project_dir)
            check: Raise exception on non-zero exit

        Returns:
            Completed process
        """
        cwd = cwd or self.project_dir
        cmd = ["git", *args]

        logger.debug(f"Running: {' '.join(cmd)} in {cwd}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if check and proc.returncode != 0:
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{error_msg}")

        return proc

    async def _run_git_output(
        self,
        *args: str,
        cwd: Optional[Path] = None
    ) -> str:
        """Run a git command and return stdout."""
        cwd = cwd or self.project_dir
        cmd = ["git", *args]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    async def setup_worktree(self, worker_id: int) -> Path:
        """
        Create a worktree for a worker.

        Args:
            worker_id: Worker index (0-based)

        Returns:
            Path to the created worktree
        """
        worktree_path = self.worktree_base / f"worker-{worker_id}"
        branch_name = f"agent/worker-{worker_id}"

        # Create worktree base directory if needed
        self.worktree_base.mkdir(parents=True, exist_ok=True)

        # Remove existing worktree if present
        if worktree_path.exists():
            await self._remove_worktree(worktree_path)

        # Get current HEAD for the branch
        head = await self._run_git_output("rev-parse", "HEAD")

        # Create branch if it doesn't exist
        branches = await self._run_git_output("branch", "--list", branch_name)
        if not branches:
            await self._run_git("branch", branch_name, head)
            self._created_branches.append(branch_name)
            logger.info(f"Created branch: {branch_name}")

        # Create worktree
        await self._run_git("worktree", "add", str(worktree_path), branch_name)
        self._created_worktrees.append(worktree_path)
        logger.info(f"Created worktree: {worktree_path}")

        return worktree_path

    async def setup_all_worktrees(self) -> dict[int, Path]:
        """
        Create worktrees for all workers.

        Returns:
            Dict mapping worker_id to worktree path
        """
        # Capture the target branch BEFORE creating any worktrees
        # This is the branch we'll merge completed features into
        await self._capture_target_branch()

        worktrees = {}
        for i in range(self.worker_count):
            worktrees[i] = await self.setup_worktree(i)
        return worktrees

    async def _capture_target_branch(self) -> None:
        """
        Capture the current branch name as the merge target.

        Must be called before any merges. Fails if HEAD is detached.
        """
        # Get symbolic ref to current branch (fails if detached)
        try:
            branch = await self._run_git_output("symbolic-ref", "--short", "HEAD")
            self._target_branch = branch
            logger.info(f"Target branch for merges: {self._target_branch}")
        except RuntimeError:
            # HEAD is detached - fall back to default branch
            try:
                # Try to get the default branch from origin
                default = await self._run_git_output("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
                # Extract branch name (e.g., "origin/main" -> "main")
                self._target_branch = default.split("/")[-1]
                logger.warning(f"HEAD is detached, falling back to default branch: {self._target_branch}")
            except RuntimeError:
                raise RuntimeError(
                    "Cannot determine target branch: HEAD is detached and no default branch found. "
                    "Please checkout a branch before running parallel mode."
                )

    async def checkout_feature_branch(
        self,
        worker_id: int,
        feature_id: int,
        worktree_path: Path
    ) -> str:
        """
        Create and checkout a fresh feature branch in a worktree.

        Args:
            worker_id: Worker index
            feature_id: Feature ID being worked on
            worktree_path: Path to the worker's worktree

        Returns:
            Name of the created feature branch
        """
        branch_name = f"feature/{feature_id}-worker-{worker_id}"

        # Get current main branch ref
        main_ref = await self._run_git_output("rev-parse", "HEAD")

        # Clean the worktree
        await self._run_git("checkout", "--force", "HEAD", cwd=worktree_path)
        await self._run_git("clean", "-fd", cwd=worktree_path)

        # Create and checkout feature branch
        # Delete existing branch if present
        branches = await self._run_git_output("branch", "--list", branch_name, cwd=worktree_path)
        if branches:
            await self._run_git("branch", "-D", branch_name, cwd=worktree_path, check=False)

        await self._run_git("checkout", "-b", branch_name, main_ref, cwd=worktree_path)
        logger.info(f"Worker {worker_id} checked out branch: {branch_name}")

        return branch_name

    async def get_current_main_ref(self) -> str:
        """Get the current HEAD ref of main branch."""
        return await self._run_git_output("rev-parse", "HEAD")

    async def merge_feature_branch(
        self,
        feature_branch: str,
        worktree_path: Path
    ) -> tuple[bool, str]:
        """
        Attempt to merge a feature branch into the target branch.

        First tries fast-forward merge. If that fails, rebases the
        feature branch onto the target and tries again.

        Args:
            feature_branch: Name of the feature branch to merge
            worktree_path: Path to the worktree with the feature branch

        Returns:
            Tuple of (success, message)
        """
        if not self._target_branch:
            raise RuntimeError("Target branch not captured. Call setup_all_worktrees first.")

        # Ensure we're on the target branch (NOT detached HEAD)
        await self._run_git("checkout", self._target_branch, cwd=self.project_dir, check=False)

        # Try fast-forward merge
        proc = await self._run_git(
            "merge", "--ff-only", feature_branch,
            cwd=self.project_dir,
            check=False
        )

        if proc.returncode == 0:
            logger.info(f"Fast-forward merged {feature_branch} into {self._target_branch}")
            return True, "Fast-forward merge successful"

        # Fast-forward failed, try rebase
        logger.info(f"Fast-forward failed for {feature_branch}, attempting rebase onto {self._target_branch}")

        # Get current target branch ref
        target_ref = await self._run_git_output("rev-parse", self._target_branch)

        # Rebase feature branch onto target
        proc = await self._run_git(
            "rebase", target_ref,
            cwd=worktree_path,
            check=False
        )

        if proc.returncode != 0:
            # Rebase failed - conflict
            await self._run_git("rebase", "--abort", cwd=worktree_path, check=False)
            logger.warning(f"Rebase failed for {feature_branch}, conflict detected")
            return False, "Merge conflict - rebase failed"

        # Retry fast-forward merge after rebase
        proc = await self._run_git(
            "merge", "--ff-only", feature_branch,
            cwd=self.project_dir,
            check=False
        )

        if proc.returncode == 0:
            logger.info(f"Merged {feature_branch} into {self._target_branch} after rebase")
            return True, "Merged after rebase"

        logger.warning(f"Merge still failed after rebase for {feature_branch}")
        return False, "Merge failed even after rebase"

    async def delete_feature_branch(self, branch_name: str) -> None:
        """Delete a feature branch after successful merge."""
        await self._run_git("branch", "-d", branch_name, check=False)
        logger.debug(f"Deleted branch: {branch_name}")

    async def _remove_worktree(self, worktree_path: Path) -> None:
        """Remove a single worktree."""
        if worktree_path.exists():
            # Try git worktree remove first
            await self._run_git(
                "worktree", "remove", "--force", str(worktree_path),
                check=False
            )
            # If still exists, force remove
            if worktree_path.exists():
                shutil.rmtree(worktree_path, ignore_errors=True)

    async def cleanup_worktree(self, worker_id: int) -> None:
        """
        Clean up a single worker's worktree.

        Args:
            worker_id: Worker index
        """
        worktree_path = self.worktree_base / f"worker-{worker_id}"
        branch_name = f"agent/worker-{worker_id}"

        await self._remove_worktree(worktree_path)

        # Delete the worker branch
        await self._run_git("branch", "-D", branch_name, check=False)

        logger.info(f"Cleaned up worktree for worker-{worker_id}")

    async def cleanup_all(self) -> None:
        """Clean up all worktrees and branches created by this manager."""
        logger.info("Cleaning up all worktrees...")

        # Remove all created worktrees
        for worktree_path in self._created_worktrees:
            await self._remove_worktree(worktree_path)

        # Prune worktree references
        await self._run_git("worktree", "prune", check=False)

        # Delete created branches
        for branch in self._created_branches:
            await self._run_git("branch", "-D", branch, check=False)

        # Remove worktree base directory if empty
        if self.worktree_base.exists():
            try:
                self.worktree_base.rmdir()
            except OSError:
                pass  # Not empty, leave it

        logger.info("Worktree cleanup complete")

    async def reset_worktree_to_main(self, worktree_path: Path) -> None:
        """
        Reset a worktree to match main branch.

        Used to prepare worktree for next feature.

        Args:
            worktree_path: Path to the worktree to reset
        """
        main_ref = await self.get_current_main_ref()
        await self._run_git("checkout", "--force", main_ref, cwd=worktree_path)
        await self._run_git("clean", "-fd", cwd=worktree_path)
        logger.debug(f"Reset worktree to main: {worktree_path}")

    def get_worktree_path(self, worker_id: int) -> Path:
        """Get the worktree path for a worker."""
        return self.worktree_base / f"worker-{worker_id}"

    async def is_git_repo(self) -> bool:
        """Check if the project directory is a git repository."""
        git_dir = self.project_dir / ".git"
        return git_dir.exists()
