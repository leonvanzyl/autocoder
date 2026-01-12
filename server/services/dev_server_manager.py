"""
Dev Server Process Manager
==========================

Manages the lifecycle of dev server subprocesses per project.
Provides start/stop functionality with cross-platform support via psutil.

This is a simplified version of AgentProcessManager, tailored for dev servers:
- No pause/resume (not needed for dev servers)
- URL detection from output (regex for http://localhost:XXXX patterns)
- Simpler status states: stopped, running, crashed
"""

import asyncio
import logging
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Literal, Set

import psutil

from registry import list_registered_projects

logger = logging.getLogger(__name__)

# Patterns for sensitive data that should be redacted from output
SENSITIVE_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',  # Anthropic API keys
    r'ANTHROPIC_API_KEY=[^\s]+',
    r'api[_-]?key[=:][^\s]+',
    r'token[=:][^\s]+',
    r'password[=:][^\s]+',
    r'secret[=:][^\s]+',
    r'ghp_[a-zA-Z0-9]{36,}',  # GitHub personal access tokens
    r'gho_[a-zA-Z0-9]{36,}',  # GitHub OAuth tokens
    r'ghs_[a-zA-Z0-9]{36,}',  # GitHub server tokens
    r'ghr_[a-zA-Z0-9]{36,}',  # GitHub refresh tokens
    r'aws[_-]?access[_-]?key[=:][^\s]+',  # AWS keys
    r'aws[_-]?secret[=:][^\s]+',
]

# Patterns to detect URLs in dev server output
# Matches common patterns like:
#   - http://localhost:3000
#   - http://127.0.0.1:5173
#   - https://localhost:8080/
#   - Local: http://localhost:3000
#   - http://localhost:3000/api/docs
URL_PATTERNS = [
    r'https?://(?:localhost|127\.0\.0\.1):\d+(?:/[^\s]*)?',
    r'https?://\[::1\]:\d+(?:/[^\s]*)?',  # IPv6 localhost
    r'https?://0\.0\.0\.0:\d+(?:/[^\s]*)?',  # Bound to all interfaces
]


def sanitize_output(line: str) -> str:
    """Remove sensitive information from output lines."""
    for pattern in SENSITIVE_PATTERNS:
        line = re.sub(pattern, '[REDACTED]', line, flags=re.IGNORECASE)
    return line


def extract_url(line: str) -> str | None:
    """
    Extract a localhost URL from an output line if present.

    Returns the first URL found, or None if no URL is detected.
    """
    for pattern in URL_PATTERNS:
        match = re.search(pattern, line)
        if match:
            return match.group(0)
    return None


class DevServerProcessManager:
    """
    Manages dev server subprocess lifecycle for a single project.

    Provides start/stop with cross-platform support via psutil.
    Supports multiple output callbacks for WebSocket clients.
    Detects and tracks the server URL from output.
    """

    def __init__(
        self,
        project_name: str,
        project_dir: Path,
    ):
        """
        Initialize the dev server process manager.

        Args:
            project_name: Name of the project
            project_dir: Absolute path to the project directory
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.process: subprocess.Popen | None = None
        self._status: Literal["stopped", "running", "crashed"] = "stopped"
        self.started_at: datetime | None = None
        self._output_task: asyncio.Task | None = None
        self._detected_url: str | None = None
        self._command: str | None = None  # Store the command used to start

        # Support multiple callbacks (for multiple WebSocket clients)
        self._output_callbacks: Set[Callable[[str], Awaitable[None]]] = set()
        self._status_callbacks: Set[Callable[[str], Awaitable[None]]] = set()
        self._callbacks_lock = threading.Lock()

        # Lock file to prevent multiple instances (stored in project directory)
        self.lock_file = self.project_dir / ".devserver.lock"

    @property
    def status(self) -> Literal["stopped", "running", "crashed"]:
        """Current status of the dev server."""
        return self._status

    @status.setter
    def status(self, value: Literal["stopped", "running", "crashed"]):
        old_status = self._status
        self._status = value
        if old_status != value:
            self._notify_status_change(value)

    @property
    def detected_url(self) -> str | None:
        """The URL detected from server output, if any."""
        return self._detected_url

    @property
    def pid(self) -> int | None:
        """Process ID of the running dev server, or None if not running."""
        return self.process.pid if self.process else None

    def _notify_status_change(self, status: str) -> None:
        """Notify all registered callbacks of status change."""
        with self._callbacks_lock:
            callbacks = list(self._status_callbacks)

        for callback in callbacks:
            try:
                # Schedule the callback in the event loop
                loop = asyncio.get_running_loop()
                loop.create_task(self._safe_callback(callback, status))
            except RuntimeError:
                # No running event loop
                pass

    async def _safe_callback(self, callback: Callable, *args) -> None:
        """Safely execute a callback, catching and logging any errors."""
        try:
            await callback(*args)
        except Exception as e:
            logger.warning(f"Callback error: {e}")

    def add_output_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Add a callback for output lines."""
        with self._callbacks_lock:
            self._output_callbacks.add(callback)

    def remove_output_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Remove an output callback."""
        with self._callbacks_lock:
            self._output_callbacks.discard(callback)

    def add_status_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Add a callback for status changes."""
        with self._callbacks_lock:
            self._status_callbacks.add(callback)

    def remove_status_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Remove a status callback."""
        with self._callbacks_lock:
            self._status_callbacks.discard(callback)

    def _check_lock(self) -> bool:
        """
        Check if another dev server is already running for this project.

        Validates that the PID in the lock file belongs to a process running
        in the same project directory to avoid false positives from PID recycling.

        Returns:
            True if we can proceed (no other server running), False otherwise.
        """
        if not self.lock_file.exists():
            return True

        try:
            pid = int(self.lock_file.read_text().strip())
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running():
                        try:
                            # Verify the process is running in our project directory
                            # to avoid false positives from PID recycling
                            proc_cwd = Path(proc.cwd()).resolve()
                            if sys.platform == "win32":
                                # Windows paths are case-insensitive
                                if proc_cwd.as_posix().lower() == self.project_dir.resolve().as_posix().lower():
                                    return False  # Likely our dev server
                            else:
                                if proc_cwd == self.project_dir.resolve():
                                    return False  # Likely our dev server
                        except (psutil.AccessDenied, OSError):
                            # Cannot verify cwd, assume it's our process to be safe
                            return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Stale lock file - process no longer exists or is in different directory
            self.lock_file.unlink(missing_ok=True)
            return True
        except (ValueError, OSError):
            # Invalid lock file content - remove it
            self.lock_file.unlink(missing_ok=True)
            return True

    def _create_lock(self) -> None:
        """Create lock file with current process PID."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        if self.process:
            self.lock_file.write_text(str(self.process.pid))

    def _remove_lock(self) -> None:
        """Remove lock file."""
        self.lock_file.unlink(missing_ok=True)

    async def _broadcast_output(self, line: str) -> None:
        """Broadcast output line to all registered callbacks."""
        with self._callbacks_lock:
            callbacks = list(self._output_callbacks)

        for callback in callbacks:
            await self._safe_callback(callback, line)

    async def _stream_output(self) -> None:
        """Stream process output to callbacks and detect URL."""
        if not self.process or not self.process.stdout:
            return

        try:
            loop = asyncio.get_running_loop()
            while True:
                # Use run_in_executor for blocking readline
                line = await loop.run_in_executor(
                    None, self.process.stdout.readline
                )
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").rstrip()
                sanitized = sanitize_output(decoded)

                # Try to detect URL from output (only if not already detected)
                if not self._detected_url:
                    url = extract_url(decoded)
                    if url:
                        self._detected_url = url
                        logger.info(
                            "Dev server URL detected for %s: %s",
                            self.project_name, url
                        )

                await self._broadcast_output(sanitized)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Output streaming error: {e}")
        finally:
            # Check if process ended
            if self.process and self.process.poll() is not None:
                exit_code = self.process.returncode
                if exit_code != 0 and self.status == "running":
                    self.status = "crashed"
                elif self.status == "running":
                    self.status = "stopped"
                self._remove_lock()

    async def start(self, command: str) -> tuple[bool, str]:
        """
        Start the dev server as a subprocess.

        Args:
            command: The shell command to run (e.g., "npm run dev")

        Returns:
            Tuple of (success, message)
        """
        if self.status == "running":
            return False, "Dev server is already running"

        if not self._check_lock():
            return False, "Another dev server instance is already running for this project"

        # Validate that project directory exists
        if not self.project_dir.exists():
            return False, f"Project directory does not exist: {self.project_dir}"

        self._command = command
        self._detected_url = None  # Reset URL detection

        try:
            # Determine shell based on platform
            if sys.platform == "win32":
                # On Windows, use cmd.exe
                shell_cmd = ["cmd", "/c", command]
            else:
                # On Unix-like systems, use sh
                shell_cmd = ["sh", "-c", command]

            # Start subprocess with piped stdout/stderr
            # stdin=DEVNULL prevents interactive dev servers from blocking on stdin
            # On Windows, use CREATE_NO_WINDOW to prevent console window from flashing
            if sys.platform == "win32":
                self.process = subprocess.Popen(
                    shell_cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(self.project_dir),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                self.process = subprocess.Popen(
                    shell_cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(self.project_dir),
                )

            self._create_lock()
            self.started_at = datetime.now()
            self.status = "running"

            # Start output streaming task
            self._output_task = asyncio.create_task(self._stream_output())

            return True, f"Dev server started with PID {self.process.pid}"
        except Exception as e:
            logger.exception("Failed to start dev server")
            return False, f"Failed to start dev server: {e}"

    async def stop(self) -> tuple[bool, str]:
        """
        Stop the dev server (SIGTERM then SIGKILL if needed).

        Uses psutil to terminate the entire process tree, ensuring
        child processes (like Node.js) are also terminated.

        Returns:
            Tuple of (success, message)
        """
        if not self.process or self.status == "stopped":
            return False, "Dev server is not running"

        try:
            # Cancel output streaming
            if self._output_task:
                self._output_task.cancel()
                try:
                    await self._output_task
                except asyncio.CancelledError:
                    pass

            # Use psutil to terminate the entire process tree
            # This is important for dev servers that spawn child processes
            try:
                parent = psutil.Process(self.process.pid)
                children = parent.children(recursive=True)

                # Terminate children first
                for child in children:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass

                # Terminate parent
                parent.terminate()

                # Wait for graceful shutdown
                _, still_alive = psutil.wait_procs(
                    [parent] + children, timeout=5
                )

                # Force kill any remaining processes
                for proc in still_alive:
                    try:
                        proc.kill()
                    except psutil.NoSuchProcess:
                        pass

            except psutil.NoSuchProcess:
                # Process already gone
                pass

            self._remove_lock()
            self.status = "stopped"
            self.process = None
            self.started_at = None
            self._detected_url = None
            self._command = None

            return True, "Dev server stopped"
        except Exception as e:
            logger.exception("Failed to stop dev server")
            return False, f"Failed to stop dev server: {e}"

    async def healthcheck(self) -> bool:
        """
        Check if the dev server process is still alive.

        Updates status to 'crashed' if process has died unexpectedly.

        Returns:
            True if healthy, False otherwise
        """
        if not self.process:
            return self.status == "stopped"

        poll = self.process.poll()
        if poll is not None:
            # Process has terminated
            if self.status == "running":
                self.status = "crashed"
                self._remove_lock()
            return False

        return True

    def get_status_dict(self) -> dict:
        """Get current status as a dictionary."""
        return {
            "status": self.status,
            "pid": self.pid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "detected_url": self._detected_url,
            "command": self._command,
        }


# Global registry of dev server managers per project with thread safety
_managers: dict[str, DevServerProcessManager] = {}
_managers_lock = threading.Lock()


def get_devserver_manager(project_name: str, project_dir: Path) -> DevServerProcessManager:
    """
    Get or create a dev server process manager for a project (thread-safe).

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory

    Returns:
        DevServerProcessManager instance for the project
    """
    with _managers_lock:
        if project_name in _managers:
            manager = _managers[project_name]
            # Update project_dir in case project was moved
            if manager.project_dir.resolve() != project_dir.resolve():
                logger.info(
                    f"Project {project_name} path updated: {manager.project_dir} -> {project_dir}"
                )
                manager.project_dir = project_dir
                manager.lock_file = project_dir / ".devserver.lock"
            return manager
        _managers[project_name] = DevServerProcessManager(project_name, project_dir)
        return _managers[project_name]


async def cleanup_all_devservers() -> None:
    """Stop all running dev servers. Called on server shutdown."""
    with _managers_lock:
        managers = list(_managers.values())

    for manager in managers:
        try:
            if manager.status != "stopped":
                await manager.stop()
        except Exception as e:
            logger.warning(f"Error stopping dev server for {manager.project_name}: {e}")

    with _managers_lock:
        _managers.clear()


def cleanup_orphaned_devserver_locks() -> int:
    """
    Clean up orphaned dev server lock files from previous server runs.

    Scans all registered projects for .devserver.lock files and removes them
    if the referenced process is no longer running.

    Returns:
        Number of orphaned lock files cleaned up
    """
    cleaned = 0
    try:
        projects = list_registered_projects()
        for name, info in projects.items():
            project_path = Path(info.get("path", ""))
            if not project_path.exists():
                continue

            lock_file = project_path / ".devserver.lock"
            if not lock_file.exists():
                continue

            try:
                pid_str = lock_file.read_text().strip()
                pid = int(pid_str)

                # Check if process is still running
                if psutil.pid_exists(pid):
                    try:
                        proc = psutil.Process(pid)
                        if proc.is_running():
                            # Process is still running, don't remove
                            logger.info(
                                "Found running dev server for project '%s' (PID %d)",
                                name, pid
                            )
                            continue
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # Process not running - remove stale lock
                lock_file.unlink(missing_ok=True)
                cleaned += 1
                logger.info("Removed orphaned dev server lock file for project '%s'", name)

            except (ValueError, OSError) as e:
                # Invalid lock file content - remove it
                logger.warning(
                    "Removing invalid dev server lock file for project '%s': %s", name, e
                )
                lock_file.unlink(missing_ok=True)
                cleaned += 1

    except Exception as e:
        logger.error("Error during dev server orphan cleanup: %s", e)

    if cleaned:
        logger.info("Cleaned up %d orphaned dev server lock file(s)", cleaned)

    return cleaned
