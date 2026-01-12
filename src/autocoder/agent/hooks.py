from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass


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

    def pre_tool_use(self, input_data: dict) -> dict:
        tool_name = input_data.get("tool_name") or ""
        tool_input = input_data.get("tool_input") or {}

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

