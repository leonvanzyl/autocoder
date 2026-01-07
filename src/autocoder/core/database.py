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
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager

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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Features table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    status TEXT DEFAULT 'pending',
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

                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
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

                    FOREIGN KEY (feature_id) REFERENCES features(id)
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

    # ============================================================================
    # Feature Operations
    # ============================================================================

    def create_feature(
        self,
        name: str,
        description: str,
        category: str,
        priority: int = 0
    ) -> int:
        """Create a new feature and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO features (name, description, category, priority)
                VALUES (?, ?, ?, ?)
            """, (name, description, category, priority))
            conn.commit()
            return cursor.lastrowid

    def get_feature(self, feature_id: int) -> Optional[Dict[str, Any]]:
        """Get a feature by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM features WHERE id = ?", (feature_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_features_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all features with a specific status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM features WHERE status = ? ORDER BY priority DESC, id ASC",
                (status,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_next_pending_feature(self) -> Optional[Dict[str, Any]]:
        """Get the highest-priority pending feature."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM features
                WHERE status = 'pending'
                ORDER BY priority DESC, id ASC
                LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None

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

            # Use row locking to prevent race conditions
            cursor.execute("""
                SELECT id FROM features
                WHERE id = ? AND status = 'pending'
                FOR UPDATE
            """, (feature_id,))

            row = cursor.fetchone()
            if not row:
                return False  # Feature already claimed or doesn't exist

            # Claim the feature
            cursor.execute("""
                UPDATE features
                SET status = 'in_progress',
                    assigned_agent_id = ?,
                    assigned_at = CURRENT_TIMESTAMP,
                    branch_name = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (agent_id, branch_name, feature_id))

            conn.commit()
            return True

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

            # Claim features one by one with row locking
            for i in range(count):
                cursor.execute("""
                    SELECT id FROM features
                    WHERE status = 'pending'
                    ORDER BY priority DESC, id ASC
                    LIMIT 1
                    FOR UPDATE
                """)

                row = cursor.fetchone()
                if not row:
                    break  # No more pending features

                feature_id = row[0]
                branch_name = branch_names[i] if i < len(branch_names) else f"feat/{feature_id}"

                cursor.execute("""
                    UPDATE features
                    SET status = 'in_progress',
                        assigned_agent_id = ?,
                        assigned_at = CURRENT_TIMESTAMP,
                        branch_name = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (agent_id, branch_name, feature_id))

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
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE features
                SET status = ?,
                    review_status = COALESCE(?, review_status),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, review_status, feature_id))
            conn.commit()
            return cursor.rowcount > 0

    def mark_feature_passing(self, feature_id: int) -> bool:
        """Mark a feature as passing (complete)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE features
                SET status = 'done',
                    passes = TRUE,
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (feature_id,))
            conn.commit()
            return cursor.rowcount > 0

    def mark_feature_failed(
        self,
        feature_id: int,
        reason: str
    ) -> bool:
        """Mark a feature as failed (reset for retry)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE features
                SET status = 'pending',
                    assigned_agent_id = NULL,
                    assigned_at = NULL,
                    branch_name = NULL,
                    attempts = attempts + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
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
        feature_id: Optional[int] = None
    ) -> bool:
        """Register an agent as active."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_heartbeats (agent_id, pid, worktree_path, feature_id)
                VALUES (?, ?, ?, ?)
            """, (agent_id, pid, worktree_path, feature_id))
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
                WHERE last_ping < datetime('now', '-' || ? || ' minutes')
                ORDER BY last_ping ASC
            """, (timeout_minutes,))
            return [dict(row) for row in cursor.fetchall()]

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

            # Feature counts
            cursor.execute("SELECT COUNT(*) FROM features WHERE status = 'pending'")
            pending = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM features WHERE status = 'in_progress'")
            in_progress = cursor.fetchone()[0]

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
