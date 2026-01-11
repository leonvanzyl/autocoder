#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding with Claude.
This script implements the two-agent pattern (initializer + coding agent) and
incorporates all the strategies from the long-running agents guide.

Example Usage:
    # Using absolute path directly
    python autonomous_agent_demo.py --project-dir C:/Projects/my-app

    # Using registered project name (looked up from registry)
    python autonomous_agent_demo.py --project-dir my-app

    # Limit iterations for testing
    python autonomous_agent_demo.py --project-dir my-app --max-iterations 5

    # YOLO mode: rapid prototyping without browser testing
    python autonomous_agent_demo.py --project-dir my-app --yolo
"""

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# IMPORTANT: Must be called BEFORE importing other modules that read env vars at load time
load_dotenv()

from agent import run_autonomous_agent
from registry import DEFAULT_MODEL, get_project_path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent Demo - Long-running agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use absolute path directly
  python autonomous_agent_demo.py --project-dir C:/Projects/my-app

  # Use registered project name (looked up from registry)
  python autonomous_agent_demo.py --project-dir my-app

  # Use a specific model
  python autonomous_agent_demo.py --project-dir my-app --model claude-sonnet-4-5-20250929

  # Limit iterations for testing
  python autonomous_agent_demo.py --project-dir my-app --max-iterations 5

  # YOLO mode: rapid prototyping without browser testing
  python autonomous_agent_demo.py --project-dir my-app --yolo

Authentication:
  Uses Claude CLI authentication (run 'claude login' if not logged in)
  Authentication is handled by start.bat/start.sh before this runs
        """,
    )

    parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Project directory path (absolute) or registered project name",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    parser.add_argument(
        "--yolo",
        action="store_true",
        default=False,
        help="Enable YOLO mode: rapid prototyping without browser testing",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Note: Authentication is handled by start.bat/start.sh before this script runs.
    # The Claude SDK auto-detects credentials from ~/.claude/.credentials.json

    # Resolve project directory:
    # 1. If absolute path, use as-is
    # 2. Otherwise, look up from registry by name
    project_dir_input = args.project_dir
    project_dir = Path(project_dir_input)

    if project_dir.is_absolute():
        # Absolute path provided - use directly
        if not project_dir.exists():
            print(f"Error: Project directory does not exist: {project_dir}")
            return
    else:
        # Treat as a project name - look up from registry
        registered_path = get_project_path(project_dir_input)
        if registered_path:
            project_dir = registered_path
        else:
            print(f"Error: Project '{project_dir_input}' not found in registry")
            print("Use an absolute path or register the project first.")
            return

    try:
        # Run the agent (MCP server handles feature database)
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


if __name__ == "__main__":
    main()
