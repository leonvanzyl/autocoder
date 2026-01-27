"""
Git Workflow Module
===================

Professional git workflow with feature branches for Autocoder.

Workflow Modes:
- feature_branches: Create branch per feature, merge on completion
- trunk: All changes on main branch (default)
- none: No git operations

Branch naming: feature/{feature_id}-{slugified-name}
Example: feature/42-user-can-login
"""

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# Type alias for workflow modes
WorkflowMode = Literal["feature_branches", "trunk", "none"]


@dataclass
class BranchInfo:
    """Information about a git branch."""

    name: str
    feature_id: Optional[int] = None
    is_feature_branch: bool = False
    is_current: bool = False


@dataclass
class WorkflowResult:
    """Result of a workflow operation."""

    success: bool
    message: str
    branch_name: Optional[str] = None
    previous_branch: Optional[str] = None


def slugify(text: str) -> str:
    """
    Convert text to URL-friendly slug.

    Example: "User can login" -> "user-can-login"
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Remove non-alphanumeric characters (except hyphens)
    text = re.sub(r"[^a-z0-9-]", "", text)
    # Remove consecutive hyphens
    text = re.sub(r"-+", "-", text)
    # Trim hyphens from ends
    text = text.strip("-")
    # Limit length
    return text[:50]


def get_branch_name(feature_id: int, feature_name: str, prefix: str = "feature/") -> str:
    """
    Generate branch name for a feature.

    Args:
        feature_id: Feature ID
        feature_name: Feature name
        prefix: Branch prefix (default: "feature/")

    Returns:
        Branch name like "feature/42-user-can-login"
    """
    slug = slugify(feature_name)
    return f"{prefix}{feature_id}-{slug}"


class GitWorkflow:
    """
    Git workflow manager for feature branches.

    Usage:
        workflow = GitWorkflow(project_dir, mode="feature_branches")

        # Start working on a feature
        result = workflow.start_feature(42, "User can login")
        # ... implement feature ...

        # Complete feature (merge to main)
        result = workflow.complete_feature(42)

        # Or abort feature
        result = workflow.abort_feature(42)
    """

    def __init__(
        self,
        project_dir: Path,
        mode: WorkflowMode = "trunk",
        branch_prefix: str = "feature/",
        main_branch: str = "main",
        auto_merge: bool = False,
    ):
        self.project_dir = Path(project_dir)
        self.mode = mode
        self.branch_prefix = branch_prefix
        self.main_branch = main_branch
        self.auto_merge = auto_merge

    def _run_git(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the project directory."""
        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            cwd=self.project_dir,
            capture_output=True,
            text=True,
            check=check,
        )

    def _is_git_repo(self) -> bool:
        """Check if directory is a git repository."""
        try:
            self._run_git("rev-parse", "--git-dir")
            return True
        except subprocess.CalledProcessError:
            return False

    def _get_current_branch(self) -> Optional[str]:
        """Get name of current branch."""
        try:
            result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def _branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists."""
        result = self._run_git("branch", "--list", branch_name, check=False)
        return bool(result.stdout.strip())

    def _has_uncommitted_changes(self) -> bool:
        """Check for uncommitted changes."""
        result = self._run_git("status", "--porcelain", check=False)
        return bool(result.stdout.strip())

    def get_feature_branch(self, feature_id: int) -> Optional[str]:
        """
        Find branch for a feature ID.

        Returns branch name if found, None otherwise.
        """
        result = self._run_git("branch", "--list", f"{self.branch_prefix}{feature_id}-*", check=False)
        branches = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n") if b.strip()]
        return branches[0] if branches else None

    def start_feature(self, feature_id: int, feature_name: str) -> WorkflowResult:
        """
        Start working on a feature (create and checkout branch).

        In trunk mode, this is a no-op.
        In feature_branches mode, creates branch and checks it out.

        Args:
            feature_id: Feature ID
            feature_name: Feature name for branch naming

        Returns:
            WorkflowResult with success status and branch info
        """
        if self.mode == "none":
            return WorkflowResult(
                success=True,
                message="Git workflow disabled",
            )

        if self.mode == "trunk":
            return WorkflowResult(
                success=True,
                message="Using trunk-based development",
                branch_name=self.main_branch,
            )

        # feature_branches mode
        if not self._is_git_repo():
            return WorkflowResult(
                success=False,
                message="Not a git repository",
            )

        # Check for existing branch
        existing_branch = self.get_feature_branch(feature_id)
        if existing_branch:
            # Switch to existing branch
            try:
                self._run_git("checkout", existing_branch)
                return WorkflowResult(
                    success=True,
                    message=f"Switched to existing branch: {existing_branch}",
                    branch_name=existing_branch,
                )
            except subprocess.CalledProcessError as e:
                return WorkflowResult(
                    success=False,
                    message=f"Failed to checkout branch: {e.stderr}",
                )

        # Create new branch
        branch_name = get_branch_name(feature_id, feature_name, self.branch_prefix)
        current_branch = self._get_current_branch()

        try:
            # Stash uncommitted changes if any
            had_changes = self._has_uncommitted_changes()
            if had_changes:
                self._run_git("stash", "push", "-m", f"Auto-stash before feature/{feature_id}")

            # Create and checkout new branch from main
            self._run_git("checkout", self.main_branch)
            self._run_git("checkout", "-b", branch_name)

            # Apply stashed changes if any
            if had_changes:
                self._run_git("stash", "pop", check=False)

            logger.info(f"Created feature branch: {branch_name}")
            return WorkflowResult(
                success=True,
                message=f"Created branch: {branch_name}",
                branch_name=branch_name,
                previous_branch=current_branch,
            )

        except subprocess.CalledProcessError as e:
            return WorkflowResult(
                success=False,
                message=f"Failed to create branch: {e.stderr}",
            )

    def commit_feature_progress(
        self,
        feature_id: int,
        message: str,
        add_all: bool = True,
    ) -> WorkflowResult:
        """
        Commit current changes for a feature.

        Args:
            feature_id: Feature ID
            message: Commit message
            add_all: Whether to add all changes

        Returns:
            WorkflowResult with success status
        """
        if self.mode == "none":
            return WorkflowResult(
                success=True,
                message="Git workflow disabled",
            )

        if not self._is_git_repo():
            return WorkflowResult(
                success=False,
                message="Not a git repository",
            )

        try:
            if add_all:
                self._run_git("add", "-A")

            # Check if there are staged changes
            result = self._run_git("diff", "--cached", "--quiet", check=False)
            if result.returncode == 0:
                return WorkflowResult(
                    success=True,
                    message="No changes to commit",
                )

            # Commit
            full_message = f"feat(feature-{feature_id}): {message}"
            self._run_git("commit", "-m", full_message)

            return WorkflowResult(
                success=True,
                message=f"Committed: {message}",
            )

        except subprocess.CalledProcessError as e:
            return WorkflowResult(
                success=False,
                message=f"Commit failed: {e.stderr}",
            )

    def complete_feature(self, feature_id: int) -> WorkflowResult:
        """
        Complete a feature (merge to main if auto_merge enabled).

        Args:
            feature_id: Feature ID

        Returns:
            WorkflowResult with success status
        """
        if self.mode != "feature_branches":
            return WorkflowResult(
                success=True,
                message="Feature branches not enabled",
            )

        branch_name = self.get_feature_branch(feature_id)
        if not branch_name:
            return WorkflowResult(
                success=False,
                message=f"No branch found for feature {feature_id}",
            )

        current_branch = self._get_current_branch()

        try:
            # Commit any remaining changes
            if self._has_uncommitted_changes():
                self._run_git("add", "-A")
                self._run_git("commit", "-m", f"feat(feature-{feature_id}): final changes")

            if not self.auto_merge:
                return WorkflowResult(
                    success=True,
                    message=f"Feature complete on branch {branch_name}. Manual merge required.",
                    branch_name=branch_name,
                )

            # Auto-merge enabled
            self._run_git("checkout", self.main_branch)
            self._run_git("merge", "--no-ff", branch_name, "-m", f"Merge feature {feature_id}")

            # Optionally delete feature branch
            # self._run_git("branch", "-d", branch_name)

            logger.info(f"Merged feature branch {branch_name} to {self.main_branch}")
            return WorkflowResult(
                success=True,
                message=f"Merged {branch_name} to {self.main_branch}",
                branch_name=self.main_branch,
                previous_branch=branch_name,
            )

        except subprocess.CalledProcessError as e:
            # Restore original branch on failure
            if current_branch:
                self._run_git("checkout", current_branch, check=False)
            return WorkflowResult(
                success=False,
                message=f"Merge failed: {e.stderr}",
            )

    def abort_feature(self, feature_id: int, delete_branch: bool = False) -> WorkflowResult:
        """
        Abort a feature (discard changes, optionally delete branch).

        Args:
            feature_id: Feature ID
            delete_branch: Whether to delete the feature branch

        Returns:
            WorkflowResult with success status
        """
        if self.mode != "feature_branches":
            return WorkflowResult(
                success=True,
                message="Feature branches not enabled",
            )

        branch_name = self.get_feature_branch(feature_id)
        if not branch_name:
            return WorkflowResult(
                success=False,
                message=f"No branch found for feature {feature_id}",
            )

        try:
            # Discard uncommitted changes
            self._run_git("checkout", "--", ".", check=False)
            self._run_git("clean", "-fd", check=False)

            # Switch back to main
            self._run_git("checkout", self.main_branch)

            if delete_branch:
                self._run_git("branch", "-D", branch_name)
                return WorkflowResult(
                    success=True,
                    message=f"Aborted and deleted branch {branch_name}",
                    branch_name=self.main_branch,
                )

            return WorkflowResult(
                success=True,
                message=f"Aborted feature, branch {branch_name} preserved",
                branch_name=self.main_branch,
            )

        except subprocess.CalledProcessError as e:
            return WorkflowResult(
                success=False,
                message=f"Abort failed: {e.stderr}",
            )

    def list_feature_branches(self) -> list[BranchInfo]:
        """
        List all feature branches.

        Returns:
            List of BranchInfo objects
        """
        if not self._is_git_repo():
            return []

        result = self._run_git("branch", "--list", f"{self.branch_prefix}*", check=False)

        branches = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            is_current = line.startswith("*")
            name = line.strip().lstrip("* ")

            # Extract feature ID from branch name
            feature_id = None
            match = re.search(rf"{re.escape(self.branch_prefix)}(\d+)-", name)
            if match:
                feature_id = int(match.group(1))

            branches.append(
                BranchInfo(
                    name=name,
                    feature_id=feature_id,
                    is_feature_branch=True,
                    is_current=is_current,
                )
            )

        return branches

    def get_status(self) -> dict:
        """
        Get current git workflow status.

        Returns:
            Dict with current branch, mode, uncommitted changes, etc.
        """
        if not self._is_git_repo():
            return {
                "is_git_repo": False,
                "mode": self.mode,
            }

        current = self._get_current_branch()
        feature_branches = self.list_feature_branches()

        # Check if current branch is a feature branch
        current_feature_id = None
        if current and current.startswith(self.branch_prefix):
            match = re.search(rf"{re.escape(self.branch_prefix)}(\d+)-", current)
            if match:
                current_feature_id = int(match.group(1))

        return {
            "is_git_repo": True,
            "mode": self.mode,
            "current_branch": current,
            "main_branch": self.main_branch,
            "is_on_feature_branch": current_feature_id is not None,
            "current_feature_id": current_feature_id,
            "has_uncommitted_changes": self._has_uncommitted_changes(),
            "feature_branches": [b.name for b in feature_branches],
            "feature_branch_count": len(feature_branches),
        }


def get_workflow(project_dir: Path) -> GitWorkflow:
    """
    Get git workflow manager for a project.

    Reads configuration from .autocoder/config.json.

    Args:
        project_dir: Project directory

    Returns:
        GitWorkflow instance configured for the project
    """
    # Try to load config
    mode: WorkflowMode = "trunk"
    branch_prefix = "feature/"
    main_branch = "main"
    auto_merge = False

    try:
        from server.services.autocoder_config import load_config

        config = load_config(project_dir)
        git_config = config.get("git_workflow", {})

        mode = git_config.get("mode", "trunk")
        branch_prefix = git_config.get("branch_prefix", "feature/")
        main_branch = git_config.get("main_branch", "main")
        auto_merge = git_config.get("auto_merge", False)
    except Exception:
        pass

    return GitWorkflow(
        project_dir,
        mode=mode,
        branch_prefix=branch_prefix,
        main_branch=main_branch,
        auto_merge=auto_merge,
    )
