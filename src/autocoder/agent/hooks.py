from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from autocoder.core.file_locks import get_lock_holder, try_acquire_lock


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class ToolUsageGuardrails:
    """
    Lightweight, per-session tool guardrails enforced via PreToolUse hook.

    Env vars:
    - AUTOCODER_GUARDRAIL_MAX_TOOL_CALLS (default 400)
    - AUTOCODER_GUARDRAIL_MAX_SAME_TOOL_CALLS (default 50)
    """

    max_tool_calls: int = 400
    max_same_tool_calls: int = 50

    def __post_init__(self):
        self.max_tool_calls = max(1, self.max_tool_calls)
        self.max_same_tool_calls = max(1, self.max_same_tool_calls)
        self._tool_calls = 0
        self._sig_counts: dict[str, int] = {}

    @classmethod
    def from_env(cls) -> "ToolUsageGuardrails":
        return cls(
            max_tool_calls=_env_int("AUTOCODER_GUARDRAIL_MAX_TOOL_CALLS", 400),
            max_same_tool_calls=_env_int("AUTOCODER_GUARDRAIL_MAX_SAME_TOOL_CALLS", 50),
        )

    async def pre_tool_use(self, input_data, tool_use_id=None, context=None) -> dict:
        """
        PreToolUse hook entrypoint (Claude Agent SDK).

        The SDK passes a mapping-like object with keys like `tool_name` and `tool_input`.
        """
        if not isinstance(input_data, Mapping):
            return {}

        tool_name = input_data.get("tool_name") or ""
        tool_input = input_data.get("tool_input") or {}
        if not isinstance(tool_input, Mapping):
            tool_input = {"value": tool_input}

        self._tool_calls += 1
        if self._tool_calls > self.max_tool_calls:
            return {
                "decision": "block",
                "reason": f"Guardrail: too many tool calls ({self._tool_calls} > {self.max_tool_calls})",
            }

        # Signature = tool + stable hash of normalized input
        try:
            normalized = json.dumps(tool_input, sort_keys=True, default=str)
        except Exception:
            normalized = str(tool_input)
        sig = f"{tool_name}:{hashlib.sha256(normalized.encode('utf-8', errors='replace')).hexdigest()[:12]}"
        self._sig_counts[sig] = self._sig_counts.get(sig, 0) + 1
        if self._sig_counts[sig] > self.max_same_tool_calls:
            return {
                "decision": "block",
                "reason": (
                    "Guardrail: repeated identical tool call "
                    f"({self._sig_counts[sig]} > {self.max_same_tool_calls})"
                ),
            }

        return {}


@dataclass(frozen=True)
class FileLockGuard:
    """
    PreToolUse hook that enforces optional file locks.

    When enabled, blocks file-write tools unless the agent holds the lock for that path.

    Env vars:
    - AUTOCODER_LOCKS_ENABLED=1
    - AUTOCODER_LOCK_DIR (default: <cwd>/.autocoder/locks)
    - AUTOCODER_AGENT_ID (required)
    """

    lock_dir: Path
    agent_id: str

    @classmethod
    def from_env(cls) -> "FileLockGuard | None":
        enabled = os.environ.get("AUTOCODER_LOCKS_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        if not enabled:
            return None
        agent_id = (os.environ.get("AUTOCODER_AGENT_ID") or os.environ.get("AGENT_ID") or "").strip()
        if not agent_id:
            return None
        lock_dir = os.environ.get("AUTOCODER_LOCK_DIR") or str(Path.cwd() / ".autocoder" / "locks")
        return cls(lock_dir=Path(lock_dir).resolve(), agent_id=agent_id)

    async def pre_tool_use(self, input_data, tool_use_id=None, context=None) -> dict:
        if not isinstance(input_data, Mapping):
            return {}
        tool_name = str(input_data.get("tool_name") or "")
        if tool_name not in {"Write", "Edit", "MultiEdit"}:
            return {}
        tool_input = input_data.get("tool_input") or {}
        if not isinstance(tool_input, Mapping):
            return {}

        path = tool_input.get("path") or tool_input.get("file_path")
        if not isinstance(path, str) or not path.strip():
            return {}

        holder = get_lock_holder(self.lock_dir, path)
        if holder == self.agent_id:
            return {}
        if holder:
            return {
                "decision": "block",
                "reason": f"File lock required: '{path}' is locked by '{holder}' (agent '{self.agent_id}' cannot write).",
            }

        # Opportunistic auto-acquire: first writer wins. This keeps UX smooth while still preventing
        # concurrent edits to the same file across agents/sub-agents.
        if try_acquire_lock(self.lock_dir, path, self.agent_id):
            return {}

        holder = get_lock_holder(self.lock_dir, path)
        return {
            "decision": "block",
            "reason": (
                f"File lock required: '{path}' is locked by '{holder or 'unknown'}' "
                f"(agent '{self.agent_id}', lock dir '{self.lock_dir}')."
            ),
        }

