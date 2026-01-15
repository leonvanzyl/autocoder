"""
Gatekeeper - Verification and Merge Script
==========================================

The Gatekeeper is the ONLY component allowed to merge code to the main branch.

This is a DETERMINISTIC script (not an AI agent) that:
1. Runs the test suite using detected framework
2. Verifies all tests pass
3. Merges feature branch to main IF tests pass
4. Rejects feature IF tests fail

Architecture Note:
- This is PYTHON code, not an LLM agent
- Uses direct imports (fast, efficient)
- Deterministic logic (no AI needed)
"""

import os
import subprocess
import logging
import contextlib
import json
import shutil
import sys
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Direct imports (system code = fast!)
from .test_framework_detector import TestFrameworkDetector
from .worktree_manager import WorktreeManager
from .project_config import load_project_config, infer_preset, synthesize_commands_from_preset
from autocoder.reviewers.base import ReviewConfig
from autocoder.reviewers.factory import get_reviewer

logger = logging.getLogger(__name__)


class Gatekeeper:
    """
    Gatekeeper verifies feature branches before merging to main.

    Only the Gatekeeper can write to the main branch. This ensures
    quality and prevents broken code from being merged.
    """

    @staticmethod
    def _is_yolo_mode() -> bool:
        raw = str(os.environ.get("AUTOCODER_YOLO_MODE", "")).strip().lower()
        return raw not in {"", "0", "false", "no", "off"}

    @staticmethod
    def _apply_allow_no_tests(test_results: Dict[str, Any], *, allow_no_tests: bool) -> Dict[str, Any]:
        """
        YOLO-only escape hatch when a project has no test command/script.

        This is intentionally conservative: it only flips to pass when we can clearly
        detect a "no tests" situation.
        """
        if not allow_no_tests or not Gatekeeper._is_yolo_mode():
            return test_results

        out = dict(test_results)
        if not out.get("success", False):
            return out
        if out.get("passed", False):
            return out

        exit_code = out.get("exit_code")
        cmd = str(out.get("command", "")).lower()
        combined = (str(out.get("output", "")) + str(out.get("errors", ""))).lower()

        # npm: Missing script: "test"
        if "npm" in cmd and "missing script" in combined and "\"test\"" in combined:
            out["passed"] = True
            out["note"] = "No test script detected; allowed by configuration (YOLO mode)"
            return out

        # Pytest exit code 5: no tests collected
        if ("pytest" in cmd and exit_code == 5) or ("collected 0 items" in combined):
            out["passed"] = True
            out["note"] = "No tests collected; allowed by configuration (YOLO mode)"
            return out

        # Generic "no test framework detected" (from detector path)
        if "no test framework detected" in str(out.get("error", "")).lower():
            out["passed"] = True
            out["note"] = "No tests detected; allowed by configuration (YOLO mode)"
            return out

        return out

    @staticmethod
    def _select_node_install_command(project_dir: Path) -> str | None:
        project_dir = Path(project_dir)
        if not (project_dir / "package.json").exists():
            return None

        if (project_dir / "pnpm-lock.yaml").exists() and shutil.which("pnpm"):
            return "pnpm install --frozen-lockfile"
        if (project_dir / "yarn.lock").exists() and shutil.which("yarn"):
            return "yarn install --frozen-lockfile"
        if (project_dir / "package-lock.json").exists() and shutil.which("npm"):
            return "npm ci"
        if shutil.which("npm"):
            return "npm install"
        return None

    def __init__(self, project_dir: str):
        """
        Initialize the Gatekeeper.

        Args:
            project_dir: Path to the main project directory
        """
        self.project_dir = Path(project_dir).resolve()
        self.test_detector = TestFrameworkDetector(str(self.project_dir))
        self.worktree_manager = WorktreeManager(str(self.project_dir))

        logger.info(f"Gatekeeper initialized for: {self.project_dir}")

    def verify_and_merge(
        self,
        branch_name: str,
        worktree_path: Optional[str] = None,
        agent_id: Optional[str] = None,
        *,
        feature_id: int | None = None,
        main_branch: Optional[str] = None,
        fetch_remote: bool = False,
        push_remote: bool = False,
        allow_no_tests: bool = False,
        delete_feature_branch: bool = True,
    ) -> Dict[str, Any]:
        """
        Verify a feature branch and merge to main if tests pass.

        Uses a TEMPORARY WORKTREE for verification to avoid dirty state in main directory.

        Workflow:
        1. (Optional) Fetch remote main
        2. Create temporary worktree for verification
        3. In temp worktree: merge feature branch, run tests
        4. If tests pass: commit merge, fast-forward local main to merge commit
        5. (Optional) Push main to remote

        Args:
            branch_name: Name of the feature branch (e.g., "feat/user-auth-001")
            worktree_path: Optional path to agent's worktree
            agent_id: Optional agent identifier for logging
            main_branch: Main branch name (default: auto-detect, usually "main")
            fetch_remote: If True, fetch origin/<main_branch> first (if origin exists)
            push_remote: If True, push updated main to origin (if origin exists)
            allow_no_tests: If True, allow merge even when no test command is detected
            delete_feature_branch: If True, delete feature branch after successful merge

        Returns:
            Dictionary with verification result:
            {
                "approved": bool,
                "reason": str,
                "test_results": {...},
                "merge_commit": str (if approved)
            }
        """
        logger.info(f"🛡️ Gatekeeper: Verifying branch '{branch_name}'...")

        temp_worktree_path = None
        verify_branch = None
        approved = False
        test_results: Dict[str, Any] | None = None
        verification: Dict[str, Any] = {}
        review: Dict[str, Any] | None = None

        def detect_main_branch() -> str:
            if main_branch:
                return main_branch
            env_branch = os.environ.get("AUTOCODER_MAIN_BRANCH")
            if env_branch:
                return env_branch
            # Prefer "main", fallback to "master", else current branch.
            for candidate in ("main", "master"):
                try:
                    subprocess.run(
                        ["git", "rev-parse", "--verify", candidate],
                        cwd=self.project_dir,
                        check=True,
                        capture_output=True,
                    )
                    return candidate
                except subprocess.CalledProcessError:
                    continue
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=self.project_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return result.stdout.strip() or "main"
            except subprocess.CalledProcessError:
                return "main"

        def origin_exists() -> bool:
            try:
                subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=self.project_dir,
                    check=True,
                    capture_output=True,
                )
                return True
            except subprocess.CalledProcessError:
                return False

        def _git_porcelain() -> list[str]:
            raw = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
            ).stdout
            lines = [ln for ln in raw.splitlines() if ln.strip()]
            return lines

        def _split_dirty(lines: list[str]) -> tuple[list[str], list[str]]:
            # Ignore runtime/build artifacts that the orchestrator/UI creates in the main tree.
            ignore_substrings = [
                ".autocoder/",
                "worktrees/",
                "agent_system.db",
                ".eslintrc.json",
            ]
            ignored: list[str] = []
            remaining: list[str] = []
            for ln in lines:
                target = ln.replace("\\", "/")
                if any(s in target for s in ignore_substrings):
                    ignored.append(ln)
                else:
                    remaining.append(ln)
            return ignored, remaining

        def _write_artifact(result: Dict[str, Any]) -> None:
            try:
                if feature_id is not None:
                    out_dir = self.project_dir / ".autocoder" / "features" / str(int(feature_id)) / "gatekeeper"
                else:
                    out_dir = self.project_dir / ".autocoder" / "gatekeeper"
                out_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                path = out_dir / f"{stamp}.json"
                path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
                result.setdefault("artifact_path", str(path))
            except Exception:
                return

        def _expand_placeholders(command: str, project_dir: Path) -> str:
            py = sys.executable.replace("\\", "/")
            if os.name == "nt":
                venv_py = (project_dir / ".venv" / "Scripts" / "python.exe").resolve()
            else:
                venv_py = (project_dir / ".venv" / "bin" / "python").resolve()
            venv_py_s = str(venv_py).replace("\\", "/")
            return command.replace("{PY}", py).replace("{VENV_PY}", venv_py_s)

        def _review_config_from_project(cfg: Any) -> ReviewConfig:
            # cfg is a ResolvedProjectConfig; keep conversion robust in case of missing fields.
            r = getattr(cfg, "review", None)
            return ReviewConfig(
                enabled=bool(getattr(r, "enabled", False)),
                mode=str(getattr(r, "mode", "off") or "off").strip().lower(),  # type: ignore[arg-type]
                reviewer_type=str(getattr(r, "reviewer_type", "none") or "none").strip().lower(),  # type: ignore[arg-type]
                command=getattr(r, "command", None),
                timeout_s=getattr(r, "timeout_s", None),
                model=getattr(r, "model", None),
                review_agents=getattr(r, "agents", None),
                consensus=getattr(r, "consensus", None),
                codex_model=getattr(r, "codex_model", None),
                codex_reasoning_effort=getattr(r, "codex_reasoning_effort", None),
                gemini_model=getattr(r, "gemini_model", None),
            )

        def _run_shell(command: str, *, cwd: Path, timeout_s: int | None = None) -> Dict[str, Any]:
            try:
                cmd = _expand_placeholders(command, cwd)
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    timeout=int(timeout_s) if timeout_s else None,
                )
                return {
                    "success": True,
                    "passed": result.returncode == 0,
                    "exit_code": result.returncode,
                    "command": cmd,
                    "output": result.stdout or "",
                    "errors": result.stderr or "",
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "passed": False,
                    "exit_code": None,
                    "command": command,
                    "output": "",
                    "errors": f"Timed out after {timeout_s} seconds",
                    "timeout": True,
                }
            except Exception as e:
                return {
                    "success": False,
                    "passed": False,
                    "exit_code": None,
                    "command": command,
                    "output": "",
                    "errors": str(e),
                }

        def _compute_diff_fingerprint(cwd: Path) -> str | None:
            """
            Stable fingerprint of the merged change-set (index vs HEAD) in the verification worktree.

            Used for "no progress" detection: if retries produce the same diff and still fail, the
            feature can be blocked to avoid infinite churn.
            """
            try:
                res = subprocess.run(
                    ["git", "diff", "--cached", "--no-color", "--no-ext-diff"],
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                )
                if res.returncode != 0:
                    return None
                data = (res.stdout or "").replace("\r\n", "\n").encode("utf-8", errors="replace")
                return hashlib.sha256(data).hexdigest()
            except Exception:
                return None

        try:
            detected_main = detect_main_branch()
            has_origin = origin_exists()

            porcelain = _git_porcelain()
            ignored_dirty, remaining_dirty = _split_dirty(porcelain)
            can_update_ref_without_checkout = bool(ignored_dirty) and not remaining_dirty
            if remaining_dirty:
                return {
                    "approved": False,
                    "reason": "Main working tree has uncommitted changes; refusing to merge",
                    "details": "\n".join(remaining_dirty),
                }
            if ignored_dirty:
                logger.warning(
                    "Main working tree has uncommitted runtime/artifact changes; proceeding anyway because Gatekeeper updates refs without checking out main."
                )

            if fetch_remote and has_origin:
                try:
                    subprocess.run(
                        ["git", "fetch", "origin", detected_main],
                        cwd=self.project_dir,
                        check=True,
                        capture_output=True,
                    )
                    logger.info(f"✓ Fetched origin/{detected_main}")
                except subprocess.CalledProcessError as e:
                    return {
                        "approved": False,
                        "reason": f"Failed to fetch origin/{detected_main}",
                        "error": str(e),
                    }

            # Step 2: Create temporary worktree for verification
            temp_worktree_path = self.project_dir / f"verify_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            try:
                base_ref = f"origin/{detected_main}" if (fetch_remote and has_origin) else detected_main
                verify_branch = f"verify/{branch_name.replace(' ', '-').replace('\\\\', '-').replace(':', '-')}"
                # Create temp worktree on base ref
                subprocess.run(
                    ["git", "worktree", "add", "-b", verify_branch, str(temp_worktree_path), base_ref],
                    cwd=self.project_dir,
                    check=True,
                    capture_output=True
                )
                logger.info(f"✓ Created temporary worktree: {temp_worktree_path}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create temp worktree: {e}")
                return {
                    "approved": False,
                    "reason": "Failed to create temporary worktree for verification",
                    "error": str(e)
                }

            # Step 3: In temp worktree, attempt merge (no commit yet)
            try:
                merge_result = subprocess.run(
                    ["git", "merge", "--no-commit", "--no-ff", branch_name],
                    cwd=str(temp_worktree_path),
                    capture_output=True,
                    text=True
                )

                if merge_result.returncode != 0:
                    # Merge conflict detected
                    logger.error(f"✗ Merge conflict detected:\n{merge_result.stderr}")
                    return {
                        "approved": False,
                        "reason": "Merge conflict - needs manual resolution",
                        "merge_conflict": True,
                        "errors": merge_result.stderr
                    }

                logger.info("✓ Merged branch in temp worktree (no commit yet)")

            except subprocess.CalledProcessError as e:
                logger.error(f"✗ Merge failed: {e}")
                return {
                    "approved": False,
                    "reason": "Merge command failed",
                    "error": str(e)
                }

            # Step 4: Run tests IN TEMP WORKTREE
            logger.info("🧪 Running verification in temporary worktree...")
            temp_path = Path(str(temp_worktree_path))
            diff_fingerprint = _compute_diff_fingerprint(temp_path)
            cfg = load_project_config(temp_path)
            if cfg.preset is None and not cfg.commands:
                preset = infer_preset(temp_path)
                if preset:
                    # When no autocoder.yaml exists, synthesize minimal commands from preset.
                    cmds = synthesize_commands_from_preset(preset, temp_path)
                    cfg = type(cfg)(preset=preset, commands=cmds, review=cfg.review)

            command_specs = cfg.commands or {}
            if command_specs:
                setup = command_specs.get("setup")
                if setup and setup.command:
                    setup_cmd = setup.command
                    if setup_cmd.strip() == "npm install":
                        selected = Gatekeeper._select_node_install_command(temp_path)
                        if selected:
                            setup_cmd = selected
                    verification["setup"] = _run_shell(setup_cmd, cwd=temp_path, timeout_s=setup.timeout_s)
                    verification["setup"]["allow_fail"] = bool(getattr(setup, "allow_fail", False))
                    if not verification["setup"]["passed"] and not verification["setup"]["allow_fail"]:
                        result = {
                            "approved": False,
                            "reason": "Setup failed",
                            "verification": verification,
                            "diff_fingerprint": diff_fingerprint,
                            "timestamp": datetime.now().isoformat(),
                        }
                        _write_artifact(result)
                        return result

                # Run remaining commands; ensure "test" runs early.
                ordered = ["test", "lint", "typecheck", "format", "build", "acceptance"]
                seen = set(["setup"])
                for name in ordered + sorted(k for k in command_specs.keys() if k not in ordered):
                    if name in seen:
                        continue
                    spec = command_specs.get(name)
                    if not spec or not getattr(spec, "command", None):
                        continue
                    seen.add(name)
                    verification[name] = _run_shell(spec.command, cwd=temp_path, timeout_s=spec.timeout_s)
                    verification[name]["allow_fail"] = bool(getattr(spec, "allow_fail", False))
                    if name == "test":
                        verification[name] = Gatekeeper._apply_allow_no_tests(
                            verification[name], allow_no_tests=allow_no_tests
                        )
                    if not verification[name]["success"] and not verification[name]["allow_fail"]:
                        result = {
                            "approved": False,
                            "reason": f"Verification command failed: {name}",
                            "verification": verification,
                            "diff_fingerprint": diff_fingerprint,
                            "timestamp": datetime.now().isoformat(),
                        }
                        _write_artifact(result)
                        return result
                    if not verification[name]["passed"] and not verification[name]["allow_fail"]:
                        result = {
                            "approved": False,
                            "reason": f"Verification command failed: {name}",
                            "verification": verification,
                            "diff_fingerprint": diff_fingerprint,
                            "timestamp": datetime.now().isoformat(),
                        }
                        _write_artifact(result)
                        return result

                test_results = verification.get("test")
            else:
                test_results = self._run_tests_in_directory(str(temp_worktree_path))
                test_results = Gatekeeper._apply_allow_no_tests(test_results, allow_no_tests=allow_no_tests)
                verification["test"] = test_results
                if not test_results.get("success", False):
                    result = {
                        "approved": False,
                        "reason": "Test execution failed",
                        "test_results": test_results,
                        "verification": verification,
                        "diff_fingerprint": diff_fingerprint,
                        "timestamp": datetime.now().isoformat(),
                    }
                    _write_artifact(result)
                    return result
                if not test_results.get("passed", False):
                    result = {
                        "approved": False,
                        "reason": "Tests failed - fix and resubmit",
                        "test_results": test_results,
                        "verification": verification,
                        "diff_fingerprint": diff_fingerprint,
                        "timestamp": datetime.now().isoformat(),
                    }
                    _write_artifact(result)
                    return result

            # Optional review gate (Codex/Gemini/command/Claude) on the staged diff.
            review_cfg = _review_config_from_project(cfg)
            reviewer = get_reviewer(review_cfg)
            if reviewer is not None:
                try:
                    rr = reviewer.review(
                        workdir=str(temp_path),
                        base_branch=detected_main,
                        feature_branch=branch_name,
                        agent_id=agent_id,
                    )
                    review = {
                        "approved": bool(rr.approved),
                        "skipped": bool(rr.skipped),
                        "reason": rr.reason,
                        "findings": [
                            {"severity": f.severity, "message": f.message, "file": f.file} for f in (rr.findings or [])
                        ],
                        "stdout": rr.stdout,
                        "stderr": rr.stderr,
                        "mode": review_cfg.mode,
                        "type": review_cfg.reviewer_type,
                    }
                except Exception as e:
                    review = {
                        "approved": False,
                        "skipped": False,
                        "reason": f"Reviewer error: {e}",
                        "findings": [],
                        "stdout": "",
                        "stderr": "",
                        "mode": review_cfg.mode,
                        "type": review_cfg.reviewer_type,
                    }

                if review_cfg.mode == "gate" and review and not review.get("approved") and not review.get("skipped"):
                    result = {
                        "approved": False,
                        "reason": "Review failed",
                        "verification": verification,
                        "test_results": test_results,
                        "review": review,
                        "diff_fingerprint": diff_fingerprint,
                        "timestamp": datetime.now().isoformat(),
                    }
                    _write_artifact(result)
                    return result

            logger.info("✓ Verification passed!")

            # Step 5: Commit the merge IN TEMP WORKTREE
            try:
                commit_result = subprocess.run(
                    ["git", "commit", "-m", f"Merge {branch_name}"],
                    cwd=str(temp_worktree_path),
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"✓ Committed merge in temp worktree: {commit_result.stdout.strip()}")
            except subprocess.CalledProcessError as e:
                return {
                    "approved": False,
                    "reason": "Failed to commit merge",
                    "error": str(e),
                    "test_results": test_results,
                    "diff_fingerprint": diff_fingerprint,
                }

            merge_commit_hash = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(temp_worktree_path),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            # Step 6: Update main to verified merge commit.
            current_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if can_update_ref_without_checkout and current_branch not in {detected_main, "HEAD"}:
                subprocess.run(
                    ["git", "update-ref", f"refs/heads/{detected_main}", merge_commit_hash],
                    cwd=self.project_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                # Fast-forward local main to verified merge commit, updating working tree.
                original_ref = current_branch
                try:
                    subprocess.run(
                        ["git", "checkout", detected_main],
                        cwd=self.project_dir,
                        check=True,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["git", "merge", "--ff-only", merge_commit_hash],
                        cwd=self.project_dir,
                        check=True,
                        capture_output=True,
                    )
                finally:
                    # Restore original branch (best-effort).
                    with contextlib.suppress(Exception):
                        if original_ref and original_ref != detected_main:
                            subprocess.run(
                                ["git", "checkout", original_ref],
                                cwd=self.project_dir,
                                check=True,
                                capture_output=True,
                            )

            if push_remote and has_origin:
                try:
                    subprocess.run(
                        ["git", "push", "origin", detected_main],
                        cwd=self.project_dir,
                        check=True,
                        capture_output=True,
                    )
                    logger.info(f"✓ Pushed {detected_main} to origin")
                except subprocess.CalledProcessError as e:
                    return {
                        "approved": False,
                        "reason": f"Merged locally but failed to push origin/{detected_main}",
                        "error": str(e),
                        "test_results": test_results,
                        "merge_commit": merge_commit_hash,
                        "diff_fingerprint": diff_fingerprint,
                    }

            logger.info(f"✅ Gatekeeper: APPROVED '{branch_name}'")
            approved = True

            result = {
                "approved": True,
                "reason": "All tests passed - merged to main",
                "test_results": test_results,
                "verification": verification,
                "review": review,
                "merge_commit": merge_commit_hash,
                "diff_fingerprint": diff_fingerprint,
                "timestamp": datetime.now().isoformat()
            }
            _write_artifact(result)
            return result

        finally:
            # CRITICAL: Always cleanup temp worktree, whether pass or fail!
            if temp_worktree_path and temp_worktree_path.exists():
                try:
                    # Remove the worktree using git worktree remove
                    subprocess.run(
                        ["git", "worktree", "remove", "-f", str(temp_worktree_path)],
                        cwd=self.project_dir,
                        capture_output=True,
                        timeout=30
                    )
                    logger.info(f"✓ Cleaned up temporary worktree: {temp_worktree_path}")

                    # Also try to remove the directory if git worktree remove didn't clean it up
                    if temp_worktree_path.exists():
                        shutil.rmtree(str(temp_worktree_path), ignore_errors=True)

                except Exception as e:
                    logger.warning(f"Failed to cleanup temp worktree: {e}")
                    # Force remove directory as fallback
                    try:
                        shutil.rmtree(str(temp_worktree_path), ignore_errors=True)
                    except:
                        pass

            # Cleanup agent's worktree if provided
            if worktree_path or agent_id:
                if agent_id:
                    try:
                        self.worktree_manager.delete_worktree(agent_id, force=True)
                        logger.info(f"✓ Cleaned up agent worktree for {agent_id}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup agent worktree: {e}")

            # Delete verify branch (best-effort).
            if verify_branch:
                with contextlib.suppress(Exception):
                    subprocess.run(
                        ["git", "branch", "-D", verify_branch],
                        cwd=self.project_dir,
                        capture_output=True,
                    )

            # Delete feature branch only after successful merge (configurable).
            if approved and delete_feature_branch:
                with contextlib.suppress(Exception):
                    subprocess.run(
                        ["git", "branch", "-D", branch_name],
                        cwd=self.project_dir,
                        capture_output=True,
                    )

    def _run_tests(self, timeout: int = 300) -> Dict[str, Any]:
        """
        Run the test suite using the detected framework in project directory.

        Args:
            timeout: Maximum time to wait for tests (seconds)

        Returns:
            Test results dictionary
        """
        return self._run_tests_in_directory(str(self.project_dir), timeout)

    def _run_tests_in_directory(self, directory: str, timeout: int = 300) -> Dict[str, Any]:
        """
        Run the test suite using the detected framework in specified directory.

        Args:
            directory: Path to directory where tests should run
            timeout: Maximum time to wait for tests (seconds)

        Returns:
            Test results dictionary
        """
        try:
            # Get CI-safe test command
            cmd = self.test_detector.get_test_command(ci_mode=True)

            if not cmd:
                return {
                    "success": False,
                    "error": "No test framework detected"
                }

            logger.info(f"Running: {cmd}")

            # Execute tests in specified directory
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Parse output
            output = result.stdout if result.stdout else ""
            errors = result.stderr if result.stderr else ""

            # Determine success
            passed = result.returncode == 0

            return {
                "success": True,
                "passed": passed,
                "exit_code": result.returncode,
                "command": cmd,
                "output": output,
                "errors": errors,
                "summary": self._extract_test_summary(output, errors)
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Tests timed out after {timeout} seconds")
            return {
                "success": False,
                "error": f"Tests timed out after {timeout} seconds",
                "timeout": True
            }
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _extract_test_summary(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Extract test summary from output.

        Tries to parse test counts from common frameworks.
        """
        import re

        combined = stdout + stderr

        summary = {
            "total": None,
            "passed": None,
            "failed": None,
            "skipped": None,
            "duration": None
        }

        # Jest/Vitest pattern
        jest_pattern = r"(\d+)\s+passed,\s*(\d+)\s+failed"
        match = re.search(jest_pattern, combined)
        if match:
            summary["passed"] = int(match.group(1))
            summary["failed"] = int(match.group(2))
            summary["total"] = summary["passed"] + summary["failed"]

        # Pytest pattern
        pytest_pattern = r"(\d+)\s+passed,\s*(\d+)\s+failed"
        match = re.search(pytest_pattern, combined)
        if match:
            summary["passed"] = int(match.group(1))
            summary["failed"] = int(match.group(2))
            summary["total"] = summary["passed"] + summary["failed"]

        # Go test pattern
        go_pattern = r"PASS:\s*(\w+)"
        passed = len(re.findall(go_pattern, combined))
        if passed > 0:
            summary["passed"] = passed
            summary["total"] = passed

        return summary

    def reject_feature(
        self,
        branch_name: str,
        reason: str,
        errors: str
    ) -> Dict[str, Any]:
        """
        Reject a feature branch and clean up.

        Args:
            branch_name: Name of the feature branch
            reason: Why the feature was rejected
            errors: Error output from tests

        Returns:
            Rejection result
        """
        logger.info(f"❌ Gatekeeper: REJECTED '{branch_name}'")
        logger.info(f"   Reason: {reason}")

        # Abort any pending merge
        try:
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=self.project_dir,
                capture_output=True
            )
            logger.info("✓ Aborted pending merge")
        except subprocess.CalledProcessError:
            pass  # No merge in progress

        # Reset to main
        try:
            subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=self.project_dir,
                check=True,
                capture_output=True
            )
            logger.info("✓ Reset to origin/main")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reset: {e}")

        return {
            "approved": False,
            "reason": reason,
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }

    def verify_commands_only(
        self,
        *,
        worktree_path: str | None = None,
        allow_no_tests: bool = False,
        feature_id: int | None = None,
        agent_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        Run deterministic verification commands without merging.

        This is a "preflight" check to catch obvious failures (missing scripts, lint/typecheck)
        before doing a full Gatekeeper temp-worktree merge verification.
        """

        def _write_artifact(result: Dict[str, Any]) -> None:
            try:
                if feature_id is not None:
                    out_dir = self.project_dir / ".autocoder" / "features" / str(int(feature_id)) / "controller"
                else:
                    out_dir = self.project_dir / ".autocoder" / "controller"
                out_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                path = out_dir / f"{stamp}.json"
                path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
                result.setdefault("artifact_path", str(path))
            except Exception:
                return

        def _expand_placeholders(command: str, project_dir: Path) -> str:
            py = sys.executable.replace("\\", "/")
            if os.name == "nt":
                venv_py = (project_dir / ".venv" / "Scripts" / "python.exe").resolve()
            else:
                venv_py = (project_dir / ".venv" / "bin" / "python").resolve()
            venv_py_s = str(venv_py).replace("\\", "/")
            return command.replace("{PY}", py).replace("{VENV_PY}", venv_py_s)

        def _run_shell(command: str, *, cwd: Path, timeout_s: int | None) -> Dict[str, Any]:
            cmd = _expand_placeholders(command, cwd)
            try:
                result = subprocess.run(
                    cmd,
                    cwd=str(cwd),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=int(timeout_s) if timeout_s else None,
                )
                return {
                    "success": True,
                    "passed": result.returncode == 0,
                    "exit_code": result.returncode,
                    "command": cmd,
                    "output": result.stdout or "",
                    "errors": result.stderr or "",
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "passed": False,
                    "exit_code": None,
                    "command": command,
                    "output": "",
                    "errors": f"Timed out after {timeout_s} seconds",
                    "timeout": True,
                }
            except Exception as e:
                return {
                    "success": False,
                    "passed": False,
                    "exit_code": None,
                    "command": command,
                    "output": "",
                    "errors": str(e),
                }

        workdir = Path(worktree_path or self.project_dir).resolve()
        cfg = load_project_config(workdir)
        if cfg.preset is None and not cfg.commands:
            preset = infer_preset(workdir)
            if preset:
                cmds = synthesize_commands_from_preset(preset, workdir)
                cfg = type(cfg)(preset=preset, commands=cmds, review=cfg.review)

        command_specs = cfg.commands or {}
        verification: dict[str, Any] = {}

        if not command_specs:
            result = {
                "approved": False,
                "reason": "No deterministic verification commands configured",
                "verification": verification,
                "timestamp": datetime.now().isoformat(),
                "agent_id": agent_id,
            }
            _write_artifact(result)
            return result

        setup = command_specs.get("setup")
        if setup and setup.command:
            setup_cmd = setup.command
            if setup_cmd.strip() == "npm install":
                selected = Gatekeeper._select_node_install_command(workdir)
                if selected:
                    setup_cmd = selected
            verification["setup"] = _run_shell(setup_cmd, cwd=workdir, timeout_s=setup.timeout_s)
            verification["setup"]["allow_fail"] = bool(getattr(setup, "allow_fail", False))
            if not verification["setup"]["passed"] and not verification["setup"]["allow_fail"]:
                result = {
                    "approved": False,
                    "reason": "Setup failed",
                    "verification": verification,
                    "timestamp": datetime.now().isoformat(),
                    "agent_id": agent_id,
                }
                _write_artifact(result)
                return result

        ordered = ["test", "lint", "typecheck", "format", "build", "acceptance"]
        seen = {"setup"}
        for name in ordered + sorted(k for k in command_specs.keys() if k not in ordered):
            if name in seen:
                continue
            spec = command_specs.get(name)
            if not spec or not getattr(spec, "command", None):
                continue
            seen.add(name)
            verification[name] = _run_shell(spec.command, cwd=workdir, timeout_s=spec.timeout_s)
            verification[name]["allow_fail"] = bool(getattr(spec, "allow_fail", False))
            if name == "test":
                verification[name] = Gatekeeper._apply_allow_no_tests(verification[name], allow_no_tests=allow_no_tests)
            if not verification[name]["success"] and not verification[name]["allow_fail"]:
                result = {
                    "approved": False,
                    "reason": f"Verification command failed: {name}",
                    "verification": verification,
                    "timestamp": datetime.now().isoformat(),
                    "agent_id": agent_id,
                }
                _write_artifact(result)
                return result
            if not verification[name]["passed"] and not verification[name]["allow_fail"]:
                result = {
                    "approved": False,
                    "reason": f"Verification command failed: {name}",
                    "verification": verification,
                    "timestamp": datetime.now().isoformat(),
                    "agent_id": agent_id,
                }
                _write_artifact(result)
                return result

        result = {
            "approved": True,
            "reason": "Preflight verification passed",
            "verification": verification,
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
        }
        _write_artifact(result)
        return result


def main():
    """CLI interface for the Gatekeeper."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Gatekeeper - Verify and merge feature branches"
    )
    parser.add_argument(
        "branch",
        help="Feature branch name (e.g., feat/user-auth-001)"
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Path to project directory (default: current directory)"
    )

    args = parser.parse_args()

    # Initialize gatekeeper
    gatekeeper = Gatekeeper(args.project_dir)

    # Verify and merge
    result = gatekeeper.verify_and_merge(args.branch)

    # Print result
    print("\n" + "=" * 60)
    if result["approved"]:
        print("✅ APPROVED")
        print(f"Reason: {result['reason']}")
        if "test_results" in result:
            summary = result["test_results"].get("summary", {})
            print(f"Tests: {summary.get('passed', '?')} passed")
    else:
        print("❌ REJECTED")
        print(f"Reason: {result['reason']}")
        if "test_results" in result:
            errors = result["test_results"].get("errors", "")
            if errors:
                print(f"\nErrors:\n{errors[:500]}")
    print("=" * 60)

    return 0 if result["approved"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
