"""
Projects Router
===============

API endpoints for project management.
Uses project registry for path lookups instead of fixed generations/ directory.
"""

import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..schemas import (
    DetachResponse,
    DetachStatusResponse,
    ProjectCreate,
    ProjectDetail,
    ProjectPrompts,
    ProjectPromptsUpdate,
    ProjectSettingsUpdate,
    ProjectStats,
    ProjectSummary,
    ReattachResponse,
)


# Lazy imports to avoid circular dependencies
# These are initialized by _init_imports() before first use.
_imports_initialized = False
_check_spec_exists: Callable[..., Any] | None = None
_scaffold_project_prompts: Callable[..., Any] | None = None
_get_project_prompts_dir: Callable[..., Any] | None = None
_count_passing_tests: Callable[..., Any] | None = None
_detach_module: Any = None


def _init_imports():
    """Lazy import of project-level modules."""
    global _imports_initialized, _check_spec_exists
    global _scaffold_project_prompts, _get_project_prompts_dir
    global _count_passing_tests, _detach_module

    if _imports_initialized:
        return

    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import detach as detach_module
    from progress import count_passing_tests
    from prompts import get_project_prompts_dir, scaffold_project_prompts
    from start import check_spec_exists

    _check_spec_exists = check_spec_exists
    _scaffold_project_prompts = scaffold_project_prompts
    _get_project_prompts_dir = get_project_prompts_dir
    _count_passing_tests = count_passing_tests
    _detach_module = detach_module
    _imports_initialized = True


def _get_registry_functions():
    """Get registry functions with lazy import."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import (
        get_project_concurrency,
        get_project_path,
        list_registered_projects,
        register_project,
        set_project_concurrency,
        unregister_project,
        validate_project_path,
    )
    return (
        register_project,
        unregister_project,
        get_project_path,
        list_registered_projects,
        validate_project_path,
        get_project_concurrency,
        set_project_concurrency,
    )


router = APIRouter(prefix="/api/projects", tags=["projects"])


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name. Use only letters, numbers, hyphens, and underscores (1-50 chars)."
        )
    return name


def get_project_stats(project_dir: Path) -> ProjectStats:
    """Get statistics for a project."""
    _init_imports()
    assert _count_passing_tests is not None  # guaranteed by _init_imports()
    passing, in_progress, total = _count_passing_tests(project_dir)
    percentage = (passing / total * 100) if total > 0 else 0.0
    return ProjectStats(
        passing=passing,
        in_progress=in_progress,
        total=total,
        percentage=round(percentage, 1)
    )


@router.get("", response_model=list[ProjectSummary])
async def list_projects():
    """List all registered projects."""
    _init_imports()
    assert _check_spec_exists is not None  # guaranteed by _init_imports()
    (_, _, _, list_registered_projects, validate_project_path,
     get_project_concurrency, _) = _get_registry_functions()

    projects = list_registered_projects()
    result = []

    for name, info in projects.items():
        project_dir = Path(info["path"])

        # Skip if path no longer exists
        is_valid, _ = validate_project_path(project_dir)
        if not is_valid:
            continue

        has_spec = _check_spec_exists(project_dir)
        stats = get_project_stats(project_dir)
        is_detached = _detach_module.is_project_detached(project_dir)

        result.append(ProjectSummary(
            name=name,
            path=info["path"],
            has_spec=has_spec,
            stats=stats,
            default_concurrency=info.get("default_concurrency", 3),
            is_detached=is_detached,
        ))

    return result


@router.post("", response_model=ProjectSummary)
async def create_project(project: ProjectCreate):
    """Create a new project at the specified path."""
    _init_imports()
    assert _scaffold_project_prompts is not None  # guaranteed by _init_imports()
    (register_project, _, get_project_path, list_registered_projects,
     _, _, _) = _get_registry_functions()

    name = validate_project_name(project.name)
    project_path = Path(project.path).resolve()

    # Check if project name already registered
    existing = get_project_path(name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Project '{name}' already exists at {existing}"
        )

    # Check if path already registered under a different name
    all_projects = list_registered_projects()
    for existing_name, info in all_projects.items():
        existing_path = Path(info["path"]).resolve()
        # Case-insensitive comparison on Windows
        if sys.platform == "win32":
            paths_match = str(existing_path).lower() == str(project_path).lower()
        else:
            paths_match = existing_path == project_path

        if paths_match:
            raise HTTPException(
                status_code=409,
                detail=f"Path '{project_path}' is already registered as project '{existing_name}'"
            )

    # Security: Check if path is in a blocked location
    from .filesystem import is_path_blocked
    if is_path_blocked(project_path):
        raise HTTPException(
            status_code=403,
            detail="Cannot create project in system or sensitive directory"
        )

    # Validate the path is usable
    if project_path.exists():
        if not project_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail="Path exists but is not a directory"
            )
    else:
        # Create the directory
        try:
            project_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create directory: {e}"
            )

    # Scaffold prompts
    _scaffold_project_prompts(project_path)

    # Register in registry
    try:
        register_project(name, project_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register project: {e}"
        )

    return ProjectSummary(
        name=name,
        path=project_path.as_posix(),
        has_spec=False,  # Just created, no spec yet
        stats=ProjectStats(passing=0, total=0, percentage=0.0),
        default_concurrency=3,
    )


@router.get("/{name}", response_model=ProjectDetail)
async def get_project(name: str):
    """Get detailed information about a project."""
    _init_imports()
    assert _check_spec_exists is not None  # guaranteed by _init_imports()
    assert _get_project_prompts_dir is not None  # guaranteed by _init_imports()
    (_, _, get_project_path, _, _, get_project_concurrency, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory no longer exists: {project_dir}")

    has_spec = _check_spec_exists(project_dir)
    stats = get_project_stats(project_dir)
    prompts_dir = _get_project_prompts_dir(project_dir)

    return ProjectDetail(
        name=name,
        path=project_dir.as_posix(),
        has_spec=has_spec,
        stats=stats,
        prompts_dir=str(prompts_dir),
        default_concurrency=get_project_concurrency(name),
        is_detached=_detach_module.is_project_detached(project_dir),
    )


@router.delete("/{name}")
async def delete_project(name: str, delete_files: bool = False):
    """
    Delete a project from the registry.

    Args:
        name: Project name to delete
        delete_files: If True, also delete the project directory and files
    """
    _init_imports()
    (_, unregister_project, get_project_path, _, _, _, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    # Check if agent is running
    from autoforge_paths import has_agent_running
    if has_agent_running(project_dir):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete project while agent is running. Stop the agent first."
        )

    # Optionally delete files
    if delete_files and project_dir.exists():
        try:
            shutil.rmtree(project_dir)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete project files: {e}")

    # Unregister from registry
    unregister_project(name)

    return {
        "success": True,
        "message": f"Project '{name}' deleted" + (" (files removed)" if delete_files else " (files preserved)")
    }


@router.get("/{name}/prompts", response_model=ProjectPrompts)
async def get_project_prompts(name: str):
    """Get the content of project prompt files."""
    _init_imports()
    assert _get_project_prompts_dir is not None  # guaranteed by _init_imports()
    (_, _, get_project_path, _, _, _, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    prompts_dir: Path = _get_project_prompts_dir(project_dir)

    def read_file(filename: str) -> str:
        filepath = prompts_dir / filename
        if filepath.exists():
            try:
                return filepath.read_text(encoding="utf-8")
            except Exception:
                return ""
        return ""

    return ProjectPrompts(
        app_spec=read_file("app_spec.txt"),
        initializer_prompt=read_file("initializer_prompt.md"),
        coding_prompt=read_file("coding_prompt.md"),
    )


@router.put("/{name}/prompts")
async def update_project_prompts(name: str, prompts: ProjectPromptsUpdate):
    """Update project prompt files."""
    _init_imports()
    assert _get_project_prompts_dir is not None  # guaranteed by _init_imports()
    (_, _, get_project_path, _, _, _, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    prompts_dir = _get_project_prompts_dir(project_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    def write_file(filename: str, content: str | None):
        if content is not None:
            filepath = prompts_dir / filename
            filepath.write_text(content, encoding="utf-8")

    write_file("app_spec.txt", prompts.app_spec)
    write_file("initializer_prompt.md", prompts.initializer_prompt)
    write_file("coding_prompt.md", prompts.coding_prompt)

    return {"success": True, "message": "Prompts updated"}


@router.get("/{name}/stats", response_model=ProjectStats)
async def get_project_stats_endpoint(name: str):
    """Get current progress statistics for a project."""
    _init_imports()
    (_, _, get_project_path, _, _, _, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    return get_project_stats(project_dir)


@router.post("/{name}/reset")
async def reset_project(name: str, full_reset: bool = False):
    """
    Reset a project to its initial state.

    Args:
        name: Project name to reset
        full_reset: If True, also delete prompts/ directory (triggers setup wizard)

    Returns:
        Dictionary with list of deleted files and reset type
    """
    _init_imports()
    (_, _, get_project_path, _, _, _, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Check if agent is running
    from autoforge_paths import has_agent_running
    if has_agent_running(project_dir):
        raise HTTPException(
            status_code=409,
            detail="Cannot reset project while agent is running. Stop the agent first."
        )

    # Dispose of database engines to release file locks (required on Windows)
    # Import here to avoid circular imports
    from api.database import dispose_engine as dispose_features_engine
    from server.services.assistant_database import dispose_engine as dispose_assistant_engine

    dispose_features_engine(project_dir)
    dispose_assistant_engine(project_dir)

    deleted_files: list[str] = []

    from autoforge_paths import (
        get_assistant_db_path,
        get_claude_assistant_settings_path,
        get_claude_settings_path,
        get_features_db_path,
    )

    # Build list of files to delete using path helpers (finds files at current location)
    # Plus explicit old-location fallbacks for backward compatibility
    db_path = get_features_db_path(project_dir)
    asst_path = get_assistant_db_path(project_dir)
    reset_files: list[Path] = [
        db_path,
        db_path.with_suffix(".db-wal"),
        db_path.with_suffix(".db-shm"),
        asst_path,
        asst_path.with_suffix(".db-wal"),
        asst_path.with_suffix(".db-shm"),
        get_claude_settings_path(project_dir),
        get_claude_assistant_settings_path(project_dir),
        # Also clean old root-level locations if they exist
        project_dir / "features.db",
        project_dir / "features.db-wal",
        project_dir / "features.db-shm",
        project_dir / "assistant.db",
        project_dir / "assistant.db-wal",
        project_dir / "assistant.db-shm",
        project_dir / ".claude_settings.json",
        project_dir / ".claude_assistant_settings.json",
    ]

    for file_path in reset_files:
        if file_path.exists():
            try:
                relative = file_path.relative_to(project_dir)
                file_path.unlink()
                deleted_files.append(str(relative))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to delete {file_path.name}: {e}")

    # Full reset: also delete prompts directory
    if full_reset:
        from autoforge_paths import get_prompts_dir
        # Delete prompts from both possible locations
        for prompts_dir in [get_prompts_dir(project_dir), project_dir / "prompts"]:
            if prompts_dir.exists():
                try:
                    relative = prompts_dir.relative_to(project_dir)
                    shutil.rmtree(prompts_dir)
                    deleted_files.append(f"{relative}/")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to delete prompts: {e}")

    return {
        "success": True,
        "reset_type": "full" if full_reset else "quick",
        "deleted_files": deleted_files,
        "message": f"Project '{name}' has been reset" + (" (full reset)" if full_reset else " (quick reset)")
    }


@router.patch("/{name}/settings", response_model=ProjectDetail)
async def update_project_settings(name: str, settings: ProjectSettingsUpdate):
    """Update project-level settings (concurrency, etc.)."""
    _init_imports()
    assert _check_spec_exists is not None  # guaranteed by _init_imports()
    assert _get_project_prompts_dir is not None  # guaranteed by _init_imports()
    (_, _, get_project_path, _, _, get_project_concurrency,
     set_project_concurrency) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Update concurrency if provided
    if settings.default_concurrency is not None:
        success = set_project_concurrency(name, settings.default_concurrency)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update concurrency")

    # Return updated project details
    has_spec = _check_spec_exists(project_dir)
    stats = get_project_stats(project_dir)
    prompts_dir = _get_project_prompts_dir(project_dir)

    return ProjectDetail(
        name=name,
        path=project_dir.as_posix(),
        has_spec=has_spec,
        stats=stats,
        prompts_dir=str(prompts_dir),
        default_concurrency=get_project_concurrency(name),
        is_detached=_detach_module.is_project_detached(project_dir),
    )


# ============================================================================
# Detach/Reattach Endpoints
# ============================================================================

@router.get("/{name}/detach-status", response_model=DetachStatusResponse)
def get_detach_status(name: str):
    """Check if a project is detached and get backup info."""
    _init_imports()
    (_, _, get_project_path, _, _, _, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    status = _detach_module.get_detach_status(name)

    return DetachStatusResponse(
        is_detached=status["is_detached"],
        backup_exists=status["backup_exists"],
        backup_size=status.get("backup_size"),
        detached_at=status.get("detached_at"),
        file_count=status.get("file_count"),
    )


@router.post("/{name}/detach", response_model=DetachResponse)
def detach_project(name: str):
    """
    Detach a project by moving Autocoder files to backup.

    This allows Claude Code to run without Autocoder restrictions.
    Files can be restored later with reattach.

    Note: Using sync function because detach_project() performs blocking I/O.
    FastAPI will run this in a threadpool automatically.
    """
    _init_imports()
    (_, _, get_project_path, _, _, _, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Note: Agent lock check is handled inside detach_project() to avoid TOCTOU race.
    # The detach module will return an appropriate error message if agent is running.

    # Dispose cached database engines before detach to release file locks (Windows)
    from api.database import dispose_engine as dispose_features_engine
    from server.services.assistant_database import dispose_engine as dispose_assistant_engine
    dispose_features_engine(project_dir)
    dispose_assistant_engine(project_dir)

    assert _detach_module is not None
    success, message, manifest, user_files_restored = _detach_module.detach_project(
        name,
        force=False,
        include_artifacts=True,
        dry_run=False,
    )

    if not success:
        # Map common error messages to appropriate HTTP status codes
        if "Agent is currently running" in message:
            raise HTTPException(status_code=409, detail=message)
        elif "already detached" in message:
            raise HTTPException(status_code=409, detail=message)
        elif "in progress" in message:
            raise HTTPException(status_code=409, detail=message)
        raise HTTPException(status_code=400, detail=message)

    return DetachResponse(
        success=True,
        files_moved=manifest["file_count"] if manifest else 0,
        backup_size=manifest["total_size_bytes"] if manifest else 0,
        backup_path=_detach_module.BACKUP_DIR,  # Return relative path, not absolute
        message=message,
        user_files_restored=user_files_restored,
    )


@router.post("/{name}/reattach", response_model=ReattachResponse)
def reattach_project(name: str):
    """
    Reattach a project by restoring Autocoder files from backup.

    This restores all Autocoder files and re-enables restrictions.

    Note: Using sync function because reattach_project() performs blocking I/O.
    FastAPI will run this in a threadpool automatically.
    """
    _init_imports()
    (_, _, get_project_path, _, _, _, _) = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Check if agent is running (consistent with detach endpoint)
    lock_file = project_dir / ".agent.lock"
    if lock_file.exists():
        raise HTTPException(
            status_code=409,
            detail="Cannot reattach while agent is running. Stop the agent first."
        )

    success, message, files_restored, conflicts = _detach_module.reattach_project(name)

    if not success:
        # Map common error messages to appropriate HTTP status codes
        if "in progress" in message:
            raise HTTPException(status_code=409, detail=message)
        elif "already attached" in message:
            raise HTTPException(status_code=409, detail=message)
        raise HTTPException(status_code=400, detail=message)

    # Dispose cached database engines so next request gets fresh connection
    from api.database import dispose_engine as dispose_features_engine
    from server.services.assistant_database import dispose_engine as dispose_assistant_engine
    dispose_features_engine(project_dir)
    dispose_assistant_engine(project_dir)

    return ReattachResponse(
        success=True,
        files_restored=files_restored,
        message=message,
        conflicts=conflicts,
        conflicts_backup_path=_detach_module.PRE_REATTACH_BACKUP_DIR if conflicts else None,
    )
