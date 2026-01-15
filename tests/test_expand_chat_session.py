import json
from pathlib import Path


def test_extract_features_to_create_dedupes_and_skips_invalid_json():
    from autocoder.server.services.expand_chat_session import _extract_features_to_create

    text = (
        "Hello\n"
        "<features_to_create>\n"
        "[\n"
        "  {\"category\":\"functional\",\"name\":\"A\",\"description\":\"d\",\"steps\":[\"s1\"]},\n"
        "  {\"category\":\"functional\",\"name\":\"B\",\"description\":\"d\",\"steps\":[\"s1\"]}\n"
        "]\n"
        "</features_to_create>\n"
        "Noise\n"
        "<features_to_create>[not valid json]</features_to_create>\n"
        "<features_to_create>\n"
        "[{\"category\":\"functional\",\"name\":\"B\",\"description\":\"dup\",\"steps\":[]}, {\"name\":\"C\"}]\n"
        "</features_to_create>\n"
    )

    out = _extract_features_to_create(text)
    assert [x["name"] for x in out] == ["A", "B", "C"]


def test_create_features_bulk_with_ids_increments_priority(tmp_path: Path):
    from autocoder.core.database import get_database
    from autocoder.server.services.expand_chat_session import _create_features_bulk_with_ids

    project_dir = tmp_path
    db = get_database(str(project_dir))

    # Seed an existing feature with a high-ish priority.
    seed_id = db.create_feature("seed", "d", "functional", steps=json.dumps(["x"]), priority=10)
    assert isinstance(seed_id, int)

    created = _create_features_bulk_with_ids(
        project_dir,
        [
            {"category": "functional", "name": "New 1", "description": "d1", "steps": ["a"]},
            {"category": "style", "name": "New 2", "description": "d2", "steps": ["b", "c"]},
        ],
    )

    assert [x["name"] for x in created] == ["New 1", "New 2"]
    assert all(isinstance(x["id"], int) and x["id"] > 0 for x in created)

    # Verify priorities are strictly increasing from the previous max.
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, priority, steps FROM features WHERE name IN ('New 1', 'New 2') ORDER BY priority ASC")
        rows = cursor.fetchall()

    assert [r[0] for r in rows] == ["New 1", "New 2"]
    assert [int(r[1]) for r in rows] == [11, 12]
    assert json.loads(rows[0][2]) == ["a"]
    assert json.loads(rows[1][2]) == ["b", "c"]

