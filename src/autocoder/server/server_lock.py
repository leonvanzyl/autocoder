from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil


@dataclass(frozen=True)
class LockStatus:
    is_running: bool
    pid: Optional[int]
    reason: str


class ServerLock:
    """
    Cross-process lock to ensure only one UI server runs per port.

    Uses a PID file in the OS temp directory and detects stale locks.
    """

    def __init__(self, port: int, *, namespace: str = "autocoder-ui"):
        self.port = int(port)
        self.namespace = namespace
        lock_dir = Path(tempfile.gettempdir()) / "autocoder-locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = lock_dir / f"{namespace}-{self.port}.pid"
        self.pid = os.getpid()

    def status(self) -> LockStatus:
        if not self.lock_file.exists():
            return LockStatus(is_running=False, pid=None, reason="no lock file")
        try:
            raw = self.lock_file.read_text(encoding="utf-8", errors="replace").strip()
            existing_pid = int(raw)
        except Exception:
            return LockStatus(is_running=False, pid=None, reason="invalid lock file")

        if not psutil.pid_exists(existing_pid):
            return LockStatus(is_running=False, pid=existing_pid, reason="stale lock (pid dead)")

        # PID exists; treat as running. (PID reuse is possible, but this is good enough for dev.)
        return LockStatus(is_running=True, pid=existing_pid, reason="pid alive")

    def acquire(self, *, force: bool = False, timeout_s: int = 10) -> bool:
        start = time.time()
        while True:
            st = self.status()
            if not st.is_running:
                if self.lock_file.exists():
                    # Remove stale lock if requested
                    if force or st.reason.startswith("stale"):
                        try:
                            self.lock_file.unlink()
                        except OSError:
                            pass
                    else:
                        return False

                try:
                    tmp = self.lock_file.with_suffix(".tmp")
                    tmp.write_text(str(self.pid), encoding="utf-8")
                    tmp.replace(self.lock_file)
                    return True
                except OSError:
                    pass

            if time.time() - start > timeout_s:
                return False
            time.sleep(0.2)

    def release(self) -> None:
        try:
            if not self.lock_file.exists():
                return
            raw = self.lock_file.read_text(encoding="utf-8", errors="replace").strip()
            existing_pid = int(raw)
            if existing_pid == self.pid:
                self.lock_file.unlink()
        except Exception:
            return

    def __enter__(self):
        ok = self.acquire(force=True)
        if not ok:
            st = self.status()
            pid_info = f" (PID {st.pid})" if st.pid else ""
            raise RuntimeError(f"UI server already running on port {self.port}{pid_info}")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()

