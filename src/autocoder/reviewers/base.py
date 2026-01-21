from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ReviewMode = Literal["off", "advisory", "gate"]
@dataclass(frozen=True)
class ReviewConfig:
    enabled: bool = False
    mode: ReviewMode = "off"
    timeout_s: int | None = None

    # claude reviewer (optional)
    model: str | None = None

    # multi_cli reviewer (optional)
    engines: list[str] | None = None
    consensus: str | None = None  # majority|all|any
    codex_model: str | None = None
    codex_reasoning_effort: str | None = None
    gemini_model: str | None = None


@dataclass(frozen=True)
class ReviewFinding:
    severity: Literal["P0", "P1", "P2", "P3"] = "P2"
    message: str = ""
    file: str | None = None


@dataclass
class ReviewResult:
    approved: bool
    skipped: bool = False
    reason: str = ""
    findings: list[ReviewFinding] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


class Reviewer:
    def review(
        self,
        *,
        workdir: str,
        base_branch: str,
        feature_branch: str,
        agent_id: str | None = None,
    ) -> ReviewResult:
        raise NotImplementedError
