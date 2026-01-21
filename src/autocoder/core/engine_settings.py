"""
Engine Chain Settings
=====================

Defines per-project engine chains (patch/review/spec) stored in agent_system.db.
These settings replace legacy provider+CSV order fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from .database import get_database


EngineId = Literal[
    "codex_cli",
    "gemini_cli",
    "claude_patch",
    "claude_review",
    "claude_spec",
]

StageId = Literal[
    "implement",
    "qa_fix",
    "review",
    "spec_draft",
    "spec_synthesize",
    "initializer",
]

ALLOWED_ENGINES_BY_STAGE: dict[StageId, set[EngineId]] = {
    "implement": {"codex_cli", "gemini_cli", "claude_patch"},
    "qa_fix": {"codex_cli", "gemini_cli", "claude_patch"},
    "review": {"codex_cli", "gemini_cli", "claude_review"},
    "spec_draft": {"codex_cli", "gemini_cli", "claude_spec"},
    "spec_synthesize": {"claude_spec"},
    "initializer": {"codex_cli", "gemini_cli", "claude_spec"},
}


class EngineChain(BaseModel):
    enabled: bool = True
    max_iterations: int = Field(default=2, ge=1, le=20)
    engines: list[EngineId] = Field(default_factory=list)


class EngineSettings(BaseModel):
    version: int = 1
    chains: dict[StageId, EngineChain]

    @model_validator(mode="after")
    def _validate_chains(self) -> "EngineSettings":
        for stage, chain in self.chains.items():
            allowed = ALLOWED_ENGINES_BY_STAGE.get(stage, set())
            seen: set[str] = set()
            normalized: list[EngineId] = []
            for engine in chain.engines:
                if engine not in allowed:
                    raise ValueError(f"{stage} contains unsupported engine: {engine}")
                if engine in seen:
                    continue
                seen.add(engine)
                normalized.append(engine)
            chain.engines = normalized

            if chain.enabled and not chain.engines:
                raise ValueError(f"{stage} chain must include at least one engine")
        return self

    def chain_for(self, stage: StageId) -> EngineChain:
        return self.chains.get(stage) or EngineChain(enabled=False, engines=[])

    def to_dict(self) -> dict:
        return self.model_dump()

    @staticmethod
    def defaults() -> "EngineSettings":
        return EngineSettings(
            version=1,
            chains={
                "implement": EngineChain(
                    enabled=True,
                    max_iterations=2,
                    engines=["codex_cli", "gemini_cli", "claude_patch"],
                ),
                "qa_fix": EngineChain(
                    enabled=True,
                    max_iterations=2,
                    engines=["codex_cli", "gemini_cli", "claude_patch"],
                ),
                "review": EngineChain(
                    enabled=True,
                    max_iterations=1,
                    engines=["claude_review", "codex_cli", "gemini_cli"],
                ),
                "spec_draft": EngineChain(
                    enabled=True,
                    max_iterations=1,
                    engines=["codex_cli", "gemini_cli", "claude_spec"],
                ),
                "spec_synthesize": EngineChain(
                    enabled=True,
                    max_iterations=1,
                    engines=["claude_spec"],
                ),
                "initializer": EngineChain(
                    enabled=True,
                    max_iterations=1,
                    engines=["claude_spec"],
                ),
            },
        )


ENGINE_SETTINGS_KEY = "engine_settings_v1"


def load_engine_settings(project_dir: str) -> EngineSettings:
    db = get_database(str(project_dir))
    stored = db.get_project_setting(ENGINE_SETTINGS_KEY)
    if stored and isinstance(stored, dict):
        try:
            return EngineSettings.model_validate(stored)
        except ValidationError:
            pass
    return EngineSettings.defaults()


def save_engine_settings(project_dir: str, settings: EngineSettings) -> None:
    db = get_database(str(project_dir))
    db.set_project_setting(ENGINE_SETTINGS_KEY, settings.to_dict())


def parse_engine_settings(payload: dict) -> EngineSettings:
    return EngineSettings.model_validate(payload)

