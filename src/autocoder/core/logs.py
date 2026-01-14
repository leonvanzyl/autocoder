from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PruneResult:
    deleted_files: int
    deleted_bytes: int
    kept_files: int
    kept_bytes: int


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value


def prune_worker_logs(
    project_dir: Path,
    *,
    keep_days: int = 7,
    keep_files: int = 200,
    max_total_mb: int = 200,
    dry_run: bool = False,
) -> PruneResult:
    """
    Prune `.autocoder/logs/*.log` in a project directory.

    Strategy:
    - Delete logs older than `keep_days`.
    - Then enforce `keep_files` by deleting oldest.
    - Then enforce `max_total_mb` by deleting oldest until under budget.
    """
    logs_dir = (project_dir / ".autocoder" / "logs").resolve()
    if not logs_dir.exists():
        return PruneResult(deleted_files=0, deleted_bytes=0, kept_files=0, kept_bytes=0)

    keep_days = max(0, keep_days)
    keep_files = max(0, keep_files)
    max_total_bytes = max(0, max_total_mb) * 1024 * 1024

    now = time.time()
    cutoff = now - (keep_days * 86400)

    candidates: list[tuple[Path, float, int]] = []
    for p in logs_dir.glob("*.log"):
        try:
            st = p.stat()
        except OSError:
            continue
        candidates.append((p, st.st_mtime, int(st.st_size)))

    # Oldest first.
    candidates.sort(key=lambda x: x[1])

    deleted_files = 0
    deleted_bytes = 0

    def delete_path(path: Path, size: int) -> None:
        nonlocal deleted_files, deleted_bytes
        if dry_run:
            deleted_files += 1
            deleted_bytes += size
            return
        try:
            path.unlink()
        except OSError:
            return
        deleted_files += 1
        deleted_bytes += size

    # Phase 1: age-based pruning
    remaining: list[tuple[Path, float, int]] = []
    for p, mtime, size in candidates:
        if keep_days and mtime < cutoff:
            delete_path(p, size)
        else:
            remaining.append((p, mtime, size))

    # Phase 2: keep_files
    if keep_files >= 0 and len(remaining) > keep_files:
        to_delete = remaining[: len(remaining) - keep_files]
        to_keep = remaining[len(remaining) - keep_files :]
        for p, _, size in to_delete:
            delete_path(p, size)
        remaining = to_keep

    # Phase 3: max_total_mb
    total = sum(size for _, _, size in remaining)
    if max_total_bytes > 0 and total > max_total_bytes:
        # Delete oldest until under budget.
        for p, _, size in list(remaining):
            if total <= max_total_bytes:
                break
            delete_path(p, size)
            total -= size
            remaining = [t for t in remaining if t[0] != p]

    kept_files = len(remaining)
    kept_bytes = sum(size for _, _, size in remaining)
    return PruneResult(
        deleted_files=deleted_files,
        deleted_bytes=deleted_bytes,
        kept_files=kept_files,
        kept_bytes=kept_bytes,
    )


def prune_worker_logs_from_env(project_dir: Path, *, dry_run: bool = False) -> PruneResult:
    """
    Prune worker logs using env configuration.

    Env vars:
    - AUTOCODER_LOGS_KEEP_DAYS (default 7)
    - AUTOCODER_LOGS_KEEP_FILES (default 200)
    - AUTOCODER_LOGS_MAX_TOTAL_MB (default 200)
    """
    return prune_worker_logs(
        project_dir,
        keep_days=_env_int("AUTOCODER_LOGS_KEEP_DAYS", 7),
        keep_files=_env_int("AUTOCODER_LOGS_KEEP_FILES", 200),
        max_total_mb=_env_int("AUTOCODER_LOGS_MAX_TOTAL_MB", 200),
        dry_run=dry_run,
    )


def prune_gatekeeper_artifacts(
    project_dir: Path,
    *,
    keep_days: int = 14,
    keep_files: int = 500,
    max_total_mb: int = 200,
    dry_run: bool = False,
) -> PruneResult:
    """
    Prune Gatekeeper artifact JSON files under `.autocoder/**/gatekeeper/*.json`.

    Strategy matches `prune_worker_logs`: age → keep_files → max_total_mb (oldest first).
    """
    root = (project_dir / ".autocoder").resolve()
    if not root.exists():
        return PruneResult(deleted_files=0, deleted_bytes=0, kept_files=0, kept_bytes=0)

    keep_days = max(0, keep_days)
    keep_files = max(0, keep_files)
    max_total_bytes = max(0, max_total_mb) * 1024 * 1024

    now = time.time()
    cutoff = now - (keep_days * 86400)

    candidates: list[tuple[Path, float, int]] = []
    for p in root.glob("gatekeeper/*.json"):
        try:
            st = p.stat()
        except OSError:
            continue
        candidates.append((p, st.st_mtime, int(st.st_size)))

    for p in root.glob("features/*/gatekeeper/*.json"):
        try:
            st = p.stat()
        except OSError:
            continue
        candidates.append((p, st.st_mtime, int(st.st_size)))

    candidates.sort(key=lambda x: x[1])  # oldest first

    deleted_files = 0
    deleted_bytes = 0

    def delete_path(path: Path, size: int) -> None:
        nonlocal deleted_files, deleted_bytes
        if dry_run:
            deleted_files += 1
            deleted_bytes += size
            return
        try:
            path.unlink()
        except OSError:
            return
        deleted_files += 1
        deleted_bytes += size

    remaining: list[tuple[Path, float, int]] = []
    for p, mtime, size in candidates:
        if keep_days and mtime < cutoff:
            delete_path(p, size)
        else:
            remaining.append((p, mtime, size))

    if keep_files >= 0 and len(remaining) > keep_files:
        to_delete = remaining[: len(remaining) - keep_files]
        to_keep = remaining[len(remaining) - keep_files :]
        for p, _, size in to_delete:
            delete_path(p, size)
        remaining = to_keep

    total = sum(size for _, _, size in remaining)
    if max_total_bytes > 0 and total > max_total_bytes:
        for p, _, size in list(remaining):
            if total <= max_total_bytes:
                break
            delete_path(p, size)
            total -= size
            remaining = [t for t in remaining if t[0] != p]

    kept_files = len(remaining)
    kept_bytes = sum(size for _, _, size in remaining)
    return PruneResult(
        deleted_files=deleted_files,
        deleted_bytes=deleted_bytes,
        kept_files=kept_files,
        kept_bytes=kept_bytes,
    )


def prune_gatekeeper_artifacts_from_env(project_dir: Path, *, dry_run: bool = False) -> PruneResult:
    """
    Prune Gatekeeper artifacts using env configuration.

    Env vars (fall back to the logs knobs if unset):
    - AUTOCODER_ARTIFACTS_KEEP_DAYS (default: AUTOCODER_LOGS_KEEP_DAYS or 14)
    - AUTOCODER_ARTIFACTS_KEEP_FILES (default: AUTOCODER_LOGS_KEEP_FILES or 500)
    - AUTOCODER_ARTIFACTS_MAX_TOTAL_MB (default: AUTOCODER_LOGS_MAX_TOTAL_MB or 200)
    """
    keep_days = _env_int("AUTOCODER_ARTIFACTS_KEEP_DAYS", _env_int("AUTOCODER_LOGS_KEEP_DAYS", 14))
    keep_files = _env_int("AUTOCODER_ARTIFACTS_KEEP_FILES", _env_int("AUTOCODER_LOGS_KEEP_FILES", 500))
    max_mb = _env_int("AUTOCODER_ARTIFACTS_MAX_TOTAL_MB", _env_int("AUTOCODER_LOGS_MAX_TOTAL_MB", 200))
    return prune_gatekeeper_artifacts(
        project_dir,
        keep_days=keep_days,
        keep_files=keep_files,
        max_total_mb=max_mb,
        dry_run=dry_run,
    )
