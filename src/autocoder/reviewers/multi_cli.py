from __future__ import annotations

import json
import os
import contextlib
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .base import ReviewConfig, ReviewFinding, ReviewResult, Reviewer
from autocoder.agent.retry import execute_with_retry_sync, retry_config_from_env
from autocoder.core.cli_defaults import get_codex_cli_defaults


ConsensusMode = Literal["majority", "all", "any"]


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _repo_asset_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent / "config" / Path(*parts)


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
    if resolved.endswith(".ps1"):
        shell = "pwsh" if shutil.which("pwsh") else "powershell"
        # Arguments after the script path are forwarded to the script.
        return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", shutil.which(name) or name]
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


def _parse_agents(value: str | None) -> list[str]:
    if not value:
        return []
    raw = [x.strip().lower() for x in value.replace(";", ",").split(",")]
    out = [x for x in raw if x]
    # Deduplicate, preserve order
    seen: set[str] = set()
    deduped: list[str] = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        deduped.append(x)
    return deduped


def _consensus_mode(value: str | None) -> ConsensusMode:
    v = (value or "majority").strip().lower()
    if v in {"majority", "all", "any"}:
        return v  # type: ignore[return-value]
    return "majority"


def _codex_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "approved": {"type": "boolean"},
            "reason": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                        "message": {"type": "string"},
                        "file": {"type": ["string", "null"]},
                    },
                    "required": ["severity", "message"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["approved", "reason", "findings"],
        "additionalProperties": False,
    }


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """
    Best-effort JSON extraction for CLIs that emit non-JSON preamble.
    """
    s = (text or "").strip()
    if not s:
        return None
    # Fast path: full JSON
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    # Fallback: try to find a top-level JSON object region.
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(s[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def _normalize_findings(raw: object) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    if not isinstance(raw, list):
        return findings
    for item in raw:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "P2").strip().upper()
        if sev not in {"P0", "P1", "P2", "P3"}:
            sev = "P2"
        msg = str(item.get("message") or "").strip()
        if not msg:
            continue
        f = item.get("file")
        findings.append(
            ReviewFinding(
                severity=sev,  # type: ignore[arg-type]
                message=msg,
                file=str(f) if f not in (None, "") else None,
            )
        )
    return findings


@dataclass(frozen=True)
class MultiCliReviewer(Reviewer):
    """
    External multi-model reviewer using local CLIs (Codex + Gemini).

    This mirrors the Cerberus pattern: treat external models as a read-only gate
    driven by `git diff --cached` in the verification worktree.
    """

    cfg: ReviewConfig

    def _build_prompt(self, *, diff: str, base_branch: str, feature_branch: str) -> str:
        return (
            "You are a strict code reviewer. Review ONLY the staged diff below.\n"
            "Return JSON only (no markdown), matching this schema:\n"
            '{ "approved": boolean, "reason": string, "findings": [ { "severity": "P0|P1|P2|P3", "message": string, "file": string|null } ] }\n\n'
            f"Base branch: {base_branch}\n"
            f"Feature branch: {feature_branch}\n\n"
            "Guidance:\n"
            "- P0: security/data loss/broken builds\n"
            "- P1: correctness bugs, failing tests, major DX issues\n"
            "- P2: maintainability, missing edge cases\n"
            "- P3: style/nit\n\n"
            "STAGED DIFF (git diff --cached):\n\n"
            + diff[:200_000]
        )

    def _run_codex(self, *, prompt_file: Path, schema_file: Path, timeout_s: int) -> tuple[bool, str, str]:
        if shutil.which("codex") is None:
            return True, "", "codex not found; skipped"
        if _breaker_is_open("codex"):
            return True, "", "codex circuit breaker open; skipped"
        defaults = get_codex_cli_defaults()
        model = (
            (self.cfg.codex_model or "").strip()
            or (os.environ.get("AUTOCODER_CODEX_MODEL") or "").strip()
            or defaults.model
            or "gpt-5.2"
        )
        reasoning = (
            (self.cfg.codex_reasoning_effort or "").strip()
            or (os.environ.get("AUTOCODER_CODEX_REASONING_EFFORT") or "").strip()
            or defaults.reasoning_effort
            or "high"
        )
        cfg = retry_config_from_env(prefix="AUTOCODER_SDK_")

        def attempt() -> tuple[str, str]:
            fd, out_path = tempfile.mkstemp(prefix="autocoder-codex-review-", suffix=".json")
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
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_file),
                "--output-last-message",
                str(out_file),
                "-",
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    stdin=prompt_file.open("r", encoding="utf-8"),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_s,
                )
            except subprocess.TimeoutExpired as e:
                with contextlib.suppress(Exception):
                    out_file.unlink(missing_ok=True)
                raise TimeoutError("codex timed out") from e
            try:
                text_out = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
            except Exception:
                text_out = ""
            with contextlib.suppress(Exception):
                out_file.unlink(missing_ok=True)
            if proc.returncode != 0 or not text_out.strip():
                msg = (proc.stderr or proc.stdout or "").strip() or "codex failed"
                raise RuntimeError(msg)
            return text_out.strip(), (proc.stderr or proc.stdout or "").strip()

        try:
            text_out, err = execute_with_retry_sync(attempt, config=cfg)
            _breaker_record_success("codex")
            return True, text_out, err
        except Exception as e:
            _breaker_record_failure("codex")
            return False, "", str(e)

    def _run_gemini(self, *, prompt_file: Path, timeout_s: int) -> tuple[bool, str, str]:
        if shutil.which("gemini") is None:
            return True, "", "gemini not found; skipped"
        if _breaker_is_open("gemini"):
            return True, "", "gemini circuit breaker open; skipped"
        settings = _repo_asset_path("gemini-readonly-settings.json")
        if not settings.exists():
            return True, "", "gemini read-only settings missing; skipped"
        model = self.cfg.gemini_model or os.environ.get("AUTOCODER_GEMINI_MODEL") or "gemini-3-pro-preview"
        env = dict(os.environ)
        env["GEMINI_CLI_SYSTEM_SETTINGS_PATH"] = str(settings)
        cmd = [*_cli_argv("gemini"), "-m", model, "-o", "json"]
        cfg = retry_config_from_env(prefix="AUTOCODER_SDK_")

        def attempt() -> tuple[str, str]:
            try:
                proc = subprocess.run(
                    cmd,
                    stdin=prompt_file.open("r", encoding="utf-8"),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_s,
                    env=env,
                )
            except subprocess.TimeoutExpired as e:
                raise TimeoutError("gemini timed out") from e
            if proc.returncode != 0:
                msg = (proc.stderr or proc.stdout or "").strip() or "gemini failed"
                raise RuntimeError(msg)
            return (proc.stdout or ""), (proc.stderr or "")

        try:
            out, err = execute_with_retry_sync(attempt, config=cfg)
            _breaker_record_success("gemini")
            return True, out, err
        except Exception as e:
            _breaker_record_failure("gemini")
            return False, "", str(e)

    def _decide(self, results: list[tuple[str, ReviewResult]]) -> ReviewResult:
        """
        Apply consensus across available reviewers.

        - Skipped reviewers do not count toward consensus.
        - If all reviewers are skipped, default to approved+skipped.
        """
        active = [(n, r) for (n, r) in results if not r.skipped]
        if not active:
            return ReviewResult(approved=True, skipped=True, reason="All external reviewers skipped")

        mode = _consensus_mode(self.cfg.consensus)
        approvals = sum(1 for _, r in active if r.approved)
        total = len(active)

        if mode == "all":
            approved = approvals == total
        elif mode == "any":
            approved = approvals >= 1
        else:
            approved = approvals >= ((total // 2) + 1)

        findings: list[ReviewFinding] = []
        reasons: list[str] = []
        for name, r in active:
            reasons.append(f"{name}: {r.reason}".strip())
            findings.extend(r.findings)

        return ReviewResult(
            approved=approved,
            reason=("; ".join([x for x in reasons if x]) or "External review complete"),
            findings=findings,
        )

    def review(
        self,
        *,
        workdir: str,
        base_branch: str,
        feature_branch: str,
        agent_id: str | None = None,
    ) -> ReviewResult:
        # Policy: allow operators to disable multi-CLI review entirely.
        if _truthy_env("AUTOCODER_DISABLE_MULTI_REVIEW"):
            return ReviewResult(approved=True, skipped=True, reason="Multi-CLI review disabled by env")

        workdir_path = Path(workdir).resolve()
        diff = os.popen(f'cd "{workdir_path}" && git diff --cached').read()
        if not diff.strip():
            return ReviewResult(approved=True, skipped=True, reason="Empty diff; skipping external review")

        timeout_s = int(self.cfg.timeout_s or 300)
        raw_agents = self.cfg.engines or ["codex_cli", "gemini_cli"]
        agents = []
        for a in raw_agents:
            if a == "codex_cli":
                agents.append("codex")
            elif a == "gemini_cli":
                agents.append("gemini")
        if not agents:
            agents = ["codex", "gemini"]

        prompt = self._build_prompt(diff=diff, base_branch=base_branch, feature_branch=feature_branch)

        with tempfile.TemporaryDirectory(prefix="autocoder-review-") as td:
            td_path = Path(td)
            prompt_file = td_path / "prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            schema_file = td_path / "schema.json"
            schema_file.write_text(json.dumps(_codex_schema(), indent=2), encoding="utf-8")

            per: list[tuple[str, ReviewResult]] = []
            for name in agents:
                if name == "codex":
                    ok, out, err = self._run_codex(prompt_file=prompt_file, schema_file=schema_file, timeout_s=timeout_s)
                else:
                    ok, out, err = self._run_gemini(prompt_file=prompt_file, timeout_s=timeout_s)

                if "not found" in (err or "").lower() or "skipped" in (err or "").lower():
                    per.append((name, ReviewResult(approved=True, skipped=True, reason=err.strip())))
                    continue

                # gemini -o json wraps the model response; extract `response` when present.
                if name == "gemini":
                    outer = _extract_json_from_text(out)
                    if isinstance(outer, dict) and isinstance(outer.get("response"), str):
                        out = outer["response"]

                data = _extract_json_from_text(out)
                if not ok or data is None:
                    per.append(
                        (
                            name,
                            ReviewResult(
                                approved=False,
                                reason="Reviewer failed or returned non-JSON",
                                stdout=out,
                                stderr=err,
                            ),
                        )
                    )
                    continue

                approved = bool(data.get("approved", False))
                reason = str(data.get("reason") or "")
                findings = _normalize_findings(data.get("findings"))
                per.append((name, ReviewResult(approved=approved, reason=reason, findings=findings, stdout=out, stderr=err)))

            return self._decide(per)
