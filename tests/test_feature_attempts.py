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


def test_requeue_feature_preserves_branch_and_does_not_increment_attempts(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCODER_FEATURE_RETRY_INITIAL_DELAY_S", "0")

    db = Database(str(tmp_path / "agent_system.db"))
    feature_id = db.create_feature("x", "y", "backend")

    # Simulate a previously-created branch and a failure.
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE features SET branch_name = ?, status = 'IN_PROGRESS' WHERE id = ?", ("feat/keep", feature_id))
        conn.commit()

    assert db.mark_feature_failed(feature_id=feature_id, reason="fail", preserve_branch=True, next_status="IN_PROGRESS") is True
    row = db.get_feature(feature_id)
    assert row is not None
    assert row["attempts"] == 1
    assert row["branch_name"] == "feat/keep"

    assert db.requeue_feature(feature_id, preserve_branch=True) is True
    row2 = db.get_feature(feature_id)
    assert row2 is not None
    assert row2["status"] == "PENDING"
    assert row2["attempts"] == 1
    assert row2["branch_name"] == "feat/keep"


def test_increment_qa_attempts(tmp_path):
    db = Database(str(tmp_path / "agent_system.db"))
    feature_id = db.create_feature("x", "y", "backend")
    assert db.increment_qa_attempts(feature_id) == 1
    assert db.increment_qa_attempts(feature_id) == 2
    row = db.get_feature(feature_id)
    assert row is not None
    assert int(row.get("qa_attempts") or 0) == 2
