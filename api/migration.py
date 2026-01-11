"""
Database Migration Scripts
==========================

Contains two migration types:

1. JSON to SQLite Migration (legacy):
   Migrates existing feature_list.json files to SQLite database.

2. V2 Schema Migration (new):
   Migrates legacy 'features' table to new hierarchical schema with:
   - Phases (project milestones)
   - Features (major work items)
   - Tasks (formerly 'features' - atomic work items)
   - UsageLogs (API usage tracking)
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from api.database import (
    Base,
    Feature,
    LegacyFeature,
    Phase,
    Task,
    get_database_path,
    get_database_url,
)


# =============================================================================
# JSON to SQLite Migration (Legacy)
# =============================================================================


def migrate_json_to_sqlite(
    project_dir: Path,
    session_maker: sessionmaker,
) -> bool:
    """
    Detect existing feature_list.json, import to SQLite, rename to backup.

    This function:
    1. Checks if feature_list.json exists
    2. Checks if database already has data (skips if so)
    3. Imports all features from JSON
    4. Renames JSON file to feature_list.json.backup.<timestamp>

    Args:
        project_dir: Directory containing the project
        session_maker: SQLAlchemy session maker

    Returns:
        True if migration was performed, False if skipped
    """
    json_file = project_dir / "feature_list.json"

    if not json_file.exists():
        return False  # No JSON file to migrate

    # Check if database already has data
    session: Session = session_maker()
    try:
        existing_count = session.query(LegacyFeature).count()
        if existing_count > 0:
            print(
                f"Database already has {existing_count} features, skipping migration"
            )
            return False
    finally:
        session.close()

    # Load JSON data
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            features_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing feature_list.json: {e}")
        return False
    except IOError as e:
        print(f"Error reading feature_list.json: {e}")
        return False

    if not isinstance(features_data, list):
        print("Error: feature_list.json must contain a JSON array")
        return False

    # Import features into database
    session = session_maker()
    try:
        imported_count = 0
        for i, feature_dict in enumerate(features_data):
            # Handle both old format (no id/priority/name) and new format
            feature = LegacyFeature(
                id=feature_dict.get("id", i + 1),
                priority=feature_dict.get("priority", i + 1),
                category=feature_dict.get("category", "uncategorized"),
                name=feature_dict.get("name", f"Feature {i + 1}"),
                description=feature_dict.get("description", ""),
                steps=feature_dict.get("steps", []),
                passes=feature_dict.get("passes", False),
            )
            session.add(feature)
            imported_count += 1

        session.commit()

        # Verify import
        final_count = session.query(LegacyFeature).count()
        print(f"Migrated {final_count} features from JSON to SQLite")

    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
        return False
    finally:
        session.close()

    # Rename JSON file to backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = project_dir / f"feature_list.json.backup.{timestamp}"

    try:
        shutil.move(json_file, backup_file)
        print(f"Original JSON backed up to: {backup_file.name}")
    except IOError as e:
        print(f"Warning: Could not backup JSON file: {e}")
        # Continue anyway - the data is in the database

    return True


def export_to_json(
    project_dir: Path,
    session_maker: sessionmaker,
    output_file: Optional[Path] = None,
) -> Path:
    """
    Export features from database back to JSON format.

    Useful for debugging or if you need to revert to the old format.

    Args:
        project_dir: Directory containing the project
        session_maker: SQLAlchemy session maker
        output_file: Output file path (default: feature_list_export.json)

    Returns:
        Path to the exported file
    """
    if output_file is None:
        output_file = project_dir / "feature_list_export.json"

    session: Session = session_maker()
    try:
        # Try new Task table first, fall back to legacy
        try:
            tasks = (
                session.query(Task)
                .order_by(Task.priority.asc(), Task.id.asc())
                .all()
            )
            features_data = [t.to_dict() for t in tasks]
        except Exception:
            features = (
                session.query(LegacyFeature)
                .order_by(LegacyFeature.priority.asc(), LegacyFeature.id.asc())
                .all()
            )
            features_data = [f.to_dict() for f in features]

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(features_data, f, indent=2)

        print(f"Exported {len(features_data)} items to {output_file}")
        return output_file

    finally:
        session.close()


# =============================================================================
# V2 Schema Migration (New Hierarchical Schema)
# =============================================================================


def backup_database(project_dir: Path) -> Path:
    """Create a backup of the existing database.

    Args:
        project_dir: Directory containing the project

    Returns:
        Path to the backup file
    """
    db_path = get_database_path(project_dir)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"features.db.backup.{timestamp}"
    shutil.copy2(db_path, backup_path)

    print(f"  Created backup: {backup_path.name}")
    return backup_path


def get_schema_version(engine) -> str:
    """Check which schema version the database is using.

    Returns:
        'legacy': Old schema with only 'features' table
        'v2': New schema with phases, features_v2, tasks tables
        'empty': No tables exist yet
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result.fetchall()}

        if "tasks" in tables and "phases" in tables:
            return "v2"
        elif "features" in tables:
            return "legacy"
        else:
            return "empty"


def count_legacy_features(engine) -> int:
    """Count features in the legacy table."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM features"))
        return result.scalar() or 0


def migrate_to_v2(
    project_dir: Path,
    project_name: Optional[str] = None,
    phase_name: str = "Phase 1: Initial Development",
    feature_name: str = "Core Features",
    dry_run: bool = False,
) -> dict:
    """Migrate a legacy database to the v2 schema.

    This migration:
    1. Creates a backup of the existing database
    2. Creates the new v2 tables (phases, features_v2, tasks, usage_logs)
    3. Creates a default Phase and Feature
    4. Copies all legacy features to the new tasks table
    5. Links tasks to the default Feature

    Args:
        project_dir: Directory containing the project
        project_name: Name of the project (defaults to directory name)
        phase_name: Name for the default phase
        feature_name: Name for the default feature
        dry_run: If True, don't actually migrate, just report what would happen

    Returns:
        Migration result dictionary with counts and status
    """
    db_path = get_database_path(project_dir)
    if not db_path.exists():
        return {
            "status": "skipped",
            "reason": "Database does not exist",
            "path": str(db_path),
        }

    # Determine project name
    if project_name is None:
        project_name = project_dir.name

    db_url = get_database_url(project_dir)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    # Check current schema version
    schema_version = get_schema_version(engine)

    if schema_version == "v2":
        return {
            "status": "skipped",
            "reason": "Already migrated to v2 schema",
            "path": str(db_path),
        }

    if schema_version == "empty":
        return {
            "status": "skipped",
            "reason": "Empty database, no migration needed",
            "path": str(db_path),
        }

    # Count legacy features
    legacy_count = count_legacy_features(engine)

    if dry_run:
        return {
            "status": "dry_run",
            "would_migrate": legacy_count,
            "path": str(db_path),
            "project_name": project_name,
            "phase_name": phase_name,
            "feature_name": feature_name,
        }

    print(f"\nMigrating: {project_dir}")
    print(f"  Found {legacy_count} legacy features to migrate")

    # Create backup
    backup_path = backup_database(project_dir)

    # Create new tables
    Base.metadata.create_all(bind=engine)
    print("  Created new v2 tables")

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Create default phase
        phase = Phase(
            project_name=project_name,
            name=phase_name,
            description="Initial development phase containing migrated tasks",
            order=1,
            status="in_progress",
        )
        db.add(phase)
        db.flush()  # Get the phase ID
        print(f"  Created phase: {phase_name}")

        # Create default feature
        feature = Feature(
            phase_id=phase.id,
            name=feature_name,
            description="Migrated features from legacy schema",
            status="in_progress",
            priority=1,
        )
        db.add(feature)
        db.flush()  # Get the feature ID
        print(f"  Created feature: {feature_name}")

        # Migrate legacy features to tasks
        legacy_features = db.query(LegacyFeature).all()
        migrated_count = 0
        passing_count = 0

        for legacy in legacy_features:
            task = Task(
                feature_id=feature.id,
                priority=legacy.priority,
                category=legacy.category,
                name=legacy.name,
                description=legacy.description,
                steps=legacy.steps,
                passes=legacy.passes,
                in_progress=legacy.in_progress,
                estimated_complexity=2,  # Default complexity
                reviewed=False,
            )
            db.add(task)
            migrated_count += 1
            if legacy.passes:
                passing_count += 1

        db.commit()
        print(f"  Migrated {migrated_count} tasks ({passing_count} passing)")

        # Update feature status based on task completion
        if passing_count == migrated_count and migrated_count > 0:
            feature.status = "completed"
            phase.status = "awaiting_approval"
        elif passing_count > 0:
            feature.status = "in_progress"

        db.commit()

        return {
            "status": "success",
            "migrated_count": migrated_count,
            "passing_count": passing_count,
            "backup_path": str(backup_path),
            "path": str(db_path),
            "project_name": project_name,
            "phase_id": phase.id,
            "feature_id": feature.id,
        }

    except Exception as e:
        db.rollback()
        # Restore backup on failure
        shutil.copy2(backup_path, db_path)
        print(f"  Migration failed, restored backup: {e}")
        return {
            "status": "error",
            "error": str(e),
            "backup_restored": True,
            "path": str(db_path),
        }

    finally:
        db.close()


def check_migration_status(project_dir: Path) -> dict:
    """Check the migration status of a project database.

    Args:
        project_dir: Directory containing the project

    Returns:
        Dictionary with schema version and counts
    """
    db_path = get_database_path(project_dir)
    if not db_path.exists():
        return {
            "exists": False,
            "path": str(db_path),
        }

    db_url = get_database_url(project_dir)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    schema_version = get_schema_version(engine)

    result = {
        "exists": True,
        "path": str(db_path),
        "schema_version": schema_version,
    }

    with engine.connect() as conn:
        if schema_version == "legacy":
            count = conn.execute(text("SELECT COUNT(*) FROM features")).scalar()
            passing = conn.execute(
                text("SELECT COUNT(*) FROM features WHERE passes = 1")
            ).scalar()
            result["legacy_features"] = count
            result["legacy_passing"] = passing

        elif schema_version == "v2":
            phases = conn.execute(text("SELECT COUNT(*) FROM phases")).scalar()
            features = conn.execute(text("SELECT COUNT(*) FROM features_v2")).scalar()
            tasks = conn.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
            passing = conn.execute(
                text("SELECT COUNT(*) FROM tasks WHERE passes = 1")
            ).scalar()
            result["phases"] = phases
            result["features"] = features
            result["tasks"] = tasks
            result["tasks_passing"] = passing

    return result


def migrate_all_projects(registry_db_path: Path, dry_run: bool = False) -> list[dict]:
    """Migrate all registered projects to v2 schema.

    Args:
        registry_db_path: Path to the project registry database
        dry_run: If True, don't actually migrate

    Returns:
        List of migration results for each project
    """
    if not registry_db_path.exists():
        return [{"status": "error", "error": "Registry database not found"}]

    registry_url = f"sqlite:///{registry_db_path.as_posix()}"
    engine = create_engine(registry_url)

    results = []

    with engine.connect() as conn:
        projects = conn.execute(text("SELECT name, path FROM projects")).fetchall()

        for name, path_str in projects:
            project_dir = Path(path_str)
            if not project_dir.exists():
                results.append({
                    "project": name,
                    "status": "skipped",
                    "reason": "Project directory not found",
                })
                continue

            result = migrate_to_v2(
                project_dir=project_dir,
                project_name=name,
                dry_run=dry_run,
            )
            result["project"] = name
            results.append(result)

    return results


# =============================================================================
# CLI Interface
# =============================================================================


def main():
    """CLI entry point for migration."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate Autocoder databases to v2 schema"
    )
    parser.add_argument(
        "project_dir",
        type=Path,
        nargs="?",
        help="Project directory to migrate",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check migration status, don't migrate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all registered projects",
    )
    parser.add_argument(
        "--phase-name",
        default="Phase 1: Initial Development",
        help="Name for the default phase",
    )
    parser.add_argument(
        "--feature-name",
        default="Core Features",
        help="Name for the default feature",
    )

    args = parser.parse_args()

    if args.all:
        # Migrate all registered projects
        registry_path = Path.home() / ".autocoder" / "registry.db"
        print(f"Migrating all projects from: {registry_path}")

        results = migrate_all_projects(registry_path, dry_run=args.dry_run)

        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)

        for result in results:
            status = result.get("status", "unknown")
            project = result.get("project", "unknown")
            if status == "success":
                count = result.get("migrated_count", 0)
                print(f"  {project}: Migrated {count} tasks")
            elif status == "skipped":
                reason = result.get("reason", "")
                print(f"  {project}: Skipped - {reason}")
            elif status == "dry_run":
                count = result.get("would_migrate", 0)
                print(f"  {project}: Would migrate {count} tasks")
            else:
                error = result.get("error", "Unknown error")
                print(f"  {project}: Error - {error}")

    elif args.project_dir:
        project_dir = args.project_dir.resolve()

        if args.check:
            result = check_migration_status(project_dir)
            print(json.dumps(result, indent=2))
        else:
            result = migrate_to_v2(
                project_dir=project_dir,
                phase_name=args.phase_name,
                feature_name=args.feature_name,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
