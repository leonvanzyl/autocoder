import os
from pathlib import Path

from autocoder.generation.multi_model import (
    build_generation_prompt,
    default_output_path,
    MultiModelGenerateConfig,
)


def test_default_output_paths():
    p = Path("C:/tmp/myproj")
    assert default_output_path(p, "spec").as_posix().endswith("/prompts/app_spec.txt")
    assert default_output_path(p, "plan").as_posix().endswith("/prompts/plan.md")


def test_build_generation_prompt_spec_has_tags():
    prompt = build_generation_prompt("spec", "Build a thing")
    assert "<project_specification>" in prompt
    assert "Output ONLY" in prompt


def test_build_generation_prompt_plan_is_markdown():
    prompt = build_generation_prompt("plan", "Build a thing")
    assert "Output ONLY Markdown" in prompt
    assert "<project_specification>" not in prompt


def test_generate_config_from_env_defaults():
    prev = dict(os.environ)
    try:
        os.environ.pop("AUTOCODER_GENERATE_AGENTS", None)
        os.environ.pop("AUTOCODER_GENERATE_SYNTHESIZER", None)
        cfg = MultiModelGenerateConfig.from_env()
        assert cfg.synthesizer in {"claude", "codex", "gemini", "none"}
        assert "codex" in cfg.agents or "gemini" in cfg.agents
    finally:
        os.environ.clear()
        os.environ.update(prev)

