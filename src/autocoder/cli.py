#!/usr/bin/env python3
"""
AutoCoder Unified CLI
======================

A unified command-line interface for the AutoCoder autonomous coding system.

Modes:
1. Interactive (default) - Menu-driven project creation and selection
2. Agent mode - Run single autonomous agent
3. Parallel mode - Run multiple parallel agents (3x faster)
4. UI mode - Launch web interface

Examples:
    # Interactive menu
    autocoder

    # Run single agent
    autocoder agent --project-dir my-app
    autocoder agent --project-dir C:/Projects/my-app --yolo

    # Run parallel agents
    autocoder parallel --project-dir my-app --parallel 3 --preset balanced

    # Launch UI
    autocoder-ui
"""

import argparse
import asyncio
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from new package structure
from autocoder.agent import (
    run_autonomous_agent,
    scaffold_project_prompts,
    has_project_prompts,
    get_project_prompts_dir,
    register_project,
    get_project_path,
    list_registered_projects,
)
from autocoder.core import Orchestrator
from autocoder.server import start_server
from autocoder.core.port_config import get_ui_port
from autocoder.core.logs import prune_worker_logs


# Default configuration
DEFAULT_MODEL = "claude-opus-4-5-20251101"
DEFAULT_PARALLEL = 3
DEFAULT_PRESET = "balanced"


# ============================================================================
# SETUP CHECKS & AUTO-SETUP
# ============================================================================

def check_setup() -> dict:
    """Check if all dependencies and requirements are installed."""
    import shutil

    issues = []

    # Check Python version
    if sys.version_info < (3, 10):
        issues.append(f"❌ Python 3.10+ required (you have {sys.version_info.major}.{sys.version_info.minor})")

    # Check if running in virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

    if not in_venv:
        issues.append("⚠️  Not running in a virtual environment (recommended but not required)")

    # Check for Claude CLI
    claude_cli = shutil.which("claude")
    if not claude_cli:
        issues.append("❌ Claude CLI not found. Run: npm install -g @anthropic-ai/claude-code")

    # Check for Node.js and npm (for UI)
    node = shutil.which("node")
    npm = shutil.which("npm")

    if not node:
        issues.append("❌ Node.js not found (required for UI). Install from: https://nodejs.org/")
    if not npm:
        issues.append("❌ npm not found (required for UI). Install Node.js to get npm")

    # Check if UI is built
    ROOT_DIR = Path(__file__).parent.parent.parent
    ui_dist = ROOT_DIR / "ui" / "dist"
    if not ui_dist.exists():
        issues.append("⚠️  UI not built")

    # Check if package is installed
    try:
        import autocoder
    except ImportError:
        issues.append("❌ AutoCoder package not installed")

    return {
        "has_issues": len(issues) > 0,
        "issues": issues,
        "in_venv": in_venv,
        "claude_cli": claude_cli is not None,
        "node": node is not None,
        "npm": npm is not None,
        "ui_built": ui_dist.exists(),
        "package_installed": True,  # We're running, so it's installed
    }


def auto_setup(setup: dict) -> bool:
    """Automatically set up missing dependencies.

    Returns True if setup succeeded or was not needed, False on failure.
    """
    import shutil
    import subprocess

    ROOT_DIR = Path(__file__).parent.parent.parent
    ui_dir = ROOT_DIR / "ui"

    print("\n" + "=" * 60)
    print("  🔧 Auto-Setup")
    print("=" * 60)

    # 1. Build UI if needed
    if not setup["ui_built"] and setup["npm"] and setup["node"]:
        print("\n📦 Building UI (this may take a minute)...")
        try:
            # Install npm dependencies
            print("   → Installing npm dependencies...")
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(ui_dir),
                capture_output=True,
                text=True,
                timeout=300000  # 5 minutes
            )
            if result.returncode != 0:
                print(f"   ⚠️  npm install had issues, but continuing...")
                if result.stdout:
                    print(f"   stdout: {result.stdout[:200]}")
                if result.stderr:
                    print(f"   stderr: {result.stderr[:200]}")
            else:
                print("   ✅ npm install complete")

            # Build UI
            print("   → Building UI...")
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(ui_dir),
                capture_output=True,
                text=True,
                timeout=300000  # 5 minutes
            )
            if result.returncode != 0:
                print(f"   ❌ Build failed!")
                if result.stderr:
                    print(f"   stderr: {result.stderr[:500]}")
                return False
            else:
                print("   ✅ UI built successfully")
        except subprocess.TimeoutExpired:
            print("   ❌ Build timed out (took longer than 5 minutes)")
            return False
        except Exception as e:
            print(f"   ❌ Build failed: {e}")
            return False

    # 2. Warn about missing critical dependencies
    if not setup["claude_cli"]:
        print("\n⚠️  Claude CLI not installed")
        print("   You can install it with: npm install -g @anthropic-ai/claude-code")
        print("   The agent will work, but authentication may be manual")

    if not setup["node"] or not setup["npm"]:
        print("\n⚠️  Node.js/npm not installed")
        print("   Install from: https://nodejs.org/")
        print("   The Web UI will not be available")

    print("\n✅ Auto-setup complete!\n")
    print("=" * 60)
    return True



def print_setup_check(setup: dict) -> None:
    """Print setup check results."""
    print("\n" + "=" * 60)
    print("  🔍 AutoCoder Setup Check")
    print("=" * 60)

    if setup["has_issues"]:
        print("\n⚠️  Issues found:\n")
        for issue in setup["issues"]:
            print(f"  {issue}")
        print("\n💡 Some features may not work correctly.")
    else:
        print("\n✅ All checks passed! You're ready to go.")

    print("\n" + "=" * 60)


def ask_cli_or_ui() -> str:
    """Ask user if they want CLI or Web UI."""
    print("\n" + "=" * 60)
    print("  🚀 AutoCoder")
    print("=" * 60)
    print("\nWhat would you like to launch?")
    print("\n[1] Command-Line Interface (CLI)")
    print("    - Interactive menu for project management")
    print("    - Run agents directly")
    print("    - Full control via commands")
    print("\n[2] Web UI")
    print("    - Visual project dashboard")
    print("    - Kanban board for features")
    print("    - Real-time agent monitoring")
    print("\n[q] Quit")
    print()

    while True:
        choice = input("Select [1/2/q]: ").strip().lower()

        if choice == '1':
            return "cli"
        elif choice == '2':
            return "ui"
        elif choice == 'q':
            return "quit"
        else:
            print("Invalid choice. Please enter 1, 2, or q.")





def resolve_project_dir(project_input: str) -> Optional[Path]:
    """Resolve project directory from path or registered name."""
    project_dir = Path(project_input)

    if project_dir.is_absolute():
        if project_dir.exists():
            return project_dir
        else:
            print(f"Error: Project directory does not exist: {project_dir}")
            return None

    # Try to resolve from registry
    registered_path = get_project_path(project_input)
    if registered_path:
        return registered_path
    else:
        print(f"Error: Project '{project_input}' not found in registry")
        print("Use an absolute path or register the project first.")
        return None


# ============================================================================
# INTERACTIVE MODE (from start.py)
# ============================================================================

def check_spec_exists(project_dir: Path) -> bool:
    """Check if valid spec files exist for a project."""
    project_prompts = get_project_prompts_dir(project_dir)
    spec_file = project_prompts / "app_spec.txt"
    if spec_file.exists():
        try:
            content = spec_file.read_text(encoding="utf-8")
            return "<project_specification>" in content
        except (OSError, PermissionError):
            return False

    # Check legacy location
    legacy_spec = project_dir / "app_spec.txt"
    if legacy_spec.exists():
        try:
            content = legacy_spec.read_text(encoding="utf-8")
            return "<project_specification>" in content
        except (OSError, PermissionError):
            return False

    return False


def get_existing_projects() -> list[tuple[str, Path]]:
    """Get list of existing projects from registry."""
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


def get_project_choice(projects: list[tuple[str, Path]]) -> Optional[tuple[str, Path]]:
    """Get user's project selection."""
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


def get_new_project_info() -> Optional[tuple[str, Path]]:
    """Get name and path for new project."""
    print("\n" + "-" * 40)
    print("  Create New Project")
    print("-" * 40)
    print("\nEnter project name (e.g., my-awesome-app)")
    print("Leave empty to cancel.\n")

    name = input("Project name: ").strip()

    if not name:
        return None

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
    """Ensure project directory exists with prompt templates and is registered."""
    project_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSetting up project: {project_name}")
    print(f"Location: {project_dir}")
    scaffold_project_prompts(project_dir)

    register_project(project_name, project_dir)

    return project_dir


def run_agent_interactive(project_name: str, project_dir: Path) -> None:
    """Run the autonomous agent with the given project."""
    if not has_project_prompts(project_dir):
        print(f"\nWarning: No valid spec found for project '{project_name}'")
        print("The agent may not work correctly.")
        confirm = input("Continue anyway? [y/N]: ").strip().lower()
        if confirm != 'y':
            return

    print(f"\nStarting agent for project: {project_name}")
    print(f"Location: {project_dir}")
    print("-" * 50)

    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir.resolve(),
                model=DEFAULT_MODEL,
                max_iterations=None,
                yolo_mode=False,
            )
        )
    except KeyboardInterrupt:
        print("\n\nAgent interrupted. Run again to resume.")


def interactive_mode() -> None:
    """Run interactive CLI menu."""
    script_dir = Path(__file__).parent.parent.parent.absolute()
    os.chdir(script_dir)

    while True:
        projects = get_existing_projects()
        display_menu(projects)

        choice = input("Select option: ").strip().lower()

        if choice == 'q':
            print("\nGoodbye!")
            break

        elif choice == '1':
            print("\n=== New Project Workflow ===")
            print("For new projects, please use the web UI: autocoder-ui")
            print("Or create spec files manually in your project directory.")

        elif choice == '2' and projects:
            display_projects(projects)
            selected = get_project_choice(projects)
            if selected:
                project_name, project_dir = selected
                run_agent_interactive(project_name, project_dir)

        else:
            print("Invalid option. Please try again.")


# ============================================================================
# AGENT MODE (from autonomous_agent_demo.py)
# ============================================================================

def run_agent(args) -> None:
    """Run single autonomous agent."""
    project_dir = resolve_project_dir(args.project_dir)
    if not project_dir:
        return

    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=args.model,
                max_iterations=args.max_iterations,
                yolo_mode=args.yolo,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


# ============================================================================
# PARALLEL MODE (from orchestrator_demo.py)
# ============================================================================

def run_parallel(args) -> None:
    """Run parallel autonomous agents."""
    project_dir = resolve_project_dir(args.project_dir)
    if not project_dir:
        return

    # Validate parallel count
    parallel_count = args.parallel
    if parallel_count < 1:
        print("Error: --parallel must be at least 1")
        return
    if parallel_count > 5:
        print("Warning: --parallel exceeds recommended maximum of 5")
        print("Proceeding with caution...")

    try:
        # Create orchestrator
        orchestrator = Orchestrator(
            project_dir=str(project_dir),
            max_agents=parallel_count,
            model_preset=args.preset
        )

        # Run parallel agents
        print(f"\n{'='*70}")
        print(f"🚀 Starting {parallel_count} parallel agents")
        print(f"📁 Project: {project_dir}")
        print(f"⚙️  Preset: {args.preset}")
        print(f"{'='*70}\n")

        result = asyncio.run(orchestrator.run_parallel_agents())

        # Print summary
        print(f"\n{'='*70}")
        print(f"✅ Parallel agents completed")
        print(f"{'='*70}\n")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AutoCoder - Autonomous Coding Agent System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive menu
  autocoder

  # Run single agent
  autocoder agent --project-dir my-app
  autocoder agent --project-dir C:/Projects/my-app --yolo

  # Run parallel agents
  autocoder parallel --project-dir my-app --parallel 3 --preset balanced

  # Launch UI
  autocoder-ui

For more help on a specific command:
  autocoder agent --help
  autocoder parallel --help
        """,
    )

    subparsers = parser.add_subparsers(dest='mode', help='Operating mode')

    # Agent mode
    agent_parser = subparsers.add_parser(
        'agent',
        help='Run single autonomous agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  autocoder agent --project-dir my-app
  autocoder agent --project-dir C:/Projects/my-app --yolo
  autocoder agent --project-dir my-app --max-iterations 10
        """,
    )
    agent_parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Project directory path (absolute) or registered project name",
    )
    agent_parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )
    agent_parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    agent_parser.add_argument(
        "--yolo",
        action="store_true",
        default=False,
        help="Enable YOLO mode: rapid prototyping without browser testing",
    )

    # Parallel mode
    parallel_parser = subparsers.add_parser(
        'parallel',
        help='Run parallel autonomous agents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  autocoder parallel --project-dir my-app --parallel 3 --preset balanced
  autocoder parallel --project-dir my-app --parallel 5 --preset quality

Model Presets:
  quality       - Opus only (best quality, highest cost)
  balanced      - Opus + Haiku (recommended)
  economy       - Opus + Sonnet + Haiku
  cheap         - Sonnet + Haiku
  experimental  - All models
        """,
    )
    parallel_parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Project directory path (absolute) or registered project name",
    )
    parallel_parser.add_argument(
        "--parallel",
        type=int,
        default=DEFAULT_PARALLEL,
        help=f"Number of parallel agents (default: {DEFAULT_PARALLEL}, max: 5)",
    )
    parallel_parser.add_argument(
        "--preset",
        type=str,
        default=DEFAULT_PRESET,
        choices=["quality", "balanced", "economy", "cheap", "experimental"],
        help=f"Model preset (default: {DEFAULT_PRESET})",
    )

    # Logs maintenance
    logs_parser = subparsers.add_parser(
        "logs",
        help="Manage AutoCoder runtime logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  autocoder logs --project-dir my-app --prune
  autocoder logs --project-dir my-app --prune --keep-days 3 --keep-files 50 --max-mb 50
        """,
    )
    logs_parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Project directory containing .autocoder/logs/",
    )
    logs_parser.add_argument("--prune", action="store_true", help="Prune .autocoder/logs/*.log")
    logs_parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    logs_parser.add_argument("--keep-days", type=int, default=7)
    logs_parser.add_argument("--keep-files", type=int, default=200)
    logs_parser.add_argument("--max-mb", type=int, default=200)

    args = parser.parse_args()

    # Route to appropriate mode
    if args.mode == 'agent':
        run_agent(args)
    elif args.mode == 'parallel':
        run_parallel(args)
    elif args.mode == "logs":
        project_dir = resolve_project_dir(args.project_dir)
        if args.prune:
            result = prune_worker_logs(
                project_dir,
                keep_days=args.keep_days,
                keep_files=args.keep_files,
                max_total_mb=args.max_mb,
                dry_run=args.dry_run,
            )
            verb = "Would delete" if args.dry_run else "Deleted"
            print(
                f"{verb} {result.deleted_files} log file(s) "
                f"({result.deleted_bytes} bytes); kept {result.kept_files} file(s)."
            )
        else:
            print("No action specified. Try: autocoder logs --project-dir <path> --prune")
    else:
        # Default: Run setup check and ask what to launch
        setup = check_setup()

        # Auto-setup if needed
        if not setup["ui_built"] or not setup["has_issues"]:
            success = auto_setup(setup)
            if not success:
                print("\n❌ Setup failed. Please fix the issues above and try again.")
                return

            # Re-check after setup
            setup = check_setup()

        print_setup_check(setup)

        # Ask user what they want to launch
        choice = ask_cli_or_ui()

        if choice == "cli":
            # Launch interactive CLI
            interactive_mode()
        elif choice == "ui":
            # Launch web UI
            if not setup["ui_built"]:
                print("\n❌ Cannot launch UI - build failed or Node.js not installed.")
                return
            print("\n🚀 Starting Web UI...")
            print(f"   Open http://127.0.0.1:{get_ui_port()} in your browser")
            print("   Press Ctrl+C to stop\n")
            try:
                start_server()
            except KeyboardInterrupt:
                print("\n\n👋 UI stopped. Goodbye!")
        else:
            print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
