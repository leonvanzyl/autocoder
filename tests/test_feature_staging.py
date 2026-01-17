from pathlib import Path

from autocoder.core.database import Database


def _make_features(n: int) -> list[dict]:
    return [
        {
            "name": f"Feature {i}",
            "description": f"Desc {i}",
            "category": "functional",
            "steps": [f"Step {i}-1"],
            "priority": n - i,
        }
        for i in range(n)
    ]


def test_stage_and_enqueue_features(tmp_path: Path):
    db = Database(str(tmp_path / "agent_system.db"))

    created = db.create_features_bulk(_make_features(6))
    assert created == 6

    # Stage all but top 2
    staged = db.stage_features_excluding_top(2)
    assert staged == 4

    pending = db.get_features_by_status("PENDING")
    staged_rows = db.get_staged_features()
    assert len(pending) == 2
    assert len(staged_rows) == 4

    enabled = db.enqueue_staged_features(1)
    assert enabled == 1

    pending_after = db.get_features_by_status("PENDING")
    staged_after = db.get_staged_features()
    assert len(pending_after) == 3
    assert len(staged_after) == 3
