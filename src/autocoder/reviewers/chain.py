from __future__ import annotations

from dataclasses import dataclass

from .base import ReviewConfig, ReviewFinding, ReviewResult, Reviewer
from .claude import ClaudeReviewer
from .multi_cli import MultiCliReviewer


def _consensus_mode(value: str | None) -> str:
    v = (value or "majority").strip().lower()
    return v if v in {"majority", "all", "any"} else "majority"


@dataclass(frozen=True)
class ChainReviewer(Reviewer):
    """
    Review using multiple engines as a single logical gate.

    This aggregates a Claude reviewer and a multi-CLI reviewer, then applies the
    configured consensus rule across those results.
    """

    cfg: ReviewConfig

    def _decide(self, results: list[tuple[str, ReviewResult]]) -> ReviewResult:
        active = [(n, r) for (n, r) in results if not r.skipped]
        if not active:
            return ReviewResult(approved=True, skipped=True, reason="All reviewers skipped")

        mode = _consensus_mode(self.cfg.consensus)
        approvals = sum(1 for _, r in active if r.approved)
        total = len(active)

        if mode == "all":
            approved = approvals == total
        elif mode == "any":
            approved = approvals >= 1
        else:
            approved = approvals >= ((total // 2) + 1)

        findings: list[ReviewFinding] = []
        reasons: list[str] = []
        for name, r in active:
            reasons.append(f"{name}: {r.reason}".strip())
            findings.extend(r.findings)

        return ReviewResult(
            approved=approved,
            reason=("; ".join([x for x in reasons if x]) or "Review complete"),
            findings=findings,
        )

    def review(
        self,
        *,
        workdir: str,
        base_branch: str,
        feature_branch: str,
        agent_id: str | None = None,
    ) -> ReviewResult:
        engines = [e for e in (self.cfg.engines or []) if e]
        results: list[tuple[str, ReviewResult]] = []

        if "claude_review" in engines:
            results.append(("claude", ClaudeReviewer(self.cfg).review(
                workdir=workdir,
                base_branch=base_branch,
                feature_branch=feature_branch,
                agent_id=agent_id,
            )))

        if "codex_cli" in engines or "gemini_cli" in engines:
            results.append(("multi_cli", MultiCliReviewer(self.cfg).review(
                workdir=workdir,
                base_branch=base_branch,
                feature_branch=feature_branch,
                agent_id=agent_id,
            )))

        if not results:
            return ReviewResult(approved=True, skipped=True, reason="No reviewers configured")

        return self._decide(results)

