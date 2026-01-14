from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from .base import ReviewConfig, ReviewResult, Reviewer


@dataclass(frozen=True)
class CommandReviewer(Reviewer):
    cfg: ReviewConfig

    def review(
        self,
        *,
        workdir: str,
        base_branch: str,
        feature_branch: str,
        agent_id: str | None = None,
    ) -> ReviewResult:
        if not self.cfg.command or not self.cfg.command.strip():
            return ReviewResult(approved=True, skipped=True, reason="No review command configured")

        env = dict(os.environ)
        env["AUTOCODER_REVIEW_BASE_BRANCH"] = base_branch
        env["AUTOCODER_REVIEW_FEATURE_BRANCH"] = feature_branch
        if agent_id:
            env["AUTOCODER_AGENT_ID"] = agent_id
            env["AGENT_ID"] = agent_id

        try:
            proc = subprocess.run(
                self.cfg.command,
                cwd=workdir,
                shell=True,  # user-supplied command; keeps config stack-agnostic
                capture_output=True,
                text=True,
                timeout=self.cfg.timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            return ReviewResult(
                approved=False,
                reason=f"Review command timed out after {self.cfg.timeout_s}s",
                stdout=(e.stdout or ""),
                stderr=(e.stderr or ""),
            )

        approved = proc.returncode == 0
        return ReviewResult(
            approved=approved,
            reason="Review command passed" if approved else f"Review command failed (exit {proc.returncode})",
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )

