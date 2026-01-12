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


def _config_dir() -> Path:
    d = Path.home() / ".autocoder"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _settings_path() -> Path:
    return _config_dir() / "ui_settings.json"


@dataclass
class AdvancedSettings:
    # Log retention defaults (used by orchestrator periodic pruning)
    logs_keep_days: int = 7
    logs_keep_files: int = 200
    logs_max_total_mb: int = 200

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

    # Port allocator behavior
    api_port_range_start: int = 5000
    api_port_range_end: int = 5100
    web_port_range_start: int = 5173
    web_port_range_end: int = 5273
    skip_port_check: bool = False

    def to_env(self) -> dict[str, str]:
        return {
            "AUTOCODER_LOGS_KEEP_DAYS": str(self.logs_keep_days),
            "AUTOCODER_LOGS_KEEP_FILES": str(self.logs_keep_files),
            "AUTOCODER_LOGS_MAX_TOTAL_MB": str(self.logs_max_total_mb),
            "AUTOCODER_SDK_MAX_ATTEMPTS": str(self.sdk_max_attempts),
            "AUTOCODER_SDK_INITIAL_DELAY_S": str(self.sdk_initial_delay_s),
            "AUTOCODER_SDK_RATE_LIMIT_INITIAL_DELAY_S": str(self.sdk_rate_limit_initial_delay_s),
            "AUTOCODER_SDK_MAX_DELAY_S": str(self.sdk_max_delay_s),
            "AUTOCODER_SDK_EXPONENTIAL_BASE": str(self.sdk_exponential_base),
            "AUTOCODER_SDK_JITTER": "true" if self.sdk_jitter else "false",
            "AUTOCODER_REQUIRE_GATEKEEPER": "1" if self.require_gatekeeper else "0",
            "AUTOCODER_ALLOW_NO_TESTS": "1" if self.allow_no_tests else "0",
            "AUTOCODER_API_PORT_RANGE_START": str(self.api_port_range_start),
            "AUTOCODER_API_PORT_RANGE_END": str(self.api_port_range_end),
            "AUTOCODER_WEB_PORT_RANGE_START": str(self.web_port_range_start),
            "AUTOCODER_WEB_PORT_RANGE_END": str(self.web_port_range_end),
            "AUTOCODER_SKIP_PORT_CHECK": "1" if self.skip_port_check else "0",
        }


def load_advanced_settings() -> AdvancedSettings:
    path = _settings_path()
    if not path.exists():
        return AdvancedSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AdvancedSettings(**data)
    except Exception:
        # Corrupt or partial settings -> fall back to defaults.
        return AdvancedSettings()


def save_advanced_settings(settings: AdvancedSettings) -> None:
    path = _settings_path()
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")

