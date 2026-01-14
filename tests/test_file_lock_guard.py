from pathlib import Path

import asyncio

from autocoder.agent.hooks import FileLockGuard
from autocoder.core.file_locks import acquire_lock


def test_file_lock_guard_blocks_without_lock(tmp_path: Path, monkeypatch):
    lock_dir = tmp_path / "locks"
    monkeypatch.setenv("AUTOCODER_LOCKS_ENABLED", "1")
    monkeypatch.setenv("AUTOCODER_LOCK_DIR", str(lock_dir))
    monkeypatch.setenv("AUTOCODER_AGENT_ID", "agent-1")

    guard = FileLockGuard.from_env()
    assert guard is not None

    # Not locked: should block.
    result = asyncio.run(guard.pre_tool_use({"tool_name": "Write", "tool_input": {"path": "a.txt"}}))
    assert result.get("decision") == "block"

    # Lock then allow.
    assert acquire_lock(lock_dir, "a.txt", "agent-1", timeout_seconds=0) is True
    result2 = asyncio.run(guard.pre_tool_use({"tool_name": "Write", "tool_input": {"path": "a.txt"}}))
    assert result2 == {}
