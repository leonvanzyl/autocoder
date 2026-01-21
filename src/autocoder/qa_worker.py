"""
Patch Worker (External CLI Providers)
====================================

A short-lived worker that can:

- `--mode fix`: run after Gatekeeper rejection and patch ONLY the failing verification
- `--mode implement`: implement a feature by emitting a unified diff patch

Engines:
- codex_cli: `codex` CLI emits a patch (captured via output schema)
- gemini_cli: `gemini` CLI emits a patch (`-o json`)
- claude_patch: Claude SDK emits a unified diff (read-only tools)

This worker:
1) loads feature context from `agent_system.db`
2) generates a patch, applies it, commits it
3) marks the feature READY_FOR_VERIFICATION (Gatekeeper re-verifies deterministically)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from autocoder.core.cli_defaults import get_codex_cli_defaults
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from autocoder.core.database import get_database
from autocoder.core.knowledge_files import build_knowledge_bundle

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _cli_argv(name: str) -> list[str]:
    """
    Cross-platform argv prefix for calling a CLI.

    On Windows, Node CLIs often resolve to `.cmd` shims, so we execute via `cmd.exe /c`.
    """
    if os.name != "nt":
        return [name]
    resolved_full = shutil.which(name) or ""
    resolved = resolved_full.lower()
    if resolved.endswith(".exe"):
        return [name]
    if resolved.endswith(".ps1"):
        shell = "pwsh" if shutil.which("pwsh") else "powershell"
        return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved_full or name]
    return ["cmd.exe", "/c", name]


def _extract_json_from_text(text: str) -> dict | None:
    s = (text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(s[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def _strip_fences(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^```(?:diff|patch)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _looks_like_unified_diff(patch: str) -> bool:
    s = patch.strip()
    # Require a git-style header; this avoids confusing our internal apply_patch format (*** Begin Patch)
    # with a git-apply-compatible diff.
    return s.startswith("diff --git ") or ("diff --git " in s)


def _git(cwd: Path, args: list[str], *, check: bool = True, timeout_s: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )


def _detect_main_branch(repo: Path) -> str:
    for candidate in ("main", "master"):
        try:
            _git(repo, ["rev-parse", "--verify", candidate], check=True)
            return candidate
        except Exception:
            continue
    return "main"


def _repo_diff(repo: Path, base: str) -> str:
    try:
        return _git(repo, ["diff", f"{base}...HEAD"], check=True, timeout_s=120).stdout or ""
    except Exception:
        return ""


def _read_file_excerpt(path: Path, *, max_chars: int = 12_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


def _git_ls_files(repo: Path, *, max_files: int = 400) -> list[str]:
    try:
        out = _git(repo, ["ls-files"], check=True, timeout_s=60).stdout or ""
    except Exception:
        return []
    files = [x.strip() for x in out.splitlines() if x.strip()]
    if len(files) > max_files:
        return files[:max_files] + [f"... ({len(files) - max_files} more)"]
    return files


def _detect_project_hints(repo: Path) -> dict[str, str]:
    hints: dict[str, str] = {}
    for rel in ("autocoder.yaml", "README.md", "package.json", "pyproject.toml", "requirements.txt"):
        p = repo / rel
        if p.exists():
            hints[rel] = _read_file_excerpt(p, max_chars=12_000)
    return hints


def _feature_steps_text(feature: dict) -> str:
    steps = feature.get("steps")
    if isinstance(steps, list):
        parts = [str(s).strip() for s in steps]
        parts = [s for s in parts if s]
        return "\n".join(f"- {s}" for s in parts)
    if isinstance(steps, str) and steps.strip():
        return steps.strip()
    return ""


def _apply_patch(repo: Path, patch_text: str) -> tuple[bool, str]:
    patch_text = _strip_fences(patch_text)
    patch_text = patch_text.replace("\r\n", "\n").replace("\r", "\n")
    # If a model included preamble text, keep only from the first diff header.
    if "diff --git " in patch_text and not patch_text.lstrip().startswith("diff --git "):
        patch_text = patch_text[patch_text.find("diff --git ") :].lstrip()
    if not _looks_like_unified_diff(patch_text):
        return False, "Patch did not look like a unified diff"
    if not patch_text.endswith("\n"):
        patch_text += "\n"
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch", encoding="utf-8") as f:
        f.write(patch_text)
        patch_path = f.name
    try:
        proc = subprocess.run(
            ["git", "apply", "--whitespace=fix", patch_path],
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or "git apply failed").strip()
        return True, ""
    finally:
        with contextlib.suppress(Exception):
            os.unlink(patch_path)


def _stage_and_commit(repo: Path, message: str) -> tuple[bool, str]:
    try:
        _git(repo, ["add", "-A"], check=True, timeout_s=120)
        diff_res = subprocess.run(
            ["git", "diff", "--cached", "--exit-code"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if diff_res.returncode == 0:
            return False, "No staged changes to commit"
        _git(repo, ["commit", "-m", message], check=True, timeout_s=120)
        return True, ""
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or str(e)).strip()
        return False, msg
    except Exception as e:
        return False, str(e)


def _fix_prompt(*, repo: Path, failure: str, diff: str, attempt: int) -> str:
    knowledge = build_knowledge_bundle(repo, max_total_chars=8000)
    base = (
        "You are a software engineer fixing a CI failure.\n"
        "Return JSON only with keys: patch (string), summary (string).\n"
        "The patch must be a git-style UNIFIED DIFF (git apply compatible) that makes verification pass.\n"
        "Rules:\n"
        "- Only fix the failing verification (tests/lint/typecheck). No new features.\n"
        "- Keep the patch minimal.\n"
        "- The patch MUST start with 'diff --git a/... b/...'.\n"
        "- Do NOT output '*** Begin Patch' or any other wrapper format.\n"
        "- Output JSON only (no markdown, no explanation).\n\n"
        f"Attempt: {attempt}\n\n"
        "Gatekeeper failure excerpt:\n"
        + (failure.strip()[:50_000] if failure else "(missing)")
        + "\n\n"
        + (("Project knowledge files:\n" + knowledge + "\n\n") if knowledge else "")
        + "Current diff from base to HEAD:\n"
        + (diff.strip()[:200_000] if diff else "(empty diff)")
    )
    # Gemini CLI already enforces JSON output mode; Codex uses output schema. Content can be the same.
    return base


def _implement_prompt(*, repo: Path, feature: dict, files: list[str], hints: dict[str, str], diff: str, attempt: int) -> str:
    name = str(feature.get("name") or "").strip()
    desc = str(feature.get("description") or "").strip()
    category = str(feature.get("category") or "").strip()
    steps_text = _feature_steps_text(feature)
    hint_block = "\n\n".join(f"{k}:\n{v}" for k, v in hints.items() if v.strip())
    knowledge = build_knowledge_bundle(repo, max_total_chars=8000)

    return (
        "You are a software engineer implementing a feature.\n"
        "Return JSON only with keys: patch (string), summary (string).\n"
        "The patch must be a git-style UNIFIED DIFF (git apply compatible).\n"
        "Rules:\n"
        "- Implement ONLY this feature. Avoid unrelated refactors.\n"
        "- Keep changes minimal but complete.\n"
        "- The patch MUST start with 'diff --git a/... b/...'.\n"
        "- Do NOT output '*** Begin Patch' or any other wrapper format.\n"
        "- Output JSON only (no markdown, no explanation).\n\n"
        f"Attempt: {attempt}\n\n"
        "Feature:\n"
        f"- Name: {name}\n"
        + (f"- Category: {category}\n" if category else "")
        + (f"- Description: {desc}\n" if desc else "")
        + ("- Steps:\n" + steps_text + "\n" if steps_text else "")
        + "\n"
        "Repository file list (partial):\n"
        + ("\n".join(files) if files else "(unable to list files)")
        + "\n\n"
        + (("Project knowledge files:\n" + knowledge + "\n\n") if knowledge else "")
        + (hint_block + "\n\n" if hint_block else "")
        + "Current diff from base to HEAD:\n"
        + (diff.strip()[:200_000] if diff else "(empty diff)")
    )


def _run_codex(repo: Path, *, prompt: str, timeout_s: int) -> tuple[bool, str, str]:
    if shutil.which("codex") is None:
        return False, "", "codex not found"
    defaults = get_codex_cli_defaults()
    model = (os.environ.get("AUTOCODER_CODEX_MODEL") or "").strip() or defaults.model or "gpt-5.2"
    reasoning = (
        (os.environ.get("AUTOCODER_CODEX_REASONING_EFFORT") or "").strip()
        or defaults.reasoning_effort
        or "high"
    )

    schema = {
        "type": "object",
        "properties": {"patch": {"type": "string"}, "summary": {"type": "string"}},
        "required": ["patch", "summary"],
        "additionalProperties": False,
    }

    with tempfile.TemporaryDirectory(prefix="autocoder-worker-codex-") as td:
        td_path = Path(td)
        schema_file = td_path / "schema.json"
        schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
        fd, out_path = tempfile.mkstemp(prefix="autocoder-codex-worker-", suffix=".json")
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
            str(repo),
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
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
            )
            text_out = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
            stderr = (proc.stderr or proc.stdout or "").strip()
            if proc.returncode != 0 or not text_out.strip():
                return False, "", stderr or "codex failed"
            data = _extract_json_from_text(text_out)
            if not data or not isinstance(data.get("patch"), str):
                return False, "", "codex returned non-JSON or missing patch"
            return True, str(data.get("patch") or ""), stderr
        except subprocess.TimeoutExpired:
            return False, "", "codex timed out"
        finally:
            with contextlib.suppress(Exception):
                out_file.unlink(missing_ok=True)  # type: ignore[arg-type]


def _run_gemini(repo: Path, *, prompt: str, timeout_s: int) -> tuple[bool, str, str]:
    if shutil.which("gemini") is None:
        return False, "", "gemini not found"
    model = os.environ.get("AUTOCODER_GEMINI_MODEL") or "gemini-3-pro-preview"
    cmd = [*_cli_argv("gemini"), "-m", model, "-o", "json"]

    env = dict(os.environ)
    settings = (Path(__file__).resolve().parents[0] / "reviewers" / "config" / "gemini-readonly-settings.json").resolve()
    if settings.exists():
        env.setdefault("GEMINI_CLI_SYSTEM_SETTINGS_PATH", str(settings))

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=env,
        )
        if proc.returncode != 0:
            return False, "", (proc.stderr or proc.stdout or "gemini failed").strip()
        raw = proc.stdout or ""
        outer = _extract_json_from_text(raw)
        inner = raw
        if isinstance(outer, dict) and isinstance(outer.get("response"), str):
            inner = outer["response"]
        data = _extract_json_from_text(inner or "")
        if not data or not isinstance(data.get("patch"), str):
            return False, "", "gemini returned non-JSON or missing patch"
        return True, str(data.get("patch") or ""), (proc.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return False, "", "gemini timed out"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Patch worker (Codex/Gemini/Claude unified-diff applier)")
    p.add_argument("--mode", default="fix", choices=["fix", "implement"])
    p.add_argument("--project-dir", required=True)
    p.add_argument("--agent-id", required=True)
    p.add_argument("--feature-id", type=int, required=True)
    p.add_argument("--worktree-path", required=True)
    p.add_argument("--engines", required=True, help="JSON array of patch engines (codex_cli|gemini_cli|claude_patch)")
    p.add_argument("--max-iterations", type=int, default=2)
    p.add_argument("--timeout-s", type=int, default=600)
    return p.parse_args()


async def heartbeat_loop(database, agent_id: str, interval_seconds: int = 60) -> None:
    while True:
        with contextlib.suppress(Exception):
            database.update_heartbeat(agent_id)
        await asyncio.sleep(max(5, interval_seconds))


def _parse_engine_list(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        v = item.strip().lower()
        if v in {"codex_cli", "gemini_cli", "claude_patch"}:
            out.append(v)
    # de-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for v in out:
        if v in seen:
            continue
        seen.add(v)
        deduped.append(v)
    return deduped


def _claude_cli_path(use_custom_api: bool) -> str | None:
    if use_custom_api:
        return None
    cli_command = (os.environ.get("AUTOCODER_CLI_COMMAND") or os.environ.get("CLI_COMMAND") or "claude").strip()
    return shutil.which(cli_command)


async def _run_claude_patch(repo: Path, *, prompt: str, timeout_s: int) -> tuple[bool, str, str]:
    use_custom_api = False
    if "ANTHROPIC_AUTH_TOKEN" in os.environ:
        os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_AUTH_TOKEN"]
        use_custom_api = True

    credentials_path = Path.home() / ".claude" / ".credentials.json"
    if not use_custom_api and not credentials_path.exists():
        return False, "", "claude credentials not found; skipped"

    model = (
        os.environ.get("AUTOCODER_CLAUDE_PATCH_MODEL")
        or os.environ.get("AUTOCODER_REVIEW_MODEL")
        or "sonnet"
    ).strip()

    # Read-only settings file (no writes).
    settings_file = repo / ".claude_settings.patch.json"
    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "reject",
            "allow": [
                "Read(./**)",
                "Glob(./**)",
                "Grep(./**)",
            ],
        },
    }
    settings_file.write_text(json.dumps(security_settings, indent=2), encoding="utf-8")

    client = ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            cli_path=_claude_cli_path(use_custom_api),
            allowed_tools=["Read", "Glob", "Grep"],
            system_prompt=(
                "You are generating a unified diff patch.\n"
                "Output ONLY the unified diff starting with 'diff --git'.\n"
                "No explanations, no markdown fences."
            ),
            cwd=str(repo),
            settings=str(settings_file),
            max_turns=2,
            setting_sources=["project"],
        )
    )

    async def _collect() -> str:
        await client.query(prompt)
        text = ""
        async for msg in client.receive_response():
            if type(msg).__name__ == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                        text += block.text
        return text

    try:
        text = await asyncio.wait_for(_collect(), timeout=timeout_s)
        return True, text, ""
    except asyncio.TimeoutError:
        return False, "", "claude patch timed out"
    except Exception as e:
        return False, "", str(e)


async def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    repo = Path(args.worktree_path).resolve()
    mode = str(args.mode or "fix").strip().lower()

    database = get_database(str(project_dir))
    feature = database.get_feature(args.feature_id) or {}
    base = _detect_main_branch(repo)
    diff = _repo_diff(repo, base)

    failure = ""
    if mode == "fix":
        failure = str(feature.get("last_error") or "").strip()
        artifact_path = str(feature.get("last_artifact_path") or "").strip()
        if artifact_path:
            failure = (failure + "\n" + f"Artifact: {artifact_path}").strip()

    logger.info("=" * 70)
    logger.info("PATCH WORKER - " + ("IMPLEMENT" if mode == "implement" else "QA FIX"))
    logger.info("=" * 70)
    logger.info(f"Agent:    {args.agent_id}")
    logger.info(f"Feature:  #{args.feature_id} - {feature.get('name')}")
    logger.info(f"Repo:     {repo}")
    engines = _parse_engine_list(args.engines)
    if not engines:
        logger.error("No valid engines provided. Expected JSON list of codex_cli|gemini_cli|claude_patch.")
        return 2

    logger.info(f"Engines:  {', '.join(engines)}")
    logger.info(f"Max iters:{args.max_iterations}")
    logger.info("=" * 70)

    hb = asyncio.create_task(heartbeat_loop(database, args.agent_id, 60))
    try:
        ok_any = False
        last_err = ""
        artifacts_dir = (
            project_dir / ".autocoder" / "features" / str(args.feature_id) / ("worker" if mode == "implement" else "qa")
        )
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        files = _git_ls_files(repo) if mode == "implement" else []
        hints = _detect_project_hints(repo) if mode == "implement" else {}

        for attempt in range(1, max(1, int(args.max_iterations)) + 1):
            for p in engines:
                logger.info(f"Attempt {attempt}: engine={p}")
                try:
                    if mode == "implement":
                        prompt = _implement_prompt(
                            repo=repo,
                            feature=feature,
                            files=files,
                            hints=hints,
                            diff=diff,
                            attempt=attempt,
                        )
                    else:
                        failure_blob = failure + ("\n" + last_err if last_err else "")
                        prompt = _fix_prompt(repo=repo, failure=failure_blob, diff=diff, attempt=attempt)

                    if p == "codex_cli":
                        ok, patch, err = _run_codex(repo, prompt=prompt, timeout_s=int(args.timeout_s))
                    elif p == "gemini_cli":
                        ok, patch, err = _run_gemini(repo, prompt=prompt, timeout_s=int(args.timeout_s))
                    else:
                        ok, patch, err = await _run_claude_patch(repo, prompt=prompt, timeout_s=int(args.timeout_s))
                except Exception as e:
                    ok, patch, err = False, "", str(e)

                if not ok:
                    last_err = err or "engine failed"
                    logger.warning(last_err)
                    continue

                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                with contextlib.suppress(Exception):
                    (artifacts_dir / f"{stamp}.{p}.raw.txt").write_text(patch or "", encoding="utf-8")

                applied, apply_err = _apply_patch(repo, patch)
                if not applied:
                    last_err = apply_err
                    logger.warning(f"Patch apply failed: {apply_err}")
                    with contextlib.suppress(Exception):
                        (artifacts_dir / f"{stamp}.{p}.apply_error.txt").write_text(apply_err or "", encoding="utf-8")
                    continue

                commit_msg = (
                    f"worker: implement feature #{args.feature_id} ({p})"
                    if mode == "implement"
                    else f"qa: fix Gatekeeper failure ({p})"
                )
                committed, commit_err = _stage_and_commit(repo, commit_msg)
                if not committed:
                    last_err = commit_err
                    logger.warning(f"Commit failed: {commit_err}")
                    with contextlib.suppress(Exception):
                        (artifacts_dir / f"{stamp}.{p}.commit_error.txt").write_text(commit_err or "", encoding="utf-8")
                    continue

                database.mark_feature_ready_for_verification(args.feature_id)
                ok_any = True
                logger.info("Submitted for verification")
                break
            if ok_any:
                break

        if not ok_any:
            database.mark_feature_failed(
                feature_id=args.feature_id,
                reason=(
                    f"{'Worker' if mode == 'implement' else 'QA worker'} failed to produce/apply a patch.\nLast error: {last_err}"
                ),
                preserve_branch=True,
            )
            return 1
        return 0
    finally:
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await hb
        with contextlib.suppress(Exception):
            database.mark_agent_completed(args.agent_id)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
