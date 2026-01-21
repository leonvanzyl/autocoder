import pytest

from autocoder.core.engine_settings import EngineSettings


def test_engine_settings_defaults_are_valid():
    settings = EngineSettings.defaults()
    assert settings.chains["implement"].engines
    assert settings.chains["review"].engines


def test_engine_settings_rejects_invalid_engine():
    settings = EngineSettings.defaults().model_copy(deep=True)
    settings.chains["review"].engines.append("not_real")  # type: ignore[arg-type]
    with pytest.raises(Exception):
        EngineSettings.model_validate(settings.model_dump())


def test_engine_settings_requires_engine_when_enabled():
    settings = EngineSettings.defaults().model_copy(deep=True)
    settings.chains["implement"] = settings.chains["implement"].model_copy(update={"engines": []})
    with pytest.raises(Exception):
        EngineSettings.model_validate(settings.model_dump())


def test_engine_settings_dedupes_engines():
    settings = EngineSettings.defaults().model_copy(deep=True)
    settings.chains["review"] = settings.chains["review"].model_copy(
        update={"engines": ["claude_review", "claude_review", "codex_cli"]}
    )
    parsed = EngineSettings.model_validate(settings.model_dump())
    assert parsed.chains["review"].engines == ["claude_review", "codex_cli"]
