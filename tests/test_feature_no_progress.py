from autocoder.core.database import Database


def test_feature_blocks_on_same_error_streak(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCODER_FEATURE_MAX_ATTEMPTS", "99")
    monkeypatch.setenv("AUTOCODER_FEATURE_MAX_SAME_ERROR_STREAK", "2")
    monkeypatch.setenv("AUTOCODER_FEATURE_RETRY_INITIAL_DELAY_S", "0")

    db = Database(str(tmp_path / "agent_system.db"))
    feature_id = db.create_feature("x", "y", "backend")

    # First failure: pending.
    assert (
        db.mark_feature_failed(
            feature_id=feature_id,
            reason="Gatekeeper rejected: Tests failed\nArtifact: /tmp/a.json",
            artifact_path="/tmp/a.json",
        )
        is True
    )
    row = db.get_feature(feature_id)
    assert row is not None
    assert row["status"] == "PENDING"
    assert row["same_error_streak"] == 1

    # Second failure with different artifact path, but same key -> should block.
    assert (
        db.mark_feature_failed(
            feature_id=feature_id,
            reason="Gatekeeper rejected: Tests failed\nArtifact: /tmp/b.json",
            artifact_path="/tmp/b.json",
        )
        is True
    )
    row2 = db.get_feature(feature_id)
    assert row2 is not None
    assert row2["status"] == "BLOCKED"
    assert row2["same_error_streak"] == 2


def test_feature_blocks_on_same_diff_streak(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCODER_FEATURE_MAX_ATTEMPTS", "99")
    monkeypatch.setenv("AUTOCODER_FEATURE_MAX_SAME_ERROR_STREAK", "99")
    monkeypatch.setenv("AUTOCODER_FEATURE_MAX_SAME_DIFF_STREAK", "2")
    monkeypatch.setenv("AUTOCODER_FEATURE_RETRY_INITIAL_DELAY_S", "0")

    db = Database(str(tmp_path / "agent_system.db"))
    feature_id = db.create_feature("x", "y", "backend")

    assert (
        db.mark_feature_failed(
            feature_id=feature_id,
            reason="Gatekeeper rejected: lint failed",
            diff_fingerprint="abc",
        )
        is True
    )
    row = db.get_feature(feature_id)
    assert row is not None
    assert row["status"] == "PENDING"
    assert row["same_diff_streak"] == 1

    # Different error text, but identical diff fingerprint -> should block (no progress).
    assert (
        db.mark_feature_failed(
            feature_id=feature_id,
            reason="Gatekeeper rejected: typecheck failed",
            diff_fingerprint="abc",
        )
        is True
    )
    row2 = db.get_feature(feature_id)
    assert row2 is not None
    assert row2["status"] == "BLOCKED"
    assert row2["same_diff_streak"] == 2


def test_claim_next_reuses_existing_branch_name(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCODER_FEATURE_RETRY_INITIAL_DELAY_S", "0")

    db = Database(str(tmp_path / "agent_system.db"))
    feature_id = db.create_feature("x", "y", "backend")

    # Simulate a previously-created branch that should be resumed.
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE features SET branch_name = ?, status = 'PENDING' WHERE id = ?", ("feat/keep", feature_id))
        conn.commit()

    claimed = db.claim_next_pending_feature("agent-1")
    assert claimed is not None
    row = db.get_feature(feature_id)
    assert row is not None
    assert row["branch_name"] == "feat/keep"
