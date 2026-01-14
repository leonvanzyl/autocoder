"""
Settings Router
===============

Server-side "advanced settings" used by the Web UI to configure spawned agent/orchestrator env vars.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..settings_store import AdvancedSettings, load_advanced_settings, save_advanced_settings


router = APIRouter(prefix="/api/settings", tags=["settings"])


class AdvancedSettingsModel(BaseModel):
    # Review (optional)
    review_enabled: bool = False
    review_mode: str = Field(default="off", max_length=32)
    review_type: str = Field(default="none", max_length=64)
    review_command: str = Field(default="", max_length=2000)
    review_timeout_s: int = Field(default=0, ge=0, le=3600)
    review_model: str = Field(default="", max_length=128)
    review_agents: str = Field(default="", max_length=256)
    review_consensus: str = Field(default="", max_length=64)
    codex_model: str = Field(default="", max_length=128)
    codex_reasoning_effort: str = Field(default="", max_length=64)
    gemini_model: str = Field(default="", max_length=128)

    locks_enabled: bool = False
    worker_verify: bool = True

    qa_fix_enabled: bool = False
    qa_model: str = Field(default="", max_length=128)
    qa_max_sessions: int = Field(default=0, ge=0, le=50)

    controller_enabled: bool = False
    controller_model: str = Field(default="", max_length=128)
    controller_max_sessions: int = Field(default=0, ge=0, le=50)

    logs_keep_days: int = Field(default=7, ge=0, le=3650)
    logs_keep_files: int = Field(default=200, ge=0, le=100000)
    logs_max_total_mb: int = Field(default=200, ge=0, le=100000)

    sdk_max_attempts: int = Field(default=3, ge=1, le=20)
    sdk_initial_delay_s: int = Field(default=1, ge=0, le=600)
    sdk_rate_limit_initial_delay_s: int = Field(default=30, ge=0, le=3600)
    sdk_max_delay_s: int = Field(default=60, ge=0, le=3600)
    sdk_exponential_base: int = Field(default=2, ge=1, le=10)
    sdk_jitter: bool = True

    require_gatekeeper: bool = True
    allow_no_tests: bool = False

    api_port_range_start: int = Field(default=5000, ge=1024, le=65535)
    api_port_range_end: int = Field(default=5100, ge=1024, le=65536)
    web_port_range_start: int = Field(default=5173, ge=1024, le=65535)
    web_port_range_end: int = Field(default=5273, ge=1024, le=65536)
    skip_port_check: bool = False

    def to_settings(self) -> AdvancedSettings:
        return AdvancedSettings(**self.model_dump())


@router.get("/advanced", response_model=AdvancedSettingsModel)
async def get_advanced_settings():
    settings = load_advanced_settings()
    return AdvancedSettingsModel(**settings.__dict__)


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
