"""
AutoForge Path Resolution
=========================

Central module for resolving paths to autoforge-generated files within a project.

Implements a tri-path resolution strategy for backward compatibility:

    1. Check ``project_dir / ".autoforge" / X`` (current layout)
    2. Check ``project_dir / ".autocoder" / X`` (legacy layout)
    3. Check ``project_dir / X`` (legacy root-level layout)
    4. Default to the new location for fresh projects

This allows existing projects with root-level ``features.db``, ``.agent.lock``,
etc. to keep working while new projects store everything under ``.autoforge/``.
Projects using the old ``.autocoder/`` directory are auto-migrated on next start.

The ``migrate_project_layout`` function can move an old-layout project to the
new layout safely, with full integrity checks for SQLite databases.
"""

import logging
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# .gitignore content written into every .autoforge/ directory
# ---------------------------------------------------------------------------
_GITIGNORE_CONTENT = """\
# AutoForge runtime files
features.db
features.db-wal
features.db-shm
assistant.db
assistant.db-wal
assistant.db-shm
.agent.lock
.devserver.lock
.pause_drain
.claude_settings.json
.claude_assistant_settings.json
.claude_settings.expand.*.json
.progress_cache
.migration_version
"""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_path(project_dir: Path, filename: str) -> Path:
    """Resolve a file path using tri-path strategy.

    Checks the new ``.autoforge/`` location first, then the legacy
    ``.autocoder/`` location, then the root-level location.  If none exist,
    returns the new location so that newly-created files land in ``.autoforge/``.
    """
    new = project_dir / ".autoforge" / filename
    if new.exists():
        return new
    legacy = project_dir / ".autocoder" / filename
    if legacy.exists():
        return legacy
    old = project_dir / filename
    if old.exists():
        return old
    return new  # default for new projects


def _resolve_dir(project_dir: Path, dirname: str) -> Path:
    """Resolve a directory path using tri-path strategy.

    Same logic as ``_resolve_path`` but intended for directories such as
    ``prompts/``.
    """
    new = project_dir / ".autoforge" / dirname
    if new.exists():
        return new
    legacy = project_dir / ".autocoder" / dirname
    if legacy.exists():
        return legacy
    old = project_dir / dirname
    if old.exists():
        return old
    return new


# ---------------------------------------------------------------------------
# .autoforge directory management
# ---------------------------------------------------------------------------

def get_autoforge_dir(project_dir: Path) -> Path:
    """Return the ``.autoforge`` directory path.  Does NOT create it."""
    return project_dir / ".autoforge"


def ensure_autoforge_dir(project_dir: Path) -> Path:
    """Create the ``.autoforge/`` directory (if needed) and write its ``.gitignore``.

    Returns:
        The path to the ``.autoforge`` directory.
    """
    autoforge_dir = get_autoforge_dir(project_dir)
    autoforge_dir.mkdir(parents=True, exist_ok=True)

    gitignore_path = autoforge_dir / ".gitignore"
    gitignore_path.write_text(_GITIGNORE_CONTENT, encoding="utf-8")

    return autoforge_dir


# ---------------------------------------------------------------------------
# Dual-path file helpers
# ---------------------------------------------------------------------------

def get_features_db_path(project_dir: Path) -> Path:
    """Resolve the path to ``features.db``."""
    return _resolve_path(project_dir, "features.db")


def get_assistant_db_path(project_dir: Path) -> Path:
    """Resolve the path to ``assistant.db``."""
    return _resolve_path(project_dir, "assistant.db")


def get_agent_lock_path(project_dir: Path) -> Path:
    """Resolve the path to ``.agent.lock``."""
    return _resolve_path(project_dir, ".agent.lock")


def get_devserver_lock_path(project_dir: Path) -> Path:
    """Resolve the path to ``.devserver.lock``."""
    return _resolve_path(project_dir, ".devserver.lock")


def get_claude_settings_path(project_dir: Path) -> Path:
    """Resolve the path to ``.claude_settings.json``."""
    return _resolve_path(project_dir, ".claude_settings.json")


def get_claude_assistant_settings_path(project_dir: Path) -> Path:
    """Resolve the path to ``.claude_assistant_settings.json``."""
    return _resolve_path(project_dir, ".claude_assistant_settings.json")


def get_pause_drain_path(project_dir: Path) -> Path:
    """Return the path to the ``.pause_drain`` signal file.

    This file is created to request a graceful pause (drain mode).
    Always uses the new location since it's a transient signal file.
    """
    return project_dir / ".autoforge" / ".pause_drain"


def get_progress_cache_path(project_dir: Path) -> Path:
    """Resolve the path to ``.progress_cache``."""
    return _resolve_path(project_dir, ".progress_cache")


def get_prompts_dir(project_dir: Path) -> Path:
    """Resolve the path to the ``prompts/`` directory."""
    return _resolve_dir(project_dir, "prompts")


# ---------------------------------------------------------------------------
# Non-dual-path helpers (always use new location)
# ---------------------------------------------------------------------------

def get_expand_settings_path(project_dir: Path, uuid_hex: str) -> Path:
    """Return the path for an ephemeral expand-session settings file.

    These files are short-lived and always stored in ``.autoforge/``.
    """
    return project_dir / ".autoforge" / f".claude_settings.expand.{uuid_hex}.json"


# ---------------------------------------------------------------------------
# Lock-file safety check
# ---------------------------------------------------------------------------

def has_agent_running(project_dir: Path) -> bool:
    """Check whether any agent or dev-server lock file exists at either location.

    Inspects the legacy root-level paths, the old ``.autocoder/`` paths, and
    the new ``.autoforge/`` paths so that a running agent is detected
    regardless of project layout.

    Returns:
        ``True`` if any ``.agent.lock`` or ``.devserver.lock`` exists.
    """
    lock_names = (".agent.lock", ".devserver.lock")
    for name in lock_names:
        if (project_dir / name).exists():
            return True
        # Check both old and new directory names for backward compatibility
        if (project_dir / ".autocoder" / name).exists():
            return True
        if (project_dir / ".autoforge" / name).exists():
            return True
    return False


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate_project_layout(project_dir: Path) -> list[str]:
    """Migrate a project from the legacy root-level layout to ``.autoforge/``.

    The migration is incremental and safe:

    * If the agent is running (lock files present) the migration is skipped
      entirely to avoid corrupting in-use databases.
    * Each file/directory is migrated independently.  If any single step
      fails the error is logged and migration continues with the remaining
      items.  Partial migration is safe because the dual-path resolution
      strategy will find files at whichever location they ended up in.

    Returns:
        A list of human-readable descriptions of what was migrated, e.g.
        ``["prompts/ -> .autoforge/prompts/", "features.db -> .autoforge/features.db"]``.
        An empty list means nothing was migrated (either everything is
        already migrated, or the agent is running).
    """
    # Safety: refuse to migrate while an agent is running
    if has_agent_running(project_dir):
        logger.warning("Migration skipped: agent or dev-server is running for %s", project_dir)
        return []

    # --- 0. Migrate .autocoder/ → .autoforge/ directory -------------------
    old_autocoder_dir = project_dir / ".autocoder"
    new_autoforge_dir = project_dir / ".autoforge"
    if old_autocoder_dir.exists() and old_autocoder_dir.is_dir() and not new_autoforge_dir.exists():
        try:
            old_autocoder_dir.rename(new_autoforge_dir)
            logger.info("Migrated .autocoder/ -> .autoforge/")
            migrated: list[str] = [".autocoder/ -> .autoforge/"]
        except Exception:
            logger.warning("Failed to migrate .autocoder/ -> .autoforge/", exc_info=True)
            migrated = []
    else:
        migrated = []

    autoforge_dir = ensure_autoforge_dir(project_dir)

    # --- 1. Migrate prompts/ directory -----------------------------------
    try:
        old_prompts = project_dir / "prompts"
        new_prompts = autoforge_dir / "prompts"
        if old_prompts.exists() and old_prompts.is_dir() and not new_prompts.exists():
            shutil.copytree(str(old_prompts), str(new_prompts))
            shutil.rmtree(str(old_prompts))
            migrated.append("prompts/ -> .autoforge/prompts/")
            logger.info("Migrated prompts/ -> .autoforge/prompts/")
    except Exception:
        logger.warning("Failed to migrate prompts/ directory", exc_info=True)

    # --- 2. Migrate SQLite databases (features.db, assistant.db) ---------
    db_names = ("features.db", "assistant.db")
    for db_name in db_names:
        try:
            old_db = project_dir / db_name
            new_db = autoforge_dir / db_name
            if old_db.exists() and not new_db.exists():
                # Flush WAL to ensure all data is in the main database file
                conn = sqlite3.connect(str(old_db))
                try:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                finally:
                    conn.close()

                # Copy the main database file (WAL is now flushed)
                shutil.copy2(str(old_db), str(new_db))

                # Verify the copy is intact
                verify_conn = sqlite3.connect(str(new_db))
                try:
                    verify_cursor = verify_conn.cursor()
                    result = verify_cursor.execute("PRAGMA integrity_check").fetchone()
                    if result is None or result[0] != "ok":
                        logger.error(
                            "Integrity check failed for migrated %s: %s",
                            db_name, result,
                        )
                        # Remove the broken copy; old file stays in place
                        new_db.unlink(missing_ok=True)
                        continue
                finally:
                    verify_conn.close()

                # Remove old database files (.db, .db-wal, .db-shm)
                old_db.unlink(missing_ok=True)
                for suffix in ("-wal", "-shm"):
                    wal_file = project_dir / f"{db_name}{suffix}"
                    wal_file.unlink(missing_ok=True)

                migrated.append(f"{db_name} -> .autoforge/{db_name}")
                logger.info("Migrated %s -> .autoforge/%s", db_name, db_name)
        except Exception:
            logger.warning("Failed to migrate %s", db_name, exc_info=True)

    # --- 3. Migrate simple files -----------------------------------------
    simple_files = (
        ".agent.lock",
        ".devserver.lock",
        ".claude_settings.json",
        ".claude_assistant_settings.json",
        ".progress_cache",
    )
    for filename in simple_files:
        try:
            old_file = project_dir / filename
            new_file = autoforge_dir / filename
            if old_file.exists() and not new_file.exists():
                shutil.move(str(old_file), str(new_file))
                migrated.append(f"{filename} -> .autoforge/{filename}")
                logger.info("Migrated %s -> .autoforge/%s", filename, filename)
        except Exception:
            logger.warning("Failed to migrate %s", filename, exc_info=True)

    return migrated
