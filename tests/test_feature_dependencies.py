from autocoder.core.database import Database


def test_feature_dependencies_block_claim_until_done(tmp_path):
    db = Database(str(tmp_path / "agent_system.db"))

    a_id = db.create_feature("A", "first", "core")
    b_id = db.create_feature("B", "second", "core", depends_on=[a_id])

    # Only A is ready initially.
    next_row = db.get_next_pending_feature()
    assert next_row is not None
    assert next_row["id"] == a_id

    claimed = db.claim_next_pending_feature("agent-1")
    assert claimed is not None
    assert claimed["id"] == a_id

    # Even though B is pending, it shouldn't be claimable yet.
    assert db.get_next_pending_feature() is None

    assert db.mark_feature_passing(a_id) is True

    claimed2 = db.claim_next_pending_feature("agent-2")
    assert claimed2 is not None
    assert claimed2["id"] == b_id
    assert claimed2["depends_on"] == [a_id]

