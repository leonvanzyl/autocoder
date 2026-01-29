"""
Pull Request Router
===================

API endpoints for pull request workflow management.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add parent directory to path
root_dir = Path(__file__).parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from registry import get_project

router = APIRouter(prefix="/api/pr", tags=["pull-requests"])


class PRCreateRequest(BaseModel):
    """Request to create a pull request."""
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(default="")
    base_branch: str = Field(default="main")
    draft: bool = Field(default=False)


class PRResponse(BaseModel):
    """Pull request information."""
    number: int
    title: str
    state: str
    url: str
    head_branch: str
    base_branch: str
    author: str | None
    created_at: str | None
    updated_at: str | None
    mergeable: bool | None
    additions: int | None
    deletions: int | None
    changed_files: int | None


def _get_project_path(project_name: str) -> Path:
    """Get project path or raise 404."""
    project = get_project(project_name)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    project_path = Path(project.path)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    return project_path


def _run_gh_command(project_path: Path, args: list[str]) -> tuple[bool, str]:
    """
    Run a GitHub CLI command in the project directory.

    Returns:
        Tuple of (success, output/error message)
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "GitHub CLI command timed out"
    except FileNotFoundError:
        return False, "GitHub CLI (gh) is not installed. Install it from https://cli.github.com/"
    except Exception as e:
        return False, str(e)


def _parse_pr_json(data: dict[str, Any]) -> PRResponse:
    """Parse PR data from GitHub CLI JSON output."""
    return PRResponse(
        number=data.get("number", 0),
        title=data.get("title", ""),
        state=data.get("state", "unknown"),
        url=data.get("url", ""),
        head_branch=data.get("headRefName", ""),
        base_branch=data.get("baseRefName", ""),
        author=data.get("author", {}).get("login") if data.get("author") else None,
        created_at=data.get("createdAt"),
        updated_at=data.get("updatedAt"),
        mergeable=data.get("mergeable") == "MERGEABLE" if data.get("mergeable") else None,
        additions=data.get("additions"),
        deletions=data.get("deletions"),
        changed_files=data.get("changedFiles"),
    )


@router.get("/{project_name}/status")
async def get_pr_status(project_name: str):
    """
    Get the current PR status for the project's branch.

    Returns:
        PR information if one exists for the current branch, or status indicating no PR.
    """
    import json

    project_path = _get_project_path(project_name)

    # Check if gh is authenticated
    success, output = _run_gh_command(project_path, ["auth", "status"])
    if not success:
        return {
            "hasPR": False,
            "authenticated": False,
            "message": "GitHub CLI not authenticated. Run 'gh auth login' to authenticate.",
        }

    # Get current branch
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        current_branch = result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        current_branch = None

    if not current_branch:
        return {
            "hasPR": False,
            "authenticated": True,
            "currentBranch": None,
            "message": "Could not determine current branch",
        }

    # Check for existing PR
    success, output = _run_gh_command(
        project_path,
        ["pr", "view", "--json", "number,title,state,url,headRefName,baseRefName,author,createdAt,updatedAt,mergeable,additions,deletions,changedFiles"],
    )

    if success:
        try:
            data = json.loads(output)
            pr = _parse_pr_json(data)
            return {
                "hasPR": True,
                "authenticated": True,
                "currentBranch": current_branch,
                "pr": pr.model_dump(),
            }
        except json.JSONDecodeError:
            pass

    return {
        "hasPR": False,
        "authenticated": True,
        "currentBranch": current_branch,
        "message": "No pull request found for current branch",
    }


@router.post("/{project_name}/create")
async def create_pr(project_name: str, request: PRCreateRequest):
    """
    Create a new pull request.

    Args:
        project_name: The project name
        request: PR creation details

    Returns:
        Created PR information
    """
    import json

    project_path = _get_project_path(project_name)

    # Build the command
    args = [
        "pr", "create",
        "--title", request.title,
        "--body", request.body,
        "--base", request.base_branch,
    ]

    if request.draft:
        args.append("--draft")

    success, output = _run_gh_command(project_path, args)

    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to create PR: {output}")

    # Get the created PR details
    success, pr_output = _run_gh_command(
        project_path,
        ["pr", "view", "--json", "number,title,state,url,headRefName,baseRefName,author,createdAt,updatedAt,mergeable,additions,deletions,changedFiles"],
    )

    if success:
        try:
            data = json.loads(pr_output)
            pr = _parse_pr_json(data)
            return {
                "success": True,
                "pr": pr.model_dump(),
                "message": f"Pull request #{pr.number} created successfully",
            }
        except json.JSONDecodeError:
            pass

    # Return basic success if we can't get full details
    return {
        "success": True,
        "url": output,  # gh pr create outputs the URL
        "message": "Pull request created successfully",
    }


@router.get("/{project_name}/list")
async def list_prs(project_name: str, state: str = "open"):
    """
    List pull requests for the repository.

    Args:
        project_name: The project name
        state: PR state filter (open, closed, merged, all)

    Returns:
        List of PRs
    """
    import json

    project_path = _get_project_path(project_name)

    args = [
        "pr", "list",
        "--state", state,
        "--json", "number,title,state,url,headRefName,baseRefName,author,createdAt,updatedAt",
        "--limit", "20",
    ]

    success, output = _run_gh_command(project_path, args)

    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to list PRs: {output}")

    try:
        prs = json.loads(output)
        return {
            "prs": [_parse_pr_json(pr).model_dump() for pr in prs],
            "state": state,
        }
    except json.JSONDecodeError:
        return {"prs": [], "state": state}


@router.post("/{project_name}/push")
async def push_branch(project_name: str, force: bool = False):
    """
    Push the current branch to remote.

    Args:
        project_name: The project name
        force: Whether to force push

    Returns:
        Push result
    """
    project_path = _get_project_path(project_name)

    # Get current branch
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        current_branch = result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        raise HTTPException(status_code=400, detail="Could not determine current branch")

    if not current_branch:
        raise HTTPException(status_code=400, detail="Could not determine current branch")

    # Push to remote
    args = ["git", "push", "-u", "origin", current_branch]
    if force:
        args.insert(2, "--force")

    try:
        result = subprocess.run(
            args,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return {
                "success": True,
                "branch": current_branch,
                "message": f"Successfully pushed {current_branch} to origin",
            }
        else:
            error = result.stderr.strip() or result.stdout.strip()
            raise HTTPException(status_code=400, detail=f"Push failed: {error}")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Push operation timed out")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_name}/checks")
async def get_pr_checks(project_name: str):
    """
    Get CI check status for the current PR.

    Returns:
        Check status information
    """
    import json

    project_path = _get_project_path(project_name)

    success, output = _run_gh_command(
        project_path,
        ["pr", "checks", "--json", "name,state,conclusion,startedAt,completedAt,detailsUrl"],
    )

    if not success:
        if "no pull request found" in output.lower():
            return {"hasChecks": False, "checks": [], "message": "No pull request found"}
        raise HTTPException(status_code=400, detail=f"Failed to get checks: {output}")

    try:
        checks = json.loads(output)
        return {
            "hasChecks": True,
            "checks": checks,
            "summary": {
                "total": len(checks),
                "passing": len([c for c in checks if c.get("conclusion") == "SUCCESS"]),
                "failing": len([c for c in checks if c.get("conclusion") == "FAILURE"]),
                "pending": len([c for c in checks if c.get("state") == "PENDING"]),
            },
        }
    except json.JSONDecodeError:
        return {"hasChecks": False, "checks": []}
