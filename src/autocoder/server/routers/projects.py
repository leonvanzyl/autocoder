"""
Projects Router
===============

API endpoints for project management.
Uses project registry for path lookups instead of fixed generations/ directory.
"""

import re
import os
import shutil
import subprocess
import stat
import time
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from ..schemas import (
    ProjectCreate,
    ProjectSummary,
    ProjectDetail,
    ProjectDeleteInfo,
    ProjectPrompts,
    ProjectPromptsUpdate,
    ProjectStats,
    KnowledgeFilesResponse,
    KnowledgeFileSummary,
    KnowledgeFileUpdate,
    KnowledgeFile,
)
from ...core.knowledge_files import get_knowledge_dir, list_knowledge_files, knowledge_file_meta

# Lazy imports to avoid circular dependencies
_imports_initialized = False
_check_spec_exists = None
_scaffold_project_prompts = None
_get_project_prompts_dir = None
_count_passing_tests = None


def _init_imports():
    """Lazy import of project-level modules."""
    global _imports_initialized, _check_spec_exists
    global _scaffold_project_prompts, _get_project_prompts_dir
    global _count_passing_tests

    if _imports_initialized:
        return

    from autocoder.agent.prompts import (
        scaffold_project_prompts,
        get_project_prompts_dir,
        has_project_prompts,
    )
    from autocoder.agent.progress import count_passing_tests

    _check_spec_exists = has_project_prompts
    _scaffold_project_prompts = scaffold_project_prompts
    _get_project_prompts_dir = get_project_prompts_dir
    _count_passing_tests = count_passing_tests
    _imports_initialized = True


def _get_registry_functions():
    """Get registry functions with lazy import."""
    from autocoder.agent.registry import (
        register_project,
        unregister_project,
        get_project_path,
        list_registered_projects,
        validate_project_path,
    )
    return register_project, unregister_project, get_project_path, list_registered_projects, validate_project_path


router = APIRouter(prefix="/api/projects", tags=["projects"])


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name. Use only letters, numbers, hyphens, and underscores (1-50 chars)."
        )
    return name


def validate_knowledge_filename(name: str) -> str:
    """Validate knowledge file names to prevent path traversal."""
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not re.match(r'^[a-zA-Z0-9._-]{1,120}$', name):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not name.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="Knowledge files must be .md")
    return name


def get_project_stats(project_dir: Path) -> ProjectStats:
    """Get statistics for a project."""
    _init_imports()
    passing, in_progress, total = _count_passing_tests(project_dir)
    percentage = (passing / total * 100) if total > 0 else 0.0
    return ProjectStats(
        passing=passing,
        in_progress=in_progress,
        total=total,
        percentage=round(percentage, 1)
    )


_SPEC_TEMPLATE_MARKERS = (
    "YOUR_PROJECT_NAME",
    "Replace with your actual project specification",
    "Describe your project in 2-3 sentences",
)

_RUNTIME_ARTIFACTS = {
    ".autocoder",
    "worktrees",
    "agent_system.db",
    "agent_system.db-wal",
    "agent_system.db-shm",
    ".agent.lock",
}


def _git_dirty(project_dir: Path) -> bool:
    """Return True if git working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def _cleanup_queue_path(project_dir: Path) -> Path:
    return (project_dir / ".autocoder" / "cleanup_queue.json").resolve()


def _rmtree_force(path: Path) -> None:
    def onerror(func, p, excinfo):  # type: ignore[no-untyped-def]
        try:
            os.chmod(p, stat.S_IWRITE)
        except Exception:
            pass
        try:
            func(p)
        except Exception:
            pass

    shutil.rmtree(path, onerror=onerror)


def _enqueue_cleanup(project_dir: Path, target: Path, *, reason: str) -> Path:
    autocoder_dir = project_dir / ".autocoder"
    autocoder_dir.mkdir(parents=True, exist_ok=True)
    queue_path = _cleanup_queue_path(project_dir)
    try:
        data = json.loads(queue_path.read_text(encoding="utf-8")) if queue_path.exists() else []
    except Exception:
        data = []
    if not isinstance(data, list):
        data = []
    now = time.time()
    target_str = str(target)
    for item in data:
        if item.get("path") == target_str:
            item["reason"] = reason
            item["next_try_at"] = now
            queue_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return queue_path
    data.append(
        {
            "path": target_str,
            "attempts": 0,
            "next_try_at": now,
            "added_at": now,
            "reason": reason,
        }
    )
    queue_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return queue_path


def _collect_non_runtime_entries(project_dir: Path, max_items: int = 12) -> tuple[list[str], int, bool]:
    """Collect top-level entries that are not runtime artifacts."""
    entries: list[str] = []
    total = 0
    truncated = False

    try:
        for entry in project_dir.iterdir():
            name = entry.name
            if name in _RUNTIME_ARTIFACTS:
                continue
            total += 1
            label = f"{name}/" if entry.is_dir() else name
            if len(entries) < max_items:
                entries.append(label)
            else:
                truncated = True
    except Exception:
        return entries, total, truncated

    return entries, total, truncated


def _is_spec_placeholder(spec_content: str) -> bool:
    """Detect if the spec is still the scaffold template."""
    if not spec_content:
        return True
    return any(marker in spec_content for marker in _SPEC_TEMPLATE_MARKERS)


def _is_setup_required(project_dir: Path, has_spec: bool) -> bool:
    """Determine whether the project still needs spec setup."""
    if not has_spec:
        return True

    prompts_dir = _get_project_prompts_dir(project_dir)
    spec_path = prompts_dir / "app_spec.txt"
    if not spec_path.exists():
        spec_path = project_dir / "app_spec.txt"

    if not spec_path.exists():
        return True

    try:
        content = spec_path.read_text(encoding="utf-8")
    except Exception:
        return True

    return _is_spec_placeholder(content)


@router.get("", response_model=list[ProjectSummary])
async def list_projects():
    """List all registered projects."""
    _init_imports()
    _, _, _, list_registered_projects, validate_project_path = _get_registry_functions()

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
        setup_required = _is_setup_required(project_dir, has_spec)

        result.append(ProjectSummary(
            name=name,
            path=info["path"],
            has_spec=has_spec,
            setup_required=setup_required,
            stats=stats,
        ))

    return result


@router.post("", response_model=ProjectSummary)
async def create_project(project: ProjectCreate):
    """Create a new project at the specified path."""
    _init_imports()
    register_project, _, get_project_path, list_registered_projects, _ = _get_registry_functions()

    name = validate_project_name(project.name)
    project_path = Path(project.path).resolve()

    # Check if project name already registered
    existing = get_project_path(name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Project '{name}' already exists at {existing}"
        )

    # Prevent duplicate project registrations that point at the same directory.
    # This matters for "existing project" onboarding where folder name may not match project name.
    registered = list_registered_projects()
    normalized_new = str(project_path)
    if os.name == "nt":
        normalized_new = normalized_new.casefold()
    for existing_name, info in registered.items():
        try:
            existing_path = Path(info["path"]).resolve()
        except Exception:
            continue
        normalized_existing = str(existing_path)
        if os.name == "nt":
            normalized_existing = normalized_existing.casefold()
        if normalized_existing == normalized_new:
            raise HTTPException(
                status_code=409,
                detail=f"Path is already registered as project '{existing_name}'"
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
        setup_required=True,
        stats=ProjectStats(passing=0, total=0, percentage=0.0),
    )


@router.get("/{name}", response_model=ProjectDetail)
async def get_project(name: str):
    """Get detailed information about a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory no longer exists: {project_dir}")

    has_spec = _check_spec_exists(project_dir)
    stats = get_project_stats(project_dir)
    prompts_dir = _get_project_prompts_dir(project_dir)
    setup_required = _is_setup_required(project_dir, has_spec)

    return ProjectDetail(
        name=name,
        path=project_dir.as_posix(),
        has_spec=has_spec,
        setup_required=setup_required,
        stats=stats,
        prompts_dir=str(prompts_dir),
    )


@router.get("/{name}/delete-info", response_model=ProjectDeleteInfo)
async def get_project_delete_info(name: str):
    """Return safety metadata for deleting a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    exists = project_dir.exists()
    lock_file = project_dir / ".agent.lock"
    agent_running = lock_file.exists() if exists else False
    has_git = (project_dir / ".git").exists() if exists else False
    git_dirty = _git_dirty(project_dir) if has_git else False
    has_spec = _check_spec_exists(project_dir) if exists else False

    prompts_dir = _get_project_prompts_dir(project_dir) if exists else project_dir / "prompts"
    has_prompts = prompts_dir.exists() if exists else False

    non_runtime_entries: list[str] = []
    non_runtime_count = 0
    non_runtime_truncated = False
    if exists:
        non_runtime_entries, non_runtime_count, non_runtime_truncated = _collect_non_runtime_entries(project_dir)

    runtime_only = non_runtime_count == 0

    return ProjectDeleteInfo(
        name=name,
        path=project_dir.as_posix(),
        exists=exists,
        agent_running=agent_running,
        has_git=has_git,
        git_dirty=git_dirty,
        runtime_only=runtime_only,
        has_prompts=has_prompts,
        has_spec=has_spec,
        non_runtime_entries=non_runtime_entries,
        non_runtime_count=non_runtime_count,
        non_runtime_truncated=non_runtime_truncated,
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
    _, unregister_project, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    # Check if agent is running
    lock_file = project_dir / ".agent.lock"
    if lock_file.exists():
        raise HTTPException(
            status_code=409,
            detail="Cannot delete project while agent is running. Stop the agent first."
        )

    # Optionally delete files
    if delete_files and project_dir.exists():
        try:
            _rmtree_force(project_dir)
        except Exception as e:
            # Windows file locking: queue cleanup for later rather than hard-failing.
            #
            # Notes:
            # - shutil.rmtree can raise PermissionError/OSError OR shutil.Error (list of nested failures).
            # - We treat access denied / WinError 5 as "locked" and queue cleanup.
            is_locked = False
            if isinstance(e, PermissionError):
                is_locked = True
            elif isinstance(e, OSError) and os.name == "nt" and getattr(e, "winerror", None) == 5:
                is_locked = True
            else:
                try:
                    msg = str(e)
                    if os.name == "nt" and ("WinError 5" in msg or "Access is denied" in msg):
                        is_locked = True
                except Exception:
                    pass

            if is_locked:
                queue_path = _enqueue_cleanup(project_dir, project_dir, reason="project delete failed (locked files)")
                # Remove the project from the registry (UI stays clean) and queue cleanup for later.
                unregister_project(name)
                return {
                    "success": True,
                    "message": (
                        f"Project '{name}' removed from registry. Files are locked; cleanup queued at {queue_path}. "
                        "Close any apps using the project and the cleanup queue will retry."
                    ),
                }

            raise HTTPException(status_code=500, detail=f"Failed to delete project files: {e}")

    # Unregister from registry
    unregister_project(name)

    return {
        "success": True,
        "message": f"Project '{name}' deleted" + (" (files removed)" if delete_files else " (files preserved)")
    }


@router.post("/{name}/reset")
async def reset_project(name: str, full_reset: bool = False):
    """
    Reset a project by clearing runtime artifacts and, optionally, prompts/specs.

    Args:
        name: Project name to reset
        full_reset: If True, remove prompts/app_spec and force spec re-setup
    """
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    lock_file = project_dir / ".agent.lock"
    if lock_file.exists():
        raise HTTPException(
            status_code=409,
            detail="Cannot reset project while agent is running. Stop the agent first."
        )

    errors: list[str] = []

    # Remove runtime DB files
    for suffix in ("", "-wal", "-shm"):
        db_path = project_dir / f"agent_system.db{suffix}"
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception as e:
                errors.append(f"Failed to remove {db_path.name}: {e}")

    # Remove runtime directories
    for dir_name in (".autocoder", "worktrees"):
        dir_path = project_dir / dir_name
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
            except Exception as e:
                errors.append(f"Failed to remove {dir_name}: {e}")

    # Remove legacy app_spec copy (if any)
    legacy_spec = project_dir / "app_spec.txt"
    if legacy_spec.exists():
        try:
            legacy_spec.unlink()
        except Exception as e:
            errors.append(f"Failed to remove app_spec.txt: {e}")

    # Remove spec status marker (if any)
    prompts_dir = _get_project_prompts_dir(project_dir)
    status_file = prompts_dir / ".spec_status.json"
    if status_file.exists():
        try:
            status_file.unlink()
        except Exception as e:
            errors.append(f"Failed to remove .spec_status.json: {e}")

    if full_reset:
        if prompts_dir.exists():
            try:
                shutil.rmtree(prompts_dir)
            except Exception as e:
                errors.append(f"Failed to remove prompts directory: {e}")
        try:
            prompts_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Failed to recreate prompts directory: {e}")

    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    return {
        "success": True,
        "message": f"Project '{name}' reset" + (" (full)" if full_reset else "")
    }


@router.get("/{name}/prompts", response_model=ProjectPrompts)
async def get_project_prompts(name: str):
    """Get the content of project prompt files."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found")

    prompts_dir = _get_project_prompts_dir(project_dir)

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
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found")

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


@router.get("/{name}/knowledge", response_model=KnowledgeFilesResponse)
async def list_knowledge_files_endpoint(name: str):
    """List knowledge files for a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found")

    knowledge_dir = get_knowledge_dir(project_dir)
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    files = [
        KnowledgeFileSummary(**knowledge_file_meta(p))
        for p in list_knowledge_files(project_dir)
    ]

    return KnowledgeFilesResponse(
        directory=str(knowledge_dir),
        files=files,
    )


@router.get("/{name}/knowledge/{filename}", response_model=KnowledgeFile)
async def get_knowledge_file_endpoint(name: str, filename: str):
    """Get a knowledge file by name."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    filename = validate_knowledge_filename(filename)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    knowledge_dir = get_knowledge_dir(project_dir)
    file_path = knowledge_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Knowledge file not found")

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

    return KnowledgeFile(name=filename, content=content)


@router.put("/{name}/knowledge/{filename}", response_model=KnowledgeFile)
async def upsert_knowledge_file_endpoint(name: str, filename: str, payload: KnowledgeFileUpdate):
    """Create or update a knowledge file."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    filename = validate_knowledge_filename(filename)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    knowledge_dir = get_knowledge_dir(project_dir)
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    file_path = knowledge_dir / filename

    try:
        file_path.write_text(payload.content or "", encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {e}")

    return KnowledgeFile(name=filename, content=payload.content or "")


@router.delete("/{name}/knowledge/{filename}")
async def delete_knowledge_file_endpoint(name: str, filename: str):
    """Delete a knowledge file."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    filename = validate_knowledge_filename(filename)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    knowledge_dir = get_knowledge_dir(project_dir)
    file_path = knowledge_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Knowledge file not found")

    try:
        file_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")

    return {"success": True}


@router.get("/{name}/stats", response_model=ProjectStats)
async def get_project_stats_endpoint(name: str):
    """Get current progress statistics for a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found")

    return get_project_stats(project_dir)
