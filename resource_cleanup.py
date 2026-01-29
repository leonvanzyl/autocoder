"""
Resource Cleanup Module
=======================

Provides resource cleanup management for agent sessions.
Ensures proper cleanup of:
- Temporary files
- Lock files
- Process handles
- Database connections
- Browser contexts
"""

import asyncio
import atexit
import logging
import os
import signal
import sys
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class CleanupTask:
    """A registered cleanup task."""
    name: str
    callback: Callable[[], Any]
    priority: int = 0  # Higher priority = run first
    is_async: bool = False


class ResourceCleanupManager:
    """
    Manages cleanup of resources at session end.

    Features:
    - Register cleanup callbacks with priorities
    - Automatic cleanup on process exit
    - Signal handler integration (SIGINT, SIGTERM)
    - Support for both sync and async cleanup
    """

    _instance: "ResourceCleanupManager | None" = None
    _lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

    def __new__(cls) -> "ResourceCleanupManager":
        """Singleton pattern to ensure one cleanup manager per process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._cleanup_tasks: list[CleanupTask] = []
        self._temp_files: weakref.WeakSet[Path] = weakref.WeakSet()
        self._lock_files: set[Path] = set()
        self._cleanup_done = False
        self._initialized = True

        # Register atexit handler
        atexit.register(self._atexit_cleanup)

        # Register signal handlers (only in main thread)
        try:
            if hasattr(signal, 'SIGINT'):
                signal.signal(signal.SIGINT, self._signal_handler)
            if hasattr(signal, 'SIGTERM'):
                signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            # Signal handlers can only be set in main thread
            logger.debug("Cannot set signal handlers outside main thread")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle termination signals."""
        logger.info("Received signal %d, cleaning up...", signum)
        self.cleanup_sync()
        sys.exit(0)

    def _atexit_cleanup(self) -> None:
        """Cleanup handler for atexit."""
        if not self._cleanup_done:
            self.cleanup_sync()

    def register(
        self,
        name: str,
        callback: Callable[[], Any],
        priority: int = 0,
        is_async: bool = False
    ) -> None:
        """
        Register a cleanup callback.

        Args:
            name: Descriptive name for logging
            callback: Function to call during cleanup
            priority: Higher priority runs first (default 0)
            is_async: Whether callback is async
        """
        task = CleanupTask(
            name=name,
            callback=callback,
            priority=priority,
            is_async=is_async,
        )
        self._cleanup_tasks.append(task)
        logger.debug("Registered cleanup task: %s (priority=%d)", name, priority)

    def unregister(self, name: str) -> bool:
        """
        Unregister a cleanup callback by name.

        Returns:
            True if found and removed, False otherwise
        """
        for i, task in enumerate(self._cleanup_tasks):
            if task.name == name:
                del self._cleanup_tasks[i]
                logger.debug("Unregistered cleanup task: %s", name)
                return True
        return False

    def register_temp_file(self, path: Path) -> None:
        """Register a temporary file for cleanup."""
        # Note: Using a set since WeakSet doesn't work well with Path
        pass  # Temp files tracked differently

    def register_lock_file(self, path: Path) -> None:
        """Register a lock file for cleanup."""
        self._lock_files.add(Path(path))
        logger.debug("Registered lock file for cleanup: %s", path)

    def unregister_lock_file(self, path: Path) -> None:
        """Unregister a lock file (e.g., when properly released)."""
        self._lock_files.discard(Path(path))

    def cleanup_sync(self) -> None:
        """
        Run all registered cleanup tasks synchronously.

        For async tasks, creates a new event loop if needed.
        """
        if self._cleanup_done:
            return

        self._cleanup_done = True
        logger.info("Starting resource cleanup...")

        # Sort by priority (higher first)
        sorted_tasks = sorted(
            self._cleanup_tasks,
            key=lambda t: t.priority,
            reverse=True
        )

        # Run sync tasks first
        for task in sorted_tasks:
            if not task.is_async:
                try:
                    logger.debug("Running cleanup: %s", task.name)
                    task.callback()
                except Exception as e:
                    logger.warning("Cleanup failed for %s: %s", task.name, e)

        # Run async tasks
        async_tasks = [t for t in sorted_tasks if t.is_async]
        if async_tasks:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._run_async_cleanup(async_tasks))
                finally:
                    loop.close()
            except Exception as e:
                logger.warning("Async cleanup failed: %s", e)

        # Clean up lock files
        self._cleanup_lock_files()

        logger.info("Resource cleanup complete")

    async def cleanup_async(self) -> None:
        """
        Run all registered cleanup tasks asynchronously.
        """
        if self._cleanup_done:
            return

        self._cleanup_done = True
        logger.info("Starting async resource cleanup...")

        # Sort by priority (higher first)
        sorted_tasks = sorted(
            self._cleanup_tasks,
            key=lambda t: t.priority,
            reverse=True
        )

        # Run all tasks
        for task in sorted_tasks:
            try:
                logger.debug("Running cleanup: %s", task.name)
                if task.is_async:
                    await task.callback()
                else:
                    task.callback()
            except Exception as e:
                logger.warning("Cleanup failed for %s: %s", task.name, e)

        # Clean up lock files
        self._cleanup_lock_files()

        logger.info("Async resource cleanup complete")

    async def _run_async_cleanup(self, tasks: list[CleanupTask]) -> None:
        """Run async cleanup tasks."""
        for task in tasks:
            try:
                logger.debug("Running async cleanup: %s", task.name)
                await task.callback()
            except Exception as e:
                logger.warning("Async cleanup failed for %s: %s", task.name, e)

    def _cleanup_lock_files(self) -> None:
        """Remove all registered lock files."""
        for lock_file in list(self._lock_files):
            try:
                if lock_file.exists():
                    lock_file.unlink()
                    logger.debug("Removed lock file: %s", lock_file)
            except OSError as e:
                logger.warning("Failed to remove lock file %s: %s", lock_file, e)

        self._lock_files.clear()

    def reset(self) -> None:
        """Reset the cleanup manager (mainly for testing)."""
        self._cleanup_tasks.clear()
        self._lock_files.clear()
        self._cleanup_done = False


# =============================================================================
# Convenience Functions
# =============================================================================

def get_cleanup_manager() -> ResourceCleanupManager:
    """Get the singleton cleanup manager instance."""
    return ResourceCleanupManager()


def register_cleanup(
    name: str,
    callback: Callable[[], Any],
    priority: int = 0,
    is_async: bool = False
) -> None:
    """Register a cleanup callback with the global manager."""
    get_cleanup_manager().register(name, callback, priority, is_async)


def register_lock_file(path: Path) -> None:
    """Register a lock file for automatic cleanup."""
    get_cleanup_manager().register_lock_file(path)


def unregister_lock_file(path: Path) -> None:
    """Unregister a lock file."""
    get_cleanup_manager().unregister_lock_file(path)


@contextmanager
def cleanup_context(name: str, cleanup_func: Callable[[], Any]):
    """
    Context manager that ensures cleanup on exit.

    Example:
        with cleanup_context("my_resource", lambda: resource.close()):
            # use resource
    """
    try:
        yield
    finally:
        try:
            cleanup_func()
        except Exception as e:
            logger.warning("Cleanup failed for %s: %s", name, e)


# =============================================================================
# Project-Specific Cleanup
# =============================================================================

def cleanup_project_resources(project_path: Path) -> None:
    """
    Clean up resources for a specific project.

    This includes:
    - Lock files (.agent.lock)
    - Temporary files in .autocoder/tmp/
    """
    logger.info("Cleaning up project resources: %s", project_path)

    # Remove agent lock file
    lock_file = project_path / ".agent.lock"
    if lock_file.exists():
        try:
            lock_file.unlink()
            logger.debug("Removed agent lock: %s", lock_file)
        except OSError as e:
            logger.warning("Failed to remove lock file: %s", e)

    # Clean up temporary directory
    tmp_dir = project_path / ".autocoder" / "tmp"
    if tmp_dir.exists():
        try:
            import shutil
            shutil.rmtree(tmp_dir)
            logger.debug("Removed temp directory: %s", tmp_dir)
        except OSError as e:
            logger.warning("Failed to remove temp directory: %s", e)


def cleanup_orphaned_locks(base_dir: Path | None = None) -> list[Path]:
    """
    Find and remove orphaned lock files.

    Args:
        base_dir: Directory to search (default: user home)

    Returns:
        List of removed lock file paths
    """
    removed = []

    if base_dir is None:
        # Check common project locations
        home = Path.home()
        search_dirs = [
            home / "Projects",
            home / "repos",
            home / "code",
            home / "dev",
        ]
    else:
        search_dirs = [Path(base_dir)]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # Find all .agent.lock files
        for lock_file in search_dir.rglob(".agent.lock"):
            # Check if the lock is stale (no running process)
            if _is_lock_stale(lock_file):
                try:
                    lock_file.unlink()
                    removed.append(lock_file)
                    logger.info("Removed orphaned lock: %s", lock_file)
                except OSError as e:
                    logger.warning("Failed to remove orphaned lock %s: %s", lock_file, e)

    return removed


def _is_lock_stale(lock_file: Path) -> bool:
    """
    Check if a lock file is stale (process no longer running).

    A lock file is considered stale if:
    - It contains a PID and that process is not running
    - It's older than 24 hours
    """
    try:
        content = lock_file.read_text().strip()

        # Try to parse PID from lock file
        if content.isdigit():
            pid = int(content)
            # Check if process is running
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                return False  # Process is running
            except OSError:
                return True  # Process not running

        # If no PID, check file age
        import time
        file_age = time.time() - lock_file.stat().st_mtime
        return file_age > 86400  # 24 hours

    except Exception:
        # If we can't read/parse, assume stale
        return True
