"""
Parallel Agent Coordinator
==========================

Manages multiple agent workers running in parallel using git worktrees.
Each worker operates in its own isolated worktree with atomic feature claiming.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from worktree_manager import WorktreeManager
from mcp_server.feature_mcp import init_database_direct

logger = logging.getLogger(__name__)

# Configuration
IDLE_BACKOFF_INITIAL = 5  # seconds
IDLE_BACKOFF_MAX = 60  # seconds
MONITOR_INTERVAL = 60  # seconds
LEASE_TIMEOUT_MINUTES = 30
HEARTBEAT_INTERVAL = 300  # 5 minutes


class WorkerProcess:
    """Represents a single worker agent process."""

    def __init__(
        self,
        worker_id: int,
        worktree_path: Path,
        project_dir: Path,
        model: str,
        yolo_mode: bool = False,
    ):
        self.worker_id = worker_id
        self.worker_name = f"worker-{worker_id}"
        self.worktree_path = worktree_path
        self.project_dir = project_dir
        self.model = model
        self.yolo_mode = yolo_mode
        self.current_feature: Optional[dict] = None
        self.process: Optional[asyncio.subprocess.Process] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def claim_feature(self) -> Optional[dict]:
        """
        Claim the next available feature using the MCP tool.

        Returns:
            Feature dict if claimed, None if no features available.
        """
        result = await self._run_mcp_tool("feature_claim_next", {"worker_id": self.worker_name})

        if result.get("status") == "no_features_available":
            return None

        if "error" in result:
            logger.error(f"Worker {self.worker_name} claim error: {result['error']}")
            return None

        self.current_feature = result
        return result

    async def heartbeat(self) -> bool:
        """
        Send heartbeat to extend lease on current feature.

        Returns:
            True if lease renewed, False if lease lost.
        """
        if not self.current_feature:
            return False

        result = await self._run_mcp_tool(
            "feature_heartbeat",
            {"feature_id": self.current_feature["id"], "worker_id": self.worker_name}
        )

        return result.get("status") == "renewed"

    async def release_claim(self) -> None:
        """Release claim on current feature."""
        if not self.current_feature:
            return

        await self._run_mcp_tool(
            "feature_release_claim",
            {"feature_id": self.current_feature["id"], "worker_id": self.worker_name}
        )
        self.current_feature = None

    async def mark_passing(self) -> None:
        """Mark current feature as passing."""
        if not self.current_feature:
            return

        await self._run_mcp_tool(
            "feature_mark_passing",
            {"feature_id": self.current_feature["id"], "worker_id": self.worker_name}
        )
        self.current_feature = None

    async def mark_conflict(self) -> None:
        """Mark current feature as having merge conflict."""
        if not self.current_feature:
            return

        await self._run_mcp_tool(
            "feature_mark_conflict",
            {"feature_id": self.current_feature["id"], "worker_id": self.worker_name}
        )
        self.current_feature = None

    async def mark_failed(self) -> None:
        """Mark current feature as permanently failed."""
        if not self.current_feature:
            return

        await self._run_mcp_tool(
            "feature_mark_failed",
            {"feature_id": self.current_feature["id"], "worker_id": self.worker_name}
        )
        self.current_feature = None

    async def _run_mcp_tool(self, tool_name: str, params: dict) -> dict:
        """
        Run an MCP tool by calling feature_mcp.py directly.

        Database must be initialized via init_database_direct() before calling.
        """
        try:
            # Import the tool functions (DB already initialized in coordinator.run())
            from mcp_server.feature_mcp import (
                feature_claim_next,
                feature_heartbeat,
                feature_release_claim,
                feature_mark_passing,
                feature_mark_conflict,
                feature_mark_failed,
            )

            tool_map = {
                "feature_claim_next": feature_claim_next,
                "feature_heartbeat": feature_heartbeat,
                "feature_release_claim": feature_release_claim,
                "feature_mark_passing": feature_mark_passing,
                "feature_mark_conflict": feature_mark_conflict,
                "feature_mark_failed": feature_mark_failed,
            }

            tool_func = tool_map.get(tool_name)
            if not tool_func:
                return {"error": f"Unknown tool: {tool_name}"}

            result_json = tool_func(**params)
            return json.loads(result_json)

        except Exception as e:
            logger.error(f"MCP tool error: {e}")
            return {"error": str(e)}

    async def run_agent_session(self, feature: dict) -> bool:
        """
        Run a single agent session to implement a feature.

        Args:
            feature: Feature dict from claim

        Returns:
            True if feature was successfully implemented.
        """
        logger.info(f"Worker {self.worker_name} starting feature: {feature.get('name', feature.get('id'))}")

        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            # Run the agent subprocess in the worktree
            # Uses create_subprocess_exec (safe, no shell injection)
            # CRITICAL: --project-dir points to ORIGINAL project (for shared DB)
            #           --worktree-path is where code changes happen
            #           --feature-id binds worker to coordinator's claimed feature
            cmd = [
                sys.executable,
                str(Path(__file__).parent / "autonomous_agent_demo.py"),
                "--project-dir", str(self.project_dir),  # Shared DB location
                "--worktree-path", str(self.worktree_path),  # Code changes location
                "--feature-id", str(feature["id"]),  # Bound to claimed feature
                "--model", self.model,  # Pass model through
                "--max-iterations", "1",
            ]

            if self.yolo_mode:
                cmd.append("--yolo")

            logger.debug(f"Worker {self.worker_name} running: {' '.join(cmd)}")

            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(self.worktree_path),
            )

            # Stream output with worker prefix
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                print(f"[{self.worker_name}] {text}")

            await self.process.wait()

            success = self.process.returncode == 0
            logger.info(f"Worker {self.worker_name} finished feature with code: {self.process.returncode}")

            return success

        except asyncio.CancelledError:
            if self.process:
                self.process.terminate()
            raise

        finally:
            # Cancel heartbeat
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
            self.process = None

    async def _heartbeat_loop(self) -> None:
        """Background task to send periodic heartbeats."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if not await self.heartbeat():
                    logger.warning(f"Worker {self.worker_name} lost lease!")
                    break
        except asyncio.CancelledError:
            pass


class ParallelCoordinator:
    """
    Coordinates multiple parallel agent workers.

    Manages worktree lifecycle, spawns workers, handles merges,
    and monitors for stale claims.
    """

    def __init__(
        self,
        project_dir: Path,
        worker_count: int = 3,
        model: str = "claude-sonnet-4-20250514",
        yolo_mode: bool = False,
    ):
        self.project_dir = project_dir
        self.worker_count = worker_count
        self.model = model
        self.yolo_mode = yolo_mode

        self.worktree_mgr = WorktreeManager(project_dir, worker_count)
        self.workers: dict[int, WorkerProcess] = {}
        self.worktree_paths: dict[int, Path] = {}

        self.shutdown_event = asyncio.Event()
        self.merge_lock = asyncio.Lock()

    async def run(self) -> None:
        """Main coordinator loop."""
        logger.info(f"Starting parallel coordinator with {self.worker_count} workers")
        logger.info(f"Project: {self.project_dir}")
        logger.info(f"Mode: {'YOLO' if self.yolo_mode else 'Standard'}")

        # Initialize database BEFORE any MCP tool calls
        # Uses project_dir (not worktree) so all workers share the same DB
        init_database_direct(self.project_dir)
        logger.info("Database initialized for parallel execution")

        # Verify git repo
        if not await self.worktree_mgr.is_git_repo():
            raise RuntimeError(f"Not a git repository: {self.project_dir}")

        try:
            # Setup worktrees
            logger.info("Setting up worktrees...")
            self.worktree_paths = await self.worktree_mgr.setup_all_worktrees()

            # Create worker processes
            for worker_id, worktree_path in self.worktree_paths.items():
                self.workers[worker_id] = WorkerProcess(
                    worker_id=worker_id,
                    worktree_path=worktree_path,
                    project_dir=self.project_dir,
                    model=self.model,
                    yolo_mode=self.yolo_mode,
                )
                logger.info(f"Created worker-{worker_id} at {worktree_path}")

            # Start worker tasks
            worker_tasks = {
                worker_id: asyncio.create_task(
                    self._run_worker_loop(worker_id),
                    name=f"worker-{worker_id}"
                )
                for worker_id in self.workers
            }

            # Start monitor task
            monitor_task = asyncio.create_task(
                self._monitor_loop(),
                name="monitor"
            )

            # Wait for all workers to complete
            logger.info("All workers started, waiting for completion...")
            await asyncio.gather(*worker_tasks.values())

            # Workers done, cancel monitor
            logger.info("All workers completed")
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        finally:
            # Always cleanup
            logger.info("Cleaning up...")
            await self.worktree_mgr.cleanup_all()

        # Final summary
        await self._print_final_summary()

    async def _run_worker_loop(self, worker_id: int) -> None:
        """
        Main loop for a single worker.

        Claims features, processes them, and merges results.
        """
        worker = self.workers[worker_id]
        worktree_path = self.worktree_paths[worker_id]
        idle_backoff = IDLE_BACKOFF_INITIAL

        while not self.shutdown_event.is_set():
            try:
                result = await self._process_one_feature(worker, worktree_path)

                if result == "success":
                    idle_backoff = IDLE_BACKOFF_INITIAL  # Reset backoff

                elif result == "idle":
                    # Check if project is complete
                    if await self._is_project_complete():
                        logger.info(f"Worker {worker.worker_name}: Project complete, exiting")
                        break

                    logger.debug(f"Worker {worker.worker_name}: Idle, backing off {idle_backoff}s")
                    await asyncio.sleep(idle_backoff)
                    idle_backoff = min(idle_backoff * 2, IDLE_BACKOFF_MAX)

                elif result == "failed":
                    # Feature failed but continue to next
                    idle_backoff = IDLE_BACKOFF_INITIAL

            except asyncio.CancelledError:
                # Cleanup on cancellation
                if worker.current_feature:
                    await worker.release_claim()
                raise

            except Exception as e:
                logger.exception(f"Worker {worker.worker_name} error: {e}")
                if worker.current_feature:
                    await worker.release_claim()
                await asyncio.sleep(idle_backoff)

    async def _process_one_feature(
        self,
        worker: WorkerProcess,
        worktree_path: Path
    ) -> str:
        """
        Process a single feature: claim -> implement -> merge.

        Returns:
            "success" - feature completed and merged
            "idle" - no features available
            "failed" - feature failed (released or marked failed)
            "conflict" - merge conflict (marked conflict)
        """
        # 1. Claim a feature
        feature = await worker.claim_feature()
        if feature is None:
            return "idle"

        feature_id = feature.get("id")
        feature_name = feature.get("name", f"Feature {feature_id}")
        logger.info(f"Worker {worker.worker_name} claimed: {feature_name}")

        # 2. Create feature branch in worktree
        feature_branch = await self.worktree_mgr.checkout_feature_branch(
            worker.worker_id, feature_id, worktree_path
        )

        # 3. Run agent session
        success = await worker.run_agent_session(feature)

        if not success:
            logger.warning(f"Worker {worker.worker_name}: Feature {feature_name} failed")
            await worker.release_claim()  # Return to pending for retry
            return "failed"

        # 4. Merge with serialization
        async with self.merge_lock:
            merge_success, merge_msg = await self.worktree_mgr.merge_feature_branch(
                feature_branch, worktree_path
            )

            if merge_success:
                await worker.mark_passing()
                await self.worktree_mgr.delete_feature_branch(feature_branch)
                logger.info(f"Worker {worker.worker_name}: {feature_name} PASSING - {merge_msg}")
                return "success"
            else:
                await worker.mark_conflict()
                logger.warning(f"Worker {worker.worker_name}: {feature_name} CONFLICT - {merge_msg}")
                return "conflict"

    async def _monitor_loop(self) -> None:
        """
        Background monitor for health checks and stale claim recovery.
        """
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(MONITOR_INTERVAL)
                await self._recover_stale_claims()
        except asyncio.CancelledError:
            pass

    async def _recover_stale_claims(self) -> None:
        """Reclaim features with expired leases."""
        try:
            sys.path.insert(0, str(self.project_dir.parent))
            from mcp_server.feature_mcp import feature_reclaim_stale

            result_json = feature_reclaim_stale(LEASE_TIMEOUT_MINUTES)
            result = json.loads(result_json)

            reclaimed = result.get("reclaimed", 0)
            if reclaimed > 0:
                logger.info(f"Reclaimed {reclaimed} stale features")

        except Exception as e:
            logger.error(f"Error reclaiming stale claims: {e}")

    async def _is_project_complete(self) -> bool:
        """Check if no more automated work remains."""
        try:
            sys.path.insert(0, str(self.project_dir.parent))
            from mcp_server.feature_mcp import feature_is_project_complete

            result_json = feature_is_project_complete()
            result = json.loads(result_json)

            return result.get("complete", False)

        except Exception as e:
            logger.error(f"Error checking project completion: {e}")
            return False

    async def _print_final_summary(self) -> None:
        """Print final progress summary."""
        try:
            sys.path.insert(0, str(self.project_dir.parent))
            from mcp_server.feature_mcp import feature_get_stats

            result_json = feature_get_stats()
            stats = json.loads(result_json)

            print("\n" + "=" * 70)
            print("  PARALLEL EXECUTION COMPLETE")
            print("=" * 70)
            print(f"\nProject: {self.project_dir}")
            print(f"Workers: {self.worker_count}")
            print("\nResults:")
            print(f"  Passing:     {stats.get('passing', 0)}")
            print(f"  Pending:     {stats.get('pending', 0)}")
            print(f"  In Progress: {stats.get('in_progress', 0)}")
            print(f"  Conflicts:   {stats.get('conflict', 0)}")
            print(f"  Failed:      {stats.get('failed', 0)}")
            print(f"  Total:       {stats.get('total', 0)}")
            print(f"  Progress:    {stats.get('percentage', 0)}%")
            print("=" * 70)

        except Exception as e:
            logger.error(f"Error printing summary: {e}")

    def request_shutdown(self) -> None:
        """Request graceful shutdown of all workers."""
        logger.info("Shutdown requested")
        self.shutdown_event.set()
