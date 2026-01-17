from autocoder.generation.feature_backlog import parse_feature_backlog


def test_parse_feature_backlog_json_list():
    text = """
[
  {"name": "A", "description": "desc", "category": "functional", "steps": ["s1"]}
]
""".strip()
    backlog = parse_feature_backlog(text)
    assert len(backlog.features) == 1
    assert backlog.features[0]["name"] == "A"


def test_parse_feature_backlog_json_fenced():
    text = """
```json
{"features":[{"name":"B","description":"desc","category":"style","steps":["s1","s2"]}]}
```
""".strip()
    backlog = parse_feature_backlog(text)
    assert len(backlog.features) == 1
    assert backlog.features[0]["category"] == "style"
