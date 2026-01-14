"""
Database Wrapper - Feature and Agent Heartbeat Tracking
========================================================

SQLite wrapper for tracking:
- Feature status and assignment
- Agent heartbeats (crash detection)
- Branch tracking
- Review status

This is the single source of truth for the orchestrator.
"""

import sqlite3
import json
import logging
import os
import random
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, UTC
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)


class Database:
    """
    Database wrapper for autonomous coding system.

    Tracks features, agents, heartbeats, and branches.
    """

    def __init__(self, db_path: str):
        """
        Initialize the database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).resolve()
        self._init_schema()
        logger.info(f"Database initialized: {self.db_path}")

    @contextmanager
    def get_connection(self):
        """Get a database connection with context manager."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA busy_timeout = 10000")
        except sqlite3.OperationalError:
            # Some pragmas may be unsupported in constrained environments; best-effort only.
            pass
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Pragmas for better concurrency under multiple processes.
            # (Safe to run repeatedly; journal_mode is persistent for the DB file.)
            try:
                cursor.execute("PRAGMA journal_mode = WAL")
                cursor.execute("PRAGMA synchronous = NORMAL")
                cursor.execute("PRAGMA busy_timeout = 10000")
                cursor.execute("PRAGMA foreign_keys = ON")
            except sqlite3.OperationalError:
                pass

            # Features table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    steps TEXT,
                    category TEXT,
                    status TEXT DEFAULT 'PENDING',
                    priority INTEGER DEFAULT 0,

                    -- Agent assignment
                    assigned_agent_id TEXT,
                    assigned_at TIMESTAMP,

                    -- Branch tracking
                    branch_name TEXT,

                    -- Review status
                    review_status TEXT DEFAULT 'PENDING',

                    -- Completion
                    passes BOOLEAN DEFAULT FALSE,
                    completed_at TIMESTAMP,

                    -- Attempts
                    attempts INTEGER DEFAULT 0,
                    last_error TEXT,
                    next_attempt_at TIMESTAMP,
                    last_error_key TEXT,
                    same_error_streak INTEGER DEFAULT 0,
                    last_artifact_path TEXT,

                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migration: Add steps column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE features ADD COLUMN steps TEXT")
                logger.info("Added steps column to existing features table")
            except sqlite3.OperationalError:
                # Column already exists (or table just created with it)
                pass

            # Migration: Add last_error column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE features ADD COLUMN last_error TEXT")
                logger.info("Added last_error column to existing features table")
            except sqlite3.OperationalError:
                pass

            # Migration: Add next_attempt_at column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE features ADD COLUMN next_attempt_at TIMESTAMP")
                logger.info("Added next_attempt_at column to existing features table")
            except sqlite3.OperationalError:
                pass

            # Migration: Add last_error_key column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE features ADD COLUMN last_error_key TEXT")
                logger.info("Added last_error_key column to existing features table")
            except sqlite3.OperationalError:
                pass

            # Migration: Add same_error_streak column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE features ADD COLUMN same_error_streak INTEGER")
                logger.info("Added same_error_streak column to existing features table")
            except sqlite3.OperationalError:
                pass

            # Migration: Add last_artifact_path column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE features ADD COLUMN last_artifact_path TEXT")
                logger.info("Added last_artifact_path column to existing features table")
            except sqlite3.OperationalError:
                pass

            # Migration: Add port columns to agent_heartbeats if they don't exist
            try:
                cursor.execute("ALTER TABLE agent_heartbeats ADD COLUMN api_port INTEGER")
                logger.info("Added api_port column to existing agent_heartbeats table")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE agent_heartbeats ADD COLUMN web_port INTEGER")
                logger.info("Added web_port column to existing agent_heartbeats table")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE agent_heartbeats ADD COLUMN log_file_path TEXT")
                logger.info("Added log_file_path column to existing agent_heartbeats table")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Migration: Normalize legacy lowercase statuses to uppercase
            cursor.execute("""
                UPDATE features
                SET status = UPPER(status)
                WHERE status IS NOT NULL AND status != UPPER(status)
            """)

            # Agent heartbeats table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_heartbeats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'ACTIVE',

                    -- Worktree tracking
                    worktree_path TEXT,
                    feature_id INTEGER,

                    -- Process tracking
                    pid INTEGER,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Port allocation
                    api_port INTEGER,
                    web_port INTEGER,

                    -- Logging/diagnostics
                    log_file_path TEXT,

                    FOREIGN KEY (feature_id) REFERENCES features(id)
                )
            """)

            # Feature dependencies (DAG edges)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feature_dependencies (
                    feature_id INTEGER NOT NULL,
                    depends_on_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (feature_id, depends_on_id),
                    FOREIGN KEY (feature_id) REFERENCES features(id) ON DELETE CASCADE,
                    FOREIGN KEY (depends_on_id) REFERENCES features(id) ON DELETE CASCADE
                )
            """)

            # Branches table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS branches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch_name TEXT NOT NULL UNIQUE,
                    feature_id INTEGER NOT NULL,
                    agent_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    merged_at TIMESTAMP,
                    commit_hash TEXT,

                    FOREIGN KEY (feature_id) REFERENCES features(id)
                )
            """)

            # Knowledge base patterns table (optional, for tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature_id INTEGER NOT NULL,

                    -- Feature info
                    category TEXT,
                    feature_name TEXT,
                    feature_description TEXT,

                    -- Implementation
                    approach TEXT,
                    files_changed TEXT,

                    -- Results
                    model_used TEXT,
                    success BOOLEAN,
                    attempts INTEGER,
                    lessons_learned TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (feature_id) REFERENCES features(id)
                )
            """)

            # Indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_features_status
                ON features(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_features_next_attempt_at
                ON features(next_attempt_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feature_dependencies_depends_on
                ON feature_dependencies(depends_on_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_features_review_status
                ON features(review_status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_agent_id
                ON agent_heartbeats(agent_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_last_ping
                ON agent_heartbeats(last_ping)
            """)

            conn.commit()

    def _max_feature_attempts(self) -> int:
        raw = os.environ.get("AUTOCODER_FEATURE_MAX_ATTEMPTS")
        try:
            v = int(raw) if raw is not None else 0
        except Exception:
            v = 0
        return v if v > 0 else 10

    def _max_same_error_streak(self) -> int:
        raw = os.environ.get("AUTOCODER_FEATURE_MAX_SAME_ERROR_STREAK")
        try:
            v = int(raw) if raw is not None else 0
        except Exception:
            v = 0
        return v if v > 0 else 3

    def _error_key(self, reason: str) -> str:
        """
        Normalize an error reason into a stable key for no-progress detection.

        Goals:
        - Ignore volatile paths (gatekeeper artifact filenames).
        - Ignore incidental whitespace/line wrapping.
        """
        s = (reason or "").replace("\r\n", "\n")
        lines = []
        for ln in s.splitlines():
            if ln.strip().lower().startswith("artifact:"):
                continue
            lines.append(ln)
        s = "\n".join(lines).strip()
        s = re.sub(r"[ \t]+", " ", s)
        # Collapse multiple blank lines.
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s[:4000]

    def _next_retry_delay_s(self, attempts: int) -> int:
        """
        Compute retry delay after `attempts` failures (attempts starts at 1).

        Env knobs:
        - AUTOCODER_FEATURE_RETRY_INITIAL_DELAY_S (default 10)
        - AUTOCODER_FEATURE_RETRY_MAX_DELAY_S (default 600)
        - AUTOCODER_FEATURE_RETRY_EXPONENTIAL_BASE (default 2)
        - AUTOCODER_FEATURE_RETRY_JITTER (default true)
        """
        def _int_env(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, str(default)))
            except Exception:
                return default

        initial = max(0, _int_env("AUTOCODER_FEATURE_RETRY_INITIAL_DELAY_S", 10))
        max_delay = max(0, _int_env("AUTOCODER_FEATURE_RETRY_MAX_DELAY_S", 600))
        base = max(1, _int_env("AUTOCODER_FEATURE_RETRY_EXPONENTIAL_BASE", 2))
        jitter_raw = str(os.environ.get("AUTOCODER_FEATURE_RETRY_JITTER", "true")).strip().lower()
        jitter = jitter_raw not in {"0", "false", "no", "off"}

        if initial <= 0:
            return 0
        exp = max(0, attempts - 1)
        delay = initial * (base**exp)
        delay = min(delay, max_delay) if max_delay > 0 else delay

        if jitter and delay > 1:
            delay = int(max(0, round(delay * random.uniform(0.7, 1.3))))
        return int(delay)

    def _get_depends_on(self, conn: sqlite3.Connection, feature_id: int) -> List[int]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT depends_on_id FROM feature_dependencies WHERE feature_id = ? ORDER BY depends_on_id ASC",
            (feature_id,),
        )
        return [int(r[0]) for r in cursor.fetchall()]

    # ============================================================================
    # Feature Operations
    # ============================================================================

    def create_feature(
        self,
        name: str,
        description: str,
        category: str,
        steps: Optional[str] = None,
        priority: int = 0,
        *,
        depends_on: Optional[List[int]] = None,
    ) -> int:
        """Create a new feature and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO features (name, description, category, steps, priority, status)
                VALUES (?, ?, ?, ?, ?, 'PENDING')
            """, (name, description, category, steps, priority))
            feature_id = int(cursor.lastrowid)
            if depends_on:
                cursor.executemany(
                    "INSERT OR IGNORE INTO feature_dependencies (feature_id, depends_on_id) VALUES (?, ?)",
                    [(feature_id, int(dep)) for dep in depends_on],
                )
            conn.commit()
            return feature_id

    def create_features_bulk(
        self,
        features: List[Dict[str, Any]]
    ) -> int:
        """
        Create multiple features in a single transaction.

        Args:
            features: List of feature dicts with keys: name, description, category, steps, priority

        Returns:
            Number of features created
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO features (name, description, category, steps, priority, status)
                VALUES (?, ?, ?, ?, ?, 'PENDING')
            """, [
                (
                    f.get("name"),
                    f.get("description"),
                    f.get("category"),
                    json.dumps(f.get("steps")) if f.get("steps") else None,
                    f.get("priority", 0)
                )
                for f in features
            ])
            conn.commit()
            return cursor.rowcount

    def get_feature(self, feature_id: int) -> Optional[Dict[str, Any]]:
        """Get a feature by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM features WHERE id = ?", (feature_id,))
            row = cursor.fetchone()
            if not row:
                return None
            out = dict(row)
            out["depends_on"] = self._get_depends_on(conn, int(out["id"]))
            return out

    def get_features_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all features with a specific status."""
        normalized = status.upper() if status else status
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM features WHERE status = ? ORDER BY priority DESC, id ASC",
                (normalized,)
            )
            out: list[dict[str, Any]] = [dict(row) for row in cursor.fetchall()]
            for r in out:
                r["depends_on"] = self._get_depends_on(conn, int(r["id"]))
            return out

    def get_next_pending_feature(self) -> Optional[Dict[str, Any]]:
        """Get the highest-priority pending feature."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT f.* FROM features f
                WHERE f.status = 'PENDING'
                  AND (f.next_attempt_at IS NULL OR f.next_attempt_at <= CURRENT_TIMESTAMP)
                  AND NOT EXISTS (
                    SELECT 1
                    FROM feature_dependencies d
                    JOIN features dep ON dep.id = d.depends_on_id
                    WHERE d.feature_id = f.id AND dep.status != 'DONE'
                  )
                ORDER BY f.priority DESC, f.id ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None
            out = dict(row)
            out["depends_on"] = self._get_depends_on(conn, int(out["id"]))
            return out

    def claim_next_pending_feature(
        self,
        agent_id: str,
        *,
        branch_prefix: str = "feat",
        max_attempts: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """
        Atomically claim the next pending feature.

        This is safe under concurrency: it uses an UPDATE gated by status='PENDING'
        and retries if another agent wins the race.
        """
        if not agent_id:
            raise ValueError("agent_id is required to claim a feature")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            for _ in range(max_attempts):
                cursor.execute(
                    """
                    SELECT f.id FROM features f
                    WHERE f.status = 'PENDING'
                      AND (f.next_attempt_at IS NULL OR f.next_attempt_at <= CURRENT_TIMESTAMP)
                      AND NOT EXISTS (
                        SELECT 1
                        FROM feature_dependencies d
                        JOIN features dep ON dep.id = d.depends_on_id
                        WHERE d.feature_id = f.id AND dep.status != 'DONE'
                      )
                    ORDER BY f.priority DESC, f.id ASC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if not row:
                    return None

                feature_id = int(row[0])
                branch_name = f"{branch_prefix}/{feature_id}-{int(time.time())}"

                cursor.execute("""
                    UPDATE features
                    SET status = 'IN_PROGRESS',
                        assigned_agent_id = ?,
                        assigned_at = CURRENT_TIMESTAMP,
                        branch_name = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'PENDING'
                """, (agent_id, branch_name, feature_id))

                if cursor.rowcount > 0:
                    conn.commit()
                    return self.get_feature(feature_id)

            return None

    def add_dependency_to_all_pending(self, depends_on_id: int, *, exclude_ids: Optional[List[int]] = None) -> int:
        """
        Add a dependency edge (depends_on_id) to all currently pending features.

        Returns number of edges inserted (ignoring duplicates).
        """
        excludes = set(int(x) for x in (exclude_ids or []))
        excludes.add(int(depends_on_id))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if excludes:
                placeholders = ",".join(["?"] * len(excludes))
                sql = (
                    "INSERT OR IGNORE INTO feature_dependencies (feature_id, depends_on_id) "
                    f"SELECT id, ? FROM features WHERE status = 'PENDING' AND id NOT IN ({placeholders})"
                )
                params = [int(depends_on_id), *sorted(excludes)]
                cursor.execute(sql, params)
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO feature_dependencies (feature_id, depends_on_id) "
                    "SELECT id, ? FROM features WHERE status = 'PENDING'",
                    (int(depends_on_id),),
                )
            conn.commit()
            return int(cursor.rowcount if cursor.rowcount is not None else 0)

    def get_passing_features_for_regression(
        self,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get random passing features for regression testing.

        Args:
            limit: Maximum number of features to return

        Returns:
            List of passing features (randomly selected)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM features
                WHERE passes = TRUE AND status = 'DONE'
                ORDER BY RANDOM()
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def claim_feature(
        self,
        feature_id: int,
        agent_id: str,
        branch_name: str
    ) -> bool:
        """
        Claim a feature for an agent.

        Atomically claims the feature (with row locking to prevent race conditions).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE features
                SET status = 'IN_PROGRESS',
                    assigned_agent_id = ?,
                    assigned_at = CURRENT_TIMESTAMP,
                    branch_name = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'PENDING'
            """, (agent_id, branch_name, feature_id))

            conn.commit()
            return cursor.rowcount > 0

    def claim_batch(
        self,
        count: int,
        agent_id: str,
        branch_names: List[str]
    ) -> List[int]:
        """
        Claim multiple features atomically.

        Args:
            count: Number of features to claim
            agent_id: Agent claiming the features
            branch_names: List of branch names (one per feature)

        Returns:
            List of claimed feature IDs
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            claimed_ids = []

            # Claim features one by one (transaction provides locking)
            for i in range(count):
                cursor.execute("""
                    SELECT id FROM features
                    WHERE status = 'PENDING'
                    ORDER BY priority DESC, id ASC
                    LIMIT 1
                """)

                row = cursor.fetchone()
                if not row:
                    break  # No more pending features

                feature_id = row[0]
                branch_name = branch_names[i] if i < len(branch_names) else f"feat/{feature_id}"

                cursor.execute("""
                    UPDATE features
                    SET status = 'IN_PROGRESS',
                        assigned_agent_id = ?,
                        assigned_at = CURRENT_TIMESTAMP,
                        branch_name = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'PENDING'
                """, (agent_id, branch_name, feature_id))

                if cursor.rowcount > 0:
                    claimed_ids.append(feature_id)

            conn.commit()
            return claimed_ids

    def update_feature_status(
        self,
        feature_id: int,
        status: str,
        review_status: Optional[str] = None
    ) -> bool:
        """Update feature status."""
        normalized_status = status.upper() if status else status
        normalized_review_status = review_status.upper() if review_status else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE features
                SET status = ?,
                    review_status = COALESCE(?, review_status),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (normalized_status, normalized_review_status, feature_id))
            conn.commit()
            return cursor.rowcount > 0

    def mark_feature_passing(self, feature_id: int) -> bool:
        """Mark a feature as passing (complete)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE features
                SET status = 'DONE',
                    passes = TRUE,
                    review_status = 'VERIFIED',
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (feature_id,))
            conn.commit()
            return cursor.rowcount > 0

    def mark_feature_ready_for_verification(self, feature_id: int) -> bool:
        """
        Mark a feature as ready for deterministic verification (Gatekeeper).

        Parallel workers should call this instead of directly setting `passes = TRUE`.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE features
                SET status = 'IN_PROGRESS',
                    passes = FALSE,
                    review_status = 'READY_FOR_VERIFICATION',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (feature_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_feature_failed(
        self,
        feature_id: int,
        reason: str,
        *,
        artifact_path: str | None = None,
    ) -> bool:
        """Mark a feature as failed (reset for retry)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT attempts, last_error_key, same_error_streak FROM features WHERE id = ?",
                (feature_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            prev_attempts = int(row[0] or 0)
            prev_key = str(row[1] or "")
            prev_streak = int(row[2] or 0)
            new_attempts = prev_attempts + 1
            max_attempts = self._max_feature_attempts()
            max_streak = self._max_same_error_streak()

            # Derive artifact path from the reason if not provided.
            derived_artifact: str | None = None
            if not artifact_path:
                for ln in (reason or "").splitlines():
                    if ln.strip().lower().startswith("artifact:"):
                        derived_artifact = ln.split(":", 1)[1].strip() or None
                        break
            artifact_path = artifact_path or derived_artifact

            new_key = self._error_key(reason)
            if new_key and new_key == prev_key:
                streak = prev_streak + 1
            else:
                streak = 1 if new_key else 0

            blocked = (new_attempts >= max_attempts) or (streak >= max_streak and max_streak > 0)

            next_attempt_at = None
            if not blocked:
                delay_s = self._next_retry_delay_s(new_attempts)
                if delay_s > 0:
                    now_utc = datetime.now(UTC).replace(tzinfo=None)
                    next_attempt_at = (now_utc + timedelta(seconds=delay_s)).isoformat(sep=" ")

            cursor.execute(
                """
                UPDATE features
                SET status = ?,
                    assigned_agent_id = NULL,
                    assigned_at = NULL,
                    branch_name = NULL,
                    review_status = 'PENDING',
                    passes = FALSE,
                    completed_at = NULL,
                    attempts = ?,
                    last_error = ?,
                    next_attempt_at = ?,
                    last_error_key = ?,
                    same_error_streak = ?,
                    last_artifact_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    "BLOCKED" if blocked else "PENDING",
                    new_attempts,
                    reason,
                    next_attempt_at,
                    new_key,
                    streak,
                    artifact_path,
                    feature_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear_feature_in_progress(self, feature_id: int) -> bool:
        """Clear an in-progress feature back to pending without counting an attempt."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE features
                SET status = 'PENDING',
                    assigned_agent_id = NULL,
                    assigned_at = NULL,
                    branch_name = NULL,
                    review_status = NULL,
                    passes = FALSE,
                    completed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'IN_PROGRESS'
            """, (feature_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ============================================================================
    # Agent Heartbeat Operations
    # ============================================================================

    def register_agent(
        self,
        agent_id: str,
        pid: Optional[int] = None,
        worktree_path: Optional[str] = None,
        feature_id: Optional[int] = None,
        api_port: Optional[int] = None,
        web_port: Optional[int] = None,
        log_file_path: Optional[str] = None,
    ) -> bool:
        """Register an agent as active."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_heartbeats (
                    agent_id, pid, worktree_path, feature_id, api_port, web_port, log_file_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (agent_id, pid, worktree_path, feature_id, api_port, web_port, log_file_path))
            conn.commit()
            return True

    def update_heartbeat(self, agent_id: str) -> bool:
        """Update an agent's heartbeat (called periodically by agent)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE agent_heartbeats
                SET last_ping = CURRENT_TIMESTAMP,
                    status = 'ACTIVE'
                WHERE agent_id = ?
            """, (agent_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_agent_heartbeat(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get an agent's heartbeat record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_heartbeats WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_stale_agents(self, timeout_minutes: int = 10) -> List[Dict[str, Any]]:
        """
        Get agents that haven't pinged recently (potential crashes).

        Args:
            timeout_minutes: Minutes of inactivity before considering stale

        Returns:
            List of stale agent records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM agent_heartbeats
                WHERE status = 'ACTIVE'
                  AND last_ping < datetime('now', '-' || ? || ' minutes')
                ORDER BY last_ping ASC
            """, (timeout_minutes,))
            return [dict(row) for row in cursor.fetchall()]

    def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get active agents (used for port bootstrapping on orchestrator startup)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM agent_heartbeats
                WHERE status = 'ACTIVE'
                ORDER BY last_ping ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_completed_agents(self) -> List[Dict[str, Any]]:
        """
        Get agents that have completed successfully.

        Returns:
            List of completed agent records with port allocations
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM agent_heartbeats
                WHERE status = 'COMPLETED'
                  AND (api_port IS NOT NULL OR web_port IS NOT NULL)
                ORDER BY last_ping ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def mark_agent_completed(self, agent_id: str) -> bool:
        """Mark an agent as completed (no longer eligible for stale/crash detection)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE agent_heartbeats
                SET last_ping = CURRENT_TIMESTAMP,
                    status = 'COMPLETED'
                WHERE agent_id = ?
            """, (agent_id,))
            conn.commit()
            return cursor.rowcount > 0

    def mark_agent_crashed(self, agent_id: str) -> bool:
        """Mark an agent as crashed."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE agent_heartbeats
                SET status = 'CRASHED',
                    last_ping = CURRENT_TIMESTAMP
                WHERE agent_id = ?
            """, (agent_id,))
            conn.commit()
            return cursor.rowcount > 0

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the heartbeat table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM agent_heartbeats WHERE agent_id = ?", (agent_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ============================================================================
    # Branch Operations
    # ============================================================================

    def create_branch(
        self,
        branch_name: str,
        feature_id: int,
        agent_id: str
    ) -> bool:
        """Register a branch."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO branches (branch_name, feature_id, agent_id)
                VALUES (?, ?, ?)
            """, (branch_name, feature_id, agent_id))
            conn.commit()
            return True

    def mark_branch_merged(self, branch_name: str, commit_hash: str) -> bool:
        """Mark a branch as merged."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE branches
                SET merged_at = CURRENT_TIMESTAMP,
                    commit_hash = ?
                WHERE branch_name = ?
            """, (commit_hash, branch_name))
            conn.commit()
            return cursor.rowcount > 0

    # ============================================================================
    # Statistics
    # ============================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get overall system statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Feature counts (use uppercase status values)
            cursor.execute("SELECT COUNT(*) FROM features WHERE status = 'PENDING'")
            pending = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM features WHERE status = 'IN_PROGRESS'")
            in_progress = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM features WHERE review_status = 'READY_FOR_VERIFICATION'"
            )
            ready_for_verification = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM features WHERE passes = TRUE")
            completed = cursor.fetchone()[0]

            # Agent counts
            cursor.execute("SELECT COUNT(*) FROM agent_heartbeats WHERE status = 'ACTIVE'")
            active_agents = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM agent_heartbeats WHERE status = 'CRASHED'")
            crashed_agents = cursor.fetchone()[0]

            return {
                "features": {
                    "pending": pending,
                    "in_progress": in_progress,
                    "ready_for_verification": ready_for_verification,
                    "completed": completed,
                    "total": pending + in_progress + completed
                },
                "agents": {
                    "active": active_agents,
                    "crashed": crashed_agents,
                    "total": active_agents + crashed_agents
                }
            }

    def get_progress(self) -> Dict[str, Any]:
        """Get progress percentage."""
        stats = self.get_stats()
        total = stats["features"]["total"]
        completed = stats["features"]["completed"]

        if total == 0:
            return {"percentage": 0, "passing": completed, "total": total}

        percentage = round((completed / total) * 100, 1)
        return {
            "percentage": percentage,
            "passing": completed,
            "total": total
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def get_database(project_dir: str) -> Database:
    """
    Get the database instance for a project.

    Args:
        project_dir: Path to project directory

    Returns:
        Database instance
    """
    db_path = Path(project_dir) / "agent_system.db"
    return Database(str(db_path))


def init_database(project_dir: str) -> Database:
    """
    Initialize the database for a project (create if needed).

    Args:
        project_dir: Path to project directory

    Returns:
        Database instance
    """
    return get_database(project_dir)


if __name__ == "__main__":
    # Test the database
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db = init_database(tmpdir)

        # Create a test feature
        feature_id = db.create_feature(
            name="User Authentication",
            description="JWT-based login system",
            category="backend",
            priority=10
        )

        print(f"Created feature #{feature_id}")

        # Claim it
        success = db.claim_feature(
            feature_id=feature_id,
            agent_id="agent-1",
            branch_name="feat/user-auth-001"
        )

        print(f"Claim feature: {success}")

        # Register agent
        db.register_agent("agent-1", pid=12345)

        # Update heartbeat
        db.update_heartbeat("agent-1")

        # Get stats
        stats = db.get_stats()
        print(f"Stats: {json.dumps(stats, indent=2)}")

        print("✅ Database test passed!")
