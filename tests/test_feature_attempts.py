from autocoder.core.database import Database


def test_feature_blocks_after_max_attempts(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCODER_FEATURE_MAX_ATTEMPTS", "2")

    db = Database(str(tmp_path / "agent_system.db"))
    feature_id = db.create_feature("x", "y", "backend")

    # First failure: should requeue pending.
    assert db.mark_feature_failed(feature_id=feature_id, reason="fail1") is True
    row = db.get_feature(feature_id)
    assert row["status"] == "PENDING"
    assert row["attempts"] == 1
    assert row["last_error"] == "fail1"

    # Second failure: should block.
    assert db.mark_feature_failed(feature_id=feature_id, reason="fail2") is True
    row = db.get_feature(feature_id)
    assert row["status"] == "BLOCKED"
    assert row["attempts"] == 2
    assert row["last_error"] == "fail2"


def test_claim_skips_blocked_or_exhausted_features(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCODER_FEATURE_MAX_ATTEMPTS", "1")

    db = Database(str(tmp_path / "agent_system.db"))
    bad_id = db.create_feature("bad", "bad", "backend")
    good_id = db.create_feature("good", "good", "backend")

    # Exhaust first feature.
    assert db.mark_feature_failed(feature_id=bad_id, reason="nope") is True
    assert db.get_feature(bad_id)["status"] == "BLOCKED"

    claimed = db.claim_next_pending_feature("agent-1")
    assert claimed is not None
    assert claimed["id"] == good_id

