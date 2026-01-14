from autocoder.reviewers.base import ReviewConfig, ReviewResult
from autocoder.reviewers.multi_cli import MultiCliReviewer


def test_multi_cli_reviewer_consensus_majority():
    cfg = ReviewConfig(
        enabled=True,
        mode="gate",
        reviewer_type="multi_cli",
        timeout_s=1,
        review_agents=["codex", "gemini"],
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
        reviewer_type="multi_cli",
        timeout_s=1,
        review_agents=["codex", "gemini"],
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
