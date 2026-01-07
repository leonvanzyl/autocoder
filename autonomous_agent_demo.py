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

    # Parallel agents: run multiple agents simultaneously
    python autonomous_agent_demo.py --project-dir my-app --num-agents 3
"""

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# IMPORTANT: Must be called BEFORE importing other modules that read env vars at load time
load_dotenv()

from agent import run_autonomous_agent
from registry import get_project_path

# Configuration
# DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MODEL = "claude-opus-4-5-20251101"


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

    parser.add_argument(
        "--num-agents",
        type=int,
        default=1,
        help="Number of parallel agents to run (default: 1, max: 10)",
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

    # Check if parallel mode requested
    num_agents = min(args.num_agents, 10)  # Cap at 10 agents

    if num_agents > 1:
        # Parallel agent mode
        from parallel_agents import ParallelAgentOrchestrator

        print(f"\n{'=' * 70}")
        print(f"  PARALLEL AGENT MODE - {num_agents} AGENTS")
        print("=" * 70)
        print(f"\nProject directory: {project_dir}")
        print(f"Model: {args.model}")
        print(f"Number of agents: {num_agents}")
        if args.yolo:
            print("Mode: YOLO (testing disabled)")
        print()

        root_dir = Path(__file__).parent
        orchestrator = ParallelAgentOrchestrator(
            project_dir=project_dir,
            root_dir=root_dir,
            max_agents=num_agents,
        )

        async def run_parallel():
            """Run multiple agents in parallel and wait for completion."""
            try:
                results = await orchestrator.start_agents(
                    num_agents=num_agents,
                    yolo_mode=args.yolo,
                    model=args.model,
                    max_iterations=args.max_iterations,
                )
                print(f"\nStarted agents: {results}")

                # Wait for all agents to complete (or user interrupt)
                while True:
                    health = await orchestrator.healthcheck()
                    running = sum(1 for v in health.values() if v)
                    if running == 0:
                        # Distinguish between completion and crashes
                        statuses = orchestrator.get_all_statuses()
                        crashed = [s["agent_id"] for s in statuses if s["status"] == "crashed"]
                        stopped = [s["agent_id"] for s in statuses if s["status"] == "stopped"]

                        print("\nAll agents have finished.")
                        if crashed:
                            print(f"  Crashed: {', '.join(crashed)}")
                        if stopped:
                            print(f"  Completed: {', '.join(stopped)}")
                        break
                    await asyncio.sleep(5)

            except KeyboardInterrupt:
                print("\n\nInterrupted - stopping all agents...")
                await orchestrator.stop_all_agents()
            finally:
                # Optional: merge worktree changes
                print("\nCleaning up worktrees...")
                await orchestrator.cleanup()

        try:
            asyncio.run(run_parallel())
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        except Exception as e:
            print(f"\nFatal error: {e}")
            raise
    else:
        # Single agent mode (original behavior)
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
