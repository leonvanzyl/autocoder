import sys

from autocoder.reviewers.base import ReviewConfig
from autocoder.reviewers.command import CommandReviewer
from autocoder.reviewers.factory import get_reviewer


def test_get_reviewer_none_when_disabled():
    cfg = ReviewConfig(enabled=False, mode="off", reviewer_type="none")
    assert get_reviewer(cfg) is None


def test_command_reviewer_sets_env_and_passes(tmp_path):
    cmd = (
        f"\"{sys.executable}\" -c "
        "\"import os,sys; "
        "sys.exit(0 if os.environ.get('AUTOCODER_REVIEW_BASE_BRANCH')=='main' else 2)\""
    )
    cfg = ReviewConfig(enabled=True, mode="gate", reviewer_type="command", command=cmd, timeout_s=5)
    reviewer = CommandReviewer(cfg)
    result = reviewer.review(workdir=str(tmp_path), base_branch="main", feature_branch="feat/x", agent_id="a1")
    assert result.approved is True


def test_reviewer_env_overrides(monkeypatch):
    monkeypatch.setenv("AUTOCODER_REVIEW_ENABLED", "1")
    monkeypatch.setenv("AUTOCODER_REVIEW_MODE", "gate")
    monkeypatch.setenv("AUTOCODER_REVIEW_TYPE", "command")
    monkeypatch.setenv("AUTOCODER_REVIEW_COMMAND", f"\"{sys.executable}\" -c \"import sys; sys.exit(0)\"")
    monkeypatch.setenv("AUTOCODER_REVIEW_TIMEOUT_S", "5")

    cfg = ReviewConfig(enabled=False, mode="off", reviewer_type="none")
    reviewer = get_reviewer(cfg)
    assert reviewer is not None
