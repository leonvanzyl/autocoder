from pathlib import Path

from autocoder.core.database import Database


def test_pending_queue_state_counts(tmp_path: Path):
    db = Database(str(tmp_path / "agent_system.db"))

    # Feature 1: pending & claimable
    f1 = db.create_feature("f1", "desc", "cat")
    # Feature 2: pending but depends on f1
    f2 = db.create_feature("f2", "desc", "cat", depends_on=[f1])

    st = db.get_pending_queue_state()
    assert st["pending_total"] == 2
    assert st["claimable_now"] == 1
    assert st["waiting_deps"] == 1

    # Mark f1 done -> f2 becomes claimable
    assert db.mark_feature_passing(int(f1))
    st2 = db.get_pending_queue_state()
    assert st2["pending_total"] == 1
    assert st2["claimable_now"] == 1
