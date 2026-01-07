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
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify a feature branch and merge to main if tests pass.

        Uses a TEMPORARY WORKTREE for verification to avoid dirty state in main directory.

        Workflow:
        1. Fetch latest main
        2. Create temporary worktree for verification
        3. In temp worktree: checkout main, merge feature branch, run tests
        4. If tests pass: commit merge in temp worktree, push to origin/main, delete temp worktree
        5. If tests fail: just delete temp worktree (main directory untouched!)

        Args:
            branch_name: Name of the feature branch (e.g., "feat/user-auth-001")
            worktree_path: Optional path to agent's worktree
            agent_id: Optional agent identifier for logging

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
        import tempfile
        import shutil

        temp_worktree_path = None

        try:
            # Step 1: Fetch latest main
            try:
                subprocess.run(
                    ["git", "fetch", "origin", "main"],
                    cwd=self.project_dir,
                    check=True,
                    capture_output=True
                )
                logger.info("✓ Fetched latest main")
            except subprocess.CalledProcessError as e:
                return {
                    "approved": False,
                    "reason": "Failed to fetch main branch",
                    "error": str(e)
                }

            # Step 2: Create temporary worktree for verification
            temp_worktree_path = self.project_dir / f"verify_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            try:
                # Create temp worktree on main branch
                subprocess.run(
                    ["git", "worktree", "add", "-b", f"verify_{branch_name}", str(temp_worktree_path), "origin/main"],
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
                return {
                    "approved": False,
                    "reason": "Test execution failed",
                    "test_results": test_results
                }

            if not test_results["passed"]:
                logger.error(f"✗ Tests failed:\n{test_results['errors']}")
                return {
                    "approved": False,
                    "reason": "Tests failed - fix and resubmit",
                    "test_results": test_results
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

            # Step 6: Push to main FROM TEMP WORKTREE
            try:
                push_result = subprocess.run(
                    ["git", "push", "origin", f"verify_{branch_name}:main"],
                    cwd=str(temp_worktree_path),
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info("✓ Pushed to origin/main")
            except subprocess.CalledProcessError as e:
                return {
                    "approved": False,
                    "reason": "Failed to push to main",
                    "error": str(e),
                    "test_results": test_results,
                    "merge_commit": "committed but not pushed"
                }

            logger.info(f"✅ Gatekeeper: APPROVED '{branch_name}'")

            return {
                "approved": True,
                "reason": "All tests passed - merged to main",
                "test_results": test_results,
                "merge_commit": "committed and pushed",
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

            # Step 7: Delete feature branch (only after successful merge)
            if temp_worktree_path and (branch_name):
                try:
                    subprocess.run(
                        ["git", "branch", "-D", branch_name],
                        cwd=self.project_dir,
                        capture_output=True
                    )
                    logger.info(f"✓ Deleted feature branch '{branch_name}'")
                except subprocess.CalledProcessError:
                    logger.warning(f"Could not delete branch '{branch_name}'")

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
