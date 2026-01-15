"""
Agent Worker - Parallel Feature Implementation
==============================================

Entry point for each parallel agent process spawned by the Orchestrator.

Each worker:
1. Receives assignment (agent_id, feature_id, worktree_path)
2. Runs the autonomous agent loop in its isolated worktree
3. Uses the shared project database (agent_system.db) for feature state
4. Emits heartbeats for crash detection
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from autocoder.agent import run_autonomous_agent
from autocoder.core.database import get_database
from autocoder.core.file_locks import cleanup_agent_locks


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent worker (parallel feature implementation)")
    parser.add_argument("--project-dir", required=True, help="Main project directory (shared DB location)")
    parser.add_argument("--agent-id", required=True, help="Unique agent identifier")
    parser.add_argument("--feature-id", type=int, required=True, help="Feature ID to implement")
    parser.add_argument("--worktree-path", required=True, help="Isolated worktree for this agent")
    parser.add_argument(
        "--model",
        default="opus",
        choices=["opus", "sonnet", "haiku"],
        help="Claude model to use",
    )
    parser.add_argument("--max-iterations", type=int, default=5)
    parser.add_argument("--yolo", action="store_true", help="Enable YOLO mode (no Playwright)")
    parser.add_argument("--heartbeat-seconds", type=int, default=60)
    parser.add_argument("--api-port", type=int, default=5000, help="Target app API port (default: 5000)")
    parser.add_argument("--web-port", type=int, default=5173, help="Target app web port (default: 5173)")
    args = parser.parse_args()

    # Validate ports are in valid range (1024-65535)
    for port_name, port_value in [("API", args.api_port), ("Web", args.web_port)]:
        if not (1024 <= port_value <= 65535):
            parser.error(f"--{port_name.lower()}-port must be between 1024 and 65535, got {port_value}")

    return args


async def heartbeat_loop(database, agent_id: str, interval_seconds: int) -> None:
    while True:
        with contextlib.suppress(Exception):
            database.update_heartbeat(agent_id)
        await asyncio.sleep(max(5, interval_seconds))


async def main() -> int:
    args = parse_args()

    # Identify this agent for hooks/tools (locks, etc.).
    os.environ["AUTOCODER_AGENT_ID"] = str(args.agent_id)

    # Set environment variables for port configuration
    os.environ["AUTOCODER_API_PORT"] = str(args.api_port)
    os.environ["AUTOCODER_WEB_PORT"] = str(args.web_port)
    # Compatibility for common dev servers that look for generic port env vars.
    os.environ["API_PORT"] = str(args.api_port)
    os.environ["WEB_PORT"] = str(args.web_port)
    os.environ["PORT"] = str(args.api_port)
    os.environ["VITE_PORT"] = str(args.web_port)
    # Parallel workers require deterministic verification by the orchestrator (Gatekeeper).
    os.environ["AUTOCODER_REQUIRE_GATEKEEPER"] = "1"

    project_dir = Path(args.project_dir).resolve()
    worktree_path = Path(args.worktree_path).resolve()

    # Default lock dir to the shared project state directory (not the worktree).
    os.environ.setdefault("AUTOCODER_LOCK_DIR", str((project_dir / ".autocoder" / "locks").resolve()))

    if not project_dir.exists():
        logger.error(f"Project directory does not exist: {project_dir}")
        return 1
    if not worktree_path.exists():
        logger.error(f"Worktree directory does not exist: {worktree_path}")
        return 1

    database = get_database(str(project_dir))
    feature = database.get_feature(args.feature_id)
    if not feature:
        logger.error(f"Feature #{args.feature_id} not found in database")
        return 1

    logger.info("=" * 70)
    logger.info("AGENT WORKER - PARALLEL FEATURE IMPLEMENTATION")
    logger.info("=" * 70)
    logger.info(f"Agent ID:   {args.agent_id}")
    logger.info(f"Feature ID: {args.feature_id} - {feature.get('name')}")
    logger.info(f"Worktree:   {worktree_path}")
    logger.info(f"Model:      {args.model}")
    logger.info(f"YOLO:       {args.yolo}")
    logger.info(f"Max iters:  {args.max_iterations}")
    logger.info(f"Heartbeat:  {args.heartbeat_seconds}s")
    logger.info(f"API Port:   {args.api_port}")
    logger.info(f"Web Port:   {args.web_port}")
    logger.info("=" * 70)

    start_time = datetime.now()
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(database, args.agent_id, args.heartbeat_seconds)
    )

    try:
        await run_autonomous_agent(
            project_dir=worktree_path,
            model=args.model,
            max_iterations=args.max_iterations,
            yolo_mode=args.yolo,
            features_project_dir=project_dir,
            assigned_feature_id=args.feature_id,
            agent_id=args.agent_id,
        )

        feature = database.get_feature(args.feature_id)
        if feature and feature.get("passes", False):
            logger.info("FEATURE PASSED")
            return 0

        if feature and feature.get("review_status") == "READY_FOR_VERIFICATION":
            logger.info("FEATURE SUBMITTED FOR VERIFICATION")
            return 0

        database.mark_feature_failed(
            feature_id=args.feature_id,
            reason="Worker finished but feature not marked passing",
        )
        logger.warning("Feature not marked passing after worker run")
        return 1

    except Exception as e:
        database.mark_feature_failed(feature_id=args.feature_id, reason=f"Agent crashed: {e}")
        logger.exception("Worker failed")
        return 1

    finally:
        heartbeat_task.cancel()
        # asyncio.CancelledError inherits from BaseException in Python 3.11+ (incl. 3.12),
        # so it is not caught by suppress(Exception).
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task

        with contextlib.suppress(Exception):
            database.mark_agent_completed(args.agent_id)

        # Best-effort lock cleanup to avoid stale locks blocking future work.
        if os.environ.get("AUTOCODER_LOCKS_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
            lock_dir_raw = str(os.environ.get("AUTOCODER_LOCK_DIR", "")).strip()
            if lock_dir_raw:
                with contextlib.suppress(Exception):
                    cleanup_agent_locks(Path(lock_dir_raw).resolve(), str(args.agent_id))

        duration_s = (datetime.now() - start_time).total_seconds()
        logger.info(f"Worker finished in {duration_s:.1f}s")


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
