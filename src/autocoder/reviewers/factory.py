from __future__ import annotations

import os

from .base import ReviewConfig, Reviewer
from .command import CommandReviewer
from .claude import ClaudeReviewer
from .multi_cli import MultiCliReviewer


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_str(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    s = raw.strip()
    return s if s else None


def _env_int(name: str) -> int | None:
    raw = _env_str(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def apply_env_overrides(cfg: ReviewConfig) -> ReviewConfig:
    """
    Apply env var overrides to a ReviewConfig.

    This is primarily used for UI-started runs where env vars are the control plane.
    Env vars (when set) take precedence over project config.
    """
    enabled_raw = os.environ.get("AUTOCODER_REVIEW_ENABLED")
    enabled = cfg.enabled if enabled_raw is None else _env_bool("AUTOCODER_REVIEW_ENABLED", cfg.enabled)

    mode = (cfg.mode or "off").strip().lower()
    mode_raw = _env_str("AUTOCODER_REVIEW_MODE")
    if mode_raw:
        m = mode_raw.strip().lower()
        if m in {"off", "advisory", "gate"}:
            mode = m

    reviewer_type = (cfg.reviewer_type or "none").strip().lower()
    type_raw = _env_str("AUTOCODER_REVIEW_TYPE")
    if type_raw:
        t = type_raw.strip().lower()
        if t in {"none", "command", "claude", "multi_cli"}:
            reviewer_type = t

    command = cfg.command
    cmd_raw = _env_str("AUTOCODER_REVIEW_COMMAND")
    if cmd_raw is not None:
        command = cmd_raw

    timeout_s = cfg.timeout_s
    t_raw = _env_int("AUTOCODER_REVIEW_TIMEOUT_S")
    if t_raw is not None:
        timeout_s = t_raw

    model = cfg.model
    model_raw = _env_str("AUTOCODER_REVIEW_MODEL")
    if model_raw is not None:
        model = model_raw

    review_agents = cfg.review_agents
    agents_raw = _env_str("AUTOCODER_REVIEW_AGENTS")
    if agents_raw is not None:
        parts = [p.strip().lower() for p in agents_raw.replace(";", ",").split(",")]
        review_agents = [p for p in parts if p]

    consensus = cfg.consensus
    consensus_raw = _env_str("AUTOCODER_REVIEW_CONSENSUS")
    if consensus_raw is not None:
        consensus = consensus_raw.strip().lower()

    codex_model = cfg.codex_model
    codex_model_raw = _env_str("AUTOCODER_CODEX_MODEL")
    if codex_model_raw is not None:
        codex_model = codex_model_raw

    codex_reasoning_effort = cfg.codex_reasoning_effort
    codex_reasoning_raw = _env_str("AUTOCODER_CODEX_REASONING_EFFORT")
    if codex_reasoning_raw is not None:
        codex_reasoning_effort = codex_reasoning_raw

    gemini_model = cfg.gemini_model
    gemini_model_raw = _env_str("AUTOCODER_GEMINI_MODEL")
    if gemini_model_raw is not None:
        gemini_model = gemini_model_raw

    return ReviewConfig(
        enabled=enabled,
        mode=mode,  # type: ignore[arg-type]
        reviewer_type=reviewer_type,  # type: ignore[arg-type]
        command=command,
        timeout_s=timeout_s,
        model=model,
        review_agents=review_agents,
        consensus=consensus,
        codex_model=codex_model,
        codex_reasoning_effort=codex_reasoning_effort,
        gemini_model=gemini_model,
    )


def get_reviewer(cfg: ReviewConfig) -> Reviewer | None:
    # Env override to force-disable in CI or debugging.
    if _env_bool("AUTOCODER_DISABLE_REVIEW", False):
        return None

    cfg = apply_env_overrides(cfg)

    if not cfg.enabled or cfg.mode == "off" or cfg.reviewer_type in {"none"}:
        return None
    if cfg.reviewer_type == "command":
        return CommandReviewer(cfg)
    if cfg.reviewer_type == "claude":
        return ClaudeReviewer(cfg)
    if cfg.reviewer_type == "multi_cli":
        return MultiCliReviewer(cfg)
    return None
