#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding with Claude.
This script implements the multi-agent pattern (architect → initializer → coding →
reviewer → testing) with per-agent-type model configuration for cost optimization.

Example Usage:
    # Using absolute path directly
    python autonomous_agent_demo.py --project-dir C:/Projects/my-app

    # Using registered project name (looked up from registry)
    python autonomous_agent_demo.py --project-dir my-app

    # Limit iterations for testing
    python autonomous_agent_demo.py --project-dir my-app --max-iterations 5

    # YOLO mode: rapid prototyping without browser testing
    python autonomous_agent_demo.py --project-dir my-app --yolo

    # Use different models per agent type (cost optimization)
    python autonomous_agent_demo.py --project-dir my-app \\
        --architect-model claude-opus-4-5-20251101 \\
        --coding-model claude-sonnet-4-5-20250929 \\
        --testing-model claude-3-5-haiku-20241022
"""

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# IMPORTANT: Must be called BEFORE importing other modules that read env vars at load time
load_dotenv()

from agent import run_autonomous_agent
from agent_types import ModelConfig
from registry import get_project_path


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

  # Use a single model for all agent types
  python autonomous_agent_demo.py --project-dir my-app --model claude-sonnet-4-5-20250929

  # Use different models per agent type (cost optimization)
  python autonomous_agent_demo.py --project-dir my-app \\
    --architect-model claude-opus-4-5-20251101 \\
    --coding-model claude-sonnet-4-5-20250929 \\
    --reviewer-model claude-sonnet-4-5-20250929 \\
    --testing-model claude-3-5-haiku-20241022

  # Limit iterations for testing
  python autonomous_agent_demo.py --project-dir my-app --max-iterations 5

  # YOLO mode: rapid prototyping without browser testing
  python autonomous_agent_demo.py --project-dir my-app --yolo

  # YOLO+Review mode: rapid prototyping with periodic code reviews
  python autonomous_agent_demo.py --project-dir my-app --yolo-review

Authentication:
  Uses Claude CLI credentials from ~/.claude/.credentials.json
  Run 'claude login' to authenticate (handled by start.bat/start.sh)
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

    # Model configuration
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Single Claude model for ALL agent types (overrides per-type defaults)",
    )
    parser.add_argument(
        "--architect-model",
        type=str,
        default=None,
        help="Model for architect agent (default: claude-opus-4-5-20251101)",
    )
    parser.add_argument(
        "--initializer-model",
        type=str,
        default=None,
        help="Model for initializer agent (default: claude-opus-4-5-20251101)",
    )
    parser.add_argument(
        "--coding-model",
        type=str,
        default=None,
        help="Model for coding agent (default: claude-sonnet-4-5-20250929)",
    )
    parser.add_argument(
        "--reviewer-model",
        type=str,
        default=None,
        help="Model for reviewer agent (default: claude-sonnet-4-5-20250929)",
    )
    parser.add_argument(
        "--testing-model",
        type=str,
        default=None,
        help="Model for testing agent (default: claude-3-5-haiku-20241022)",
    )

    # YOLO modes
    parser.add_argument(
        "--yolo",
        action="store_true",
        default=False,
        help="Enable YOLO mode: rapid prototyping without browser testing",
    )
    parser.add_argument(
        "--yolo-review",
        action="store_true",
        default=False,
        help="Enable YOLO+Review mode: rapid prototyping with periodic code reviews",
    )

    return parser.parse_args()


def build_model_config(args: argparse.Namespace) -> ModelConfig:
    """Build a ModelConfig from CLI arguments.

    Priority:
    1. Per-agent-type flags (--architect-model, etc.)
    2. Single --model flag (applies to all types)
    3. Default per-type config (opus for planning, sonnet for coding, haiku for testing)
    """
    if args.model:
        # Start from single model for all types
        config = ModelConfig.from_single_model(args.model)
    else:
        # Start from defaults (different per type)
        config = ModelConfig()

    # Apply per-type overrides
    if args.architect_model:
        config.architect_model = args.architect_model
    if args.initializer_model:
        config.initializer_model = args.initializer_model
    if args.coding_model:
        config.coding_model = args.coding_model
    if args.reviewer_model:
        config.reviewer_model = args.reviewer_model
    if args.testing_model:
        config.testing_model = args.testing_model

    return config


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

    # Build model configuration from CLI args
    model_config = build_model_config(args)

    try:
        # Run the agent (MCP server handles feature database)
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model_config=model_config,
                max_iterations=args.max_iterations,
                yolo_mode=args.yolo or args.yolo_review,
                yolo_review=args.yolo_review,
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
