"""
Projects Router
===============

API endpoints for project management.
Uses project registry for path lookups instead of fixed generations/ directory.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import (
    DatabaseHealth,
    KnowledgeFile,
    KnowledgeFileContent,
    KnowledgeFileList,
    KnowledgeFileUpload,
    ProjectCreate,
    ProjectDetail,
    ProjectPrompts,
    ProjectPromptsUpdate,
    ProjectStats,
    ProjectSummary,
)
from ..utils.validation import validate_project_name

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

    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from progress import count_passing_tests
    from prompts import get_project_prompts_dir, scaffold_project_prompts
    from start import check_spec_exists

    _check_spec_exists = check_spec_exists
    _scaffold_project_prompts = scaffold_project_prompts
    _get_project_prompts_dir = get_project_prompts_dir
    _count_passing_tests = count_passing_tests
    _imports_initialized = True


def _get_registry_functions():
    """Get registry functions with lazy import."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import (
        get_project_path,
        list_registered_projects,
        register_project,
        unregister_project,
        validate_project_path,
    )
    return register_project, unregister_project, get_project_path, list_registered_projects, validate_project_path


router = APIRouter(prefix="/api/projects", tags=["projects"])


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

        result.append(ProjectSummary(
            name=name,
            path=info["path"],
            has_spec=has_spec,
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
    )


@router.post("/import", response_model=ProjectSummary)
async def import_project(project: ProjectCreate):
    """
    Import/reconnect to an existing project after reinstallation.

    This endpoint allows reconnecting to a project that exists on disk
    but is not registered in the current autocoder installation's registry.

    The project path must:
    - Exist as a directory
    - Contain a .autocoder folder (indicating it was previously an autocoder project)

    This is useful when:
    - Reinstalling autocoder
    - Moving to a new machine
    - Recovering from registry corruption
    """
    _init_imports()
    register_project, _, get_project_path, list_registered_projects, _ = _get_registry_functions()

    name = validate_project_name(project.name)
    project_path = Path(project.path).resolve()

    # Check if project name already registered
    existing = get_project_path(name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Project '{name}' already exists at {existing}. Use a different name or delete the existing project first."
        )

    # Check if path already registered under a different name
    all_projects = list_registered_projects()
    for existing_name, info in all_projects.items():
        existing_path = Path(info["path"]).resolve()
        if sys.platform == "win32":
            paths_match = str(existing_path).lower() == str(project_path).lower()
        else:
            paths_match = existing_path == project_path

        if paths_match:
            raise HTTPException(
                status_code=409,
                detail=f"Path '{project_path}' is already registered as project '{existing_name}'"
            )

    # Validate the path exists and is a directory
    if not project_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project path does not exist: {project_path}"
        )

    if not project_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Path exists but is not a directory"
        )

    # Check for .autocoder folder to confirm it's a valid autocoder project
    autocoder_dir = project_path / ".autocoder"
    if not autocoder_dir.exists():
        raise HTTPException(
            status_code=400,
            detail="Path does not appear to be an autocoder project (missing .autocoder folder). Use 'Create Project' instead."
        )

    # Security check
    from .filesystem import is_path_blocked
    if is_path_blocked(project_path):
        raise HTTPException(
            status_code=403,
            detail="Cannot import project from system or sensitive directory"
        )

    # Register in registry
    try:
        register_project(name, project_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register project: {e}"
        )

    # Get project stats
    has_spec = _check_spec_exists(project_path)
    stats = get_project_stats(project_path)

    return ProjectSummary(
        name=name,
        path=project_path.as_posix(),
        has_spec=has_spec,
        stats=stats,
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

    return ProjectDetail(
        name=name,
        path=project_dir.as_posix(),
        has_spec=has_spec,
        stats=stats,
        prompts_dir=str(prompts_dir),
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
            shutil.rmtree(project_dir)
        except Exception as e:
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
    Reset a project to its initial state.

    This clears all features, assistant chat history, and settings.
    Use this to restart a project from scratch without having to re-register it.

    Args:
        name: Project name to reset
        full_reset: If True, also deletes prompts directory for complete fresh start

    Always Deletes:
    - features.db (feature tracking database)
    - assistant.db (assistant chat history)
    - .claude_settings.json (agent settings)
    - .claude_assistant_settings.json (assistant settings)

    When full_reset=True, Also Deletes:
    - prompts/ directory (app_spec.txt, initializer_prompt.md, coding_prompt.md)

    Preserves:
    - Project registration in registry
    """
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Check if agent is running
    lock_file = project_dir / ".agent.lock"
    if lock_file.exists():
        raise HTTPException(
            status_code=409,
            detail="Cannot reset project while agent is running. Stop the agent first."
        )

    # Files to delete
    files_to_delete = [
        "features.db",
        "assistant.db",
        ".claude_settings.json",
        ".claude_assistant_settings.json",
    ]

    deleted_files = []
    errors = []

    for filename in files_to_delete:
        filepath = project_dir / filename
        if filepath.exists():
            try:
                filepath.unlink()
                deleted_files.append(filename)
            except Exception as e:
                errors.append(f"{filename}: {e}")

    # If full reset, also delete prompts directory
    if full_reset:
        prompts_dir = project_dir / "prompts"
        if prompts_dir.exists():
            try:
                shutil.rmtree(prompts_dir)
                deleted_files.append("prompts/")
            except Exception as e:
                errors.append(f"prompts/: {e}")

    if errors:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete some files: {'; '.join(errors)}"
        )

    reset_type = "fully reset" if full_reset else "reset"
    return {
        "success": True,
        "message": f"Project '{name}' has been {reset_type}",
        "deleted_files": deleted_files,
        "full_reset": full_reset,
    }


@router.post("/{name}/open-in-ide")
async def open_project_in_ide(name: str, ide: str):
    """Open a project in the specified IDE.

    Args:
        name: Project name
        ide: IDE to use ('vscode', 'cursor', or 'antigravity')
    """
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    # Validate IDE parameter
    ide_commands = {
        'vscode': 'code',
        'cursor': 'cursor',
        'antigravity': 'antigravity',
    }

    if ide not in ide_commands:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid IDE. Must be one of: {list(ide_commands.keys())}"
        )

    cmd = ide_commands[ide]
    project_path = str(project_dir)

    # Find the IDE executable in PATH
    cmd_path = shutil.which(cmd)
    if not cmd_path:
        raise HTTPException(
            status_code=400,
            detail=f"IDE executable '{cmd}' not found in PATH. Please ensure {ide} is installed and available in your system PATH."
        )

    try:
        if sys.platform == "win32":
            subprocess.Popen([cmd_path, project_path])
        else:
            # Unix-like systems
            subprocess.Popen([cmd, project_path], start_new_session=True)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open IDE: {e}"
        )

    return {"status": "success", "message": f"Opening {project_path} in {ide}"}


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
        raise HTTPException(status_code=404, detail="Project directory not found")

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
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    return get_project_stats(project_dir)


@router.get("/{name}/db-health", response_model=DatabaseHealth)
async def get_database_health(name: str):
    """Check database health for a project.

    Returns integrity status, journal mode, and any errors.
    Use this to diagnose database corruption issues.
    """
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Import health check function
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from api.database import check_database_health, get_database_path

    db_path = get_database_path(project_dir)
    result = check_database_health(db_path)

    return DatabaseHealth(**result)


# =============================================================================
# Knowledge Files Endpoints
# =============================================================================

def get_knowledge_dir(project_dir: Path) -> Path:
    """Get the knowledge directory for a project."""
    return project_dir / "knowledge"


@router.get("/{name}/knowledge", response_model=KnowledgeFileList)
async def list_knowledge_files(name: str):
    """List all knowledge files for a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    knowledge_dir = get_knowledge_dir(project_dir)

    if not knowledge_dir.exists():
        return KnowledgeFileList(files=[], count=0)

    files = []
    for filepath in knowledge_dir.glob("*.md"):
        if filepath.is_file():
            stat = filepath.stat()
            from datetime import datetime
            files.append(KnowledgeFile(
                name=filepath.name,
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime)
            ))

    # Sort by name
    files.sort(key=lambda f: f.name.lower())

    return KnowledgeFileList(files=files, count=len(files))


@router.get("/{name}/knowledge/{filename}", response_model=KnowledgeFileContent)
async def get_knowledge_file(name: str, filename: str):
    """Get the content of a specific knowledge file."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Validate filename (prevent path traversal)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+\.md$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    knowledge_dir = get_knowledge_dir(project_dir)
    filepath = knowledge_dir / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge file '{filename}' not found")

    try:
        content = filepath.read_text(encoding="utf-8")
        return KnowledgeFileContent(name=filename, content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")


@router.post("/{name}/knowledge", response_model=KnowledgeFileContent)
async def upload_knowledge_file(name: str, file: KnowledgeFileUpload):
    """Upload a knowledge file to a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    knowledge_dir = get_knowledge_dir(project_dir)
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    filepath = knowledge_dir / file.filename

    try:
        filepath.write_text(file.content, encoding="utf-8")
        return KnowledgeFileContent(name=file.filename, content=file.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {e}")


@router.delete("/{name}/knowledge/{filename}")
async def delete_knowledge_file(name: str, filename: str):
    """Delete a knowledge file from a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Validate filename (prevent path traversal)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+\.md$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    knowledge_dir = get_knowledge_dir(project_dir)
    filepath = knowledge_dir / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge file '{filename}' not found")

    try:
        filepath.unlink()
        return {"success": True, "message": f"Deleted '{filename}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")
