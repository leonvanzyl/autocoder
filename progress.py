"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying progress of the autonomous coding agent.
Uses direct SQLite access for database queries with robust connection handling.
"""

import json
import os
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from api.database import execute_with_retry, robust_db_connection

WEBHOOK_URL = os.environ.get("PROGRESS_N8N_WEBHOOK_URL")
PROGRESS_CACHE_FILE = ".progress_cache"


def has_features(project_dir: Path) -> bool:
    """
    Check if the project has features in the database.

    This is used to determine if the initializer agent needs to run.
    We check the database directly (not via API) since the API server
    may not be running yet when this check is performed.

    Returns True if:
    - features.db exists AND has at least 1 feature, OR
    - feature_list.json exists (legacy format)

    Returns False if no features exist (initializer needs to run).
    """
    # Check legacy JSON file first
    json_file = project_dir / "feature_list.json"
    if json_file.exists():
        return True

    # Check SQLite database
    db_file = project_dir / "features.db"
    if not db_file.exists():
        return False

    try:
        result = execute_with_retry(
            db_file,
            "SELECT COUNT(*) FROM features",
            fetch="one"
        )
        return result[0] > 0 if result else False
    except Exception:
        # Database exists but can't be read or has no features table
        return False


def count_passing_tests(project_dir: Path) -> tuple[int, int, int]:
    """
    Count passing, in_progress, and total tests via direct database access.

    Uses robust connection with WAL mode and retry logic.

    Args:
        project_dir: Directory containing the project

    Returns:
        (passing_count, in_progress_count, total_count)
    """
    db_file = project_dir / "features.db"
    if not db_file.exists():
        return 0, 0, 0

    try:
        # Use robust connection with WAL mode and proper timeout
        with robust_db_connection(db_file) as conn:
            cursor = conn.cursor()
            # Single aggregate query instead of 3 separate COUNT queries
            # Handle case where in_progress column doesn't exist yet (legacy DBs)
            try:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN passes = 1 THEN 1 ELSE 0 END) as passing,
                        SUM(CASE WHEN in_progress = 1 THEN 1 ELSE 0 END) as in_progress
                    FROM features
                """)
                row = cursor.fetchone()
                total = row[0] or 0
                passing = row[1] or 0
                in_progress = row[2] or 0
            except sqlite3.OperationalError:
                # Fallback for databases without in_progress column
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN passes = 1 THEN 1 ELSE 0 END) as passing
                    FROM features
                """)
                row = cursor.fetchone()
                total = row[0] or 0
                passing = row[1] or 0
                in_progress = 0

            return passing, in_progress, total

    except sqlite3.DatabaseError as e:
        error_msg = str(e).lower()
        if "malformed" in error_msg or "corrupt" in error_msg:
            print(f"[DATABASE CORRUPTION DETECTED in count_passing_tests: {e}]")
            print(f"[Please run: sqlite3 {db_file} 'PRAGMA integrity_check;' to diagnose]")
        else:
            print(f"[Database error in count_passing_tests: {e}]")
        return 0, 0, 0
    except Exception as e:
        print(f"[Database error in count_passing_tests: {e}]")
        return 0, 0, 0


def get_all_passing_features(project_dir: Path) -> list[dict]:
    """
    Get all passing features for webhook notifications.

    Uses robust connection with WAL mode and retry logic.

    Args:
        project_dir: Directory containing the project

    Returns:
        List of dicts with id, category, name for each passing feature
    """
    db_file = project_dir / "features.db"
    if not db_file.exists():
        return []

    try:
        with robust_db_connection(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, category, name FROM features WHERE passes = 1 ORDER BY priority ASC"
            )
            features = [
                {"id": row[0], "category": row[1], "name": row[2]}
                for row in cursor.fetchall()
            ]
            return features
    except Exception:
        return []


def send_progress_webhook(passing: int, total: int, project_dir: Path) -> None:
    """Send webhook notification when progress increases."""
    if not WEBHOOK_URL:
        return  # Webhook not configured

    cache_file = project_dir / PROGRESS_CACHE_FILE
    previous = 0
    previous_passing_ids = set()

    # Read previous progress and passing feature IDs
    if cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text())
            previous = cache_data.get("count", 0)
            previous_passing_ids = set(cache_data.get("passing_ids", []))
        except Exception:
            previous = 0

    # Only notify if progress increased
    if passing > previous:
        # Find which features are now passing via API
        completed_tests = []
        current_passing_ids = []

        # Detect transition from old cache format (had count but no passing_ids)
        # In this case, we can't reliably identify which specific tests are new
        is_old_cache_format = len(previous_passing_ids) == 0 and previous > 0

        # Get all passing features via direct database access
        all_passing = get_all_passing_features(project_dir)
        for feature in all_passing:
            feature_id = feature.get("id")
            current_passing_ids.append(feature_id)
            # Only identify individual new tests if we have previous IDs to compare
            if not is_old_cache_format and feature_id not in previous_passing_ids:
                # This feature is newly passing
                name = feature.get("name", f"Feature #{feature_id}")
                category = feature.get("category", "")
                if category:
                    completed_tests.append(f"{category} {name}")
                else:
                    completed_tests.append(name)

        payload = {
            "event": "test_progress",
            "passing": passing,
            "total": total,
            "percentage": round((passing / total) * 100, 1) if total > 0 else 0,
            "previous_passing": previous,
            "tests_completed_this_session": passing - previous,
            "completed_tests": completed_tests,
            "project": project_dir.name,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        try:
            req = urllib.request.Request(
                WEBHOOK_URL,
                data=json.dumps([payload]).encode("utf-8"),  # n8n expects array
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"[Webhook notification failed: {e}]")

        # Update cache with count and passing IDs
        cache_file.write_text(
            json.dumps({"count": passing, "passing_ids": current_passing_ids})
        )
    else:
        # Update cache even if no change (for initial state)
        if not cache_file.exists():
            all_passing = get_all_passing_features(project_dir)
            current_passing_ids = [f.get("id") for f in all_passing]
            cache_file.write_text(
                json.dumps({"count": passing, "passing_ids": current_passing_ids})
            )


def print_session_header(session_num: int, is_initializer: bool) -> None:
    """Print a formatted header for the session."""
    session_type = "INITIALIZER" if is_initializer else "CODING AGENT"

    print("\n" + "=" * 70)
    print(f"  SESSION {session_num}: {session_type}")
    print("=" * 70)
    print()


def print_progress_summary(project_dir: Path) -> None:
    """Print a summary of current progress."""
    passing, in_progress, total = count_passing_tests(project_dir)

    if total > 0:
        percentage = (passing / total) * 100
        status_parts = [f"{passing}/{total} tests passing ({percentage:.1f}%)"]
        if in_progress > 0:
            status_parts.append(f"{in_progress} in progress")
        print(f"\nProgress: {', '.join(status_parts)}")
        send_progress_webhook(passing, total, project_dir)
    else:
        print("\nProgress: No features in database yet")
