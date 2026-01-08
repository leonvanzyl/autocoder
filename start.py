#!/usr/bin/env python3
"""
Simple CLI launcher for the Autonomous Coding Agent.
Provides an interactive menu to create new projects or continue existing ones.

Supports two paths for new projects:
1. Claude path: Use /create-spec to generate spec interactively
2. Manual path: Edit template files directly, then continue
"""

import os
import subprocess
import sys
from pathlib import Path

from prompts import (
    get_project_prompts_dir,
    has_project_prompts,
    migrate_project_prompts,
    scaffold_project_prompts,
    set_analyzer_mode,
)
from registry import (
    get_project_path,
    list_registered_projects,
    register_project,
)
from api.database import ensure_database_exists


def check_spec_exists(project_dir: Path) -> bool:
    """
    Check if valid spec files exist for a project.

    Checks in order:
    1. Project prompts directory: {project_dir}/prompts/app_spec.txt
    2. Project root (legacy): {project_dir}/app_spec.txt
    """
    # Check project prompts directory first
    project_prompts = get_project_prompts_dir(project_dir)
    spec_file = project_prompts / "app_spec.txt"
    if spec_file.exists():
        try:
            content = spec_file.read_text(encoding="utf-8")
            return "<project_specification>" in content
        except (OSError, PermissionError):
            return False

    # Check legacy location in project root
    legacy_spec = project_dir / "app_spec.txt"
    if legacy_spec.exists():
        try:
            content = legacy_spec.read_text(encoding="utf-8")
            return "<project_specification>" in content
        except (OSError, PermissionError):
            return False

    return False


def get_existing_projects() -> list[tuple[str, Path]]:
    """Get list of existing projects from registry.

    Returns:
        List of (name, path) tuples for registered projects that still exist.
    """
    registry = list_registered_projects()
    projects = []

    for name, info in registry.items():
        path = Path(info["path"])
        if path.exists():
            projects.append((name, path))

    return sorted(projects, key=lambda x: x[0])


def display_menu(projects: list[tuple[str, Path]]) -> None:
    """Display the main menu."""
    print("\n" + "=" * 50)
    print("  Autonomous Coding Agent Launcher")
    print("=" * 50)
    print("\n[1] Create new project")

    if projects:
        print("[2] Continue existing project")

    print("[3] Import existing codebase")
    print("[q] Quit")
    print()


def display_projects(projects: list[tuple[str, Path]]) -> None:
    """Display list of existing projects."""
    print("\n" + "-" * 40)
    print("  Existing Projects")
    print("-" * 40)

    for i, (name, path) in enumerate(projects, 1):
        print(f"  [{i}] {name}")
        print(f"      {path}")

    print("\n  [b] Back to main menu")
    print()


def get_project_choice(projects: list[tuple[str, Path]]) -> tuple[str, Path] | None:
    """Get user's project selection.

    Returns:
        Tuple of (name, path) for the selected project, or None if cancelled.
    """
    while True:
        choice = input("Select project number: ").strip().lower()

        if choice == 'b':
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(projects):
                return projects[idx]
            print(f"Please enter a number between 1 and {len(projects)}")
        except ValueError:
            print("Invalid input. Enter a number or 'b' to go back.")


def get_new_project_info() -> tuple[str, Path] | None:
    """Get name and path for new project.

    Returns:
        Tuple of (name, path) for the new project, or None if cancelled.
    """
    print("\n" + "-" * 40)
    print("  Create New Project")
    print("-" * 40)
    print("\nEnter project name (e.g., my-awesome-app)")
    print("Leave empty to cancel.\n")

    name = input("Project name: ").strip()

    if not name:
        return None

    # Basic validation - OS-aware invalid characters
    # Windows has more restrictions than Unix
    if sys.platform == "win32":
        invalid_chars = '<>:"/\\|?*'
    else:
        # Unix only restricts / and null
        invalid_chars = '/'

    for char in invalid_chars:
        if char in name:
            print(f"Invalid character '{char}' in project name")
            return None

    # Check if name already registered
    existing = get_project_path(name)
    if existing:
        print(f"Project '{name}' already exists at {existing}")
        return None

    # Get project path
    print("\nEnter the full path for the project directory")
    print("(e.g., C:/Projects/my-app or /home/user/projects/my-app)")
    print("Leave empty to cancel.\n")

    path_str = input("Project path: ").strip()
    if not path_str:
        return None

    project_path = Path(path_str).resolve()

    return name, project_path


def ensure_project_scaffolded(project_name: str, project_dir: Path) -> Path:
    """
    Ensure project directory exists with prompt templates and is registered.

    Creates the project directory, copies template files, and registers in registry.

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory

    Returns:
        The project directory path
    """
    # Create project directory if it doesn't exist
    project_dir.mkdir(parents=True, exist_ok=True)

    # Scaffold prompts (copies templates if they don't exist)
    print(f"\nSetting up project: {project_name}")
    print(f"Location: {project_dir}")
    scaffold_project_prompts(project_dir)

    # Register in registry
    register_project(project_name, project_dir)

    return project_dir


def run_spec_creation(project_dir: Path) -> bool:
    """
    Run Claude Code with /create-spec command to create project specification.

    The project path is passed as an argument so create-spec knows where to write files.
    """
    print("\n" + "=" * 50)
    print("  Project Specification Setup")
    print("=" * 50)
    print(f"\nProject directory: {project_dir}")
    print(f"Prompts will be saved to: {get_project_prompts_dir(project_dir)}")
    print("\nLaunching Claude Code for interactive spec creation...")
    print("Answer the questions to define your project.")
    print("When done, Claude will generate the spec files.")
    print("Exit Claude Code (Ctrl+C or /exit) when finished.\n")

    try:
        # Launch Claude Code with /create-spec command
        # Project path included in command string so it populates $ARGUMENTS
        subprocess.run(
            ["claude", f"/create-spec {project_dir}"],
            check=False,  # Don't raise on non-zero exit
            cwd=str(Path(__file__).parent)  # Run from project root
        )

        # Check if spec was created in project prompts directory
        if check_spec_exists(project_dir):
            print("\n" + "-" * 50)
            print("Spec files created successfully!")
            return True
        else:
            print("\n" + "-" * 50)
            print("Spec creation incomplete.")
            print(f"Please ensure app_spec.txt exists in: {get_project_prompts_dir(project_dir)}")
            return False

    except FileNotFoundError:
        print("\nError: 'claude' command not found.")
        print("Make sure Claude Code CLI is installed:")
        print("  npm install -g @anthropic-ai/claude-code")
        return False
    except KeyboardInterrupt:
        print("\n\nSpec creation cancelled.")
        return False


def run_manual_spec_flow(project_dir: Path) -> bool:
    """
    Guide user through manual spec editing flow.

    Shows the paths to edit and waits for user to press Enter when ready.
    """
    prompts_dir = get_project_prompts_dir(project_dir)

    print("\n" + "-" * 50)
    print("  Manual Specification Setup")
    print("-" * 50)
    print("\nTemplate files have been created. Edit these files in your editor:")
    print("\n  Required:")
    print(f"    {prompts_dir / 'app_spec.txt'}")
    print("\n  Optional (customize agent behavior):")
    print(f"    {prompts_dir / 'initializer_prompt.md'}")
    print(f"    {prompts_dir / 'coding_prompt.md'}")
    print("\n" + "-" * 50)
    print("\nThe app_spec.txt file contains a template with placeholders.")
    print("Replace the placeholders with your actual project specification.")
    print("\nWhen you're done editing, press Enter to continue...")

    try:
        input()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        return False

    # Validate that spec was edited
    if check_spec_exists(project_dir):
        print("\nSpec file validated successfully!")
        return True
    else:
        print("\nWarning: The app_spec.txt file still contains the template placeholder.")
        print("The agent may not work correctly without a proper specification.")
        confirm = input("Continue anyway? [y/N]: ").strip().lower()
        return confirm == 'y'


def ask_spec_creation_choice() -> str | None:
    """Ask user whether to create spec with Claude or manually."""
    print("\n" + "-" * 40)
    print("  Specification Setup")
    print("-" * 40)
    print("\nHow would you like to define your project?")
    print("\n[1] Create spec with Claude (recommended)")
    print("    Interactive conversation to define your project")
    print("\n[2] Edit templates manually")
    print("    Edit the template files directly in your editor")
    print("\n[b] Back to main menu")
    print()

    while True:
        choice = input("Select [1/2/b]: ").strip().lower()
        if choice in ['1', '2', 'b']:
            return choice
        print("Invalid choice. Please enter 1, 2, or b.")


def import_existing_project_flow() -> tuple[str, Path] | None:
    """
    Flow for importing an existing project.

    1. Get the path to existing project
    2. Validate it has source code
    3. Get project name (default from folder name)
    4. Set up for analyzer mode
    5. Return (name, path) tuple if successful
    """
    print("\n" + "-" * 40)
    print("  Import Existing Project")
    print("-" * 40)
    print("\nThis will import an existing codebase into the system.")
    print("Claude will analyze your code and create features for management.")
    print("\nEnter the full path to your existing project directory")
    print("(e.g., C:/Projects/my-existing-app or /home/user/projects/my-app)")
    print("Leave empty to cancel.\n")

    path_str = input("Project path: ").strip()
    if not path_str:
        return None

    project_path = Path(path_str).resolve()

    # Validate path exists and is a directory
    if not project_path.exists():
        print(f"\nError: Path does not exist: {project_path}")
        return None

    if not project_path.is_dir():
        print(f"\nError: Path is not a directory: {project_path}")
        return None

    # Security: Check if path is in a blocked/sensitive location
    blocked_paths = [
        Path.home() / ".ssh",
        Path.home() / ".aws",
        Path.home() / ".gnupg",
        Path.home() / ".config",
    ]
    if sys.platform == "win32":
        blocked_paths.extend([
            Path("C:/Windows"),
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
        ])
    elif sys.platform == "darwin":
        blocked_paths.extend([
            Path("/System"),
            Path("/Library"),
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
        ])
    else:  # Linux/Unix
        blocked_paths.extend([
            Path("/etc"),
            Path("/var"),
            Path("/usr"),
            Path("/root"),
            Path("/bin"),
            Path("/sbin"),
        ])

    for blocked in blocked_paths:
        try:
            if blocked.exists() and project_path.resolve().is_relative_to(blocked.resolve()):
                print(f"\nError: Cannot import project from system or sensitive directory: {blocked}")
                return None
        except (ValueError, OSError):
            continue

    # Check for source code files
    source_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.rb', '.php', '.vue', '.svelte', '.c', '.cpp', '.h', '.cs'}
    has_source_files = False
    for item in project_path.rglob('*'):
        if item.is_file() and item.suffix.lower() in source_extensions:
            has_source_files = True
            break

    if not has_source_files:
        print("\nWarning: No source code files found in this directory.")
        confirm = input("Continue anyway? [y/N]: ").strip().lower()
        if confirm != 'y':
            return None

    # Get project name (default from folder name)
    folder_name = project_path.name
    # Sanitize for project name
    default_name = ''.join(c if c.isalnum() or c in '-_' else '-' for c in folder_name.lower())
    default_name = default_name.strip('-') or 'imported-project'

    print(f"\nProject name (default: {default_name})")
    name = input("Project name: ").strip()
    if not name:
        name = default_name

    # Basic validation
    if sys.platform == "win32":
        invalid_chars = '<>:"/\\|?*'
    else:
        invalid_chars = '/'

    for char in invalid_chars:
        if char in name:
            print(f"Invalid character '{char}' in project name")
            return None

    # Check if name already registered
    existing = get_project_path(name)
    if existing:
        print(f"\nError: Project '{name}' already exists at {existing}")
        return None

    # Set up project for import
    print(f"\nSetting up project: {name}")
    print(f"Location: {project_path}")

    # Create prompts directory with analyzer mode templates
    migrate_project_prompts(project_path)

    # Enable analyzer mode
    set_analyzer_mode(project_path, enabled=True)

    # Ensure database exists (empty)
    ensure_database_exists(project_path)

    # Register the project
    register_project(name, project_path)

    print("\n" + "-" * 50)
    print("Project imported successfully!")
    print("When you start the agent, it will analyze your codebase")
    print("and create features for ongoing management.")
    print("-" * 50)

    return name, project_path


def create_new_project_flow() -> tuple[str, Path] | None:
    """
    Complete flow for creating a new project.

    1. Get project name and path
    2. Create project directory and scaffold prompts
    3. Ask: Claude or Manual?
    4. If Claude: Run /create-spec with project path
    5. If Manual: Show paths, wait for Enter
    6. Return (name, path) tuple if successful
    """
    project_info = get_new_project_info()
    if not project_info:
        return None

    project_name, project_path = project_info

    # Create project directory and scaffold prompts FIRST
    project_dir = ensure_project_scaffolded(project_name, project_path)

    # Ask user how they want to handle spec creation
    choice = ask_spec_creation_choice()

    if choice == 'b':
        return None
    elif choice == '1':
        # Create spec with Claude
        success = run_spec_creation(project_dir)
        if not success:
            print("\nYou can try again later or edit the templates manually.")
            retry = input("Start agent anyway? [y/N]: ").strip().lower()
            if retry != 'y':
                return None
    elif choice == '2':
        # Manual mode - guide user through editing
        success = run_manual_spec_flow(project_dir)
        if not success:
            return None

    return project_name, project_dir


def run_agent(project_name: str, project_dir: Path) -> None:
    """Run the autonomous agent with the given project.

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory
    """
    # Final validation before running
    if not has_project_prompts(project_dir):
        print(f"\nWarning: No valid spec found for project '{project_name}'")
        print("The agent may not work correctly.")
        confirm = input("Continue anyway? [y/N]: ").strip().lower()
        if confirm != 'y':
            return

    print(f"\nStarting agent for project: {project_name}")
    print(f"Location: {project_dir}")
    print("-" * 50)

    # Build the command - pass absolute path
    cmd = [sys.executable, "autonomous_agent_demo.py", "--project-dir", str(project_dir.resolve())]

    # Run the agent
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\n\nAgent interrupted. Run again to resume.")


def main() -> None:
    """Main entry point."""
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

    while True:
        projects = get_existing_projects()
        display_menu(projects)

        choice = input("Select option: ").strip().lower()

        if choice == 'q':
            print("\nGoodbye!")
            break

        elif choice == '1':
            result = create_new_project_flow()
            if result:
                project_name, project_dir = result
                run_agent(project_name, project_dir)

        elif choice == '2' and projects:
            display_projects(projects)
            selected = get_project_choice(projects)
            if selected:
                project_name, project_dir = selected
                run_agent(project_name, project_dir)

        elif choice == '3':
            result = import_existing_project_flow()
            if result:
                project_name, project_dir = result
                run_agent(project_name, project_dir)

        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()
