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
        columns = {row[1]: {"notnull": row[3], "dflt_value": row[4], "type": row[2]} for row in result.fetchall()}

        if "testing_in_progress" in columns and columns["testing_in_progress"]["notnull"]:
            # SQLite doesn't support ALTER COLUMN, need to recreate table
            # Instead, we'll use a workaround: create a new table, copy data, swap
            logger.info("Migrating testing_in_progress column to nullable...")

            try:
                # Define core columns that we know about
                core_columns = {
                    "id", "priority", "category", "name", "description", "steps",
                    "passes", "in_progress", "dependencies", "testing_in_progress",
                    "last_tested_at"
                }

                # Detect any optional columns that may have been added by newer migrations
                # (e.g., created_at, started_at, completed_at, last_failed_at, last_error, regression_count)
                optional_columns = []
                for col_name, col_info in columns.items():
                    if col_name not in core_columns:
                        # Preserve the column with its type
                        col_type = col_info["type"]
                        optional_columns.append((col_name, col_type))

                # Build dynamic column definitions for optional columns
                optional_col_defs = ""
                optional_col_names = ""
                for col_name, col_type in optional_columns:
                    optional_col_defs += f",\n                        {col_name} {col_type}"
                    optional_col_names += f", {col_name}"

                # Step 1: Create new table without NOT NULL on testing columns
                # Include any optional columns that exist in the current schema
                create_sql = f"""
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
                        last_tested_at DATETIME{optional_col_defs}
                    )
                """
                # Step 2: Copy data including optional columns
                insert_sql = f"""
                    INSERT INTO features_new
                    SELECT id, priority, category, name, description, steps, passes, in_progress,
                           dependencies, testing_in_progress, last_tested_at{optional_col_names}
                    FROM features
                """

                # Wrap entire migration in a single transaction to prevent InvalidRequestError
                # from nested conn.begin() calls in SQLAlchemy 2.0
                with conn.begin():
                    # Step 1: Create new table
                    conn.execute(text(create_sql))

                    # Step 2: Copy data including optional columns
                    conn.execute(text(insert_sql))

                    # Step 3: Atomic table swap - rename old, rename new, drop old
                    conn.execute(text("ALTER TABLE features RENAME TO features_old"))
                    conn.execute(text("ALTER TABLE features_new RENAME TO features"))
                    conn.execute(text("DROP TABLE features_old"))

                    # Step 4: Recreate indexes
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_id ON features (id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_priority ON features (priority)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_passes ON features (passes)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_in_progress ON features (in_progress)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_feature_status ON features (passes, in_progress)"))

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


def migrate_add_regression_count_column(engine) -> None:
    """Add regression_count column to existing databases that don't have it.

    This column tracks how many times a feature has been regression tested,
    enabling least-tested-first selection for regression testing.
    """
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "regression_count" not in columns:
            # Add column with default 0 - existing features start with no regression tests
            conn.execute(text("ALTER TABLE features ADD COLUMN regression_count INTEGER DEFAULT 0 NOT NULL"))
            conn.commit()
            logger.debug("Added regression_count column to features table")


def migrate_add_quality_result_column(engine) -> None:
    """Add quality_result column to existing databases that don't have it.

    This column stores quality gate results (test evidence) when a feature
    is marked as passing. Format: JSON with {passed, timestamp, checks: {...}, summary}
    """
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "quality_result" not in columns:
            # Add column with NULL default - existing features have no quality results
            conn.execute(text("ALTER TABLE features ADD COLUMN quality_result JSON DEFAULT NULL"))
            conn.commit()
            logger.debug("Added quality_result column to features table")


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
    migrate_add_regression_count_column(engine)
    migrate_add_quality_result_column(engine)
