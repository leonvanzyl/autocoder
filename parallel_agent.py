#!/usr/bin/env python3
"""
Parallel Agent CLI
==================

Entry point for running multiple agents in parallel using git worktrees.
Each worker operates in its own isolated worktree with atomic feature claiming.

Usage:
    python parallel_agent.py --project-dir /path/to/project --workers 3
    python parallel_agent.py --project-dir my-project --workers 5 --yolo
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from parallel_coordinator import ParallelCoordinator
from registry import get_project_path


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the parallel agent."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def resolve_project_path(project_dir: str) -> Path:
    """
    Resolve project directory from name or path.

    Supports:
    - Absolute paths: C:/Projects/myapp
    - Relative paths: ./myapp
    - Registered project names: myapp
    """
    path = Path(project_dir)

    # If it looks like a path, use it directly
    if path.is_absolute() or project_dir.startswith((".", "/", "\\")):
        return path.resolve()

    # Try to look up in registry
    registered_path = get_project_path(project_dir)
    if registered_path:
        return Path(registered_path).resolve()

    # Fall back to treating as relative path
    return path.resolve()


def validate_project(project_dir: Path) -> None:
    """Validate that the project is ready for parallel execution."""
    if not project_dir.exists():
        raise ValueError(f"Project directory does not exist: {project_dir}")

    if not (project_dir / ".git").exists():
        raise ValueError(f"Project must be a git repository: {project_dir}")

    if not (project_dir / "features.db").exists():
        raise ValueError(
            f"No features.db found. Run the initializer agent first:\n"
            f"  python autonomous_agent_demo.py --project-dir {project_dir}"
        )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run multiple agents in parallel using git worktrees",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python parallel_agent.py --project-dir /path/to/project
  python parallel_agent.py --project-dir my-project --workers 5
  python parallel_agent.py --project-dir my-project --workers 3 --yolo

The project must:
  1. Be a git repository
  2. Have features.db (run initializer first if needed)
  3. Have a clean working tree (uncommitted changes may cause issues)
        """,
    )

    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory path or registered name",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        choices=range(1, 11),
        metavar="N",
        help="Number of parallel workers (1-10, default: 3)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Claude model to use (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--yolo",
        action="store_true",
        help="YOLO mode: skip browser testing for faster iteration",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Resolve and validate project
    try:
        project_dir = resolve_project_path(args.project_dir)
        validate_project(project_dir)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Print banner
    print("\n" + "=" * 70)
    print("  PARALLEL AGENT EXECUTION")
    print("=" * 70)
    print(f"\nProject:  {project_dir}")
    print(f"Workers:  {args.workers}")
    print(f"Model:    {args.model}")
    print(f"Mode:     {'YOLO (testing disabled)' if args.yolo else 'Standard'}")
    print()

    # Create coordinator
    coordinator = ParallelCoordinator(
        project_dir=project_dir,
        worker_count=args.workers,
        model=args.model,
        yolo_mode=args.yolo,
    )

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\nReceived interrupt, shutting down gracefully...")
        coordinator.request_shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run coordinator
    try:
        asyncio.run(coordinator.run())
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
