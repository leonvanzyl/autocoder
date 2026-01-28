"""
Resource Cleanup Manager
========================

Handles cleanup of resources spawned during agent sessions:
- Browser/Chromium processes left open by Playwright MCP
- Dev server processes (node, vite, next) that linger between sessions
- Temporary test files (screenshots, test artifacts)

Runs between agent sessions as a safety net, catching anything
the agent's own cleanup instructions missed.
"""

import glob
import logging
import os
import signal
import time
from pathlib import Path
from typing import Optional

import psutil

logger = logging.getLogger(__name__)

# Process names that should be cleaned up between sessions
# These are processes the agent starts for testing but may not stop
BROWSER_PROCESS_NAMES = {
    "chromium",
    "chromium-browser",
    "chrome",
    "google-chrome",
    "firefox",
    "geckodriver",
    "chromedriver",
}

DEV_SERVER_PROCESS_NAMES = {
    "node",
    "npm",
    "npx",
    "vite",
    "next",
}

# File patterns for test artifacts that should be cleaned up
# Paths are relative to the project directory
TEST_ARTIFACT_PATTERNS = [
    "screenshots/**/*.png",
    "screenshots/**/*.jpg",
    "test-results/**/*",
    "playwright-report/**/*",
    ".tmp/**/*",
    "*.tmp",
    "coverage/**/*",
    "verification/**/*.png",
    "verification/**/*.jpg",
]

# Max age (in seconds) for test artifacts before cleanup
# Only delete files older than this to avoid removing in-use files
TEST_ARTIFACT_MAX_AGE_SECONDS = 300  # 5 minutes


class ResourceCleanupManager:
    """
    Manages cleanup of resources between agent sessions.

    Tracks processes spawned during a session and cleans up
    orphaned processes, browser tabs, and temp files.
    """

    def __init__(self, project_dir: Path):
        """
        Initialize the cleanup manager.

        Args:
            project_dir: Path to the project directory
        """
        self.project_dir = project_dir.resolve()
        self._pre_session_pids: set[int] = set()
        self._session_active = False

    def snapshot_processes(self) -> None:
        """
        Take a snapshot of currently running processes before a session starts.

        This allows us to identify which processes were spawned during the
        session by comparing against this baseline.
        """
        self._pre_session_pids = set()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                self._pre_session_pids.add(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self._session_active = True
        logger.info(
            f"Process snapshot taken: {len(self._pre_session_pids)} processes tracked"
        )

    def cleanup_between_sessions(self) -> dict:
        """
        Run cleanup between agent sessions.

        This is the main cleanup entry point, called after each session
        exits the async context manager.

        Returns:
            Dict with cleanup results summary
        """
        results = {
            "browsers_killed": 0,
            "dev_servers_killed": 0,
            "files_cleaned": 0,
            "errors": [],
        }

        # 1. Kill orphaned browser processes
        browser_count = self._cleanup_browser_processes()
        results["browsers_killed"] = browser_count

        # 2. Kill dev server processes spawned during this session
        server_count = self._cleanup_dev_servers()
        results["dev_servers_killed"] = server_count

        # 3. Clean up test artifact files
        file_count = self._cleanup_test_artifacts()
        results["files_cleaned"] = file_count

        self._session_active = False

        total = browser_count + server_count + file_count
        if total > 0:
            logger.info(
                f"Session cleanup: killed {browser_count} browser(s), "
                f"{server_count} dev server(s), removed {file_count} temp file(s)"
            )
        else:
            logger.debug("Session cleanup: nothing to clean up")

        return results

    def _cleanup_browser_processes(self) -> int:
        """
        Kill browser processes that were spawned during the session.

        The Playwright MCP server launches Chromium instances for browser
        testing. When the MCP server exits, these should be cleaned up
        automatically, but sometimes orphaned instances remain.

        Returns:
            Number of processes killed
        """
        killed = 0

        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            try:
                pinfo = proc.info
                pname = (pinfo["name"] or "").lower()

                # Check if this is a browser process
                is_browser = any(
                    browser_name in pname for browser_name in BROWSER_PROCESS_NAMES
                )

                if not is_browser:
                    # Also check command line for headless browser flags
                    cmdline = " ".join(pinfo.get("cmdline") or []).lower()
                    is_browser = (
                        "--headless" in cmdline and "chrom" in cmdline
                    ) or ("playwright" in cmdline and "browser" in cmdline)

                if not is_browser:
                    continue

                # Only kill processes spawned during our session
                if pinfo["pid"] in self._pre_session_pids:
                    continue

                # Check if the process is related to the project directory
                # by inspecting its working directory or command line
                if self._is_related_to_project(proc):
                    self._safe_kill(proc)
                    killed += 1
                    logger.info(
                        f"Killed orphaned browser process: {pname} (PID {pinfo['pid']})"
                    )

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return killed

    def _cleanup_dev_servers(self) -> int:
        """
        Kill dev server processes spawned during this session.

        Dev servers (npm run dev, vite, next dev) are started by the agent
        for testing but should be stopped between sessions to free ports
        and resources.

        Returns:
            Number of processes killed
        """
        killed = 0

        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            try:
                pinfo = proc.info
                pid = pinfo["pid"]

                # Skip processes that existed before the session
                if pid in self._pre_session_pids:
                    continue

                pname = (pinfo["name"] or "").lower()
                cmdline = " ".join(pinfo.get("cmdline") or []).lower()

                # Check if this is a dev server process
                is_dev_server = False

                if pname in DEV_SERVER_PROCESS_NAMES:
                    # Check if it's actually a dev server (not just any node process)
                    dev_indicators = [
                        "run dev",
                        "run start",
                        "vite",
                        "next dev",
                        "next start",
                        "webpack-dev-server",
                        "react-scripts start",
                        "nodemon",
                        "ts-node",
                    ]
                    is_dev_server = any(
                        indicator in cmdline for indicator in dev_indicators
                    )

                if not is_dev_server:
                    continue

                # Check if related to our project
                if self._is_related_to_project(proc):
                    self._safe_kill(proc)
                    killed += 1
                    logger.info(
                        f"Killed dev server process: {pname} (PID {pid})"
                    )

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return killed

    def _cleanup_test_artifacts(self) -> int:
        """
        Remove temporary test files (screenshots, reports, etc.).

        Only removes files older than TEST_ARTIFACT_MAX_AGE_SECONDS to avoid
        deleting files that are still in use.

        Returns:
            Number of files removed
        """
        removed = 0
        now = time.time()

        for pattern in TEST_ARTIFACT_PATTERNS:
            full_pattern = str(self.project_dir / pattern)
            for filepath in glob.glob(full_pattern, recursive=True):
                try:
                    fpath = Path(filepath)
                    if not fpath.is_file():
                        continue

                    # Only remove files older than the threshold
                    file_age = now - fpath.stat().st_mtime
                    if file_age < TEST_ARTIFACT_MAX_AGE_SECONDS:
                        continue

                    fpath.unlink()
                    removed += 1
                    logger.debug(f"Removed test artifact: {filepath}")

                except (OSError, PermissionError) as e:
                    logger.debug(f"Could not remove {filepath}: {e}")

        # Clean up empty directories left behind
        for pattern in TEST_ARTIFACT_PATTERNS:
            dir_pattern = pattern.split("/")[0]
            dir_path = self.project_dir / dir_pattern
            if dir_path.is_dir():
                self._remove_empty_dirs(dir_path)

        return removed

    def _is_related_to_project(self, proc: psutil.Process) -> bool:
        """
        Check if a process is related to our project directory.

        Examines the process's working directory and command line arguments
        to determine if it was spawned from our project.

        Args:
            proc: psutil Process object

        Returns:
            True if the process is related to our project
        """
        try:
            # Check working directory
            cwd = proc.cwd()
            if str(self.project_dir) in cwd:
                return True

            # Check command line arguments for project path
            cmdline = proc.cmdline()
            project_str = str(self.project_dir)
            for arg in cmdline:
                if project_str in arg:
                    return True

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

        return False

    def _safe_kill(self, proc: psutil.Process, timeout: float = 3.0) -> bool:
        """
        Safely terminate a process, escalating to SIGKILL if needed.

        Args:
            proc: psutil Process object
            timeout: Seconds to wait for graceful termination

        Returns:
            True if the process was successfully killed
        """
        try:
            pid = proc.pid
            name = proc.name()

            # First try SIGTERM for graceful shutdown
            proc.terminate()

            try:
                proc.wait(timeout=timeout)
                return True
            except psutil.TimeoutExpired:
                # Escalate to SIGKILL
                logger.warning(
                    f"Process {name} (PID {pid}) did not terminate gracefully, "
                    f"sending SIGKILL"
                )
                proc.kill()
                proc.wait(timeout=2.0)
                return True

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"Could not kill process: {e}")
            return False

    def _remove_empty_dirs(self, dir_path: Path) -> None:
        """
        Recursively remove empty directories.

        Args:
            dir_path: Directory to check and potentially remove
        """
        if not dir_path.is_dir():
            return

        # Process children first (bottom-up)
        for child in dir_path.iterdir():
            if child.is_dir():
                self._remove_empty_dirs(child)

        # Remove if empty (no files or subdirs left)
        try:
            if not any(dir_path.iterdir()):
                dir_path.rmdir()
                logger.debug(f"Removed empty directory: {dir_path}")
        except OSError:
            pass


def cleanup_project_resources(project_dir: Path) -> dict:
    """
    One-shot cleanup of all resources for a project.

    Convenience function for use outside the session loop.

    Args:
        project_dir: Path to the project directory

    Returns:
        Cleanup results summary dict
    """
    manager = ResourceCleanupManager(project_dir)
    # Take a snapshot with no pre-existing PIDs so we clean everything
    manager._pre_session_pids = set()
    manager._session_active = True
    return manager.cleanup_between_sessions()


def kill_project_child_processes(project_dir: Path) -> int:
    """
    Kill all child processes related to a project directory.

    Used by the process manager when stopping an agent to ensure
    no orphaned processes remain (browsers, dev servers, etc.).

    Args:
        project_dir: Path to the project directory

    Returns:
        Number of processes killed
    """
    project_dir = project_dir.resolve()
    killed = 0
    target_names = BROWSER_PROCESS_NAMES | DEV_SERVER_PROCESS_NAMES

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            pinfo = proc.info
            pname = (pinfo["name"] or "").lower()

            # Check if this is a target process type
            is_target = any(name in pname for name in target_names)
            if not is_target:
                continue

            # Check if related to our project
            try:
                cwd = proc.cwd()
                if str(project_dir) not in cwd:
                    # Also check command line
                    cmdline = proc.cmdline()
                    project_str = str(project_dir)
                    if not any(project_str in arg for arg in cmdline):
                        continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            # Kill the process
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except psutil.TimeoutExpired:
                    proc.kill()
                killed += 1
                logger.info(f"Killed child process: {pname} (PID {pinfo['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return killed
