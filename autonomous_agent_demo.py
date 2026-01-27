#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding with Claude.
This script implements a unified orchestrator pattern that handles:
- Initialization (creating features from app_spec)
- Coding agents (implementing features)
- Testing agents (regression testing)

Example Usage:
    # Using absolute path directly
    python autonomous_agent_demo.py --project-dir C:/Projects/my-app

    # Using registered project name (looked up from registry)
    python autonomous_agent_demo.py --project-dir my-app

    # Limit iterations for testing (when running as subprocess)
    python autonomous_agent_demo.py --project-dir my-app --max-iterations 5

    # YOLO mode: rapid prototyping without testing agents
    python autonomous_agent_demo.py --project-dir my-app --yolo

    # Parallel execution with 3 concurrent coding agents
    python autonomous_agent_demo.py --project-dir my-app --concurrency 3

    # Single agent mode (orchestrator with concurrency=1, the default)
    python autonomous_agent_demo.py --project-dir my-app

    # Run as specific agent type (used by orchestrator to spawn subprocesses)
    python autonomous_agent_demo.py --project-dir my-app --agent-type initializer
    python autonomous_agent_demo.py --project-dir my-app --agent-type coding --feature-id 42
    python autonomous_agent_demo.py --project-dir my-app --agent-type testing
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Windows-specific: Set ProactorEventLoop policy for subprocess support
# This MUST be set before any other asyncio operations
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# IMPORTANT: Must be called BEFORE importing other modules that read env vars at load time
load_dotenv()

from agent import run_autonomous_agent
from registry import DEFAULT_MODEL, get_project_path


def safe_asyncio_run(coro):
    """
    Run an async coroutine with proper cleanup to avoid Windows subprocess errors.

    On Windows, subprocess transports may raise 'Event loop is closed' errors
    during garbage collection if not properly cleaned up.
    """
    if sys.platform == "win32":
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Allow cancelled tasks to complete
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            # Shutdown async generators and executors
            loop.run_until_complete(loop.shutdown_asyncgens())
            if hasattr(loop, 'shutdown_default_executor'):
                loop.run_until_complete(loop.shutdown_default_executor())

            loop.close()
    else:
        return asyncio.run(coro)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent Demo - Unified orchestrator pattern",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use absolute path directly (single agent, default)
  python autonomous_agent_demo.py --project-dir C:/Projects/my-app

  # Use registered project name (looked up from registry)
  python autonomous_agent_demo.py --project-dir my-app

  # Parallel execution with 3 concurrent agents
  python autonomous_agent_demo.py --project-dir my-app --concurrency 3

  # YOLO mode: rapid prototyping without testing agents
  python autonomous_agent_demo.py --project-dir my-app --yolo

  # Configure testing agent ratio (2 testing agents per coding agent)
  python autonomous_agent_demo.py --project-dir my-app --testing-ratio 2

  # Disable testing agents (similar to YOLO but with verification)
  python autonomous_agent_demo.py --project-dir my-app --testing-ratio 0

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
        help="Maximum number of agent iterations (default: unlimited, typically 1 for subprocesses)",
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
        help="Enable YOLO mode: skip testing agents for rapid prototyping",
    )

    # Unified orchestrator mode (replaces --parallel)
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=1,
        help="Number of concurrent coding agents (default: 1, max: 5)",
    )

    # Backward compatibility: --parallel is deprecated alias for --concurrency
    parser.add_argument(
        "--parallel", "-p",
        type=int,
        nargs="?",
        const=3,
        default=None,
        metavar="N",
        help="DEPRECATED: Use --concurrency instead. Alias for --concurrency.",
    )

    parser.add_argument(
        "--feature-id",
        type=int,
        default=None,
        help="Work on a specific feature ID only (used by orchestrator for coding agents)",
    )

    # Agent type for subprocess mode
    parser.add_argument(
        "--agent-type",
        choices=["initializer", "coding", "testing"],
        default=None,
        help="Agent type (used by orchestrator to spawn specialized subprocesses)",
    )

    parser.add_argument(
        "--testing-feature-id",
        type=int,
        default=None,
        help="Feature ID to regression test (used by orchestrator for testing agents)",
    )

    # Testing agent configuration
    parser.add_argument(
        "--testing-ratio",
        type=int,
        default=1,
        help="Testing agents per coding agent (0-3, default: 1). Set to 0 to disable testing agents.",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    print("[ENTRY] autonomous_agent_demo.py starting...", flush=True)
    args = parse_args()

    # Note: Authentication is handled by start.bat/start.sh before this script runs.
    # The Claude SDK auto-detects credentials from ~/.claude/.credentials.json

    # Handle deprecated --parallel flag
    if args.parallel is not None:
        print("WARNING: --parallel is deprecated. Use --concurrency instead.", flush=True)
        args.concurrency = args.parallel

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
        if args.agent_type:
            # Subprocess mode - spawned by orchestrator for a specific role
            safe_asyncio_run(
                run_autonomous_agent(
                    project_dir=project_dir,
                    model=args.model,
                    max_iterations=args.max_iterations or 1,
                    yolo_mode=args.yolo,
                    feature_id=args.feature_id,
                    agent_type=args.agent_type,
                    testing_feature_id=args.testing_feature_id,
                )
            )
        else:
            # Entry point mode - always use unified orchestrator
            from parallel_orchestrator import run_parallel_orchestrator

            # Clamp concurrency to valid range (1-5)
            concurrency = max(1, min(args.concurrency, 5))
            if concurrency != args.concurrency:
                print(f"Clamping concurrency to valid range: {concurrency}", flush=True)

            safe_asyncio_run(
                run_parallel_orchestrator(
                    project_dir=project_dir,
                    max_concurrency=concurrency,
                    model=args.model,
                    yolo_mode=args.yolo,
                    testing_agent_ratio=args.testing_ratio,
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
