"""
Database Models and Connection
==============================

This module re-exports all database components for backwards compatibility.

The implementation has been split into:
- api/models.py - SQLAlchemy ORM models
- api/migrations.py - Database migration functions
- api/connection.py - Connection management and session utilities
"""

from api.connection import (
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY_MS,
    check_database_health,
    checkpoint_wal,
    create_database,
    execute_with_retry,
    get_database_path,
    get_database_url,
    get_db,
    get_db_session,
    get_robust_connection,
    invalidate_engine_cache,
    robust_db_connection,
    set_session_maker,
)
from api.models import (
    Base,
    Feature,
    FeatureAttempt,
    FeatureError,
    Schedule,
    ScheduleOverride,
)

__all__ = [
    # Models
    "Base",
    "Feature",
    "FeatureAttempt",
    "FeatureError",
    "Schedule",
    "ScheduleOverride",
    # Connection utilities
    "SQLITE_BUSY_TIMEOUT_MS",
    "SQLITE_MAX_RETRIES",
    "SQLITE_RETRY_DELAY_MS",
    "check_database_health",
    "checkpoint_wal",
    "create_database",
    "execute_with_retry",
    "get_database_path",
    "get_database_url",
    "get_db",
    "get_db_session",
    "get_robust_connection",
    "invalidate_engine_cache",
    "robust_db_connection",
    "set_session_maker",
]
