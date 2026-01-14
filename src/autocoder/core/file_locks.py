from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


def canonicalize_path(path: str) -> str:
    # Normalize to a stable repo-relative key (best-effort).
    p = path.replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    return p


def _lock_file_path(lock_dir: Path, key: str) -> Path:
    digest = sha256(key.encode("utf-8", errors="replace")).hexdigest()[:16]
    return lock_dir / f"{digest}.lock"


@dataclass(frozen=True)
class LockInfo:
    key: str
    agent_id: str
    acquired_at: float


def _read_lock(path: Path) -> LockInfo | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    key = data.get("key")
    agent_id = data.get("agent_id")
    acquired_at = data.get("acquired_at")
    if not isinstance(key, str) or not isinstance(agent_id, str):
        return None
    try:
        acquired_at_f = float(acquired_at)
    except Exception:
        acquired_at_f = 0.0
    return LockInfo(key=key, agent_id=agent_id, acquired_at=acquired_at_f)


def get_lock_holder(lock_dir: Path, path: str) -> str | None:
    key = canonicalize_path(path)
    lock_path = _lock_file_path(lock_dir, key)
    info = _read_lock(lock_path)
    return info.agent_id if info else None


def try_acquire_lock(lock_dir: Path, path: str, agent_id: str) -> bool:
    lock_dir.mkdir(parents=True, exist_ok=True)
    key = canonicalize_path(path)
    lock_path = _lock_file_path(lock_dir, key)

    # Idempotent acquire.
    existing = _read_lock(lock_path)
    if existing and existing.agent_id == agent_id:
        return True

    payload = json.dumps({"key": key, "agent_id": agent_id, "acquired_at": time.time()})
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_path), flags)
    except FileExistsError:
        return False
    try:
        os.write(fd, payload.encode("utf-8", errors="replace"))
    finally:
        os.close(fd)
    return True


def acquire_lock(lock_dir: Path, path: str, agent_id: str, *, timeout_seconds: float = 0.0) -> bool:
    deadline = time.time() + max(0.0, float(timeout_seconds))
    while True:
        if try_acquire_lock(lock_dir, path, agent_id):
            return True
        if timeout_seconds <= 0:
            return False
        if time.time() >= deadline:
            return False
        time.sleep(0.2)


def release_lock(lock_dir: Path, path: str, agent_id: str) -> bool:
    key = canonicalize_path(path)
    lock_path = _lock_file_path(lock_dir, key)
    info = _read_lock(lock_path)
    if info and info.agent_id != agent_id:
        return False
    try:
        lock_path.unlink(missing_ok=True)
    except TypeError:
        # Python < 3.8 fallback, but keep compatibility.
        if lock_path.exists():
            lock_path.unlink()
    return True


def cleanup_agent_locks(lock_dir: Path, agent_id: str) -> int:
    if not lock_dir.exists():
        return 0
    removed = 0
    for p in lock_dir.glob("*.lock"):
        info = _read_lock(p)
        if info and info.agent_id == agent_id:
            try:
                p.unlink()
                removed += 1
            except Exception:
                continue
    return removed


def list_locks(lock_dir: Path) -> list[LockInfo]:
    if not lock_dir.exists():
        return []
    out: list[LockInfo] = []
    for p in lock_dir.glob("*.lock"):
        info = _read_lock(p)
        if info:
            out.append(info)
    out.sort(key=lambda x: (x.key, x.agent_id))
    return out

