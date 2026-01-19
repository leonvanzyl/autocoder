"""
UI Settings Store
=================

Server-side persistence for UI-configurable "advanced" settings.

These settings are applied by the UI server when spawning agent/orchestrator subprocesses
by setting environment variables (without requiring users to manage their shell env).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from autocoder.core.global_settings_db import get_global_setting_json, set_global_setting_json


_ADVANCED_SETTINGS_KEY = "advanced_settings_v1"

def _config_dir() -> Path:
    d = Path.home() / ".autocoder"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _settings_path() -> Path:
    return _config_dir() / "ui_settings.json"


@dataclass
class AdvancedSettings:
    # Review (optional)
    review_enabled: bool = False
    review_mode: str = "off"  # off|advisory|gate
    review_type: str = "none"  # none|command|claude|multi_cli
    review_command: str = ""
    review_timeout_s: int = 0
    review_model: str = ""
    review_agents: str = ""
    review_consensus: str = ""
    codex_model: str = ""
    codex_reasoning_effort: str = ""
    gemini_model: str = ""

    # File locks / coordination
    locks_enabled: bool = False

    # Worker behavior
    worker_verify: bool = True
    worker_provider: str = "claude"  # claude|codex_cli|gemini_cli|multi_cli
    worker_patch_max_iterations: int = 2
    worker_patch_agents: str = "codex,gemini"  # csv; used when worker_provider=multi_cli

    # QA/controller sub-agents (optional)
    qa_fix_enabled: bool = False
    qa_model: str = ""
    qa_max_sessions: int = 0
    qa_subagent_enabled: bool = False
    qa_subagent_max_iterations: int = 2
    qa_subagent_provider: str = "claude"  # claude|codex_cli|gemini_cli|multi_cli
    qa_subagent_agents: str = "codex,gemini"  # csv; used when provider=multi_cli
    controller_enabled: bool = False
    controller_model: str = ""
    controller_max_sessions: int = 0

    # Feature planner (optional; multi-model plan artifact)
    planner_enabled: bool = False
    planner_model: str = ""  # Claude model for synthesis (optional)
    planner_agents: str = "codex,gemini"  # csv (codex,gemini)
    planner_synthesizer: str = "claude"  # none|claude|codex|gemini
    planner_timeout_s: int = 180

    # Initializer defaults (feature backlog generation)
    initializer_provider: str = "claude"  # claude|codex_cli|gemini_cli|multi_cli
    initializer_agents: str = "codex,gemini"
    initializer_synthesizer: str = "claude"  # none|claude|codex|gemini
    initializer_timeout_s: int = 300
    initializer_stage_threshold: int = 120
    initializer_enqueue_count: int = 30

    # Log retention defaults (used by orchestrator periodic pruning)
    logs_keep_days: int = 7
    logs_keep_files: int = 200
    logs_max_total_mb: int = 200
    logs_prune_artifacts: bool = False

    # Diagnostics (Web UI)
    diagnostics_fixtures_dir: str = ""

    # UI server (bind host / allow remote)
    ui_host: str = ""
    ui_allow_remote: bool = False

    # UI theme overrides (optional)
    agent_color_running: str = "#00b4d8"
    agent_color_done: str = "#70e000"
    agent_color_retry: str = "#f59e0b"

    # Retry/backoff for Claude Agent SDK queries
    sdk_max_attempts: int = 3
    sdk_initial_delay_s: int = 1
    sdk_rate_limit_initial_delay_s: int = 30
    sdk_max_delay_s: int = 60
    sdk_exponential_base: int = 2
    sdk_jitter: bool = True

    # Gatekeeper behavior
    require_gatekeeper: bool = True
    allow_no_tests: bool = False
    stop_when_done: bool = True

    # Port allocator behavior
    api_port_range_start: int = 5000
    api_port_range_end: int = 5100
    web_port_range_start: int = 5173
    web_port_range_end: int = 5273
    skip_port_check: bool = False

    def to_env(self) -> dict[str, str]:
        return {
            "AUTOCODER_REVIEW_ENABLED": "1" if self.review_enabled else "0",
            "AUTOCODER_REVIEW_MODE": str(self.review_mode or "off"),
            "AUTOCODER_REVIEW_TYPE": str(self.review_type or "none"),
            "AUTOCODER_REVIEW_COMMAND": str(self.review_command or ""),
            "AUTOCODER_REVIEW_TIMEOUT_S": str(int(self.review_timeout_s or 0)),
            "AUTOCODER_REVIEW_MODEL": str(self.review_model or ""),
            "AUTOCODER_REVIEW_AGENTS": str(self.review_agents or ""),
            "AUTOCODER_REVIEW_CONSENSUS": str(self.review_consensus or ""),
            "AUTOCODER_CODEX_MODEL": str(self.codex_model or ""),
            "AUTOCODER_CODEX_REASONING_EFFORT": str(self.codex_reasoning_effort or ""),
            "AUTOCODER_GEMINI_MODEL": str(self.gemini_model or ""),
            "AUTOCODER_LOCKS_ENABLED": "1" if self.locks_enabled else "0",
            "AUTOCODER_WORKER_VERIFY": "1" if self.worker_verify else "0",
            "AUTOCODER_WORKER_PROVIDER": str(self.worker_provider or "claude"),
            "AUTOCODER_WORKER_PATCH_MAX_ITERATIONS": str(int(self.worker_patch_max_iterations or 2)),
            "AUTOCODER_WORKER_PATCH_AGENTS": str(self.worker_patch_agents or "codex,gemini"),
            "AUTOCODER_QA_FIX_ENABLED": "1" if self.qa_fix_enabled else "0",
            "AUTOCODER_QA_MODEL": str(self.qa_model or ""),
            "AUTOCODER_QA_MAX_SESSIONS": str(int(self.qa_max_sessions or 0)),
            "AUTOCODER_QA_SUBAGENT_ENABLED": "1" if self.qa_subagent_enabled else "0",
            "AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS": str(int(self.qa_subagent_max_iterations or 2)),
            "AUTOCODER_QA_SUBAGENT_PROVIDER": str(self.qa_subagent_provider or "claude"),
            "AUTOCODER_QA_SUBAGENT_AGENTS": str(self.qa_subagent_agents or "codex,gemini"),
            "AUTOCODER_CONTROLLER_ENABLED": "1" if self.controller_enabled else "0",
            "AUTOCODER_CONTROLLER_MODEL": str(self.controller_model or ""),
            "AUTOCODER_CONTROLLER_MAX_SESSIONS": str(int(self.controller_max_sessions or 0)),
            "AUTOCODER_PLANNER_ENABLED": "1" if self.planner_enabled else "0",
            "AUTOCODER_PLANNER_MODEL": str(self.planner_model or ""),
            "AUTOCODER_PLANNER_AGENTS": str(self.planner_agents or "codex,gemini"),
            "AUTOCODER_PLANNER_SYNTHESIZER": str(self.planner_synthesizer or "claude"),
            "AUTOCODER_PLANNER_TIMEOUT_S": str(int(self.planner_timeout_s or 180)),
            "AUTOCODER_INITIALIZER_PROVIDER": str(self.initializer_provider or "claude"),
            "AUTOCODER_INITIALIZER_AGENTS": str(self.initializer_agents or "codex,gemini"),
            "AUTOCODER_INITIALIZER_SYNTHESIZER": str(self.initializer_synthesizer or "claude"),
            "AUTOCODER_INITIALIZER_TIMEOUT_S": str(int(self.initializer_timeout_s or 300)),
            "AUTOCODER_INITIALIZER_STAGE_THRESHOLD": str(int(self.initializer_stage_threshold or 0)),
            "AUTOCODER_INITIALIZER_ENQUEUE_COUNT": str(int(self.initializer_enqueue_count or 0)),
            "AUTOCODER_LOGS_KEEP_DAYS": str(self.logs_keep_days),
            "AUTOCODER_LOGS_KEEP_FILES": str(self.logs_keep_files),
            "AUTOCODER_LOGS_MAX_TOTAL_MB": str(self.logs_max_total_mb),
            "AUTOCODER_LOGS_PRUNE_ARTIFACTS": "1" if self.logs_prune_artifacts else "0",
            "AUTOCODER_DIAGNOSTICS_FIXTURES_DIR": str(self.diagnostics_fixtures_dir or ""),
            "AUTOCODER_UI_HOST": str(self.ui_host or ""),
            "AUTOCODER_UI_ALLOW_REMOTE": "1" if self.ui_allow_remote else "0",
            "AUTOCODER_SDK_MAX_ATTEMPTS": str(self.sdk_max_attempts),
            "AUTOCODER_SDK_INITIAL_DELAY_S": str(self.sdk_initial_delay_s),
            "AUTOCODER_SDK_RATE_LIMIT_INITIAL_DELAY_S": str(self.sdk_rate_limit_initial_delay_s),
            "AUTOCODER_SDK_MAX_DELAY_S": str(self.sdk_max_delay_s),
            "AUTOCODER_SDK_EXPONENTIAL_BASE": str(self.sdk_exponential_base),
            "AUTOCODER_SDK_JITTER": "true" if self.sdk_jitter else "false",
            "AUTOCODER_REQUIRE_GATEKEEPER": "1" if self.require_gatekeeper else "0",
            "AUTOCODER_ALLOW_NO_TESTS": "1" if self.allow_no_tests else "0",
            "AUTOCODER_STOP_WHEN_DONE": "1" if self.stop_when_done else "0",
            "AUTOCODER_API_PORT_RANGE_START": str(self.api_port_range_start),
            "AUTOCODER_API_PORT_RANGE_END": str(self.api_port_range_end),
            "AUTOCODER_WEB_PORT_RANGE_START": str(self.web_port_range_start),
            "AUTOCODER_WEB_PORT_RANGE_END": str(self.web_port_range_end),
            "AUTOCODER_SKIP_PORT_CHECK": "1" if self.skip_port_check else "0",
        }


def load_persisted_advanced_settings() -> AdvancedSettings | None:
    """
    Load advanced settings only if they were explicitly persisted.

    This is used for applying settings to subprocess env vars: we do not want to
    override a user's existing environment with defaults when no settings were saved.
    """
    try:
        data = get_global_setting_json(_ADVANCED_SETTINGS_KEY)
        if isinstance(data, dict) and data:
            try:
                return AdvancedSettings(**data)
            except Exception:
                return None
    except Exception:
        # DB unavailable/corrupt -> fall back to legacy file if present.
        pass

    legacy_path = _settings_path()
    if legacy_path.exists():
        try:
            legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
            settings = AdvancedSettings(**legacy_data)
            try:
                set_global_setting_json(_ADVANCED_SETTINGS_KEY, asdict(settings))
            except Exception:
                pass
            return settings
        except Exception:
            return None

    return None


def apply_advanced_settings_env(env: dict[str, str]) -> dict[str, str]:
    """
    Apply persisted advanced settings as env var overrides.

    Precedence: **persisted settings override env** (for the UI-launched subprocess),
    but only when settings were actually saved. Empty string values do not override.
    """
    settings = load_persisted_advanced_settings()
    if not settings:
        return env
    for k, v in settings.to_env().items():
        if v == "":
            continue
        env[k] = v
    return env


def load_advanced_settings() -> AdvancedSettings:
    persisted = load_persisted_advanced_settings()
    return persisted if persisted else AdvancedSettings()


def save_advanced_settings(settings: AdvancedSettings) -> None:
    try:
        set_global_setting_json(_ADVANCED_SETTINGS_KEY, asdict(settings))
        return
    except Exception:
        # Last-resort fallback: keep the UI usable even if the global DB is unavailable.
        path = _settings_path()
        path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")

