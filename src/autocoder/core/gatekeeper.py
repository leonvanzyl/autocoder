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
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Direct imports (system code = fast!)
from .test_framework_detector import TestFrameworkDetector
from .worktree_manager import WorktreeManager

logger = logging.getLogger(__name__)


class Gatekeeper:
    """
    Gatekeeper verifies feature branches before merging to main.

    Only the Gatekeeper can write to the main branch. This ensures
    quality and prevents broken code from being merged.
    """

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

        # Import for temp worktree management
        import shutil

        temp_worktree_path = None
        verify_branch = None
        approved = False
        test_results: Dict[str, Any] | None = None

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

        try:
            detected_main = detect_main_branch()
            has_origin = origin_exists()

            # Refuse to operate if main working tree is dirty (we need to checkout/ff main).
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if dirty:
                return {
                    "approved": False,
                    "reason": "Main working tree is dirty; refusing to merge",
                    "details": dirty,
                }

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
            logger.info("🧪 Running tests in temporary worktree...")
            test_results = self._run_tests_in_directory(str(temp_worktree_path))

            if not test_results["success"]:
                # Optionally allow merges when no tests are detected (configurable).
                if allow_no_tests and "No test framework detected" in str(test_results.get("error", "")):
                    test_results["passed"] = True
                    test_results["note"] = "No tests detected; allowed by configuration"
                else:
                    return {
                        "approved": False,
                        "reason": "Test execution failed",
                        "test_results": test_results,
                    }

            if not test_results["passed"]:
                if allow_no_tests:
                    exit_code = test_results.get("exit_code")
                    command = str(test_results.get("command", "")).lower()
                    combined = (
                        str(test_results.get("output", "")) + str(test_results.get("errors", ""))
                    ).lower()
                    # Pytest exit code 5 commonly means "no tests collected".
                    if ("pytest" in command and exit_code == 5) or ("collected 0 items" in combined):
                        test_results["passed"] = True
                        test_results["note"] = "No tests collected; allowed by configuration"

                if not test_results["passed"]:
                    logger.error(f"✗ Tests failed:\n{test_results.get('errors', '')}")
                    return {
                        "approved": False,
                        "reason": "Tests failed - fix and resubmit",
                        "test_results": test_results,
                    }

            logger.info("✓ All tests passed!")

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
                    "test_results": test_results
                }

            merge_commit_hash = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(temp_worktree_path),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            # Step 6: Fast-forward local main to verified merge commit.
            original_ref = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
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
                    }

            logger.info(f"✅ Gatekeeper: APPROVED '{branch_name}'")
            approved = True

            return {
                "approved": True,
                "reason": "All tests passed - merged to main",
                "test_results": test_results,
                "merge_commit": merge_commit_hash,
                "timestamp": datetime.now().isoformat()
            }

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
