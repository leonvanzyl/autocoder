"""
Settings Router
===============

Server-side "advanced settings" used by the Web UI to configure spawned agent/orchestrator env vars.
"""

from __future__ import annotations

from typing import Literal
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator

from ..settings_store import AdvancedSettings, load_advanced_settings, save_advanced_settings


router = APIRouter(prefix="/api/settings", tags=["settings"])

ReviewMode = Literal["off", "advisory", "gate"]
PlannerSynthesizer = Literal["none", "claude", "codex", "gemini"]
CodexReasoningEffort = Literal["low", "medium", "high", "xlow", "xmedium", "xhigh"]
ReviewConsensus = Literal["any", "majority", "all"]
InitializerSynthesizer = Literal["none", "claude", "codex", "gemini"]


class AdvancedSettingsModel(BaseModel):
    # Review (optional)
    review_enabled: bool = False
    review_mode: ReviewMode = Field(default="off")
    review_timeout_s: int = Field(default=0, ge=0, le=3600)
    review_model: str = Field(default="", max_length=128)
    # Blank means "use default" for the configured reviewer type.
    review_consensus: str = Field(default="", max_length=64)
    codex_model: str = Field(default="", max_length=128)
    codex_reasoning_effort: str = Field(default="", max_length=64)  # low|medium|high|xhigh
    gemini_model: str = Field(default="", max_length=128)

    locks_enabled: bool = True
    worker_verify: bool = True

    qa_fix_enabled: bool = False
    qa_model: str = Field(default="", max_length=128)
    qa_max_sessions: int = Field(default=0, ge=0, le=50)
    qa_subagent_enabled: bool = True
    qa_subagent_max_iterations: int = Field(default=2, ge=1, le=20)

    controller_enabled: bool = False
    controller_model: str = Field(default="", max_length=128)
    controller_max_sessions: int = Field(default=0, ge=0, le=50)

    regression_pool_enabled: bool = False
    regression_pool_max_agents: int = Field(default=1, ge=0, le=10)
    regression_pool_model: str = Field(default="", max_length=128)
    regression_pool_min_interval_s: int = Field(default=600, ge=30, le=86400)
    regression_pool_max_iterations: int = Field(default=1, ge=1, le=5)

    planner_enabled: bool = False
    planner_model: str = Field(default="", max_length=128)
    planner_synthesizer: PlannerSynthesizer = Field(default="claude")
    planner_timeout_s: int = Field(default=180, ge=30, le=3600)

    initializer_synthesizer: InitializerSynthesizer = Field(default="claude")
    initializer_timeout_s: int = Field(default=300, ge=30, le=3600)
    initializer_stage_threshold: int = Field(default=120, ge=0, le=100000)
    initializer_enqueue_count: int = Field(default=30, ge=0, le=100000)

    logs_keep_days: int = Field(default=7, ge=0, le=3650)
    logs_keep_files: int = Field(default=200, ge=0, le=100000)
    logs_max_total_mb: int = Field(default=200, ge=0, le=100000)
    logs_prune_artifacts: bool = False
    activity_keep_days: int = Field(default=14, ge=0, le=3650)
    activity_keep_rows: int = Field(default=5000, ge=0, le=200000)

    diagnostics_fixtures_dir: str = Field(default="", max_length=2000)
    ui_host: str = Field(default="", max_length=255)
    ui_allow_remote: bool = False
    agent_color_running: str = Field(default="#00b4d8", max_length=16)
    agent_color_done: str = Field(default="#70e000", max_length=16)
    agent_color_retry: str = Field(default="#f59e0b", max_length=16)

    sdk_max_attempts: int = Field(default=3, ge=1, le=20)
    sdk_initial_delay_s: int = Field(default=1, ge=0, le=600)
    sdk_rate_limit_initial_delay_s: int = Field(default=30, ge=0, le=3600)
    sdk_max_delay_s: int = Field(default=60, ge=0, le=3600)
    sdk_exponential_base: int = Field(default=2, ge=1, le=10)
    sdk_jitter: bool = True

    require_gatekeeper: bool = True
    allow_no_tests: bool = False
    stop_when_done: bool = True

    api_port_range_start: int = Field(default=5000, ge=1024, le=65535)
    api_port_range_end: int = Field(default=5100, ge=1024, le=65536)
    web_port_range_start: int = Field(default=5173, ge=1024, le=65535)
    web_port_range_end: int = Field(default=5273, ge=1024, le=65536)
    skip_port_check: bool = False

    @model_validator(mode="after")
    def _validate_conditionals(self):
        # Review conditionals
        if self.review_enabled:
            if self.review_mode == "off":
                raise ValueError("review_mode must be advisory|gate when review_enabled=true")
            if self.review_consensus and self.review_consensus not in ("any", "majority", "all"):
                raise ValueError("review_consensus must be any|majority|all (or blank)")

        if self.codex_reasoning_effort and self.codex_reasoning_effort not in ("low", "medium", "high", "xlow", "xmedium", "xhigh"):
            raise ValueError("codex_reasoning_effort must be low|medium|high|xlow|xmedium|xhigh (or blank)")

        if self.regression_pool_enabled and self.regression_pool_max_agents <= 0:
            raise ValueError("regression_pool_max_agents must be > 0 when regression_pool_enabled=true")

        if self.initializer_enqueue_count < 0:
            raise ValueError("initializer_enqueue_count must be >= 0")

        color_fields = {
            "agent_color_running": "agent_color_running",
            "agent_color_done": "agent_color_done",
            "agent_color_retry": "agent_color_retry",
        }
        for field_name, label in color_fields.items():
            value = getattr(self, field_name, "")
            if not value:
                continue
            if not value.startswith("#"):
                value = f"#{value}"
                setattr(self, field_name, value)
            if not re.match(r"^#[0-9a-fA-F]{6}$", value):
                raise ValueError(f"{label} must be a 6-digit hex color (e.g. #00b4d8)")

        return self

    def to_settings(self) -> AdvancedSettings:
        return AdvancedSettings(**self.model_dump())


@router.get("/advanced", response_model=AdvancedSettingsModel)
async def get_advanced_settings():
    settings = load_advanced_settings()
    try:
        return AdvancedSettingsModel(**settings.__dict__)
    except ValidationError:
        # If legacy/migrated settings are invalid, avoid breaking the UI.
        return AdvancedSettingsModel()


@router.put("/advanced", response_model=AdvancedSettingsModel)
async def update_advanced_settings(req: AdvancedSettingsModel):
    # Basic sanity: end must exceed start.
    if req.api_port_range_end <= req.api_port_range_start:
        raise HTTPException(status_code=400, detail="api_port_range_end must be greater than api_port_range_start")
    if req.web_port_range_end <= req.web_port_range_start:
        raise HTTPException(status_code=400, detail="web_port_range_end must be greater than web_port_range_start")

    settings = req.to_settings()
    save_advanced_settings(settings)
    return req
