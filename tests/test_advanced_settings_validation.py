import pytest
from pydantic import ValidationError

from autocoder.server.routers.settings import AdvancedSettingsModel


def test_review_requires_mode_when_enabled():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(review_enabled=True, review_mode="off", review_type="claude")


def test_review_requires_type_when_enabled():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(review_enabled=True, review_mode="gate", review_type="none")


def test_command_review_requires_command():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(review_enabled=True, review_mode="gate", review_type="command", review_command="")


def test_multi_cli_review_requires_agents():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(review_enabled=True, review_mode="gate", review_type="multi_cli", review_agents="   ")


def test_codex_reasoning_effort_is_validated():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(codex_reasoning_effort="extreme")


def test_multi_cli_worker_requires_patch_agents():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(worker_provider="multi_cli", worker_patch_agents=" ")


def test_multi_cli_qa_requires_agents_when_enabled():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(qa_subagent_enabled=True, qa_subagent_provider="multi_cli", qa_subagent_agents="")


def test_multi_cli_initializer_requires_agents():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(initializer_provider="multi_cli", initializer_agents=" ")

