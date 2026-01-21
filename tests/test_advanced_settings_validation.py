import pytest
from pydantic import ValidationError

from autocoder.server.routers.settings import AdvancedSettingsModel


def test_review_requires_mode_when_enabled():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(review_enabled=True, review_mode="off")


def test_review_consensus_requires_valid_value():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(review_enabled=True, review_mode="gate", review_consensus="pizza")


def test_codex_reasoning_effort_is_validated():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(codex_reasoning_effort="extreme")


def test_regression_pool_requires_agents_when_enabled():
    with pytest.raises(ValidationError):
        AdvancedSettingsModel(regression_pool_enabled=True, regression_pool_max_agents=0)

