"""
Git Router
==========

API endpoints for git status and operations.
"""

import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/git", tags=["git"])


def run_git_command(project_path: Path, args: list[str]) -> tuple[bool, str]:
    """
    Run a git command in the project directory.

    Returns:
        Tuple of (success, output/error message)
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
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Git command timed out"
    except FileNotFoundError:
        return False, "Git is not installed"
    except Exception as e:
        return False, str(e)


def get_git_status_for_project(project_path: Path) -> dict:
    """
    Get comprehensive git status for a project.

    Returns:
        Dictionary with git status information.
    """
    # Check if it's a git repo
    success, _ = run_git_command(project_path, ["rev-parse", "--git-dir"])
    if not success:
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
        }

    # Get current branch
    success, branch = run_git_command(project_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if not success:
        branch = None

    # Get ahead/behind counts
    ahead = 0
    behind = 0
    if branch:
        success, counts = run_git_command(
            project_path,
            ["rev-list", "--left-right", "--count", f"{branch}...@{{upstream}}"],
        )
        if success and counts:
            parts = counts.split()
            if len(parts) >= 2:
                ahead = int(parts[0])
                behind = int(parts[1])

    # Get status counts using porcelain format
    modified = 0
    staged = 0
    untracked = 0
    success, status_output = run_git_command(project_path, ["status", "--porcelain"])
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
    success, log_output = run_git_command(
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
