"""
Project Configuration (autocoder.yaml)
=====================================

AutoCoder supports a per-project configuration file `autocoder.yaml` to make validation and
verification framework-agnostic.

Motivation:
- Test framework auto-detection is convenient but brittle across stacks.
- Gatekeeper verification runs in a fresh worktree and needs deterministic commands
  (setup/test/lint/typecheck/etc.) without guessing.

This module provides:
- Built-in presets for common stacks
- A small schema for commands
- Merge+validation logic (preset -> user overrides)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import json
import yaml


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return None


@dataclass(frozen=True)
class CommandSpec:
    command: str
    timeout_s: int | None = None
    allow_fail: bool = False

    @staticmethod
    def from_obj(obj: object) -> "CommandSpec | None":
        if obj is None:
            return None
        if isinstance(obj, str):
            if not obj.strip():
                return None
            return CommandSpec(command=obj.strip())
        if isinstance(obj, Mapping):
            cmd = obj.get("command")
            if not isinstance(cmd, str) or not cmd.strip():
                return None
            timeout = obj.get("timeout")
            timeout_s = _as_int(timeout)
            allow_fail = bool(obj.get("allow_fail", False))
            return CommandSpec(command=cmd.strip(), timeout_s=timeout_s, allow_fail=allow_fail)
        return None


@dataclass(frozen=True)
class ReviewSpec:
    enabled: bool = False
    mode: str = "off"  # off|advisory|gate
    reviewer_type: str = "none"  # none|command|claude|multi_cli
    command: str | None = None
    timeout_s: int | None = None
    model: str | None = None
    agents: list[str] | None = None
    consensus: str | None = None  # majority|all|any
    codex_model: str | None = None
    codex_reasoning_effort: str | None = None
    gemini_model: str | None = None


@dataclass(frozen=True)
class ResolvedProjectConfig:
    preset: str | None
    commands: dict[str, CommandSpec | None]
    review: ReviewSpec = field(default_factory=ReviewSpec)

    def get_command(self, name: str) -> CommandSpec | None:
        return self.commands.get(name)


def _builtin_presets() -> dict[str, dict[str, Any]]:
    # Keep this minimal; users can override/extend via autocoder.yaml.
    return {
        "python": {
            "commands": {
                # Cross-platform venv bootstrap using Gatekeeper placeholders:
                # - {PY} resolves to the Gatekeeper Python executable
                # - {VENV_PY} resolves to the project-local venv python (./.venv/...)
                "setup": {
                    "command": "{PY} -m venv .venv && {VENV_PY} -m pip install -U pip && {VENV_PY} -m pip install -r requirements.txt",
                    "timeout": 900,
                },
                "test": {"command": "{VENV_PY} -m pytest -q", "timeout": 900},
            }
        },
        "python-uv": {
            "commands": {
                "setup": {"command": "uv sync", "timeout": 900},
                "test": {"command": "uv run pytest", "timeout": 900},
                "lint": {"command": "uvx ruff check .", "timeout": 600},
                "format": {"command": "uvx ruff format .", "timeout": 600},
                "typecheck": {"command": "uvx mypy .", "timeout": 900, "allow_fail": True},
            }
        },
        "node-npm": {
            "commands": {
                # Gatekeeper may pick npm ci vs npm install based on lockfile; this is a default.
                "setup": {"command": "npm install", "timeout": 900},
                "test": {"command": "npm test", "timeout": 900},
                "lint": {"command": "npm run lint", "timeout": 600, "allow_fail": True},
                "typecheck": {"command": "npm run typecheck", "timeout": 900, "allow_fail": True},
            }
        },
        "go": {
            "commands": {
                "setup": {"command": "go mod download", "timeout": 900},
                "test": {"command": "go test ./...", "timeout": 900},
                "lint": {"command": "golangci-lint run", "timeout": 900, "allow_fail": True},
            }
        },
        "rust": {
            "commands": {
                "setup": {"command": "cargo fetch", "timeout": 900},
                "test": {"command": "cargo test", "timeout": 1800},
                "lint": {"command": "cargo clippy --all-targets --all-features -- -D warnings", "timeout": 1800, "allow_fail": True},
                "format": {"command": "cargo fmt -- --check", "timeout": 600, "allow_fail": True},
            }
        },
    }

def builtin_presets() -> dict[str, dict[str, Any]]:
    """
    Expose built-in preset configs for callers that want to infer a preset.

    These are used when no `autocoder.yaml` exists and Gatekeeper wants deterministic commands.
    """
    return _builtin_presets()


def synthesize_commands_from_preset(preset: str, project_dir: Path) -> dict[str, CommandSpec | None]:
    """
    Create a minimal, deterministic command set from a built-in preset, optionally tailored to the repo.

    This is used when no `autocoder.yaml` exists and Gatekeeper needs a framework-agnostic set of
    verification commands that won't fail due to missing package scripts (e.g. `npm test` absent).
    """
    project_dir = Path(project_dir).resolve()
    preset_cfg = _builtin_presets().get(preset, {})
    preset_cmds = preset_cfg.get("commands", {}) if isinstance(preset_cfg, dict) else {}

    cmds: dict[str, CommandSpec | None] = {}
    if isinstance(preset_cmds, dict):
        for name, spec in preset_cmds.items():
            if not isinstance(name, str) or not name.strip():
                continue
            cmds[name] = CommandSpec.from_obj(spec)

    if preset != "node-npm":
        return cmds

    scripts = _read_npm_scripts(project_dir)

    # If a script doesn't exist, remove it so Gatekeeper doesn't run `npm run <missing>`.
    if "test" not in scripts:
        cmds.pop("test", None)

    lint_key = "lint" if "lint" in scripts else None
    if lint_key is None:
        cmds.pop("lint", None)

    # Some repos use "type-check" instead of "typecheck".
    typecheck_key = None
    if "typecheck" in scripts:
        typecheck_key = "typecheck"
    elif "type-check" in scripts:
        typecheck_key = "type-check"

    if typecheck_key is None:
        cmds.pop("typecheck", None)
    else:
        cmds["typecheck"] = CommandSpec(command=f"npm run {typecheck_key}", timeout_s=900, allow_fail=True)

    # If there's no explicit test command, prefer a deterministic build.
    if "build" in scripts:
        cmds["build"] = CommandSpec(command="npm run build", timeout_s=1800, allow_fail=False)

    return cmds


def _read_npm_scripts(project_dir: Path) -> dict[str, Any]:
    pkg = Path(project_dir) / "package.json"
    if not pkg.exists():
        return {}
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except Exception:
        return {}

    scripts = data.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def load_project_config(project_dir: Path) -> ResolvedProjectConfig:
    """
    Load project configuration from `autocoder.yaml`.

    If missing or invalid, returns an empty config and callers can fall back to auto-detection.
    """
    project_dir = Path(project_dir).resolve()
    cfg_path = project_dir / "autocoder.yaml"
    if not cfg_path.exists():
        return ResolvedProjectConfig(preset=None, commands={})

    data = _load_yaml(cfg_path)
    preset = data.get("preset")
    if not isinstance(preset, str) or not preset.strip():
        preset = None
    else:
        preset = preset.strip()

    merged: dict[str, Any] = {}
    if preset:
        merged = dict(_builtin_presets().get(preset, {}))

    # User overrides (shallow), except `commands` which is merged key-by-key.
    for k, v in data.items():
        if k in ("preset", "commands"):
            continue
        merged[k] = v

    if "commands" in data and isinstance(data.get("commands"), dict):
        preset_cmds = merged.get("commands", {})
        if not isinstance(preset_cmds, dict):
            preset_cmds = {}
        user_cmds = data.get("commands", {})
        merged_cmds = dict(preset_cmds)
        merged_cmds.update(user_cmds)
        merged["commands"] = merged_cmds

    commands_in = merged.get("commands", {})
    commands: dict[str, CommandSpec | None] = {}
    if isinstance(commands_in, dict):
        for name, spec in commands_in.items():
            if not isinstance(name, str) or not name.strip():
                continue
            commands[name.strip()] = CommandSpec.from_obj(spec)

    review_in = merged.get("review", {})
    review = ReviewSpec()
    if isinstance(review_in, dict):
        enabled = bool(review_in.get("enabled", False))
        mode = str(review_in.get("mode", "off") or "off").strip().lower()
        if mode not in {"off", "advisory", "gate"}:
            mode = "off"
        reviewer_type = str(review_in.get("type", review_in.get("reviewer_type", "none")) or "none").strip().lower()
        if reviewer_type not in {"none", "command", "claude", "multi_cli"}:
            reviewer_type = "none"
        command = review_in.get("command")
        if not isinstance(command, str) or not command.strip():
            command = None
        timeout_s = _as_int(review_in.get("timeout", review_in.get("timeout_s", None)))
        model = review_in.get("model")
        if not isinstance(model, str) or not model.strip():
            model = None

        agents_in = review_in.get("agents", review_in.get("review_agents", None))
        agents: list[str] | None = None
        if isinstance(agents_in, str):
            parts = [p.strip().lower() for p in agents_in.replace(";", ",").split(",")]
            agents = [p for p in parts if p]
        elif isinstance(agents_in, list):
            parts = [str(p).strip().lower() for p in agents_in]
            agents = [p for p in parts if p]

        consensus = review_in.get("consensus")
        if not isinstance(consensus, str) or not consensus.strip():
            consensus = None
        else:
            consensus = consensus.strip().lower()

        codex_model = review_in.get("codex_model")
        if not isinstance(codex_model, str) or not codex_model.strip():
            codex_model = None
        else:
            codex_model = codex_model.strip()

        codex_reasoning_effort = review_in.get("codex_reasoning_effort")
        if not isinstance(codex_reasoning_effort, str) or not codex_reasoning_effort.strip():
            codex_reasoning_effort = None
        else:
            codex_reasoning_effort = codex_reasoning_effort.strip()

        gemini_model = review_in.get("gemini_model")
        if not isinstance(gemini_model, str) or not gemini_model.strip():
            gemini_model = None
        else:
            gemini_model = gemini_model.strip()

        review = ReviewSpec(
            enabled=enabled,
            mode=mode,
            reviewer_type=reviewer_type,
            command=command.strip() if isinstance(command, str) else None,
            timeout_s=timeout_s,
            model=model.strip() if isinstance(model, str) else None,
            agents=agents,
            consensus=consensus,
            codex_model=codex_model,
            codex_reasoning_effort=codex_reasoning_effort,
            gemini_model=gemini_model,
        )

    return ResolvedProjectConfig(preset=preset, commands=commands, review=review)


def infer_preset(project_dir: Path) -> str | None:
    """Best-effort preset inference when no autocoder.yaml exists."""
    project_dir = Path(project_dir).resolve()
    if (project_dir / "pyproject.toml").exists() and (project_dir / "uv.lock").exists():
        return "python-uv"
    if (project_dir / "requirements.txt").exists():
        return "python"
    if (project_dir / "package.json").exists():
        return "node-npm"
    if (project_dir / "go.mod").exists():
        return "go"
    if (project_dir / "Cargo.toml").exists():
        return "rust"
    return None
