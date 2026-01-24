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


def get_testing_prompt(project_dir: Path | None = None, testing_feature_id: int | None = None) -> str:
    """Load the testing agent prompt (project-specific if available).

    Args:
        project_dir: Optional project directory for project-specific prompts
        testing_feature_id: If provided, the pre-assigned feature ID to test.
            The orchestrator claims the feature before spawning the agent.

    Returns:
        The testing prompt, with pre-assigned feature instructions if applicable.
    """
    base_prompt = load_prompt("testing_prompt", project_dir)

    if testing_feature_id is not None:
        # Prepend pre-assigned feature instructions
        pre_assigned_header = f"""## ASSIGNED FEATURE

**You are assigned to regression test Feature #{testing_feature_id}.**

### Your workflow:
1. Call `feature_get_by_id` with ID {testing_feature_id} to get the feature details
2. Verify the feature through the UI using browser automation
3. If regression found, call `feature_mark_failing` with feature_id={testing_feature_id}
4. Exit when done (no cleanup needed)

---

"""
        return pre_assigned_header + base_prompt

    return base_prompt


def get_single_feature_prompt(feature_id: int, project_dir: Path | None = None, yolo_mode: bool = False) -> str:
    """Prepend single-feature assignment header to base coding prompt.

    Used in parallel mode to assign a specific feature to an agent.
    The base prompt already contains the full workflow - this just
    identifies which feature to work on.

    Args:
        feature_id: The specific feature ID to work on
        project_dir: Optional project directory for project-specific prompts
        yolo_mode: Ignored (kept for backward compatibility). Testing is now
                   handled by separate testing agents, not YOLO prompts.

    Returns:
        The prompt with single-feature header prepended
    """
    base_prompt = get_coding_prompt(project_dir)

    # Minimal header - the base prompt already contains the full workflow
    single_feature_header = f"""## ASSIGNED FEATURE: #{feature_id}

Work ONLY on this feature. Other agents are handling other features.
Use `feature_claim_and_get` with ID {feature_id} to claim it and get details.
If blocked, use `feature_skip` and document the blocker.

---

"""
    return single_feature_header + base_prompt


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

    # Create .autocoder directory for configuration files
    autocoder_dir = project_dir / ".autocoder"
    autocoder_dir.mkdir(parents=True, exist_ok=True)

    # Define template mappings: (source_template, destination_name)
    templates = [
        ("app_spec.template.txt", "app_spec.txt"),
        ("coding_prompt.template.md", "coding_prompt.md"),
        ("initializer_prompt.template.md", "initializer_prompt.md"),
        ("testing_prompt.template.md", "testing_prompt.md"),
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

    # Copy allowed_commands.yaml template to .autocoder/
    examples_dir = Path(__file__).parent / "examples"
    allowed_commands_template = examples_dir / "project_allowed_commands.yaml"
    allowed_commands_dest = autocoder_dir / "allowed_commands.yaml"
    if allowed_commands_template.exists() and not allowed_commands_dest.exists():
        try:
            shutil.copy(allowed_commands_template, allowed_commands_dest)
            copied_files.append(".autocoder/allowed_commands.yaml")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not copy allowed_commands.yaml: {e}")

    if copied_files:
        print(f"  Created project files: {', '.join(copied_files)}")

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
