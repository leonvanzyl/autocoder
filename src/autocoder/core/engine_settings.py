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
    version: int = 2
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
            version=2,
            chains={
                "implement": EngineChain(
                    enabled=True,
                    max_iterations=2,
                    engines=["claude_patch"],
                ),
                "qa_fix": EngineChain(
                    enabled=True,
                    max_iterations=2,
                    engines=["claude_patch"],
                ),
                "review": EngineChain(
                    enabled=True,
                    max_iterations=1,
                    engines=["claude_review"],
                ),
                "spec_draft": EngineChain(
                    enabled=True,
                    max_iterations=1,
                    engines=["claude_spec"],
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

    @staticmethod
    def legacy_defaults() -> "EngineSettings":
        """
        Legacy defaults (v1) that ran Codex/Gemini before Claude.
        Used only for one-time migration detection.
        """
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

    @staticmethod
    def chains_equal(a: "EngineSettings", b: "EngineSettings") -> bool:
        for stage in ALLOWED_ENGINES_BY_STAGE.keys():
            ca = a.chains.get(stage)
            cb = b.chains.get(stage)
            if ca is None or cb is None:
                return False
            if ca.enabled != cb.enabled:
                return False
            if ca.max_iterations != cb.max_iterations:
                return False
            if list(ca.engines) != list(cb.engines):
                return False
        return True


ENGINE_SETTINGS_KEY = "engine_settings_v1"


def load_engine_settings(project_dir: str) -> EngineSettings:
    db = get_database(str(project_dir))
    stored = db.get_project_setting(ENGINE_SETTINGS_KEY)
    if stored and isinstance(stored, dict):
        try:
            parsed = EngineSettings.model_validate(stored)
            legacy = EngineSettings.legacy_defaults()
            # If a project is still on the legacy Codex/Gemini-first ordering, upgrade it.
            # This keeps defaults sane (Claude-first) unless the user explicitly diverged.
            if EngineSettings.chains_equal(parsed, legacy):
                upgraded = EngineSettings.defaults()
                save_engine_settings(project_dir, upgraded)
                return upgraded
            if parsed.version < 2:
                # Preserve custom chains, just bump version.
                upgraded = EngineSettings(version=2, chains=parsed.chains)
                save_engine_settings(project_dir, upgraded)
                return upgraded
            return parsed
        except ValidationError:
            pass
    return EngineSettings.defaults()


def save_engine_settings(project_dir: str, settings: EngineSettings) -> None:
    db = get_database(str(project_dir))
    db.set_project_setting(ENGINE_SETTINGS_KEY, settings.to_dict())


def parse_engine_settings(payload: dict) -> EngineSettings:
    return EngineSettings.model_validate(payload)

