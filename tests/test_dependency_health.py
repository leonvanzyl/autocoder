from autocoder.core.database import Database


def test_block_unresolvable_dependencies_blocks_downstream_of_blocked(tmp_path):
    db = Database(str(tmp_path / "agent_system.db"))

    a_id = db.create_feature("A", "first", "core")
    b_id = db.create_feature("B", "second", "core", depends_on=[a_id])

    assert db.block_feature(a_id, "Blocked: upstream failure") is True
    n = db.block_unresolvable_dependencies()
    assert n >= 1

    b = db.get_feature(b_id)
    assert b is not None
    assert b["status"] == "BLOCKED"
    assert "dependency is BLOCKED" in str(b.get("last_error") or "")


def test_block_unresolvable_dependencies_blocks_cycles(tmp_path):
    db = Database(str(tmp_path / "agent_system.db"))

    a_id = db.create_feature("A", "first", "core")
    b_id = db.create_feature("B", "second", "core")

    # Create a cycle A <-> B
    db.create_feature("C", "dummy", "core")  # ensure IDs aren't special
    # Add dependencies via create_feature won't help for existing; use direct SQL insert.
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO feature_dependencies (feature_id, depends_on_id) VALUES (?, ?)",
            (int(a_id), int(b_id)),
        )
        cur.execute(
            "INSERT OR IGNORE INTO feature_dependencies (feature_id, depends_on_id) VALUES (?, ?)",
            (int(b_id), int(a_id)),
        )
        conn.commit()

    n = db.block_unresolvable_dependencies()
    assert n >= 2

    a = db.get_feature(a_id)
    b = db.get_feature(b_id)
    assert a is not None and b is not None
    assert a["status"] == "BLOCKED"
    assert b["status"] == "BLOCKED"
    assert "dependency cycle" in str(a.get("last_error") or "").lower()
