#!/usr/bin/env python3
"""
Project Detach/Reattach Module
==============================

Manages the separation of AutoForge files from project directories,
allowing Claude Code to run without restrictions on completed projects.

Features:
- Detach: Moves AutoForge files to .autoforge-backup/
- Reattach: Restores files from backup
- Status: Checks detach state and backup info
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from registry import get_project_path, list_registered_projects

# Module logger
logger = logging.getLogger(__name__)

# Backup directory name
BACKUP_DIR = ".autoforge-backup"
PRE_REATTACH_BACKUP_DIR = ".pre-reattach-backup"
MANIFEST_FILE = "manifest.json"
DETACH_LOCK = ".autoforge-detach.lock"

# Version for manifest format
MANIFEST_VERSION = 1

# Lock file timeout in seconds (5 minutes)
LOCK_TIMEOUT_SECONDS = 300


def get_autoforge_version() -> str:
    """Get autoforge version from pyproject.toml, with fallback."""
    try:
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                version = data.get("project", {}).get("version", "1.0.0")
                return str(version) if version is not None else "1.0.0"
    except Exception as e:
        logger.debug("Failed to read version from pyproject.toml: %s", e)
    return "1.0.0"  # Fallback


# AutoForge file patterns to detect and move
# Directories (will be moved recursively)
AUTOFORGE_DIRECTORIES = {
    ".autoforge",
    ".autocoder",  # Legacy fallback
    "prompts",
    ".playwright-mcp",
}

# Files with exact names
AUTOFORGE_FILES = {
    "features.db",
    "features.db-shm",  # SQLite shared memory file
    "features.db-wal",  # SQLite write-ahead log
    "assistant.db",
    "assistant.db-shm",  # SQLite shared memory file
    "assistant.db-wal",  # SQLite write-ahead log
    "CLAUDE.md",
    ".claude_settings.json",
    ".claude_assistant_settings.json",
    ".agent.lock",
    "claude-progress.txt",
}

# Glob patterns for generated files (searched in AUTOFORGE_DIRECTORIES only)
AUTOFORGE_PATTERNS = [
    "test-*.json",
    "test-*.py",
    "test-*.html",
    "test-*.sql",  # SQL test files
    "test-*.php",  # PHP test files
    "create-*-test*.php",  # Test helper scripts (e.g., create-xss-test.php)
    "rollback-*.json",  # Rollback test data
    "generate-*.py",
    "mark_feature*.py",
    ".claude_settings.expand.*.json",
]

# Patterns for agent-generated files at ROOT level
# More specific patterns to avoid false positives with user files like test-myfeature.py
AUTOFORGE_ROOT_PATTERNS = [
    "test-feature*.json",   # Feature test data
    "test-feature*.py",     # Feature test scripts
    "test-feature*.html",   # Feature test pages
    "test-feature*.sql",    # Feature test SQL
    "test-feature*.php",    # Feature test PHP
    "generate-*.py",        # Generator scripts
    "mark_feature*.py",     # Feature marking scripts
    "rollback-*.json",      # Rollback data
    "create-*-test*.php",   # Test helper scripts
]


class FileEntry(TypedDict):
    """Type for manifest file entry."""
    path: str
    type: str  # "file", "directory", or "symlink"
    size: int
    checksum: str | None  # MD5 for files, None for directories
    file_count: int | None  # Number of files for directories


class Manifest(TypedDict):
    """Type for manifest.json structure."""
    version: int
    detached_at: str
    project_name: str
    autocoder_version: str
    files: list[FileEntry]
    total_size_bytes: int
    file_count: int


def compute_file_checksum(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute checksum for a file using specified algorithm.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use ("sha256" or "md5")

    Returns:
        Hex digest of the file checksum
    """
    if algorithm == "md5":
        hasher = hashlib.md5(usedforsecurity=False)
    else:
        hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_checksum(file_path: Path, expected: str) -> bool:
    """Verify file checksum with algorithm auto-detection (SHA-256 vs MD5).

    Detects algorithm by checksum length: MD5=32 hex chars, SHA-256=64 hex chars.
    This provides backward compatibility with older backups using MD5.

    Args:
        file_path: Path to the file to verify
        expected: Expected checksum value

    Returns:
        True if checksum matches, False otherwise
    """
    # Detect algorithm by checksum length: MD5=32 hex chars, SHA-256=64 hex chars
    if len(expected) == 32:
        actual = compute_file_checksum(file_path, algorithm="md5")
    else:
        actual = compute_file_checksum(file_path, algorithm="sha256")
    return actual == expected


def get_directory_info(dir_path: Path) -> tuple[int, int]:
    """Get total size and file count for a directory."""
    total_size = 0
    file_count = 0
    for item in dir_path.rglob("*"):
        if item.is_file():
            total_size += item.stat().st_size
            file_count += 1
    return total_size, file_count


def get_autoforge_files(project_dir: Path, include_artifacts: bool = True) -> list[Path]:
    """
    Detect all AutoForge files in a project directory.

    Args:
        project_dir: Path to the project directory
        include_artifacts: Whether to include .playwright-mcp and other artifacts

    Returns:
        List of Path objects for AutoForge files/directories
    """
    files = []

    # Check directories
    for dir_name in AUTOFORGE_DIRECTORIES:
        if not include_artifacts and dir_name == ".playwright-mcp":
            continue
        dir_path = project_dir / dir_name
        if dir_path.exists():
            files.append(dir_path)

    # Check exact files
    for file_name in AUTOFORGE_FILES:
        file_path = project_dir / file_name
        if file_path.exists():
            files.append(file_path)

    # Check glob patterns ONLY in AutoForge-owned directories
    # to avoid accidentally moving user files like test-myfeature.py
    for dir_name in AUTOFORGE_DIRECTORIES:
        dir_path = project_dir / dir_name
        if dir_path.exists() and dir_path.is_dir():
            for pattern in AUTOFORGE_PATTERNS:
                for match in dir_path.rglob(pattern):
                    if match.exists() and match not in files:
                        files.append(match)

    # Check ROOT-safe patterns at project root level
    # These are more specific patterns to avoid false positives
    for pattern in AUTOFORGE_ROOT_PATTERNS:
        for match in project_dir.glob(pattern):  # glob, not rglob - root level only
            if match.exists() and match not in files:
                files.append(match)

    return sorted(files, key=lambda p: p.name)


def is_project_detached(project_dir: Path) -> bool:
    """Check if a project is currently detached."""
    manifest_path = project_dir / BACKUP_DIR / MANIFEST_FILE
    return manifest_path.exists()


def get_project_detach_state(project_dir: Path, include_artifacts: bool = True) -> tuple[str, list[Path]]:
    """
    Determine the actual detach state of a project.

    This function detects inconsistent states where both manifest AND files exist,
    which can happen after a partial reattach operation.

    Args:
        project_dir: Path to the project directory
        include_artifacts: Whether to include .playwright-mcp and other artifacts

    Returns:
        Tuple of (state, files) where state is one of:
        - "detached": Manifest exists, no AutoForge files at root
        - "attached": No manifest, files present at root
        - "inconsistent": Both manifest and files exist (needs cleanup)
        - "clean": No manifest, no AutoForge files
    """
    manifest_exists = is_project_detached(project_dir)
    files = get_autoforge_files(project_dir, include_artifacts=include_artifacts)

    if manifest_exists and files:
        return "inconsistent", files
    elif manifest_exists and not files:
        return "detached", []
    elif not manifest_exists and files:
        return "attached", files
    else:
        return "clean", []


def has_backup(project_dir: Path) -> bool:
    """Check if a backup exists for a project."""
    return is_project_detached(project_dir)


def get_backup_info(project_dir: Path) -> Manifest | None:
    """
    Get manifest info from backup if it exists.

    Returns:
        Manifest dict or None if no backup exists
    """
    manifest_path = project_dir / BACKUP_DIR / MANIFEST_FILE
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data: Manifest = json.load(f)
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read manifest: %s", e)
        return None


def acquire_detach_lock(project_dir: Path) -> bool:
    """
    Acquire lock for detach operations using atomic file creation.

    Uses O_CREAT|O_EXCL for atomic lock creation to prevent TOCTOU race conditions.
    Writes PID and timestamp to lock file for stale lock detection.

    Returns:
        True if lock acquired, False if already locked
    """
    lock_file = project_dir / DETACH_LOCK

    def try_atomic_create() -> bool:
        """Attempt atomic lock file creation. Returns True if successful."""
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                lock_data = {
                    "pid": os.getpid(),
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                }
                os.write(fd, json.dumps(lock_data).encode("utf-8"))
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            return False
        except OSError as e:
            logger.error("Failed to create lock file: %s", e)
            return False

    # First attempt
    if try_atomic_create():
        return True

    # Lock exists - check if stale/corrupted
    try:
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
        lock_pid = lock_data.get("pid")
        lock_time = lock_data.get("timestamp", 0)

        if lock_pid is not None:
            try:
                os.kill(lock_pid, 0)  # Check if process exists
                # Process exists, check timeout
                elapsed = datetime.now(timezone.utc).timestamp() - lock_time
                if elapsed < LOCK_TIMEOUT_SECONDS:
                    return False  # Valid lock held by another process
                logger.warning("Removing stale lock (timeout): pid=%s", lock_pid)
            except OSError:
                # Process doesn't exist - stale lock
                logger.warning("Removing stale lock (dead process): pid=%s", lock_pid)
    except (json.JSONDecodeError, OSError, KeyError):
        logger.warning("Removing corrupted lock file")

    # Remove stale/corrupted lock and retry once
    try:
        lock_file.unlink()
    except OSError:
        pass

    return try_atomic_create()


def release_detach_lock(project_dir: Path) -> None:
    """Release detach operation lock."""
    lock_file = project_dir / DETACH_LOCK
    lock_file.unlink(missing_ok=True)


def create_backup(
    project_dir: Path,
    project_name: str,
    files: list[Path],
    dry_run: bool = False
) -> Manifest:
    """
    Create backup of AutoForge files.

    Uses copy-then-delete approach to prevent data loss on partial failures.

    Args:
        project_dir: Path to project directory
        project_name: Name of the project
        files: List of files/directories to backup
        dry_run: If True, only simulate the operation

    Returns:
        Manifest describing the backup
    """
    backup_dir = project_dir / BACKUP_DIR

    # Build manifest
    manifest_files: list[FileEntry] = []
    total_size = 0
    total_file_count = 0

    for file_path in files:
        relative_path = file_path.relative_to(project_dir)

        if file_path.is_symlink():
            # Handle symlinks before is_dir() which follows symlinks
            manifest_files.append({
                "path": str(relative_path),
                "type": "symlink",
                "size": 0,
                "checksum": None,
                "file_count": None,
            })
            total_file_count += 1
        elif file_path.is_dir():
            size, count = get_directory_info(file_path)
            manifest_files.append({
                "path": str(relative_path),
                "type": "directory",
                "size": size,
                "checksum": None,
                "file_count": count,
            })
            total_size += size
            total_file_count += count
        else:
            size = file_path.stat().st_size
            checksum = compute_file_checksum(file_path) if not dry_run else "dry-run"
            manifest_files.append({
                "path": str(relative_path),
                "type": "file",
                "size": size,
                "checksum": checksum,
                "file_count": None,
            })
            total_size += size
            total_file_count += 1

    manifest: Manifest = {
        "version": MANIFEST_VERSION,
        "detached_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name,
        "autocoder_version": get_autoforge_version(),
        "files": manifest_files,
        "total_size_bytes": total_size,
        "file_count": total_file_count,
    }

    if dry_run:
        return manifest

    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)
    phase = 1  # Track phase: 1=Copy, 2=Manifest, 3=Delete originals

    try:
        # Phase 1: Copy files to backup (preserves originals on failure)
        for file_path in files:
            relative_path = file_path.relative_to(project_dir)
            dest_path = backup_dir / relative_path

            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file/directory (handle symlinks explicitly)
            if file_path.is_symlink():
                # Preserve symlinks as symlinks
                link_target = os.readlink(file_path)
                dest_path.symlink_to(link_target)
            elif file_path.is_dir():
                shutil.copytree(file_path, dest_path, symlinks=True)
            else:
                shutil.copy2(file_path, dest_path)

            logger.debug("Copied %s to backup", relative_path)

        # Phase 2: Write manifest (before deleting originals)
        phase = 2
        manifest_path = backup_dir / MANIFEST_FILE
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Phase 3: Delete originals (only after successful copy + manifest)
        phase = 3
        logger.debug("Phase 3: Deleting %d original files", len(files))
        for file_path in files:
            if file_path.is_dir() and not file_path.is_symlink():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
            logger.debug("Removed original: %s", file_path.relative_to(project_dir))

    except Exception as e:
        # Cleanup partial backup on failure - but only for Phase 1/2
        # Phase 3 failure means backup is valid, keep it for recovery
        if phase < 3:
            logger.error("Backup failed in phase %d: %s - cleaning up partial backup", phase, e)
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
        else:
            logger.error("Delete originals failed in phase 3: %s - backup preserved for recovery", e)
        raise

    return manifest


def restore_backup(project_dir: Path, verify_checksums: bool = False) -> tuple[bool, int, list[str]]:
    """
    Restore files from backup.

    Uses copy-then-delete approach to prevent data loss on partial failures.
    Detects and backs up conflicting user files before restore.

    Args:
        project_dir: Path to project directory
        verify_checksums: If True, verify file checksums after restore

    Returns:
        Tuple of (success, files_restored, conflicts_backed_up)
    """
    backup_dir = project_dir / BACKUP_DIR
    manifest_path = backup_dir / MANIFEST_FILE
    project_dir_resolved = project_dir.resolve()

    if not manifest_path.exists():
        logger.error("No backup manifest found")
        return False, 0, []

    # Read manifest
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest: Manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read manifest: %s", e)
        return False, 0, []

    # Validate manifest structure
    required_keys = {"version", "files", "detached_at"}
    if not required_keys.issubset(manifest.keys()):
        logger.error("Invalid manifest structure: missing required keys")
        return False, 0, []

    # Check manifest version compatibility
    manifest_version = manifest.get("version", 1)
    if manifest_version > MANIFEST_VERSION:
        logger.error(
            "Manifest version %d not supported (max: %d)",
            manifest_version, MANIFEST_VERSION
        )
        return False, 0, []

    # Detect and backup user files that would be overwritten
    conflicts = detect_conflicts(project_dir, manifest)
    if conflicts:
        backup_conflicts(project_dir, conflicts)
        logger.info("Backed up %d user files to %s", len(conflicts), PRE_REATTACH_BACKUP_DIR)

    # Restore files
    files_restored = 0
    restored_entries: list[FileEntry] = []

    for entry in manifest["files"]:
        src_path = backup_dir / entry["path"]
        dest_path = project_dir / entry["path"]

        # SECURITY: Validate path to prevent path traversal attacks
        try:
            dest_resolved = dest_path.resolve()
            # Ensure the resolved path is within the project directory
            dest_resolved.relative_to(project_dir_resolved)
        except ValueError:
            logger.error("Path traversal detected: %s", entry["path"])
            return False, 0, []

        if not src_path.exists():
            logger.warning("Backup file missing: %s", entry["path"])
            continue

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic copy-then-replace: copy to temp, then atomically replace destination
        temp_path: Path | None = None
        try:
            if src_path.is_symlink():
                # Symlinks can be created atomically - remove existing first
                if dest_path.exists() or dest_path.is_symlink():
                    if dest_path.is_dir() and not dest_path.is_symlink():
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()
                link_target = os.readlink(src_path)
                dest_path.symlink_to(link_target)
            elif src_path.is_dir():
                # Directories: copy to temp location, then replace
                temp_fd, temp_path_str = tempfile.mkstemp(
                    dir=dest_path.parent,
                    prefix=f".{dest_path.name}.",
                    suffix=".tmp"
                )
                temp_path = Path(temp_path_str)
                os.close(temp_fd)
                # mkstemp creates a file, but we need a directory
                temp_path.unlink()
                shutil.copytree(src_path, temp_path, symlinks=True)

                # Remove existing destination if needed
                if dest_path.exists():
                    if dest_path.is_dir() and not dest_path.is_symlink():
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()

                os.replace(temp_path, dest_path)
                temp_path = None  # Successfully moved, no cleanup needed
            else:
                # Files: copy to temp location, then atomically replace
                temp_fd, temp_path_str = tempfile.mkstemp(
                    dir=dest_path.parent,
                    prefix=f".{dest_path.name}.",
                    suffix=".tmp"
                )
                temp_path = Path(temp_path_str)
                os.close(temp_fd)
                shutil.copy2(src_path, temp_path)

                # Remove existing destination if needed (handles dir where file should be)
                if dest_path.exists():
                    if dest_path.is_dir() and not dest_path.is_symlink():
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()

                # Atomic replace
                os.replace(temp_path, dest_path)
                temp_path = None  # Successfully moved, no cleanup needed

        except OSError as e:
            logger.error("Failed to restore %s: %s", entry["path"], e)
            # Clean up temp file/directory on failure
            if temp_path and temp_path.exists():
                try:
                    if temp_path.is_dir():
                        shutil.rmtree(temp_path)
                    else:
                        temp_path.unlink()
                except OSError:
                    pass
            return False, files_restored, conflicts

        # Verify checksum if requested and available
        entry_checksum = entry.get("checksum")
        if verify_checksums and entry_checksum and entry["type"] == "file":
            if not verify_checksum(dest_path, entry_checksum):
                logger.error(
                    "Checksum mismatch for %s: expected %s",
                    entry["path"], entry["checksum"]
                )
                return False, files_restored, conflicts

        if entry["type"] == "directory":
            files_restored += entry.get("file_count") or 0
        else:
            files_restored += 1

        restored_entries.append(entry)
        logger.debug("Restored %s", entry["path"])

    # Only remove backup directory if ALL files were restored
    expected_count = len(manifest["files"])
    restored_count = len(restored_entries)

    if restored_count == expected_count:
        shutil.rmtree(backup_dir)
        logger.info("Backup directory removed after successful restore")
        return True, files_restored, conflicts
    else:
        # Partial restore - delete manifest to allow re-detach, but keep backup files
        manifest_path = backup_dir / MANIFEST_FILE
        manifest_path.unlink(missing_ok=True)
        logger.warning(
            "Partial restore: %d/%d files - manifest removed to allow re-detach, backup files preserved",
            restored_count, expected_count
        )
        return False, files_restored, conflicts


def update_gitignore(project_dir: Path) -> None:
    """Add backup directories to .gitignore if not already present."""
    gitignore_path = project_dir / ".gitignore"

    patterns = [
        (f"{BACKUP_DIR}/", "AutoForge backup (for reattach)"),
        (f"{PRE_REATTACH_BACKUP_DIR}/", "User files backup (for detach)"),
    ]

    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for pattern, comment in patterns:
            if not any(line.strip() == pattern for line in lines):
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    f.write(f"\n# {comment}\n{pattern}\n")
                logger.info("Added %s to .gitignore", pattern)
    else:
        entries = "\n".join(f"# {comment}\n{pattern}" for pattern, comment in patterns)
        gitignore_path.write_text(entries + "\n", encoding="utf-8")
        logger.info("Created .gitignore with backup entries")


def detect_conflicts(project_dir: Path, manifest: Manifest) -> list[str]:
    """Return list of relative paths that exist in both backup and project.

    These are files the user created/modified after detaching that would
    be overwritten by restoring autoforge files.

    Args:
        project_dir: Path to the project directory
        manifest: The backup manifest containing file entries

    Returns:
        List of relative path strings for conflicting files
    """
    conflicts = []
    project_dir_resolved = project_dir.resolve()
    for entry in manifest["files"]:
        dest = project_dir / entry["path"]
        # SECURITY: Validate path to prevent path traversal attacks
        try:
            dest.resolve().relative_to(project_dir_resolved)
        except ValueError:
            logger.error("Path traversal detected in manifest: %s", entry["path"])
            continue  # Skip malicious path
        if dest.exists():
            conflicts.append(entry["path"])
    return conflicts


def backup_conflicts(project_dir: Path, conflicts: list[str]) -> Path:
    """Backup conflicting user files to .pre-reattach-backup/ before restore.

    If backup dir already exists, merges new conflicts (doesn't overwrite).

    Args:
        project_dir: Path to the project directory
        conflicts: List of relative paths to backup

    Returns:
        Path to the backup directory
    """
    backup_dir = project_dir / PRE_REATTACH_BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_dir_resolved = backup_dir.resolve()

    for rel_path in conflicts:
        src = project_dir / rel_path
        dest = backup_dir / rel_path

        # SECURITY: Validate path to prevent path traversal attacks
        try:
            dest.resolve().relative_to(backup_dir_resolved)
        except ValueError:
            logger.error("Path traversal detected in conflicts: %s", rel_path)
            continue  # Skip malicious path

        # Don't overwrite existing backups (merge mode)
        if dest.exists():
            logger.debug("Skipping existing backup: %s", rel_path)
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            shutil.copytree(src, dest, symlinks=True)
        else:
            shutil.copy2(src, dest)

        logger.debug("Backed up user file: %s", rel_path)

    return backup_dir


def restore_pre_reattach_backup(project_dir: Path) -> int:
    """Restore user files from .pre-reattach-backup/ after detaching.

    Includes path traversal protection.

    Args:
        project_dir: Path to the project directory

    Returns:
        Number of files restored
    """
    backup_dir = project_dir / PRE_REATTACH_BACKUP_DIR
    if not backup_dir.exists():
        return 0

    project_dir_resolved = project_dir.resolve()
    files_restored = 0
    files_failed = 0

    for item in backup_dir.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(backup_dir)
            dest = project_dir / rel_path

            # SECURITY: Path traversal protection
            try:
                dest.resolve().relative_to(project_dir_resolved)
            except ValueError:
                logger.error("Path traversal detected in pre-reattach backup: %s", rel_path)
                continue  # Skip malicious path

            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                files_restored += 1
                logger.debug("Restored user file: %s", rel_path)
            except OSError as e:
                logger.error("Failed to restore user file %s: %s", rel_path, e)
                files_failed += 1

    # Only clean up backup directory if all files were restored successfully
    if files_failed == 0:
        shutil.rmtree(backup_dir)
        logger.info("Removed %s after restoring %d files", PRE_REATTACH_BACKUP_DIR, files_restored)
    else:
        logger.warning("Kept %s - %d files failed to restore", PRE_REATTACH_BACKUP_DIR, files_failed)

    return files_restored


def _checkpoint_databases(project_dir: Path) -> None:
    """Checkpoint SQLite databases to merge WAL files into main database.

    This ensures -wal and -shm files are empty/minimal before backup,
    preventing them from being recreated during the detach operation.
    """
    import sqlite3

    for db_name in ["features.db", "assistant.db"]:
        db_file = project_dir / db_name
        if db_file.exists():
            try:
                conn = sqlite3.connect(str(db_file))
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()
                logger.debug(f"Checkpointed {db_name}")
            except Exception as e:
                logger.warning(f"Failed to checkpoint {db_name}: {e}")


def detach_project(
    name_or_path: str,
    force: bool = False,
    include_artifacts: bool = True,
    dry_run: bool = False
) -> tuple[bool, str, Manifest | None, int]:
    """
    Detach a project by moving AutoForge files to backup.

    Args:
        name_or_path: Project name (from registry) or absolute path
        force: Skip confirmations
        include_artifacts: Include .playwright-mcp and other artifacts
        dry_run: Only simulate, don't actually move files

    Returns:
        Tuple of (success, message, manifest, user_files_restored)
    """
    # Resolve project path
    project_dir = get_project_path(name_or_path)
    if project_dir is None:
        # Try as path
        project_dir = Path(name_or_path)
        if not project_dir.exists():
            return False, f"Project '{name_or_path}' not found in registry and path doesn't exist", None, 0

    project_dir = Path(project_dir).resolve()
    project_name = name_or_path

    # Check project state
    state, existing_files = get_project_detach_state(project_dir, include_artifacts)

    if state == "detached":
        return False, "Project is already detached. Use --reattach to restore.", None, 0
    elif state == "inconsistent":
        # Files exist but so does manifest - likely partial reattach
        # Clean up old backup and proceed with fresh detach
        if not force:
            return False, (
                "Inconsistent state detected: backup manifest exists but AutoForge files are also present. "
                "This can happen after a partial reattach. Use --force to clean up and detach."
            ), None, 0
        # Force mode: remove old backup and proceed
        backup_dir = project_dir / BACKUP_DIR
        if not dry_run:
            shutil.rmtree(backup_dir)
            logger.info("Removed stale backup directory due to --force")
    elif state == "clean":
        return False, "No AutoForge files found in project.", None, 0
    # state == "attached" -> proceed normally with existing_files

    # Clean up orphaned backup directory (exists without manifest)
    # This can happen after partial reattach removes manifest but keeps backup files
    backup_dir = project_dir / BACKUP_DIR
    if backup_dir.exists() and not (backup_dir / MANIFEST_FILE).exists():
        if not dry_run:
            shutil.rmtree(backup_dir)
            logger.info("Removed orphaned backup directory (no manifest)")

    # Check for agent lock
    agent_lock = project_dir / ".agent.lock"
    if agent_lock.exists() and not force:
        return False, "Agent is currently running. Stop the agent first or use --force.", None, 0

    # Acquire detach lock
    if not dry_run and not acquire_detach_lock(project_dir):
        return False, "Another detach operation is in progress.", None, 0

    try:
        # Use files from state detection if available, otherwise get them fresh
        files = existing_files if existing_files else get_autoforge_files(project_dir, include_artifacts)
        if not files:
            return False, "No AutoForge files found in project.", None, 0

        # Checkpoint databases to merge WAL files before backup
        if not dry_run:
            _checkpoint_databases(project_dir)

        # Create backup
        manifest = create_backup(project_dir, project_name, files, dry_run)

        # Update .gitignore
        if not dry_run:
            update_gitignore(project_dir)

        # Restore user files from pre-reattach backup if exists
        user_files_restored = 0
        if not dry_run:
            user_files_restored = restore_pre_reattach_backup(project_dir)

        action = "Would move" if dry_run else "Moved"
        message = f"{action} {manifest['file_count']} files ({manifest['total_size_bytes'] / 1024 / 1024:.1f} MB) to backup"
        if user_files_restored > 0:
            message += f", restored {user_files_restored} user files"

        return True, message, manifest, user_files_restored

    finally:
        if not dry_run:
            release_detach_lock(project_dir)


def _cleanup_orphaned_db_files(project_dir: Path, manifest: Manifest) -> list[str]:
    """Remove database files that were recreated after detach.

    When the UI/API accesses a detached project, it may recreate empty
    database files. This function detects and removes them before restore.

    Heuristic: If root file is smaller than backup file, it was recreated empty.

    Args:
        project_dir: Path to the project directory
        manifest: Backup manifest containing original file info

    Returns:
        List of files that were cleaned up
    """
    cleaned = []

    # Build map of backup database files with their sizes
    backup_db_files = {}
    for entry in manifest.get("files", []):
        path = entry.get("path", "")
        if path in ("features.db", "assistant.db"):
            backup_db_files[path] = entry.get("size", 0)

    for db_name in ["features.db", "assistant.db"]:
        root_file = project_dir / db_name

        # If root file exists but backup also has it, check if recreated
        if root_file.exists() and db_name in backup_db_files:
            root_size = root_file.stat().st_size
            backup_size = backup_db_files[db_name]

            # If root is much smaller than backup, it was likely recreated empty
            # Empty SQLite DB is typically 4-8KB, real DB with features is much larger
            if backup_size > 0 and root_size < backup_size:
                try:
                    root_file.unlink()
                    cleaned.append(db_name)
                    logger.info(f"Removed recreated {db_name} ({root_size}B < {backup_size}B backup)")
                except OSError as e:
                    logger.warning(f"Failed to remove orphaned {db_name}: {e}")

        # Always clean WAL/SHM files at root - they should be in backup if needed
        for ext in ["-shm", "-wal"]:
            wal_file = project_dir / f"{db_name}{ext}"
            if wal_file.exists():
                try:
                    wal_file.unlink()
                    cleaned.append(f"{db_name}{ext}")
                    logger.debug(f"Removed orphaned {db_name}{ext}")
                except OSError as e:
                    logger.warning(f"Failed to remove {db_name}{ext}: {e}")

    return cleaned


def reattach_project(name_or_path: str) -> tuple[bool, str, int, list[str]]:
    """
    Reattach a project by restoring AutoForge files from backup.

    Args:
        name_or_path: Project name (from registry) or absolute path

    Returns:
        Tuple of (success, message, files_restored, conflicts_backed_up)
    """
    # Resolve project path
    project_dir = get_project_path(name_or_path)
    if project_dir is None:
        project_dir = Path(name_or_path)
        if not project_dir.exists():
            return False, f"Project '{name_or_path}' not found in registry and path doesn't exist", 0, []

    project_dir = Path(project_dir).resolve()

    # Check for agent lock - don't reattach while agent is running
    agent_lock = project_dir / ".agent.lock"
    if agent_lock.exists():
        return False, "Agent is currently running. Stop the agent first.", 0, []

    # Check if backup exists
    if not has_backup(project_dir):
        # Distinguish between "attached" (files at root) and "clean" (no files)
        files_at_root = get_autoforge_files(project_dir)
        if files_at_root:
            return False, "Project is already attached. Nothing to restore.", 0, []
        return False, "No backup found. Project is not detached.", 0, []
    # Backup exists - proceed with restore (handles "detached" and "inconsistent" states)

    # Acquire detach lock
    if not acquire_detach_lock(project_dir):
        return False, "Another detach operation is in progress.", 0, []

    try:
        # Read manifest for cleanup decision
        manifest = get_backup_info(project_dir)

        # Clean up orphaned database files that may have been recreated
        # by the UI/API accessing the detached project
        if manifest:
            cleaned = _cleanup_orphaned_db_files(project_dir, manifest)
            if cleaned:
                logger.info(f"Cleaned up {len(cleaned)} orphaned files before restore: {cleaned}")

        success, files_restored, conflicts = restore_backup(project_dir)
        if success:
            if conflicts:
                return True, f"Restored {files_restored} files. {len(conflicts)} user files saved to {PRE_REATTACH_BACKUP_DIR}/", files_restored, conflicts
            return True, f"Restored {files_restored} files from backup", files_restored, []
        else:
            return False, "Failed to restore backup", 0, []
    finally:
        release_detach_lock(project_dir)


def get_detach_status(name_or_path: str) -> dict:
    """
    Get detach status for a project.

    Args:
        name_or_path: Project name (from registry) or absolute path

    Returns:
        Dict with status information including:
        - state: "detached", "attached", "inconsistent", or "clean"
        - is_detached: True if cleanly detached
        - is_inconsistent: True if both manifest and files exist
        - files_at_root: Number of AutoForge files at project root
        - backup_exists: True if backup directory exists
    """
    project_dir = get_project_path(name_or_path)
    if project_dir is None:
        project_dir = Path(name_or_path)
        if not project_dir.exists():
            return {
                "state": "error",
                "is_detached": False,
                "is_inconsistent": False,
                "files_at_root": 0,
                "backup_exists": False,
                "error": f"Project '{name_or_path}' not found",
            }

    project_dir = Path(project_dir).resolve()
    state, files = get_project_detach_state(project_dir)
    backup_dir = project_dir / BACKUP_DIR
    manifest = get_backup_info(project_dir) if backup_dir.exists() else None

    return {
        "state": state,
        "is_detached": state == "detached",
        "is_inconsistent": state == "inconsistent",
        "files_at_root": len(files),
        "backup_exists": backup_dir.exists(),
        "backup_size": manifest["total_size_bytes"] if manifest else None,
        "detached_at": manifest["detached_at"] if manifest else None,
        "file_count": manifest["file_count"] if manifest else None,
    }


def list_projects_with_status() -> list[dict]:
    """
    List all registered projects with their detach status.

    Returns:
        List of project dicts with name, path, and is_detached
    """
    projects = list_registered_projects()
    result = []

    for name, info in projects.items():
        project_dir = Path(info["path"])
        if project_dir.exists():
            result.append({
                "name": name,
                "path": info["path"],
                "is_detached": is_project_detached(project_dir),
            })

    return sorted(result, key=lambda p: p["name"])


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Detach/Reattach AutoForge files from projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python detach.py my-project              # Detach project
  python detach.py --reattach my-project   # Reattach project
  python detach.py --status my-project     # Check status
  python detach.py --list                  # List all projects with status
  python detach.py --dry-run my-project    # Preview detach operation
        """,
    )

    parser.add_argument(
        "project",
        nargs="?",
        help="Project name (from registry) or path",
    )
    parser.add_argument(
        "--reattach",
        action="store_true",
        help="Reattach project (restore files from backup)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show detach status for project",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all projects with detach status",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would happen without making changes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmations and safety checks",
    )

    # Mutually exclusive artifact options
    artifact_group = parser.add_mutually_exclusive_group()
    artifact_group.add_argument(
        "--include-artifacts",
        dest="include_artifacts",
        action="store_true",
        default=True,
        help="Include artifacts (.playwright-mcp, screenshots) in backup (default)",
    )
    artifact_group.add_argument(
        "--no-artifacts",
        dest="include_artifacts",
        action="store_false",
        help="Exclude artifacts from backup",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        return e.code if e.code else 0

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        # Handle --list
        if args.list:
            projects = list_projects_with_status()
            if not projects:
                print("No projects registered.")
                return 0

            print("\nRegistered Projects:")
            print("-" * 60)
            for p in projects:
                status_text = "DETACHED" if p["is_detached"] else "attached"
                print(f"  [{status_text:8}] {p['name']}")
                print(f"            {p['path']}")
            print()
            return 0

        # All other commands require a project
        if not args.project:
            parser.print_help()
            return 1

        # Handle --status
        if args.status:
            status_info = get_detach_status(args.project)
            if "error" in status_info:
                print(f"Error: {status_info['error']}")
                return 1

            print(f"\nProject: {args.project}")
            print("-" * 40)
            state = status_info.get("state", "unknown")
            if state == "detached":
                print("  Status: DETACHED")
                print(f"  Detached at: {status_info['detached_at']}")
                backup_size = status_info['backup_size']
                if backup_size is not None:
                    print(f"  Backup size: {backup_size / 1024 / 1024:.1f} MB")
                print(f"  Files in backup: {status_info['file_count']}")
            elif state == "inconsistent":
                print("  Status: INCONSISTENT (needs cleanup)")
                print(f"  Files at root: {status_info['files_at_root']}")
                print("  Backup manifest exists but AutoForge files also present.")
                print("  Use --force to clean up and detach.")
            elif state == "attached":
                print("  Status: attached (AutoForge files present)")
                print(f"  Files at root: {status_info['files_at_root']}")
            else:
                print("  Status: clean (no AutoForge files)")
            print()
            return 0

        # Handle --reattach
        if args.reattach:
            print(f"\nReattaching project: {args.project}")
            success, message, files_restored, conflicts = reattach_project(args.project)
            print(f"  {message}")
            if conflicts:
                print(f"  ⚠ {len(conflicts)} user files backed up to {PRE_REATTACH_BACKUP_DIR}/")
                for f in conflicts[:5]:
                    print(f"      - {f}")
                if len(conflicts) > 5:
                    print(f"      ... and {len(conflicts) - 5} more")
            return 0 if success else 1

        # Handle detach (default)
        if args.dry_run:
            print(f"\nDRY RUN - Previewing detach for: {args.project}")
        else:
            print(f"\nDetaching project: {args.project}")

        success, message, manifest, user_files_restored = detach_project(
            args.project,
            force=args.force,
            include_artifacts=args.include_artifacts,
            dry_run=args.dry_run,
        )

        print(f"  {message}")
        if user_files_restored > 0:
            print(f"  ✓ Restored {user_files_restored} user files from previous session")

        if manifest and args.dry_run:
            print("\n  Files to be moved:")
            for entry in manifest["files"]:
                size_str = f"{entry['size'] / 1024:.1f} KB"
                if entry["type"] == "directory":
                    print(f"    [DIR] {entry['path']} ({entry['file_count']} files, {size_str})")
                else:
                    print(f"    [FILE] {entry['path']} ({size_str})")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\nOperation cancelled.")
        return 130  # Standard exit code for Ctrl+C


if __name__ == "__main__":
    sys.exit(main())
