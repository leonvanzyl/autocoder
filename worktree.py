"""
Git Worktree Management
=======================

Manages git worktrees for parallel agent execution.
Each agent gets its own isolated working directory while sharing
the same git repository and feature database.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WorktreeManager:
    """
    Manages git worktrees for parallel agents.

    Each worktree provides an isolated working directory where an agent
    can make changes without conflicting with other agents.
    """

    def __init__(self, project_dir: Path):
        """
        Initialize the worktree manager.

        Args:
            project_dir: The main project directory (must be a git repo)
        """
        self.project_dir = project_dir.resolve()
        self.worktrees_dir = self.project_dir.parent / f".{self.project_dir.name}_worktrees"

    def _run_git(self, *args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Run a git command and return the result."""
        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            cwd=cwd or self.project_dir,
            capture_output=True,
            text=True,
        )

    def is_git_repo(self) -> bool:
        """Check if the project directory is a git repository."""
        result = self._run_git("rev-parse", "--git-dir")
        return result.returncode == 0

    def ensure_git_repo(self) -> bool:
        """
        Ensure the project directory is a git repository.
        Initializes one if it doesn't exist.

        Returns:
            True if repo exists or was created, False on error
        """
        if self.is_git_repo():
            return True

        logger.info(f"Initializing git repository in {self.project_dir}")
        result = self._run_git("init")
        if result.returncode != 0:
            logger.error(f"Failed to initialize git repo: {result.stderr}")
            return False

        # Create initial commit so worktrees can branch from it
        result = self._run_git("add", "-A")
        if result.returncode != 0:
            logger.error(f"Git add failed: {result.stderr}")
            return False

        result = self._run_git("commit", "-m", "Initial commit for parallel agents", "--allow-empty")
        if result.returncode != 0:
            logger.error(f"Git commit failed: {result.stderr}")
            return False

        return True

    def get_worktree_path(self, agent_id: str) -> Path:
        """Get the path for an agent's worktree."""
        return self.worktrees_dir / f"agent_{agent_id}"

    def create_worktree(self, agent_id: str, branch_name: Optional[str] = None) -> Optional[Path]:
        """
        Create a worktree for an agent.

        Args:
            agent_id: Unique identifier for the agent
            branch_name: Optional branch name (defaults to agent-{agent_id})

        Returns:
            Path to the worktree, or None on failure
        """
        if not self.ensure_git_repo():
            return None

        worktree_path = self.get_worktree_path(agent_id)
        branch = branch_name or f"agent-{agent_id}"

        # Check if worktree already exists
        if worktree_path.exists():
            logger.info(f"Worktree already exists for agent {agent_id}")
            return worktree_path

        # Ensure worktrees directory exists
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

        # Get current branch/HEAD for base
        result = self._run_git("rev-parse", "HEAD")
        if result.returncode != 0:
            # No commits yet, create one
            commit_result = self._run_git("commit", "--allow-empty", "-m", "Initial commit")
            if commit_result.returncode != 0:
                logger.error(f"Failed to create initial commit: {commit_result.stderr}")
                return None
            result = self._run_git("rev-parse", "HEAD")
            if result.returncode != 0:
                logger.error(f"Failed to get HEAD ref after initial commit: {result.stderr}")
                return None

        base_ref = result.stdout.strip()

        # Create the worktree with a new branch
        result = self._run_git(
            "worktree", "add",
            "-b", branch,
            str(worktree_path),
            base_ref
        )

        if result.returncode != 0:
            # Branch might already exist, try without -b
            result = self._run_git(
                "worktree", "add",
                str(worktree_path),
                branch
            )

        if result.returncode != 0:
            logger.error(f"Failed to create worktree: {result.stderr}")
            return None

        logger.info(f"Created worktree for agent {agent_id} at {worktree_path}")

        # Copy features.db to worktree (symlink would be better but cross-platform issues)
        self._setup_shared_resources(worktree_path)

        return worktree_path

    def _setup_shared_resources(self, worktree_path: Path) -> None:
        """
        Set up shared resources in the worktree.

        The features.db is shared across all worktrees via symlink.
        This is critical for atomic feature claiming via feature_claim_next().

        Raises:
            RuntimeError: If features.db cannot be shared with the worktree.
        """
        # Create symlink to shared features.db
        features_db = self.project_dir / "features.db"
        worktree_db = worktree_path / "features.db"

        if features_db.exists() and not worktree_db.exists():
            try:
                # Try symlink first (preferred)
                worktree_db.symlink_to(features_db)
                logger.debug(f"Created symlink to features.db in {worktree_path}")
            except OSError as e:
                # Symlink failed (common on Windows without admin privileges)
                # This is OK because parallel_agent_runner.py sets PROJECT_DIR
                # environment variable to the main project directory, and the
                # MCP server uses that env var to locate features.db
                logger.info(
                    f"Symlink creation failed ({e}), but this is OK - "
                    f"MCP server uses PROJECT_DIR env var to access {features_db}"
                )
                # Write a marker file for debugging purposes only
                # (not read by MCP server, just useful for troubleshooting)
                db_path_file = worktree_path / ".features_db_path"
                db_path_file.write_text(str(features_db))
                logger.debug(f"Wrote features.db path marker to {db_path_file}")

        # Copy prompts directory if it exists
        prompts_dir = self.project_dir / "prompts"
        worktree_prompts = worktree_path / "prompts"
        if prompts_dir.exists() and not worktree_prompts.exists():
            try:
                worktree_prompts.symlink_to(prompts_dir)
            except OSError:
                import shutil
                shutil.copytree(prompts_dir, worktree_prompts)

    def remove_worktree(self, agent_id: str) -> bool:
        """
        Remove a worktree for an agent.

        Args:
            agent_id: Unique identifier for the agent

        Returns:
            True if successful, False otherwise
        """
        worktree_path = self.get_worktree_path(agent_id)

        if not worktree_path.exists():
            return True

        # Remove the worktree
        result = self._run_git("worktree", "remove", str(worktree_path), "--force")

        if result.returncode != 0:
            logger.warning(f"Failed to remove worktree: {result.stderr}")
            # Try manual removal
            import shutil
            try:
                shutil.rmtree(worktree_path)
            except Exception as e:
                logger.error(f"Failed to manually remove worktree: {e}")
                return False

        # Prune worktree references
        self._run_git("worktree", "prune")

        logger.info(f"Removed worktree for agent {agent_id}")
        return True

    def list_worktrees(self) -> list[dict]:
        """
        List all active worktrees.

        Returns:
            List of dicts with worktree info (path, branch, head)
        """
        result = self._run_git("worktree", "list", "--porcelain")

        if result.returncode != 0:
            return []

        worktrees = []
        current = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue

            if line.startswith("worktree "):
                current["path"] = line[9:]
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "bare":
                current["bare"] = True
            elif line == "detached":
                current["detached"] = True

        if current:
            worktrees.append(current)

        return worktrees

    def merge_worktree_changes(self, agent_id: str, commit_message: Optional[str] = None) -> bool:
        """
        Merge changes from an agent's worktree back to main branch.

        Args:
            agent_id: Unique identifier for the agent
            commit_message: Optional commit message

        Returns:
            True if successful, False otherwise
        """
        worktree_path = self.get_worktree_path(agent_id)
        branch = f"agent-{agent_id}"

        if not worktree_path.exists():
            logger.error(f"Worktree for agent {agent_id} does not exist")
            return False

        # Commit any uncommitted changes in the worktree
        self._run_git("add", "-A", cwd=worktree_path)
        msg = commit_message or f"Agent {agent_id} changes"
        self._run_git("commit", "-m", msg, "--allow-empty", cwd=worktree_path)

        # Get the target branch to merge into (default to "main")
        result = self._run_git("branch", "--show-current")
        target_branch = result.stdout.strip() or "main"

        # Ensure we're on the target branch before merging
        result = self._run_git("checkout", target_branch)
        if result.returncode != 0:
            logger.error(f"Failed to checkout {target_branch}: {result.stderr}")
            return False

        # Merge the agent branch into the target branch
        result = self._run_git("merge", branch, "--no-edit")

        if result.returncode != 0:
            logger.warning(
                f"Merge conflict for agent {agent_id}. "
                f"Agent branch: {branch}. Error: {result.stderr}"
            )
            logger.warning(
                f"Manual resolution required. Worktree at: {worktree_path}"
            )
            # Abort the merge to clean up
            self._run_git("merge", "--abort")
            return False

        logger.info(f"Merged changes from agent {agent_id}")
        return True

    def cleanup_all_worktrees(self) -> None:
        """Remove all worktrees and clean up."""
        worktrees = self.list_worktrees()

        for wt in worktrees:
            path = Path(wt.get("path", ""))
            # Use is_relative_to() for robust path matching instead of string matching
            # This avoids false positives from substring matches
            if path != self.project_dir and path.is_relative_to(self.worktrees_dir):
                # Extract agent_id from path
                agent_id = path.name.replace("agent_", "")
                self.remove_worktree(agent_id)

        # Clean up worktrees directory if empty
        if self.worktrees_dir.exists():
            try:
                self.worktrees_dir.rmdir()
            except OSError:
                pass  # Directory not empty

        # Prune stale worktree references
        self._run_git("worktree", "prune")
