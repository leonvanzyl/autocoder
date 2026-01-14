from pathlib import Path

import json

from autocoder.core.project_config import load_project_config, synthesize_commands_from_preset


def test_load_project_config_missing_returns_empty(tmp_path: Path):
    cfg = load_project_config(tmp_path)
    assert cfg.preset is None
    assert cfg.commands == {}
    assert cfg.review.enabled is False


def test_load_project_config_with_preset_and_override(tmp_path: Path):
    (tmp_path / "autocoder.yaml").write_text(
        """
preset: python-uv
commands:
  test:
    command: "uv run pytest -q"
    timeout: 123
""".strip(),
        encoding="utf-8",
    )

    cfg = load_project_config(tmp_path)
    assert cfg.preset == "python-uv"
    # preset provides setup, user overrides test
    assert cfg.get_command("setup") is not None
    t = cfg.get_command("test")
    assert t is not None
    assert t.command == "uv run pytest -q"
    assert t.timeout_s == 123


def test_load_project_config_review_section(tmp_path: Path):
    (tmp_path / "autocoder.yaml").write_text(
        """
review:
  enabled: true
  mode: gate
  type: command
  command: "python -c \\"print('ok')\\""
  timeout: 12
""".strip(),
        encoding="utf-8",
    )

    cfg = load_project_config(tmp_path)
    assert cfg.review.enabled is True
    assert cfg.review.mode == "gate"
    assert cfg.review.reviewer_type == "command"
    assert cfg.review.command is not None and "python -c" in cfg.review.command
    assert cfg.review.timeout_s == 12


def test_synthesize_node_commands_avoids_missing_test_script(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "scripts": {
                    "dev": "next dev",
                    "build": "next build",
                    "lint": "next lint",
                    "type-check": "tsc -p tsconfig.json --noEmit",
                },
            }
        ),
        encoding="utf-8",
    )

    cmds = synthesize_commands_from_preset("node-npm", tmp_path)
    assert "test" not in cmds  # no test script
    assert "build" in cmds and cmds["build"] is not None
    assert cmds["typecheck"] is not None
    assert cmds["typecheck"].command == "npm run type-check"


def test_synthesize_node_commands_keeps_test_script(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "scripts": {"test": "vitest run", "build": "vite build"}}),
        encoding="utf-8",
    )

    cmds = synthesize_commands_from_preset("node-npm", tmp_path)
    assert "test" in cmds and cmds["test"] is not None
    assert cmds["test"].command == "npm test"
