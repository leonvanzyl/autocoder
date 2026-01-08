#!/usr/bin/env python3
"""
Parallel Agent Runner
=====================

Runs a single agent instance as part of a parallel agent pool.
Each agent runs in its own worktree and identifies itself with an agent_id.

This script is spawned by the ParallelAgentOrchestrator for each agent.
"""

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent import run_autonomous_agent
from registry import get_project_path


DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Parallel Agent Runner - Single agent in parallel pool",
    )

    parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Main project directory (for database access)",
    )

    parser.add_argument(
        "--worktree-dir",
        type=str,
        required=True,
        help="Git worktree directory (agent's working directory)",
    )

    parser.add_argument(
        "--agent-id",
        type=str,
        required=True,
        help="Unique identifier for this agent",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum iterations (default: unlimited)",
    )

    parser.add_argument(
        "--yolo",
        action="store_true",
        default=False,
        help="Enable YOLO mode (no browser testing)",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    project_dir = Path(args.project_dir).resolve()
    worktree_dir = Path(args.worktree_dir).resolve()

    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        return

    if not worktree_dir.exists():
        print(f"Error: Worktree directory does not exist: {worktree_dir}")
        return

    print(f"[{args.agent_id}] Starting agent")
    print(f"[{args.agent_id}] Project dir: {project_dir}")
    print(f"[{args.agent_id}] Worktree dir: {worktree_dir}")

    # Set environment variable for MCP server to use main project dir for database
    os.environ["PROJECT_DIR"] = str(project_dir)
    os.environ["AGENT_ID"] = args.agent_id

    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=worktree_dir,  # Agent works in worktree
                model=args.model,
                max_iterations=args.max_iterations,
                yolo_mode=args.yolo,
                agent_id=args.agent_id,  # Pass agent_id to agent
            )
        )
    except KeyboardInterrupt:
        print(f"\n\n[{args.agent_id}] Interrupted by user")
    except Exception as e:
        print(f"\n[{args.agent_id}] Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
