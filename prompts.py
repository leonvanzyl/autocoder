"""
Prompt Loading Utilities
========================

Functions for loading prompt templates with project-specific support.

Fallback chain:
1. Project-specific: {project_dir}/prompts/{name}.md
2. Base template: .claude/templates/{name}.template.md
"""

import shutil
from pathlib import Path

# Base templates location (generic templates)
TEMPLATES_DIR = Path(__file__).parent / ".claude" / "templates"


def get_project_prompts_dir(project_dir: Path) -> Path:
    """Get the prompts directory for a specific project."""
    return project_dir / "prompts"


def load_prompt(name: str, project_dir: Path | None = None) -> str:
    """
    Load a prompt template with fallback chain.

    Fallback order:
    1. Project-specific: {project_dir}/prompts/{name}.md
    2. Base template: .claude/templates/{name}.template.md

    Args:
        name: The prompt name (without extension), e.g., "initializer_prompt"
        project_dir: Optional project directory for project-specific prompts

    Returns:
        The prompt content as a string

    Raises:
        FileNotFoundError: If prompt not found in any location
    """
    # 1. Try project-specific first
    if project_dir:
        project_prompts = get_project_prompts_dir(project_dir)
        project_path = project_prompts / f"{name}.md"
        if project_path.exists():
            try:
                return project_path.read_text(encoding="utf-8")
            except (OSError, PermissionError) as e:
                print(f"Warning: Could not read {project_path}: {e}")

    # 2. Try base template
    template_path = TEMPLATES_DIR / f"{name}.template.md"
    if template_path.exists():
        try:
            return template_path.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            print(f"Warning: Could not read {template_path}: {e}")

    raise FileNotFoundError(
        f"Prompt '{name}' not found in:\n"
        f"  - Project: {project_dir / 'prompts' if project_dir else 'N/A'}\n"
        f"  - Templates: {TEMPLATES_DIR}"
    )


def get_initializer_prompt(project_dir: Path | None = None) -> str:
    """Load the initializer prompt (project-specific if available)."""
    return load_prompt("initializer_prompt", project_dir)


def get_coding_prompt(project_dir: Path | None = None) -> str:
    """Load the coding agent prompt (project-specific if available)."""
    return load_prompt("coding_prompt", project_dir)


def get_coding_prompt_yolo(project_dir: Path | None = None) -> str:
    """Load the YOLO mode coding agent prompt (project-specific if available)."""
    return load_prompt("coding_prompt_yolo", project_dir)


def get_analyzer_prompt(project_dir: Path | None = None) -> str:
    """Load the analyzer agent prompt for importing existing projects."""
    return load_prompt("analyzer_prompt", project_dir)


def get_app_spec(project_dir: Path) -> str:
    """
    Load the app spec from the project.

    Checks in order:
    1. Project prompts directory: {project_dir}/prompts/app_spec.txt
    2. Project root (legacy): {project_dir}/app_spec.txt

    Args:
        project_dir: The project directory

    Returns:
        The app spec content

    Raises:
        FileNotFoundError: If no app_spec.txt found
    """
    # Try project prompts directory first
    project_prompts = get_project_prompts_dir(project_dir)
    spec_path = project_prompts / "app_spec.txt"
    if spec_path.exists():
        try:
            return spec_path.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            raise FileNotFoundError(f"Could not read {spec_path}: {e}") from e

    # Fallback to legacy location in project root
    legacy_spec = project_dir / "app_spec.txt"
    if legacy_spec.exists():
        try:
            return legacy_spec.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            raise FileNotFoundError(f"Could not read {legacy_spec}: {e}") from e

    raise FileNotFoundError(f"No app_spec.txt found for project: {project_dir}")


def scaffold_project_prompts(project_dir: Path) -> Path:
    """
    Create the project prompts directory and copy base templates.

    This sets up a new project with template files that can be customized.

    Args:
        project_dir: The absolute path to the project directory

    Returns:
        The path to the project prompts directory
    """
    project_prompts = get_project_prompts_dir(project_dir)
    project_prompts.mkdir(parents=True, exist_ok=True)

    # Define template mappings: (source_template, destination_name)
    templates = [
        ("app_spec.template.txt", "app_spec.txt"),
        ("coding_prompt.template.md", "coding_prompt.md"),
        ("coding_prompt_yolo.template.md", "coding_prompt_yolo.md"),
        ("initializer_prompt.template.md", "initializer_prompt.md"),
    ]

    copied_files = []
    for template_name, dest_name in templates:
        template_path = TEMPLATES_DIR / template_name
        dest_path = project_prompts / dest_name

        # Only copy if template exists and destination doesn't
        if template_path.exists() and not dest_path.exists():
            try:
                shutil.copy(template_path, dest_path)
                copied_files.append(dest_name)
            except (OSError, PermissionError) as e:
                print(f"  Warning: Could not copy {dest_name}: {e}")

    if copied_files:
        print(f"  Created prompt files: {', '.join(copied_files)}")

    return project_prompts


def has_project_prompts(project_dir: Path) -> bool:
    """
    Check if a project has valid prompts set up.

    A project has valid prompts if:
    1. The prompts directory exists, AND
    2. app_spec.txt exists within it, AND
    3. app_spec.txt contains the <project_specification> tag

    Args:
        project_dir: The project directory to check

    Returns:
        True if valid project prompts exist, False otherwise
    """
    project_prompts = get_project_prompts_dir(project_dir)
    app_spec = project_prompts / "app_spec.txt"

    if not app_spec.exists():
        # Also check legacy location in project root
        legacy_spec = project_dir / "app_spec.txt"
        if legacy_spec.exists():
            try:
                content = legacy_spec.read_text(encoding="utf-8")
                return "<project_specification>" in content
            except (OSError, PermissionError):
                return False
        return False

    # Check for valid spec content
    try:
        content = app_spec.read_text(encoding="utf-8")
        return "<project_specification>" in content
    except (OSError, PermissionError):
        return False


def copy_spec_to_project(project_dir: Path) -> None:
    """
    Copy the app spec file into the project root directory for the agent to read.

    This maintains backwards compatibility - the agent expects app_spec.txt
    in the project root directory.

    The spec is sourced from: {project_dir}/prompts/app_spec.txt

    Args:
        project_dir: The project directory
    """
    spec_dest = project_dir / "app_spec.txt"

    # Don't overwrite if already exists
    if spec_dest.exists():
        return

    # Copy from project prompts directory
    project_prompts = get_project_prompts_dir(project_dir)
    project_spec = project_prompts / "app_spec.txt"
    if project_spec.exists():
        try:
            shutil.copy(project_spec, spec_dest)
            print("Copied app_spec.txt to project directory")
            return
        except (OSError, PermissionError) as e:
            print(f"Warning: Could not copy app_spec.txt: {e}")
            return

    print("Warning: No app_spec.txt found to copy to project directory")


def migrate_project_prompts(project_dir: Path) -> Path:
    """
    Set up prompts directory for an imported existing project.

    Unlike scaffold_project_prompts(), this only copies the coding prompts
    (not app_spec.txt or initializer_prompt.md) since the analyzer agent
    will create the app_spec.txt based on the existing codebase.

    Args:
        project_dir: The absolute path to the existing project directory

    Returns:
        The path to the project prompts directory
    """
    project_prompts = get_project_prompts_dir(project_dir)
    project_prompts.mkdir(parents=True, exist_ok=True)

    # For imported projects, only copy coding prompts
    # The analyzer_prompt will be used first, then coding_prompt for ongoing work
    templates = [
        ("coding_prompt.template.md", "coding_prompt.md"),
        ("coding_prompt_yolo.template.md", "coding_prompt_yolo.md"),
        ("analyzer_prompt.template.md", "analyzer_prompt.md"),
    ]

    copied_files = []
    for template_name, dest_name in templates:
        template_path = TEMPLATES_DIR / template_name
        dest_path = project_prompts / dest_name

        # Only copy if template exists and destination doesn't
        if template_path.exists() and not dest_path.exists():
            try:
                shutil.copy(template_path, dest_path)
                copied_files.append(dest_name)
            except (OSError, PermissionError) as e:
                print(f"  Warning: Could not copy {dest_name}: {e}")

    if copied_files:
        print(f"  Created prompt files for import: {', '.join(copied_files)}")

    return project_prompts


def is_analyzer_mode(project_dir: Path) -> bool:
    """
    Check if a project should run in analyzer mode.

    Analyzer mode is triggered when:
    1. The .analyze_mode marker file exists, OR
    2. No features.db exists AND no valid app_spec.txt exists
       (indicating an imported project that needs analysis)

    Args:
        project_dir: The project directory to check

    Returns:
        True if analyzer mode should be used
    """
    # Explicit marker file takes precedence
    marker_file = project_dir / ".analyze_mode"
    if marker_file.exists():
        return True

    # Check if this looks like an imported project needing analysis
    features_db = project_dir / "features.db"
    has_features_db = features_db.exists()

    # If we have features, we're past analyzer phase
    if has_features_db:
        return False

    # Check if we have a valid app_spec
    has_valid_spec = has_project_prompts(project_dir)

    # No features AND no valid spec = needs analyzer
    return not has_valid_spec


def set_analyzer_mode(project_dir: Path, enabled: bool = True) -> None:
    """
    Set or clear the analyzer mode marker for a project.

    Args:
        project_dir: The project directory
        enabled: If True, enable analyzer mode; if False, disable it
    """
    marker_file = project_dir / ".analyze_mode"

    if enabled:
        marker_file.touch()
        print(f"  Analyzer mode enabled for {project_dir.name}")
    else:
        if marker_file.exists():
            marker_file.unlink()
            print(f"  Analyzer mode disabled for {project_dir.name}")


# =============================================================================
# Context Management for Large Projects
# =============================================================================

def get_context_dir(project_dir: Path) -> Path:
    """Get the context directory path for persistent codebase documentation."""
    return project_dir / "prompts" / "context"


def ensure_context_dir(project_dir: Path) -> Path:
    """
    Ensure the context directory exists for storing codebase documentation.

    Args:
        project_dir: The project directory

    Returns:
        Path to the context directory
    """
    context_dir = get_context_dir(project_dir)
    context_dir.mkdir(parents=True, exist_ok=True)
    return context_dir


def get_context_index_path(project_dir: Path) -> Path:
    """Get the path to the context index file."""
    return get_context_dir(project_dir) / "_index.md"


def has_context(project_dir: Path) -> bool:
    """
    Check if a project has context documentation.

    Args:
        project_dir: The project directory

    Returns:
        True if context index exists and has content
    """
    index_path = get_context_index_path(project_dir)
    if not index_path.exists():
        return False

    try:
        content = index_path.read_text(encoding="utf-8")
        return len(content.strip()) > 100  # More than just a header
    except (OSError, PermissionError):
        return False


def list_context_files(project_dir: Path) -> list[tuple[str, Path]]:
    """
    List all context documentation files.

    Args:
        project_dir: The project directory

    Returns:
        List of (name, path) tuples for each context file
    """
    context_dir = get_context_dir(project_dir)
    if not context_dir.exists():
        return []

    files = []
    for f in sorted(context_dir.glob("*.md")):
        if f.is_file():
            # Extract name without extension, skip index
            name = f.stem
            files.append((name, f))

    return files


def load_context_file(project_dir: Path, name: str) -> str | None:
    """
    Load a specific context file.

    Args:
        project_dir: The project directory
        name: Context file name (without .md extension)

    Returns:
        File content or None if not found
    """
    context_dir = get_context_dir(project_dir)
    file_path = context_dir / f"{name}.md"

    if not file_path.exists():
        return None

    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, PermissionError):
        return None


def load_all_context(project_dir: Path, max_chars: int = 50000) -> str:
    """
    Load all context documentation as a single string.

    Combines all context files with headers for use in prompts.
    Prioritizes the index file, then loads other files alphabetically.

    Args:
        project_dir: The project directory
        max_chars: Maximum characters to include (to avoid context overflow)

    Returns:
        Combined context string, or empty string if no context
    """
    context_dir = get_context_dir(project_dir)
    if not context_dir.exists():
        return ""

    parts = []
    total_chars = 0

    # Priority order for context files
    priority_files = [
        "_index",           # Overview/index always first
        "architecture",     # High-level architecture
        "database_schema",  # Database structure
        "api_endpoints",    # API reference
        "components",       # UI components
        "services",         # Business logic
    ]

    # Get all context files
    all_files = {f.stem: f for f in context_dir.glob("*.md") if f.is_file()}

    # Process in priority order first
    processed = set()
    for name in priority_files:
        if name in all_files and total_chars < max_chars:
            try:
                content = all_files[name].read_text(encoding="utf-8")
                if total_chars + len(content) <= max_chars:
                    parts.append(f"## Context: {name}\n\n{content}")
                    total_chars += len(content)
                    processed.add(name)
            except (OSError, PermissionError):
                continue

    # Then add remaining files
    for name, path in sorted(all_files.items()):
        if name not in processed and total_chars < max_chars:
            try:
                content = path.read_text(encoding="utf-8")
                if total_chars + len(content) <= max_chars:
                    parts.append(f"## Context: {name}\n\n{content}")
                    total_chars += len(content)
            except (OSError, PermissionError):
                continue

    if not parts:
        return ""

    return "# PROJECT CONTEXT DOCUMENTATION\n\n" + "\n\n---\n\n".join(parts)


def get_analysis_progress(project_dir: Path) -> dict:
    """
    Get the current analysis progress for a project.

    Reads the _index.md file to determine what areas have been analyzed.

    Args:
        project_dir: The project directory

    Returns:
        Dictionary with analysis status:
        {
            "analyzed_areas": ["architecture", "database", ...],
            "pending_areas": ["api", "frontend", ...],
            "total_files": int,
            "is_complete": bool
        }
    """
    context_files = list_context_files(project_dir)
    analyzed = [name for name, _ in context_files if name != "_index"]

    # Standard areas we expect for a complete analysis
    expected_areas = {
        "architecture",
        "database_schema",
        "api_endpoints",
        "components",
        "services",
        "configuration",
    }

    analyzed_set = set(analyzed)
    pending = expected_areas - analyzed_set

    return {
        "analyzed_areas": analyzed,
        "pending_areas": list(pending),
        "total_files": len(context_files),
        "is_complete": len(pending) == 0 and len(analyzed) >= 3,
    }
