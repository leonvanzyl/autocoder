from autocoder.reviewers.base import ReviewConfig, ReviewResult
from autocoder.reviewers.multi_cli import MultiCliReviewer


def test_multi_cli_reviewer_consensus_majority():
    cfg = ReviewConfig(
        enabled=True,
        mode="gate",
        timeout_s=1,
        engines=["codex_cli", "gemini_cli"],
        consensus="majority",
    )
    r = MultiCliReviewer(cfg)

    res = r._decide(
        [
            ("codex", ReviewResult(approved=True, reason="ok")),
            ("gemini", ReviewResult(approved=False, reason="no")),
        ]
    )
    assert res.approved is False  # 1/2 is not majority


def test_multi_cli_reviewer_consensus_any():
    cfg = ReviewConfig(
        enabled=True,
        mode="gate",
        timeout_s=1,
        engines=["codex_cli", "gemini_cli"],
        consensus="any",
    )
    r = MultiCliReviewer(cfg)
    res = r._decide(
        [
            ("codex", ReviewResult(approved=True, reason="ok")),
            ("gemini", ReviewResult(approved=False, reason="no")),
        ]
    )
    assert res.approved is True
