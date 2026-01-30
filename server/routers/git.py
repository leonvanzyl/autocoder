"""
Git Router
==========

API endpoints for git status and operations.
"""

import subprocess
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/git", tags=["git"])


# Error types for structured error reporting
ErrorType = Literal[
    "git_not_installed",
    "not_a_repo",
    "auth_failed",
    "timeout",
    "no_remote",
    "network",
    "unknown",
]


class GitError(BaseModel):
    """Structured git error information."""
    error_type: ErrorType
    message: str
    action: str  # Suggested remediation


def classify_git_error(error_message: str) -> GitError:
    """Classify a git error and provide structured information."""
    lower = error_message.lower()

    if "not installed" in lower or "not found" in lower:
        return GitError(
            error_type="git_not_installed",
            message="Git is not installed on this system",
            action="Install Git from https://git-scm.com/downloads",
        )

    if "timed out" in lower:
        return GitError(
            error_type="timeout",
            message="Git command timed out",
            action="Check your network connection or try again",
        )

    if "authentication" in lower or "permission denied" in lower or "403" in lower:
        return GitError(
            error_type="auth_failed",
            message="Git authentication failed",
            action="Check your SSH keys or GitHub credentials",
        )

    if "could not resolve" in lower or "unable to access" in lower or "network" in lower:
        return GitError(
            error_type="network",
            message="Network error connecting to remote",
            action="Check your internet connection",
        )

    if "no such remote" in lower or "no upstream" in lower or "does not have upstream" in lower:
        return GitError(
            error_type="no_remote",
            message="No remote configured for this branch",
            action="Run: git push -u origin <branch>",
        )

    return GitError(
        error_type="unknown",
        message=error_message or "Unknown error",
        action="Check the git output for details",
    )


def run_git_command(project_path: Path, args: list[str]) -> tuple[bool, str, GitError | None]:
    """
    Run a git command in the project directory.

    Returns:
        Tuple of (success, output/error message, structured error if failed)
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip(), None
        error = classify_git_error(result.stderr.strip())
        return False, result.stderr.strip(), error
    except subprocess.TimeoutExpired:
        error = classify_git_error("Git command timed out")
        return False, "Git command timed out", error
    except FileNotFoundError:
        error = classify_git_error("Git is not installed")
        return False, "Git is not installed", error
    except Exception as e:
        error = classify_git_error(str(e))
        return False, str(e), error


def get_git_status_for_project(project_path: Path) -> dict:
    """
    Get comprehensive git status for a project.

    Returns:
        Dictionary with git status information.
    """
    # Check if it's a git repo
    success, _, error = run_git_command(project_path, ["rev-parse", "--git-dir"])
    if not success:
        # Check if it's "not a git repo" vs an actual error
        if error and error.error_type == "git_not_installed":
            return {
                "isRepo": False,
                "branch": None,
                "ahead": 0,
                "behind": 0,
                "modified": 0,
                "staged": 0,
                "untracked": 0,
                "hasUncommittedChanges": False,
                "lastCommitMessage": None,
                "lastCommitDate": None,
                "error": error.model_dump() if error else None,
            }
        return {
            "isRepo": False,
            "branch": None,
            "ahead": 0,
            "behind": 0,
            "modified": 0,
            "staged": 0,
            "untracked": 0,
            "hasUncommittedChanges": False,
            "lastCommitMessage": None,
            "lastCommitDate": None,
            "error": None,
        }

    # Get current branch
    success, branch, _ = run_git_command(project_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if not success:
        branch = None

    # Get ahead/behind counts
    ahead = 0
    behind = 0
    remote_error = None
    if branch:
        success, counts, error = run_git_command(
            project_path,
            ["rev-list", "--left-right", "--count", f"{branch}...@{{upstream}}"],
        )
        if success and counts:
            parts = counts.split()
            if len(parts) >= 2:
                ahead = int(parts[0])
                behind = int(parts[1])
        elif error:
            # Save remote error to include in response
            remote_error = error

    # Get status counts using porcelain format
    modified = 0
    staged = 0
    untracked = 0
    success, status_output, _ = run_git_command(project_path, ["status", "--porcelain"])
    if success:
        for line in status_output.split("\n"):
            if not line:
                continue
            index_status = line[0] if len(line) > 0 else " "
            worktree_status = line[1] if len(line) > 1 else " "

            # Staged changes (index)
            if index_status in "MADRC":
                staged += 1

            # Modified in worktree
            if worktree_status in "MD":
                modified += 1

            # Untracked
            if index_status == "?" and worktree_status == "?":
                untracked += 1

    has_uncommitted = (modified + staged + untracked) > 0

    # Get last commit info
    last_commit_message = None
    last_commit_date = None
    success, log_output, _ = run_git_command(
        project_path,
        ["log", "-1", "--format=%s|||%ci"],
    )
    if success and log_output:
        parts = log_output.split("|||")
        if len(parts) >= 1:
            last_commit_message = parts[0]
        if len(parts) >= 2:
            last_commit_date = parts[1]

    return {
        "isRepo": True,
        "branch": branch,
        "ahead": ahead,
        "behind": behind,
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "hasUncommittedChanges": has_uncommitted,
        "lastCommitMessage": last_commit_message,
        "lastCommitDate": last_commit_date,
        "error": remote_error.model_dump() if remote_error else None,
    }


@router.get("/status/{project_name}")
async def get_git_status(project_name: str):
    """
    Get git status for a project.

    Args:
        project_name: The project name.

    Returns:
        Git status information.
    """
    import sys

    # Import registry to get project path
    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    return get_git_status_for_project(project_path)


@router.post("/status/{project_name}/refresh")
async def refresh_git_status(project_name: str):
    """
    Force refresh git status (useful after git operations).

    Args:
        project_name: The project name.

    Returns:
        Fresh git status information.
    """
    return await get_git_status(project_name)
