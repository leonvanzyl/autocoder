import json
from pathlib import Path

import pytest


def test_update_feature_details_disallows_done(tmp_path: Path):
    from autocoder.core.database import Database

    db = Database(str(tmp_path / "agent_system.db"))
    fid = db.create_feature(name="a", description="d", category="c", steps=json.dumps(["x"]), priority=1)
    db.update_feature_status(fid, "DONE")

    with pytest.raises(ValueError):
        db.update_feature_details(fid, name="new")


def test_update_feature_details_updates_fields(tmp_path: Path):
    from autocoder.core.database import Database

    db = Database(str(tmp_path / "agent_system.db"))
    fid = db.create_feature(name="a", description="d", category="c", steps=json.dumps(["x"]), priority=1)

    out = db.update_feature_details(
        fid,
        name="new-name",
        category="new-cat",
        description="new-desc",
        steps=json.dumps(["s1", "s2"]),
        priority=99,
    )
    assert out is not None
    assert out["name"] == "new-name"
    assert out["category"] == "new-cat"
    assert out["description"] == "new-desc"
    assert out["priority"] == 99
    assert json.loads(out["steps"]) == ["s1", "s2"]

