from autocoder.core.database import Database


def test_add_dependency_to_all_pending(tmp_path):
    db = Database(str(tmp_path / "agent_system.db"))
    a = db.create_feature("A", "a", "c")
    b = db.create_feature("B", "b", "c")
    c = db.create_feature("C", "c", "c")

    # Create a special dep feature and add it as dependency to all others.
    dep = db.create_feature("DEP", "dep", "infra", priority=999)
    inserted = db.add_dependency_to_all_pending(dep, exclude_ids=[dep])
    assert inserted == 3

    assert dep in db.get_feature(a)["depends_on"]
    assert dep in db.get_feature(b)["depends_on"]
    assert dep in db.get_feature(c)["depends_on"]
