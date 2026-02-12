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
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# IMPORTANT: Must be called BEFORE importing other modules that read env vars at load time
load_dotenv()

import os

from agent import run_autonomous_agent
from registry import DEFAULT_MODEL, get_effective_sdk_env, get_project_path


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

    parser.add_argument(
        "--feature-ids",
        type=str,
        default=None,
        help="Comma-separated feature IDs to implement in batch (e.g., '5,8,12')",
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
        help="Feature ID to regression test (used by orchestrator for testing agents, legacy single mode)",
    )

    parser.add_argument(
        "--testing-feature-ids",
        type=str,
        default=None,
        help="Comma-separated feature IDs to regression test in batch (e.g., '5,12,18')",
    )

    # Testing agent configuration
    parser.add_argument(
        "--testing-ratio",
        type=int,
        default=1,
        help="Testing agents per coding agent (0-3, default: 1). Set to 0 to disable testing agents.",
    )

    parser.add_argument(
        "--testing-batch-size",
        type=int,
        default=3,
        help="Number of features per testing batch (1-5, default: 3)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Max features per coding agent batch (1-3, default: 3)",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    print("[ENTRY] autonomous_agent_demo.py starting...", flush=True)
    args = parse_args()

    # Note: Authentication is handled by start.bat/start.sh before this script runs.
    # The Claude SDK auto-detects credentials from ~/.claude/.credentials.json

    # Apply UI-configured provider settings to this process's environment.
    # This ensures CLI-launched agents respect Settings UI provider config (GLM, Ollama, etc.).
    # Uses setdefault so explicit env vars / .env file take precedence.
    sdk_overrides = get_effective_sdk_env()
    for key, value in sdk_overrides.items():
        if value:  # Only set non-empty values (empty values are used to clear conflicts)
            os.environ.setdefault(key, value)

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

    # Migrate project layout to .autoforge/ if needed (idempotent, safe)
    from autoforge_paths import migrate_project_layout
    migrated = migrate_project_layout(project_dir)
    if migrated:
        print(f"Migrated project files to .autoforge/: {', '.join(migrated)}", flush=True)

    # Migrate project to current AutoForge version (idempotent, safe)
    from prompts import migrate_project_to_current
    version_migrated = migrate_project_to_current(project_dir)
    if version_migrated:
        print(f"Upgraded project: {', '.join(version_migrated)}", flush=True)

    # Parse batch testing feature IDs (comma-separated string -> list[int])
    testing_feature_ids: list[int] | None = None
    if args.testing_feature_ids:
        try:
            testing_feature_ids = [int(x.strip()) for x in args.testing_feature_ids.split(",") if x.strip()]
        except ValueError:
            print(f"Error: --testing-feature-ids must be comma-separated integers, got: {args.testing_feature_ids}")
            return

    # Parse batch coding feature IDs (comma-separated string -> list[int])
    coding_feature_ids: list[int] | None = None
    if args.feature_ids:
        try:
            coding_feature_ids = [int(x.strip()) for x in args.feature_ids.split(",") if x.strip()]
        except ValueError:
            print(f"Error: --feature-ids must be comma-separated integers, got: {args.feature_ids}")
            return

    try:
        if args.agent_type:
            # Subprocess mode - spawned by orchestrator for a specific role
            asyncio.run(
                run_autonomous_agent(
                    project_dir=project_dir,
                    model=args.model,
                    max_iterations=args.max_iterations or 1,
                    yolo_mode=args.yolo,
                    feature_id=args.feature_id,
                    feature_ids=coding_feature_ids,
                    agent_type=args.agent_type,
                    testing_feature_id=args.testing_feature_id,
                    testing_feature_ids=testing_feature_ids,
                )
            )
        else:
            # Entry point mode - always use unified orchestrator
            # Clean up stale temp files before starting (prevents temp folder bloat)
            from temp_cleanup import cleanup_stale_temp
            cleanup_stats = cleanup_stale_temp()
            if cleanup_stats["dirs_deleted"] > 0 or cleanup_stats["files_deleted"] > 0:
                mb_freed = cleanup_stats["bytes_freed"] / (1024 * 1024)
                print(
                    f"[CLEANUP] Removed {cleanup_stats['dirs_deleted']} dirs, "
                    f"{cleanup_stats['files_deleted']} files ({mb_freed:.1f} MB freed)",
                    flush=True,
                )

            from parallel_orchestrator import run_parallel_orchestrator

            # Clamp concurrency to valid range (1-5)
            concurrency = max(1, min(args.concurrency, 5))
            if concurrency != args.concurrency:
                print(f"Clamping concurrency to valid range: {concurrency}", flush=True)

            asyncio.run(
                run_parallel_orchestrator(
                    project_dir=project_dir,
                    max_concurrency=concurrency,
                    model=args.model,
                    yolo_mode=args.yolo,
                    testing_agent_ratio=args.testing_ratio,
                    testing_batch_size=args.testing_batch_size,
                    batch_size=args.batch_size,
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
