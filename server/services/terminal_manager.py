"""
Terminal Manager
================

Manages PTY terminal sessions per project with cross-platform support.
Uses winpty (ConPTY) on Windows and built-in pty module on Unix.
"""

import asyncio
import logging
import os
import platform
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Set

logger = logging.getLogger(__name__)


@dataclass
class TerminalInfo:
    """Metadata for a terminal instance."""

    id: str
    name: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# Platform detection
IS_WINDOWS = platform.system() == "Windows"

# Conditional imports for PTY support
# Note: Type checking is disabled for cross-platform PTY modules since mypy
# cannot properly handle conditional imports for platform-specific APIs.
if IS_WINDOWS:
    try:
        from winpty import PtyProcess as WinPtyProcess

        WINPTY_AVAILABLE = True
    except ImportError:
        WinPtyProcess = None
        WINPTY_AVAILABLE = False
        logger.warning(
            "winpty package not installed. Terminal sessions will not be available on Windows. "
            "Install with: pip install pywinpty"
        )
else:
    # Unix systems use built-in pty module
    import fcntl
    import pty
    import select
    import signal
    import struct
    import termios

    WINPTY_AVAILABLE = False  # Not applicable on Unix


def _get_shell() -> str:
    """
    Get the appropriate shell for the current platform.

    Returns:
        Path to shell executable
    """
    if IS_WINDOWS:
        # Prefer PowerShell, fall back to cmd.exe
        powershell = shutil.which("powershell.exe")
        if powershell:
            return powershell
        cmd = shutil.which("cmd.exe")
        if cmd:
            return cmd
        # Last resort fallback
        return "cmd.exe"
    else:
        # Unix: Use $SHELL environment variable or fall back to /bin/bash
        shell = os.environ.get("SHELL")
        if shell and shutil.which(shell):
            return shell
        # Fall back to common shells
        for fallback in ["/bin/bash", "/bin/sh"]:
            if os.path.exists(fallback):
                return fallback
        return "/bin/sh"


class TerminalSession:
    """
    Manages a single PTY terminal session for a project.

    Provides cross-platform PTY support with async output streaming
    and multiple output callbacks for WebSocket clients.
    """

    def __init__(self, project_name: str, project_dir: Path):
        """
        Initialize the terminal session.

        Args:
            project_name: Name of the project
            project_dir: Absolute path to the project directory (used as cwd)
        """
        self.project_name = project_name
        self.project_dir = project_dir

        # PTY process references (platform-specific)
        self._pty_process: "WinPtyProcess | None" = None  # Windows winpty
        self._master_fd: int | None = None  # Unix master file descriptor
        self._child_pid: int | None = None  # Unix child process PID

        # State tracking
        self._is_active = False
        self._output_task: asyncio.Task | None = None

        # Output callbacks with thread-safe access
        self._output_callbacks: Set[Callable[[bytes], None]] = set()
        self._callbacks_lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        """Check if the terminal session is currently active."""
        return self._is_active

    @property
    def pid(self) -> int | None:
        """Get the PID of the PTY child process."""
        if IS_WINDOWS:
            if self._pty_process is not None:
                try:
                    pid = self._pty_process.pid
                    return int(pid) if pid is not None else None
                except Exception:
                    return None
            return None
        else:
            return self._child_pid

    def add_output_callback(self, callback: Callable[[bytes], None]) -> None:
        """
        Add a callback to receive terminal output.

        Args:
            callback: Function that receives raw bytes from the PTY
        """
        with self._callbacks_lock:
            self._output_callbacks.add(callback)

    def remove_output_callback(self, callback: Callable[[bytes], None]) -> None:
        """
        Remove an output callback.

        Args:
            callback: The callback to remove
        """
        with self._callbacks_lock:
            self._output_callbacks.discard(callback)

    def _broadcast_output(self, data: bytes) -> None:
        """Broadcast output data to all registered callbacks."""
        with self._callbacks_lock:
            callbacks = list(self._output_callbacks)

        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.warning(f"Output callback error: {e}")

    async def start(self, cols: int = 80, rows: int = 24) -> bool:
        """
        Start the PTY terminal session.

        Args:
            cols: Terminal width in columns
            rows: Terminal height in rows

        Returns:
            True if started successfully, False otherwise
        """
        if self._is_active:
            logger.warning(f"Terminal session already active for {self.project_name}")
            return False

        # Validate project directory
        if not self.project_dir.exists():
            logger.error(f"Project directory does not exist: {self.project_dir}")
            return False
        if not self.project_dir.is_dir():
            logger.error(f"Project path is not a directory: {self.project_dir}")
            return False

        shell = _get_shell()
        cwd = str(self.project_dir.resolve())

        try:
            if IS_WINDOWS:
                return await self._start_windows(shell, cwd, cols, rows)
            else:
                return await self._start_unix(shell, cwd, cols, rows)
        except Exception as e:
            logger.exception(f"Failed to start terminal for {self.project_name}: {e}")
            return False

    async def _start_windows(self, shell: str, cwd: str, cols: int, rows: int) -> bool:
        """Start PTY on Windows using winpty."""
        if not WINPTY_AVAILABLE:
            logger.error("Cannot start terminal: winpty package not available")
            # This error will be caught and sent to the client
            raise RuntimeError(
                "Terminal requires pywinpty on Windows. Install with: pip install pywinpty"
            )

        try:
            # WinPtyProcess.spawn expects the shell command
            self._pty_process = WinPtyProcess.spawn(
                shell,
                cwd=cwd,
                dimensions=(rows, cols),
            )
            self._is_active = True

            # Start output reading task
            self._output_task = asyncio.create_task(self._read_output_windows())

            logger.info(f"Terminal started for {self.project_name} (PID: {self.pid}, shell: {shell})")
            return True

        except Exception as e:
            logger.exception(f"Failed to start Windows PTY: {e}")
            self._pty_process = None
            return False

    async def _start_unix(self, shell: str, cwd: str, cols: int, rows: int) -> bool:
        """Start PTY on Unix using built-in pty module."""
        # Note: This entire method uses Unix-specific APIs that don't exist on Windows.
        # Type checking is disabled for these platform-specific calls.
        try:
            # Fork a new pseudo-terminal
            pid, master_fd = pty.fork()  # type: ignore[attr-defined]

            if pid == 0:
                # Child process - exec the shell
                os.chdir(cwd)
                # Set terminal size (Unix-specific modules imported at top-level)
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(0, termios.TIOCSWINSZ, winsize)  # type: ignore[attr-defined]

                # Execute the shell
                os.execvp(shell, [shell])
                os._exit(1)  # Fallback if execvp returns (shouldn't happen)
            else:
                # Parent process
                self._master_fd = master_fd
                self._child_pid = pid
                self._is_active = True

                # Set terminal size on master (Unix-specific modules imported at top-level)
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)  # type: ignore[attr-defined]

                # Start output reading task
                self._output_task = asyncio.create_task(self._read_output_unix())

                logger.info(f"Terminal started for {self.project_name} (PID: {pid}, shell: {shell})")
                return True

        except Exception as e:
            logger.exception(f"Failed to start Unix PTY: {e}")
            self._master_fd = None
            self._child_pid = None
            return False

    async def _read_output_windows(self) -> None:
        """Read output from Windows PTY and broadcast to callbacks."""
        pty = self._pty_process
        if pty is None:
            return

        loop = asyncio.get_running_loop()

        def read_data():
            """Read data from PTY, capturing pty reference to avoid race condition."""
            try:
                if pty.isalive():
                    return pty.read(4096)
            except Exception:
                pass
            return b""

        try:
            while self._is_active and self._pty_process is not None:
                try:
                    # Use run_in_executor for non-blocking read
                    # winpty read() is blocking, so we need to run it in executor
                    data = await loop.run_in_executor(None, read_data)

                    if data:
                        # winpty may return string, convert to bytes if needed
                        if isinstance(data, str):
                            data = data.encode("utf-8", errors="replace")
                        self._broadcast_output(data)
                    else:
                        # Check if process is still alive
                        if self._pty_process is None or not self._pty_process.isalive():
                            break
                        # Small delay to prevent busy loop
                        await asyncio.sleep(0.01)

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if self._is_active:
                        logger.warning(f"Windows PTY read error: {e}")
                    break

        except asyncio.CancelledError:
            pass
        finally:
            if self._is_active:
                self._is_active = False
                logger.info(f"Terminal output stream ended for {self.project_name}")

    async def _read_output_unix(self) -> None:
        """Read output from Unix PTY and broadcast to callbacks."""
        if self._master_fd is None:
            return

        loop = asyncio.get_running_loop()

        try:
            while self._is_active and self._master_fd is not None:
                try:
                    # Use run_in_executor with select for non-blocking read
                    def read_with_select():
                        if self._master_fd is None:
                            return b""
                        try:
                            # Wait up to 100ms for data
                            readable, _, _ = select.select([self._master_fd], [], [], 0.1)
                            if readable:
                                return os.read(self._master_fd, 4096)
                            return b""
                        except (OSError, ValueError):
                            return b""

                    data = await loop.run_in_executor(None, read_with_select)

                    if data:
                        self._broadcast_output(data)
                    elif not self._check_child_alive():
                        break

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if self._is_active:
                        logger.warning(f"Unix PTY read error: {e}")
                    break

        except asyncio.CancelledError:
            pass
        finally:
            if self._is_active:
                self._is_active = False
                logger.info(f"Terminal output stream ended for {self.project_name}")
            # Reap zombie if not already reaped
            if self._child_pid is not None:
                try:
                    os.waitpid(self._child_pid, os.WNOHANG)
                except ChildProcessError:
                    pass
                except Exception:
                    pass

    def _check_child_alive(self) -> bool:
        """Check if the Unix child process is still alive."""
        if self._child_pid is None:
            return False
        try:
            # Use signal 0 to check if process exists without reaping it.
            # This avoids race conditions with os.waitpid which can reap the process.
            os.kill(self._child_pid, 0)
            return True
        except OSError:
            return False

    def write(self, data: bytes) -> None:
        """
        Write input data to the PTY.

        Args:
            data: Raw bytes to write to the terminal
        """
        if not self._is_active:
            logger.warning(f"Cannot write to inactive terminal for {self.project_name}")
            return

        try:
            if IS_WINDOWS:
                if self._pty_process is not None:
                    # winpty expects string input
                    text = data.decode("utf-8", errors="replace")
                    self._pty_process.write(text)
            else:
                if self._master_fd is not None:
                    os.write(self._master_fd, data)
        except Exception as e:
            logger.warning(f"Failed to write to PTY: {e}")

    def resize(self, cols: int, rows: int) -> None:
        """
        Resize the terminal.

        Args:
            cols: New terminal width in columns
            rows: New terminal height in rows
        """
        if not self._is_active:
            return

        try:
            if IS_WINDOWS:
                if self._pty_process is not None:
                    self._pty_process.setwinsize(rows, cols)
            else:
                if self._master_fd is not None:
                    # Unix-specific modules imported at top-level
                    winsize = struct.pack("HHHH", rows, cols, 0, 0)
                    fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)  # type: ignore[attr-defined]

            logger.debug(f"Terminal resized for {self.project_name}: {cols}x{rows}")
        except Exception as e:
            logger.warning(f"Failed to resize terminal: {e}")

    async def stop(self) -> None:
        """Stop the terminal session and clean up resources."""
        if not self._is_active:
            return

        self._is_active = False

        # Cancel output reading task
        if self._output_task is not None:
            self._output_task.cancel()
            try:
                await self._output_task
            except asyncio.CancelledError:
                pass
            self._output_task = None

        try:
            if IS_WINDOWS:
                await self._stop_windows()
            else:
                await self._stop_unix()
        except Exception as e:
            logger.warning(f"Error stopping terminal: {e}")

        logger.info(f"Terminal stopped for {self.project_name}")

    async def _stop_windows(self) -> None:
        """Stop Windows PTY process."""
        if self._pty_process is None:
            return

        try:
            if self._pty_process.isalive():
                self._pty_process.terminate()
                # Give it a moment to terminate
                await asyncio.sleep(0.1)
                if self._pty_process.isalive():
                    self._pty_process.kill()
        except Exception as e:
            logger.warning(f"Error terminating Windows PTY: {e}")
        finally:
            self._pty_process = None

    async def _stop_unix(self) -> None:
        """Stop Unix PTY process."""
        # Note: This method uses Unix-specific signal handling (signal imported at top-level)

        # Close master file descriptor
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

        # Terminate child process
        if self._child_pid is not None:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
                # Wait briefly for graceful shutdown
                await asyncio.sleep(0.1)
                # Check if still running and force kill if needed
                try:
                    os.kill(self._child_pid, 0)  # Check if process exists
                    # SIGKILL is Unix-specific (Windows would use SIGTERM)
                    os.kill(self._child_pid, signal.SIGKILL)  # type: ignore[attr-defined]
                except ProcessLookupError:
                    pass  # Already terminated
                # Reap the child process to prevent zombie
                try:
                    os.waitpid(self._child_pid, 0)
                except ChildProcessError:
                    pass
            except ProcessLookupError:
                pass  # Already terminated
            except Exception as e:
                logger.warning(f"Error terminating Unix PTY child: {e}")
            finally:
                self._child_pid = None


# Global registry of terminal sessions per project with thread safety
# Structure: Dict[project_name, Dict[terminal_id, TerminalSession]]
_sessions: dict[str, dict[str, TerminalSession]] = {}
_sessions_lock = threading.Lock()

# Terminal metadata registry (in-memory, resets on server restart)
# Structure: Dict[project_name, List[TerminalInfo]]
_terminal_metadata: dict[str, list[TerminalInfo]] = {}
_metadata_lock = threading.Lock()


def create_terminal(project_name: str, name: str | None = None) -> TerminalInfo:
    """
    Create a new terminal entry for a project.

    Args:
        project_name: Name of the project
        name: Optional terminal name (auto-generated if not provided)

    Returns:
        TerminalInfo for the new terminal
    """
    with _metadata_lock:
        if project_name not in _terminal_metadata:
            _terminal_metadata[project_name] = []

        terminals = _terminal_metadata[project_name]

        # Auto-generate name if not provided
        if name is None:
            existing_nums = []
            for t in terminals:
                if t.name.startswith("Terminal "):
                    try:
                        num = int(t.name.replace("Terminal ", ""))
                        existing_nums.append(num)
                    except ValueError:
                        pass
            next_num = max(existing_nums, default=0) + 1
            name = f"Terminal {next_num}"

        terminal_id = str(uuid.uuid4())[:8]
        info = TerminalInfo(id=terminal_id, name=name)
        terminals.append(info)

        logger.info(f"Created terminal '{name}' (ID: {terminal_id}) for project {project_name}")
        return info


def list_terminals(project_name: str) -> list[TerminalInfo]:
    """
    List all terminals for a project.

    Args:
        project_name: Name of the project

    Returns:
        List of TerminalInfo for the project
    """
    with _metadata_lock:
        return list(_terminal_metadata.get(project_name, []))


def rename_terminal(project_name: str, terminal_id: str, new_name: str) -> bool:
    """
    Rename a terminal.

    Args:
        project_name: Name of the project
        terminal_id: ID of the terminal to rename
        new_name: New name for the terminal

    Returns:
        True if renamed successfully, False if terminal not found
    """
    with _metadata_lock:
        terminals = _terminal_metadata.get(project_name, [])
        for terminal in terminals:
            if terminal.id == terminal_id:
                old_name = terminal.name
                terminal.name = new_name
                logger.info(
                    f"Renamed terminal '{old_name}' to '{new_name}' "
                    f"(ID: {terminal_id}) for project {project_name}"
                )
                return True
        return False


def delete_terminal(project_name: str, terminal_id: str) -> bool:
    """
    Delete a terminal and stop its session if active.

    Args:
        project_name: Name of the project
        terminal_id: ID of the terminal to delete

    Returns:
        True if deleted, False if not found
    """
    # Remove from metadata
    with _metadata_lock:
        terminals = _terminal_metadata.get(project_name, [])
        for i, terminal in enumerate(terminals):
            if terminal.id == terminal_id:
                terminals.pop(i)
                logger.info(
                    f"Deleted terminal '{terminal.name}' (ID: {terminal_id}) "
                    f"for project {project_name}"
                )
                break
        else:
            return False

    # Remove session if exists (will be stopped async by caller)
    with _sessions_lock:
        project_sessions = _sessions.get(project_name, {})
        if terminal_id in project_sessions:
            del project_sessions[terminal_id]

    return True


def get_terminal_session(
    project_name: str, project_dir: Path, terminal_id: str | None = None
) -> TerminalSession:
    """
    Get or create a terminal session for a project (thread-safe).

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory
        terminal_id: ID of the terminal (creates default if not provided)

    Returns:
        TerminalSession instance for the project/terminal
    """
    # Ensure terminal metadata exists
    if terminal_id is None:
        # Create default terminal if none exists
        terminals = list_terminals(project_name)
        if not terminals:
            info = create_terminal(project_name)
            terminal_id = info.id
        else:
            terminal_id = terminals[0].id

    with _sessions_lock:
        if project_name not in _sessions:
            _sessions[project_name] = {}

        project_sessions = _sessions[project_name]
        if terminal_id not in project_sessions:
            project_sessions[terminal_id] = TerminalSession(project_name, project_dir)

        return project_sessions[terminal_id]


def remove_terminal_session(project_name: str, terminal_id: str) -> TerminalSession | None:
    """
    Remove a terminal session from the registry.

    Args:
        project_name: Name of the project
        terminal_id: ID of the terminal

    Returns:
        The removed session, or None if not found
    """
    with _sessions_lock:
        project_sessions = _sessions.get(project_name, {})
        return project_sessions.pop(terminal_id, None)


def get_terminal_info(project_name: str, terminal_id: str) -> TerminalInfo | None:
    """
    Get terminal info by ID.

    Args:
        project_name: Name of the project
        terminal_id: ID of the terminal

    Returns:
        TerminalInfo if found, None otherwise
    """
    with _metadata_lock:
        terminals = _terminal_metadata.get(project_name, [])
        for terminal in terminals:
            if terminal.id == terminal_id:
                return terminal
        return None


async def stop_terminal_session(project_name: str, terminal_id: str) -> bool:
    """
    Stop a specific terminal session.

    Args:
        project_name: Name of the project
        terminal_id: ID of the terminal

    Returns:
        True if stopped, False if not found
    """
    session = remove_terminal_session(project_name, terminal_id)
    if session and session.is_active:
        await session.stop()
        return True
    return False


async def cleanup_all_terminals() -> None:
    """
    Stop all active terminal sessions.

    Called on server shutdown to ensure all PTY processes are terminated.
    """
    with _sessions_lock:
        all_sessions = []
        for project_sessions in _sessions.values():
            all_sessions.extend(project_sessions.values())

    for session in all_sessions:
        try:
            if session.is_active:
                await session.stop()
        except Exception as e:
            logger.warning(f"Error stopping terminal for {session.project_name}: {e}")

    with _sessions_lock:
        _sessions.clear()

    with _metadata_lock:
        _terminal_metadata.clear()

    logger.info("All terminal sessions cleaned up")
