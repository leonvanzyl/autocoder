"""
Database Migrations
==================

Migration functions for evolving the database schema.
"""

import logging

from sqlalchemy import text

from api.models import (
    FeatureAttempt,
    FeatureError,
    Schedule,
    ScheduleOverride,
)

logger = logging.getLogger(__name__)


def migrate_add_in_progress_column(engine) -> None:
    """Add in_progress column to existing databases that don't have it."""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "in_progress" not in columns:
            # Add the column with default value
            conn.execute(text("ALTER TABLE features ADD COLUMN in_progress BOOLEAN DEFAULT 0"))
            conn.commit()


def migrate_fix_null_boolean_fields(engine) -> None:
    """Fix NULL values in passes and in_progress columns."""
    with engine.connect() as conn:
        # Fix NULL passes values
        conn.execute(text("UPDATE features SET passes = 0 WHERE passes IS NULL"))
        # Fix NULL in_progress values
        conn.execute(text("UPDATE features SET in_progress = 0 WHERE in_progress IS NULL"))
        conn.commit()


def migrate_add_dependencies_column(engine) -> None:
    """Add dependencies column to existing databases that don't have it.

    Uses NULL default for backwards compatibility - existing features
    without dependencies will have NULL which is treated as empty list.
    """
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "dependencies" not in columns:
            # Use TEXT for SQLite JSON storage, NULL default for backwards compat
            conn.execute(text("ALTER TABLE features ADD COLUMN dependencies TEXT DEFAULT NULL"))
            conn.commit()


def migrate_add_testing_columns(engine) -> None:
    """Legacy migration - handles testing columns that were removed from the model.

    The testing_in_progress and last_tested_at columns were removed from the
    Feature model as part of simplifying the testing agent architecture.
    Multiple testing agents can now test the same feature concurrently
    without coordination.

    This migration ensures these columns are nullable so INSERTs don't fail
    on databases that still have them with NOT NULL constraints.
    """
    with engine.connect() as conn:
        # Check if testing_in_progress column exists with NOT NULL
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = {row[1]: {"notnull": row[3], "dflt_value": row[4]} for row in result.fetchall()}

        if "testing_in_progress" in columns and columns["testing_in_progress"]["notnull"]:
            # SQLite doesn't support ALTER COLUMN, need to recreate table
            # Instead, we'll use a workaround: create a new table, copy data, swap
            logger.info("Migrating testing_in_progress column to nullable...")

            try:
                # Step 1: Create new table without NOT NULL on testing columns
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS features_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        priority INTEGER NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        description TEXT NOT NULL,
                        steps JSON NOT NULL,
                        passes BOOLEAN NOT NULL DEFAULT 0,
                        in_progress BOOLEAN NOT NULL DEFAULT 0,
                        dependencies JSON,
                        testing_in_progress BOOLEAN DEFAULT 0,
                        last_tested_at DATETIME
                    )
                """))

                # Step 2: Copy data
                conn.execute(text("""
                    INSERT INTO features_new
                    SELECT id, priority, category, name, description, steps, passes, in_progress,
                           dependencies, testing_in_progress, last_tested_at
                    FROM features
                """))

                # Step 3: Drop old table and rename
                conn.execute(text("DROP TABLE features"))
                conn.execute(text("ALTER TABLE features_new RENAME TO features"))

                # Step 4: Recreate indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_id ON features (id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_priority ON features (priority)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_passes ON features (passes)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_in_progress ON features (in_progress)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_feature_status ON features (passes, in_progress)"))

                conn.commit()
                logger.info("Successfully migrated testing columns to nullable")
            except Exception as e:
                logger.error(f"Failed to migrate testing columns: {e}")
                conn.rollback()
                raise


def migrate_add_schedules_tables(engine) -> None:
    """Create schedules and schedule_overrides tables if they don't exist."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Create schedules table if missing
    if "schedules" not in existing_tables:
        Schedule.__table__.create(bind=engine)

    # Create schedule_overrides table if missing
    if "schedule_overrides" not in existing_tables:
        ScheduleOverride.__table__.create(bind=engine)

    # Add crash_count column if missing (for upgrades)
    if "schedules" in existing_tables:
        columns = [c["name"] for c in inspector.get_columns("schedules")]
        if "crash_count" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    text("ALTER TABLE schedules ADD COLUMN crash_count INTEGER DEFAULT 0")
                )
                conn.commit()

        # Add max_concurrency column if missing (for upgrades)
        if "max_concurrency" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    text("ALTER TABLE schedules ADD COLUMN max_concurrency INTEGER DEFAULT 3")
                )
                conn.commit()


def migrate_add_timestamp_columns(engine) -> None:
    """Add timestamp and error tracking columns to features table.

    Adds: created_at, started_at, completed_at, last_failed_at, last_error
    All columns are nullable to preserve backwards compatibility with existing data.
    """
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        # Add each timestamp column if missing
        timestamp_columns = [
            ("created_at", "DATETIME"),
            ("started_at", "DATETIME"),
            ("completed_at", "DATETIME"),
            ("last_failed_at", "DATETIME"),
        ]

        for col_name, col_type in timestamp_columns:
            if col_name not in columns:
                conn.execute(text(f"ALTER TABLE features ADD COLUMN {col_name} {col_type}"))
                logger.debug(f"Added {col_name} column to features table")

        # Add error tracking column if missing
        if "last_error" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN last_error TEXT"))
            logger.debug("Added last_error column to features table")

        conn.commit()


def migrate_add_feature_attempts_table(engine) -> None:
    """Create feature_attempts table for agent attribution tracking."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "feature_attempts" not in existing_tables:
        FeatureAttempt.__table__.create(bind=engine)
        logger.debug("Created feature_attempts table")


def migrate_add_feature_errors_table(engine) -> None:
    """Create feature_errors table for error history tracking."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "feature_errors" not in existing_tables:
        FeatureError.__table__.create(bind=engine)
        logger.debug("Created feature_errors table")


def run_all_migrations(engine) -> None:
    """Run all migrations in order."""
    migrate_add_in_progress_column(engine)
    migrate_fix_null_boolean_fields(engine)
    migrate_add_dependencies_column(engine)
    migrate_add_testing_columns(engine)
    migrate_add_timestamp_columns(engine)
    migrate_add_schedules_tables(engine)
    migrate_add_feature_attempts_table(engine)
    migrate_add_feature_errors_table(engine)
