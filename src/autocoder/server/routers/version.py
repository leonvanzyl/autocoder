"""
Version Router
==============

Lightweight endpoint to help debug UI/backend mismatches.
"""

from __future__ import annotations

import subprocess
from importlib import metadata
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/version", tags=["version"])


def _try_get_package_version() -> str | None:
    try:
        return metadata.version("autocoder")
    except Exception:
        return None


def _try_get_git_sha() -> str | None:
    # Only attempt git when we appear to be in a source checkout.
    here = Path(__file__).resolve()
    repo_root: Path | None = None
    for parent in [here, *here.parents]:
        if (parent / ".git").exists():
            repo_root = parent
            break
    if repo_root is None:
        return None

    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(repo_root))
        return sha.decode("utf-8", errors="ignore").strip() or None
    except Exception:
        return None


@router.get("")
async def get_version():
    return {
        "package_version": _try_get_package_version(),
        "git_sha": _try_get_git_sha(),
    }

