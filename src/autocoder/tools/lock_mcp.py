#!/usr/bin/env python3
"""
MCP Server for File Locks
========================

Provides optional file-level locks to coordinate multiple agents operating on the same repo.

This is disabled by default in AutoCoder (worktrees already isolate most edits), but becomes
useful for:
- shared-worktree modes
- sub-agents collaborating in one workspace
- enforcing "lock before write" guardrails
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from autocoder.core.file_locks import (
    acquire_lock,
    cleanup_agent_locks,
    get_lock_holder,
    list_locks,
    release_lock,
)


PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()
LOCK_DIR = Path(os.environ.get("AUTOCODER_LOCK_DIR", PROJECT_DIR / ".autocoder" / "locks")).resolve()

mcp = FastMCP("locks")


class LockAcquireInput(BaseModel):
    filepaths: list[str] = Field(..., min_length=1, description="Repo-relative file paths to lock")
    timeout_seconds: float = Field(default=0.0, ge=0.0, description="How long to wait for locks")
    agent_id: str | None = Field(default=None, description="Agent ID (defaults to AUTOCODER_AGENT_ID)")


class LockReleaseInput(BaseModel):
    filepaths: list[str] | None = Field(default=None, description="Repo-relative file paths to unlock")
    all: bool = Field(default=False, description="Release all locks held by this agent")
    agent_id: str | None = Field(default=None, description="Agent ID (defaults to AUTOCODER_AGENT_ID)")


@mcp.tool()
def lock_acquire(filepaths: list[str], timeout_seconds: float = 0.0, agent_id: str | None = None) -> dict:
    agent_id = agent_id or os.environ.get("AUTOCODER_AGENT_ID") or os.environ.get("AGENT_ID") or "default"
    results = []
    all_acquired = True
    for p in filepaths:
        ok = acquire_lock(LOCK_DIR, p, agent_id, timeout_seconds=timeout_seconds)
        holder = get_lock_holder(LOCK_DIR, p)
        results.append({"path": p, "acquired": ok, "holder": holder})
        if not ok:
            all_acquired = False
    return {"lock_dir": str(LOCK_DIR), "agent_id": agent_id, "all_acquired": all_acquired, "results": results}


@mcp.tool()
def lock_release(filepaths: list[str] | None = None, all: bool = False, agent_id: str | None = None) -> dict:
    agent_id = agent_id or os.environ.get("AUTOCODER_AGENT_ID") or os.environ.get("AGENT_ID") or "default"
    released = []
    if all:
        count = cleanup_agent_locks(LOCK_DIR, agent_id)
        return {"lock_dir": str(LOCK_DIR), "agent_id": agent_id, "released_count": count, "released": []}
    for p in (filepaths or []):
        ok = release_lock(LOCK_DIR, p, agent_id)
        released.append({"path": p, "released": ok})
    return {"lock_dir": str(LOCK_DIR), "agent_id": agent_id, "released": released}


@mcp.tool()
def lock_list() -> dict:
    items = [{"key": li.key, "agent_id": li.agent_id, "acquired_at": li.acquired_at} for li in list_locks(LOCK_DIR)]
    return {"lock_dir": str(LOCK_DIR), "locks": items}


if __name__ == "__main__":
    mcp.run()

