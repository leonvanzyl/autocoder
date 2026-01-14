from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from autocoder.agent.retry import execute_with_retry_sync, retry_config_from_env


Kind = Literal["spec", "plan"]
Agent = Literal["codex", "gemini"]
Synthesizer = Literal["none", "claude", "codex", "gemini"]


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def default_output_path(project_dir: Path, kind: Kind) -> Path:
    prompts = project_dir / "prompts"
    if kind == "spec":
        return prompts / "app_spec.txt"
    return prompts / "plan.md"


def build_generation_prompt(kind: Kind, user_prompt: str) -> str:
    user_prompt = (user_prompt or "").strip()
    if kind == "spec":
        return (
            "You are drafting an AutoCoder app specification file.\n"
            "Output ONLY the final file contents with these exact tags:\n"
            "<project_specification> ... </project_specification>\n\n"
            "Constraints:\n"
            "- No surrounding commentary.\n"
            "- Be concrete: pages/routes, data model, tests, commands.\n"
            "- Assume this spec will be used to generate a feature backlog.\n\n"
            f"User request:\n{user_prompt}\n"
        )
    return (
        "You are drafting an implementation plan in Markdown.\n"
        "Output ONLY Markdown.\n\n"
        "Include:\n"
        "- Goals and non-goals\n"
        "- Architecture sketch\n"
        "- Step-by-step implementation checklist\n"
        "- Verification plan (tests + commands)\n\n"
        f"User request:\n{user_prompt}\n"
    )


def _available_agents(requested: list[Agent]) -> list[Agent]:
    out: list[Agent] = []
    for a in requested:
        if a == "codex" and shutil.which("codex"):
            out.append(a)
        elif a == "gemini" and shutil.which("gemini"):
            out.append(a)
    return out


def _cli_argv(name: str) -> list[str]:
    """
    Build a cross-platform argv prefix for calling a CLI.

    On Windows, many Node-installed CLIs resolve to `.cmd` shims (not directly executable by
    Python's CreateProcess), so we execute via `cmd.exe /c`.
    """
    if os.name != "nt":
        return [name]
    resolved = (shutil.which(name) or "").lower()
    if resolved.endswith((".exe",)):
        return [name]
    # `.cmd`/`.bat` shims or extensionless launchers -> `cmd.exe /c`.
    return ["cmd.exe", "/c", name]


_BREAKER_STATE: dict[str, dict[str, float]] = {}


def _breaker_threshold() -> int:
    try:
        return max(1, int(os.environ.get("AUTOCODER_CLI_BREAKER_THRESHOLD", "3")))
    except ValueError:
        return 3


def _breaker_cooldown_s() -> int:
    try:
        return max(1, int(os.environ.get("AUTOCODER_CLI_BREAKER_COOLDOWN_S", "600")))
    except ValueError:
        return 600


def _breaker_is_open(name: str) -> bool:
    st = _BREAKER_STATE.get(name) or {}
    return time.time() < float(st.get("open_until", 0.0))


def _breaker_record_success(name: str) -> None:
    _BREAKER_STATE[name] = {"failures": 0.0, "open_until": 0.0}


def _breaker_record_failure(name: str) -> None:
    st = _BREAKER_STATE.get(name) or {"failures": 0.0, "open_until": 0.0}
    failures = int(st.get("failures", 0.0)) + 1
    open_until = float(st.get("open_until", 0.0))
    if failures >= _breaker_threshold():
        open_until = time.time() + float(_breaker_cooldown_s())
        failures = 0
    _BREAKER_STATE[name] = {"failures": float(failures), "open_until": float(open_until)}


@dataclass(frozen=True)
class MultiModelGenerateConfig:
    agents: list[Agent]
    synthesizer: Synthesizer = "claude"
    timeout_s: int = 300

    codex_model: str = ""
    codex_reasoning_effort: str = ""
    gemini_model: str = ""
    claude_model: str = ""

    @staticmethod
    def from_env(
        *,
        agents: list[Agent] | None = None,
        synthesizer: Synthesizer | None = None,
        timeout_s: int | None = None,
    ) -> "MultiModelGenerateConfig":
        env_agents = _split_csv(os.environ.get("AUTOCODER_GENERATE_AGENTS")) or None
        picked_agents = agents or [a for a in (env_agents or ["codex", "gemini"]) if a in {"codex", "gemini"}]  # type: ignore[list-item]

        synth = synthesizer or (os.environ.get("AUTOCODER_GENERATE_SYNTHESIZER") or "claude").strip().lower()
        if synth not in {"none", "claude", "codex", "gemini"}:
            synth = "claude"

        t_raw = os.environ.get("AUTOCODER_GENERATE_TIMEOUT_S")
        t = timeout_s
        if t is None:
            try:
                t = int(t_raw) if t_raw else 300
            except Exception:
                t = 300

        return MultiModelGenerateConfig(
            agents=picked_agents,  # type: ignore[arg-type]
            synthesizer=synth,  # type: ignore[arg-type]
            timeout_s=max(30, int(t)),
            codex_model=os.environ.get("AUTOCODER_CODEX_MODEL", ""),
            codex_reasoning_effort=os.environ.get("AUTOCODER_CODEX_REASONING_EFFORT", ""),
            gemini_model=os.environ.get("AUTOCODER_GEMINI_MODEL", ""),
            claude_model=os.environ.get("AUTOCODER_GENERATE_CLAUDE_MODEL", ""),
        )


def _run_codex(prompt: str, cfg: MultiModelGenerateConfig, *, workdir: Path) -> tuple[bool, str, str]:
    if shutil.which("codex") is None:
        return False, "", "codex not found"
    if _breaker_is_open("codex"):
        return False, "", "codex circuit breaker open"
    model = cfg.codex_model or "gpt-5.2"
    reasoning = cfg.codex_reasoning_effort or "high"
    retry_cfg = retry_config_from_env(prefix="AUTOCODER_SDK_")

    def attempt() -> tuple[str, str]:
        fd, out_path = tempfile.mkstemp(prefix="autocoder-codex-", suffix=".txt")
        os.close(fd)
        out_file = Path(out_path)
        cmd = [
            *_cli_argv("codex"),
            "exec",
            "-m",
            model,
            "-c",
            f"model_reasoning_effort={reasoning}",
            "-s",
            "read-only",
            "-C",
            str(workdir),
            "--skip-git-repo-check",
            "--output-last-message",
            str(out_file),
            "-",
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=cfg.timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            with contextlib.suppress(Exception):
                out_file.unlink(missing_ok=True)  # type: ignore[arg-type]
            raise TimeoutError("codex timed out") from e
        try:
            text_out = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
        except Exception:
            text_out = ""
        with contextlib.suppress(Exception):
            out_file.unlink(missing_ok=True)  # type: ignore[arg-type]
        if proc.returncode != 0 or not text_out.strip():
            msg = (proc.stderr or proc.stdout or "").strip() or "codex failed"
            raise RuntimeError(msg)
        stderr = (proc.stderr or "").strip()
        return text_out.strip(), stderr or (proc.stdout or "")

    try:
        out, err = execute_with_retry_sync(attempt, config=retry_cfg)
        _breaker_record_success("codex")
        return True, out, err
    except Exception as e:
        _breaker_record_failure("codex")
        return False, "", str(e)


def _run_gemini(prompt: str, cfg: MultiModelGenerateConfig) -> tuple[bool, str, str]:
    if shutil.which("gemini") is None:
        return False, "", "gemini not found"
    if _breaker_is_open("gemini"):
        return False, "", "gemini circuit breaker open"
    model = cfg.gemini_model or "gemini-3-pro-preview"
    cmd = [*_cli_argv("gemini"), "-m", model, "-o", "text"]
    env = dict(os.environ)
    # Reuse the read-only settings used by the multi-model review gate when available.
    settings = (Path(__file__).resolve().parents[1] / "reviewers" / "config" / "gemini-readonly-settings.json").resolve()
    if settings.exists():
        env.setdefault("GEMINI_CLI_SYSTEM_SETTINGS_PATH", str(settings))
    retry_cfg = retry_config_from_env(prefix="AUTOCODER_SDK_")

    def attempt() -> tuple[str, str]:
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=cfg.timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            raise TimeoutError("gemini timed out") from e
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip() or "gemini failed"
            raise RuntimeError(msg)
        return proc.stdout or "", proc.stderr or ""

    try:
        out, err = execute_with_retry_sync(attempt, config=retry_cfg)
        _breaker_record_success("gemini")
        return True, out, err
    except Exception as e:
        _breaker_record_failure("gemini")
        return False, "", str(e)


async def _claude_synthesize(prompt: str, model: str, workdir: Path, timeout_s: int) -> tuple[bool, str, str]:
    settings_file = workdir / ".claude_settings.generate.json"
    settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {"defaultMode": "reject", "allow": []},
    }
    settings_file.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    client = ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            allowed_tools=[],
            system_prompt="You are a strict synthesizer. Output only the requested artifact content.",
            cwd=str(workdir),
            settings=str(settings_file),
            max_turns=3,
            setting_sources=["project"],
        )
    )
    try:
        await asyncio.wait_for(client.query(prompt), timeout=timeout_s)
        text = ""
        async for msg in client.receive_response():
            if type(msg).__name__ == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                        text += block.text
        return True, text.strip(), ""
    except Exception as e:
        return False, "", str(e)


def _synth_prompt(kind: Kind, user_prompt: str, drafts: dict[str, str]) -> str:
    header = "You are synthesizing multiple drafts into one final artifact.\n"
    if kind == "spec":
        header += (
            "Output ONLY the final file contents with these exact tags:\n"
            "<project_specification> ... </project_specification>\n\n"
        )
    else:
        header += "Output ONLY Markdown.\n\n"
    header += "User request:\n" + user_prompt.strip() + "\n\n"
    header += "Drafts:\n\n"
    for name, content in drafts.items():
        header += f"--- BEGIN {name.upper()} DRAFT ---\n{content}\n--- END {name.upper()} DRAFT ---\n\n"
    return header


def generate_multi_model_artifact(
    *,
    project_dir: Path,
    kind: Kind,
    user_prompt: str,
    cfg: MultiModelGenerateConfig,
    output_path: Path | None = None,
    drafts_root: Path | None = None,
    synthesize: bool = True,
) -> dict[str, str]:
    project_dir = Path(project_dir).resolve()
    (project_dir / "prompts").mkdir(parents=True, exist_ok=True)

    output = Path(output_path) if output_path else default_output_path(project_dir, kind)
    output.parent.mkdir(parents=True, exist_ok=True)

    drafts_root = drafts_root or (project_dir / ".autocoder" / "drafts" / kind / _now_stamp())
    drafts_root.mkdir(parents=True, exist_ok=True)

    prompt = build_generation_prompt(kind, user_prompt)
    requested = cfg.agents or ["codex", "gemini"]  # type: ignore[list-item]
    agents = _available_agents(requested)
    if not agents and cfg.synthesizer in {"codex", "gemini"}:
        # If user asked for a CLI synthesizer but it's not present, fail fast.
        raise RuntimeError("No requested generation CLIs found (codex/gemini).")

    drafts: dict[str, str] = {}
    run_log: dict[str, str] = {}
    for a in agents:
        if a == "codex":
            ok, out, err = _run_codex(prompt, cfg, workdir=drafts_root)
        else:
            ok, out, err = _run_gemini(prompt, cfg)
        run_log[a] = (err or "").strip()
        if ok and out.strip():
            drafts[a] = out.strip()
            (drafts_root / f"{a}.md").write_text(out.strip(), encoding="utf-8")
        else:
            (drafts_root / f"{a}.failed.txt").write_text((err or out or "").strip(), encoding="utf-8")

    if not drafts and cfg.synthesizer != "claude":
        raise RuntimeError("No drafts generated (codex/gemini missing or failed).")

    final_text = ""
    if not synthesize or cfg.synthesizer == "none":
        # Always write a combined view for manual selection.
        combined = _synth_prompt(kind, user_prompt, drafts)
        (drafts_root / "combined.md").write_text(combined, encoding="utf-8")
        final_text = drafts.get(agents[0], "") if agents and agents[0] in drafts else (next(iter(drafts.values()), ""))
    elif cfg.synthesizer == "codex":
        ok, out, err = _run_codex(_synth_prompt(kind, user_prompt, drafts), cfg, workdir=drafts_root)
        if not ok or not out.strip():
            raise RuntimeError(f"codex synthesizer failed: {(err or out)[:500]}")
        final_text = out.strip()
    elif cfg.synthesizer == "gemini":
        ok, out, err = _run_gemini(_synth_prompt(kind, user_prompt, drafts), cfg)
        if not ok or not out.strip():
            raise RuntimeError(f"gemini synthesizer failed: {(err or out)[:500]}")
        final_text = out.strip()
    else:
        # Claude Agent SDK synthesis (optional). If it fails, fall back to combined drafts.
        model = cfg.claude_model or os.environ.get("AUTOCODER_REVIEW_MODEL") or "sonnet"
        ok, out, err = asyncio.run(_claude_synthesize(_synth_prompt(kind, user_prompt, drafts), model, drafts_root, cfg.timeout_s))
        if ok and out.strip():
            final_text = out.strip()
        else:
            combined = _synth_prompt(kind, user_prompt, drafts)
            (drafts_root / "combined.md").write_text(combined, encoding="utf-8")
            final_text = next(iter(drafts.values()), combined)

    output.write_text(final_text, encoding="utf-8")
    status = {
        "status": "complete",
        "kind": kind,
        "output_path": str(output),
        "drafts_dir": str(drafts_root),
        "agents": list(drafts.keys()),
        "synthesizer": cfg.synthesizer,
        "timestamp": datetime.now().isoformat(),
        "notes": run_log,
    }
    (drafts_root / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return {"output_path": str(output), "drafts_dir": str(drafts_root)}
