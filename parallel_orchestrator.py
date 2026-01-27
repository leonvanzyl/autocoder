"""
Parallel Orchestrator
=====================

Unified orchestrator that handles all agent lifecycle:
- Initialization: Creates features from app_spec if needed
- Coding agents: Implement features one at a time
- Testing agents: Regression test passing features (optional)

Uses dependency-aware scheduling to ensure features are only started when their
dependencies are satisfied.

Usage:
    # Entry point (always uses orchestrator)
    python autonomous_agent_demo.py --project-dir my-app --concurrency 3

    # Direct orchestrator usage
    python parallel_orchestrator.py --project-dir my-app --max-concurrency 3
"""

import asyncio
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from api.database import Feature, create_database
from api.dependency_resolver import are_dependencies_satisfied, compute_scheduling_scores
from api.logging_config import log_section, setup_orchestrator_logging
from progress import has_features
from server.utils.process_utils import kill_process_tree

# Root directory of autocoder (where this script and autonomous_agent_demo.py live)
AUTOCODER_ROOT = Path(__file__).parent.resolve()

# Debug log file path
DEBUG_LOG_FILE = AUTOCODER_ROOT / "logs" / "orchestrator.log"

# Module logger - initialized lazily in run_loop
logger: logging.Logger = logging.getLogger("orchestrator")


def _dump_database_state(session, label: str = ""):
    """Helper to dump full database state to debug log."""
    from api.database import Feature
    all_features = session.query(Feature).all()

    passing = [f for f in all_features if f.passes]
    in_progress = [f for f in all_features if f.in_progress and not f.passes]
    pending = [f for f in all_features if not f.passes and not f.in_progress]

    logger.debug(
        f"[DB_DUMP] Full database state {label} | "
        f"total={len(all_features)} passing={len(passing)} in_progress={len(in_progress)} pending={len(pending)}"
    )
    logger.debug(f"    passing_ids: {[f.id for f in passing]}")
    logger.debug(f"    in_progress_ids: {[f.id for f in in_progress]}")
    logger.debug(f"    pending_ids (first 10): {[f.id for f in pending[:10]]}")

# =============================================================================
# Process Limits
# =============================================================================
# These constants bound the number of concurrent agent processes to prevent
# resource exhaustion (memory, CPU, API rate limits).
#
# MAX_PARALLEL_AGENTS: Max concurrent coding agents (each is a Claude session)
# MAX_TOTAL_AGENTS: Hard limit on total child processes (coding + testing)
#
# Expected process count during normal operation:
#   - 1 orchestrator process (this script)
#   - Up to MAX_PARALLEL_AGENTS coding agents
#   - Up to max_concurrency testing agents
#   - Total never exceeds MAX_TOTAL_AGENTS + 1 (including orchestrator)
#
# Stress test verification:
#   1. Note baseline: tasklist | findstr python | find /c /v ""
#   2. Run: python autonomous_agent_demo.py --project-dir test --parallel --max-concurrency 5
#   3. During run: count should never exceed baseline + 11 (1 orchestrator + 10 agents)
#   4. After stop: should return to baseline
# =============================================================================
MAX_PARALLEL_AGENTS = 5
MAX_TOTAL_AGENTS = 10
DEFAULT_CONCURRENCY = 3
POLL_INTERVAL = 5  # seconds between checking for ready features
MAX_FEATURE_RETRIES = 3  # Maximum times to retry a failed feature
INITIALIZER_TIMEOUT = 1800  # 30 minutes timeout for initializer


class ParallelOrchestrator:
    """Orchestrates parallel execution of independent features.

    Process bounds:
    - Up to MAX_PARALLEL_AGENTS (5) coding agents concurrently
    - Up to max_concurrency testing agents concurrently
    - Hard limit of MAX_TOTAL_AGENTS (10) total child processes
    """

    def __init__(
        self,
        project_dir: Path,
        max_concurrency: int = DEFAULT_CONCURRENCY,
        model: str = None,
        yolo_mode: bool = False,
        testing_agent_ratio: int = 1,
        on_output: Callable[[int, str], None] = None,
        on_status: Callable[[int, str], None] = None,
    ):
        """Initialize the orchestrator.

        Args:
            project_dir: Path to the project directory
            max_concurrency: Maximum number of concurrent coding agents (1-5).
                Also caps testing agents at the same limit.
            model: Claude model to use (or None for default)
            yolo_mode: Whether to run in YOLO mode (skip testing agents entirely)
            testing_agent_ratio: Number of regression testing agents to maintain (0-3).
                0 = disabled, 1-3 = maintain that many testing agents running independently.
            on_output: Callback for agent output (feature_id, line)
            on_status: Callback for agent status changes (feature_id, status)
        """
        self.project_dir = project_dir
        self.max_concurrency = min(max(max_concurrency, 1), MAX_PARALLEL_AGENTS)
        self.model = model
        self.yolo_mode = yolo_mode
        self.testing_agent_ratio = min(max(testing_agent_ratio, 0), 3)  # Clamp 0-3
        self.on_output = on_output
        self.on_status = on_status

        # Thread-safe state
        self._lock = threading.Lock()
        # Coding agents: feature_id -> process
        self.running_coding_agents: dict[int, subprocess.Popen] = {}
        # Testing agents: agent_id (pid) -> (feature_id, process)
        # Using pid as key allows multiple agents to test the same feature
        self.running_testing_agents: dict[int, tuple[int, subprocess.Popen] | None] = {}
        # Legacy alias for backward compatibility
        self.running_agents = self.running_coding_agents
        self.abort_events: dict[int, threading.Event] = {}
        self.is_running = False

        # Track feature failures to prevent infinite retry loops
        self._failure_counts: dict[int, int] = {}

        # Session tracking for logging/debugging
        self.session_start_time: datetime = None

        # Event signaled when any agent completes, allowing the main loop to wake
        # immediately instead of waiting for the full POLL_INTERVAL timeout.
        # This reduces latency when spawning the next feature after completion.
        self._agent_completed_event: asyncio.Event = None  # Created in run_loop
        self._event_loop: asyncio.AbstractEventLoop = None  # Stored for thread-safe signaling

        # Database session for this orchestrator
        self._engine, self._session_maker = create_database(project_dir)

    def get_session(self):
        """Get a new database session."""
        return self._session_maker()

    def _get_random_passing_feature(self) -> int | None:
        """Get a random passing feature for regression testing (no claim needed).

        Testing agents can test the same feature concurrently - it doesn't matter.
        This simplifies the architecture by removing unnecessary coordination.

        Returns the feature ID if available, None if no passing features exist.
        """
        from sqlalchemy.sql.expression import func

        session = self.get_session()
        try:
            # Find a passing feature that's not currently being coded
            # Multiple testing agents can test the same feature - that's fine
            feature = (
                session.query(Feature)
                .filter(Feature.passes == True)
                .filter(Feature.in_progress == False)  # Don't test while coding
                .order_by(func.random())
                .first()
            )
            return feature.id if feature else None
        finally:
            session.close()

    def get_resumable_features(self) -> list[dict]:
        """Get features that were left in_progress from a previous session.

        These are features where in_progress=True but passes=False, and they're
        not currently being worked on by this orchestrator. This handles the case
        where a previous session was interrupted before completing the feature.
        """
        session = self.get_session()
        try:
            # Force fresh read from database to avoid stale cached data
            # This is critical when agent subprocesses have committed changes
            session.expire_all()

            # Find features that are in_progress but not complete
            stale = session.query(Feature).filter(
                Feature.in_progress == True,
                Feature.passes == False
            ).all()

            resumable = []
            for f in stale:
                # Skip if already running in this orchestrator instance
                with self._lock:
                    if f.id in self.running_coding_agents:
                        continue
                # Skip if feature has failed too many times
                if self._failure_counts.get(f.id, 0) >= MAX_FEATURE_RETRIES:
                    continue
                resumable.append(f.to_dict())

            # Sort by scheduling score (higher = first), then priority, then id
            all_dicts = [f.to_dict() for f in session.query(Feature).all()]
            scores = compute_scheduling_scores(all_dicts)
            resumable.sort(key=lambda f: (-scores.get(f["id"], 0), f["priority"], f["id"]))
            return resumable
        finally:
            session.close()

    def get_ready_features(self) -> list[dict]:
        """Get features with satisfied dependencies, not already running."""
        session = self.get_session()
        try:
            # Force fresh read from database to avoid stale cached data
            # This is critical when agent subprocesses have committed changes
            session.expire_all()

            all_features = session.query(Feature).all()
            all_dicts = [f.to_dict() for f in all_features]

            # Pre-compute passing_ids once to avoid O(n^2) in the loop
            passing_ids = {f.id for f in all_features if f.passes}

            ready = []
            skipped_reasons = {"passes": 0, "in_progress": 0, "running": 0, "failed": 0, "deps": 0}
            for f in all_features:
                if f.passes:
                    skipped_reasons["passes"] += 1
                    continue
                if f.in_progress:
                    skipped_reasons["in_progress"] += 1
                    continue
                # Skip if already running in this orchestrator
                with self._lock:
                    if f.id in self.running_coding_agents:
                        skipped_reasons["running"] += 1
                        continue
                # Skip if feature has failed too many times
                if self._failure_counts.get(f.id, 0) >= MAX_FEATURE_RETRIES:
                    skipped_reasons["failed"] += 1
                    continue
                # Check dependencies (pass pre-computed passing_ids)
                if are_dependencies_satisfied(f.to_dict(), all_dicts, passing_ids):
                    ready.append(f.to_dict())
                else:
                    skipped_reasons["deps"] += 1

            # Sort by scheduling score (higher = first), then priority, then id
            scores = compute_scheduling_scores(all_dicts)
            ready.sort(key=lambda f: (-scores.get(f["id"], 0), f["priority"], f["id"]))

            # Debug logging
            passing = sum(1 for f in all_features if f.passes)
            in_progress = sum(1 for f in all_features if f.in_progress and not f.passes)
            print(
                f"[DEBUG] get_ready_features: {len(ready)} ready, "
                f"{passing} passing, {in_progress} in_progress, {len(all_features)} total",
                flush=True
            )
            print(
                f"[DEBUG]   Skipped: {skipped_reasons['passes']} passing, {skipped_reasons['in_progress']} in_progress, "
                f"{skipped_reasons['running']} running, {skipped_reasons['failed']} failed, {skipped_reasons['deps']} blocked by deps",
                flush=True
            )

            # Log to debug file (but not every call to avoid spam)
            logger.debug(
                f"[READY] get_ready_features() | ready={len(ready)} passing={passing} "
                f"in_progress={in_progress} total={len(all_features)}"
            )
            logger.debug(f"    ready_ids (first 5): {[f['id'] for f in ready[:5]]}")
            logger.debug(f"    skipped: {skipped_reasons}")

            return ready
        finally:
            session.close()

    def get_all_complete(self) -> bool:
        """Check if all features are complete or permanently failed.

        Returns False if there are no features (initialization needed).
        """
        session = self.get_session()
        try:
            # Force fresh read from database to avoid stale cached data
            # This is critical when agent subprocesses have committed changes
            session.expire_all()

            all_features = session.query(Feature).all()

            # No features = NOT complete, need initialization
            if len(all_features) == 0:
                return False

            passing_count = 0
            failed_count = 0
            pending_count = 0
            for f in all_features:
                if f.passes:
                    passing_count += 1
                    continue  # Completed successfully
                if self._failure_counts.get(f.id, 0) >= MAX_FEATURE_RETRIES:
                    failed_count += 1
                    continue  # Permanently failed, count as "done"
                pending_count += 1

            total = len(all_features)
            is_complete = pending_count == 0
            print(
                f"[DEBUG] get_all_complete: {passing_count}/{total} passing, "
                f"{failed_count} failed, {pending_count} pending -> {is_complete}",
                flush=True
            )
            return is_complete
        finally:
            session.close()

    def get_passing_count(self) -> int:
        """Get the number of passing features."""
        session = self.get_session()
        try:
            session.expire_all()
            return session.query(Feature).filter(Feature.passes == True).count()
        finally:
            session.close()

    def _maintain_testing_agents(self) -> None:
        """Maintain the desired count of testing agents independently.

        This runs every loop iteration and spawns testing agents as needed to maintain
        the configured testing_agent_ratio. Testing agents run independently from
        coding agents and continuously re-test passing features to catch regressions.

        Multiple testing agents can test the same feature concurrently - this is
        intentional and simplifies the architecture by removing claim coordination.

        Stops spawning when:
        - YOLO mode is enabled
        - testing_agent_ratio is 0
        - No passing features exist yet

        Race Condition Prevention:
        - Uses placeholder pattern to reserve slot inside lock before spawning
        - Placeholder ensures other threads see the reserved slot
        - Placeholder is replaced with real process after spawn completes
        """
        # Skip if testing is disabled
        if self.yolo_mode or self.testing_agent_ratio == 0:
            return

        # No testing until there are passing features
        passing_count = self.get_passing_count()
        if passing_count == 0:
            return

        # Don't spawn testing agents if all features are already complete
        if self.get_all_complete():
            return

        # Spawn testing agents one at a time, using placeholder pattern to prevent races
        while True:
            placeholder_key = None
            spawn_index = 0

            # Check limits and reserve slot atomically
            with self._lock:
                current_testing = len(self.running_testing_agents)
                desired = self.testing_agent_ratio
                total_agents = len(self.running_coding_agents) + current_testing

                # Check if we need more testing agents
                if current_testing >= desired:
                    return  # Already at desired count

                # Check hard limit on total agents
                if total_agents >= MAX_TOTAL_AGENTS:
                    return  # At max total agents

                # Reserve slot with placeholder (negative key to avoid collision with feature IDs)
                # This prevents other threads from exceeding limits during spawn
                placeholder_key = -(current_testing + 1)
                self.running_testing_agents[placeholder_key] = None  # Placeholder
                spawn_index = current_testing + 1
                logger.debug(f"[TESTING] Reserved slot for testing agent ({spawn_index}/{desired}) | passing_count={passing_count}")

            # Spawn outside lock (I/O bound operation)
            # Wrapped in try/except to ensure placeholder cleanup on unexpected errors
            print(f"[DEBUG] Spawning testing agent ({spawn_index}/{desired})", flush=True)
            try:
                success, _ = self._spawn_testing_agent(placeholder_key=placeholder_key)
            except Exception as e:
                # Ensure placeholder is removed on any exception
                logger.error(f"[TESTING] Exception during spawn: {e}")
                success = False

            # If spawn failed, remove the placeholder
            if not success:
                with self._lock:
                    self.running_testing_agents.pop(placeholder_key, None)
                break  # Exit on failure to avoid infinite loop

    def start_feature(self, feature_id: int, resume: bool = False) -> tuple[bool, str]:
        """Start a single coding agent for a feature.

        Args:
            feature_id: ID of the feature to start
            resume: If True, resume a feature that's already in_progress from a previous session

        Returns:
            Tuple of (success, message)

        Transactional State Management:
        - If spawn fails after marking in_progress, we rollback the database state
        - This prevents features from getting stuck in a limbo state
        """
        with self._lock:
            if feature_id in self.running_coding_agents:
                return False, "Feature already running"
            if len(self.running_coding_agents) >= self.max_concurrency:
                return False, "At max concurrency"
            # Enforce hard limit on total agents (coding + testing)
            total_agents = len(self.running_coding_agents) + len(self.running_testing_agents)
            if total_agents >= MAX_TOTAL_AGENTS:
                return False, f"At max total agents ({total_agents}/{MAX_TOTAL_AGENTS})"

        # Mark as in_progress in database (or verify it's resumable)
        marked_in_progress = False
        session = self.get_session()
        try:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if not feature:
                return False, "Feature not found"
            if feature.passes:
                return False, "Feature already complete"

            if resume:
                # Resuming: feature should already be in_progress
                if not feature.in_progress:
                    return False, "Feature not in progress, cannot resume"
            else:
                # Starting fresh: feature should not be in_progress
                if feature.in_progress:
                    return False, "Feature already in progress"
                feature.in_progress = True
                session.commit()
                marked_in_progress = True
        finally:
            session.close()

        # Start coding agent subprocess
        success, message = self._spawn_coding_agent(feature_id)
        if not success:
            # Rollback in_progress if we set it
            if marked_in_progress:
                rollback_session = self.get_session()
                try:
                    feature = rollback_session.query(Feature).filter(Feature.id == feature_id).first()
                    if feature and feature.in_progress:
                        feature.in_progress = False
                        rollback_session.commit()
                        logger.debug(f"[ROLLBACK] Cleared in_progress for feature #{feature_id} after spawn failure")
                except Exception as e:
                    logger.error(f"[ROLLBACK] Failed to clear in_progress for feature #{feature_id}: {e}")
                finally:
                    rollback_session.close()
            return False, message

        # NOTE: Testing agents are now maintained independently via _maintain_testing_agents()
        # called in the main loop, rather than being spawned when coding agents start.

        return True, f"Started feature {feature_id}"

    def _spawn_coding_agent(self, feature_id: int) -> tuple[bool, str]:
        """Spawn a coding agent subprocess for a specific feature."""
        # Create abort event
        abort_event = threading.Event()

        # Start subprocess for this feature
        cmd = [
            sys.executable,
            "-u",  # Force unbuffered stdout/stderr
            str(AUTOCODER_ROOT / "autonomous_agent_demo.py"),
            "--project-dir", str(self.project_dir),
            "--max-iterations", "1",
            "--agent-type", "coding",
            "--feature-id", str(feature_id),
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.yolo_mode:
            cmd.append("--yolo")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(AUTOCODER_ROOT),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except Exception as e:
            # Reset in_progress on failure
            session = self.get_session()
            try:
                feature = session.query(Feature).filter(Feature.id == feature_id).first()
                if feature:
                    feature.in_progress = False
                    session.commit()
            finally:
                session.close()
            return False, f"Failed to start agent: {e}"

        with self._lock:
            self.running_coding_agents[feature_id] = proc
            self.abort_events[feature_id] = abort_event

        # Start output reader thread
        threading.Thread(
            target=self._read_output,
            args=(feature_id, proc, abort_event, "coding"),
            daemon=True
        ).start()

        if self.on_status:
            self.on_status(feature_id, "running")

        print(f"Started coding agent for feature #{feature_id}", flush=True)
        return True, f"Started feature {feature_id}"

    def _spawn_testing_agent(self, placeholder_key: int | None = None) -> tuple[bool, str]:
        """Spawn a testing agent subprocess for regression testing.

        Picks a random passing feature to test. Multiple testing agents can test
        the same feature concurrently - this is intentional and simplifies the
        architecture by removing claim coordination.

        Args:
            placeholder_key: If provided, this slot was pre-reserved by _maintain_testing_agents.
                The placeholder will be replaced with the real process once spawned.
                If None, performs its own limit checking (legacy behavior).
        """
        # If no placeholder was provided, check limits (legacy direct-call behavior)
        if placeholder_key is None:
            with self._lock:
                current_testing_count = len(self.running_testing_agents)
                if current_testing_count >= self.max_concurrency:
                    logger.debug(f"[TESTING] Skipped spawn - at max testing agents ({current_testing_count}/{self.max_concurrency})")
                    return False, f"At max testing agents ({current_testing_count})"
                total_agents = len(self.running_coding_agents) + len(self.running_testing_agents)
                if total_agents >= MAX_TOTAL_AGENTS:
                    logger.debug(f"[TESTING] Skipped spawn - at max total agents ({total_agents}/{MAX_TOTAL_AGENTS})")
                    return False, f"At max total agents ({total_agents})"

        # Pick a random passing feature (no claim needed - concurrent testing is fine)
        feature_id = self._get_random_passing_feature()
        if feature_id is None:
            logger.debug("[TESTING] No features available for testing")
            return False, "No features available for testing"

        logger.debug(f"[TESTING] Selected feature #{feature_id} for testing")

        cmd = [
            sys.executable,
            "-u",
            str(AUTOCODER_ROOT / "autonomous_agent_demo.py"),
            "--project-dir", str(self.project_dir),
            "--max-iterations", "1",
            "--agent-type", "testing",
            "--testing-feature-id", str(feature_id),
        ]
        if self.model:
            cmd.extend(["--model", self.model])

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(AUTOCODER_ROOT),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except Exception as e:
            logger.error(f"[TESTING] FAILED to spawn testing agent: {e}")
            return False, f"Failed to start testing agent: {e}"

        # Register process with pid as key (allows multiple agents for same feature)
        with self._lock:
            if placeholder_key is not None:
                # Remove placeholder and add real entry
                self.running_testing_agents.pop(placeholder_key, None)
            self.running_testing_agents[proc.pid] = (feature_id, proc)
            testing_count = len(self.running_testing_agents)

        # Start output reader thread with feature ID (same as coding agents)
        threading.Thread(
            target=self._read_output,
            args=(feature_id, proc, threading.Event(), "testing"),
            daemon=True
        ).start()

        print(f"Started testing agent for feature #{feature_id} (PID {proc.pid})", flush=True)
        logger.info(f"[TESTING] Spawned testing agent for feature #{feature_id} | pid={proc.pid} total={testing_count}")
        return True, f"Started testing agent for feature #{feature_id}"

    async def _run_initializer(self) -> bool:
        """Run initializer agent as async subprocess.

        Returns True if initialization succeeded (features were created).
        Uses asyncio subprocess for non-blocking I/O.
        """
        log_section(logger, "INITIALIZER PHASE")
        logger.info(f"[INIT] Starting initializer subprocess | project_dir={self.project_dir}")

        cmd = [
            sys.executable, "-u",
            str(AUTOCODER_ROOT / "autonomous_agent_demo.py"),
            "--project-dir", str(self.project_dir),
            "--agent-type", "initializer",
            "--max-iterations", "1",
        ]
        if self.model:
            cmd.extend(["--model", self.model])

        print("Running initializer agent...", flush=True)

        # Use asyncio subprocess for non-blocking I/O
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(AUTOCODER_ROOT),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        logger.info(f"[INIT] Initializer subprocess started | pid={proc.pid}")

        # Stream output with timeout using native async I/O
        try:
            async def stream_output():
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    decoded_line = line.decode().rstrip()
                    print(decoded_line, flush=True)
                    if self.on_output:
                        self.on_output(0, decoded_line)
                await proc.wait()

            await asyncio.wait_for(stream_output(), timeout=INITIALIZER_TIMEOUT)

        except asyncio.TimeoutError:
            print(f"ERROR: Initializer timed out after {INITIALIZER_TIMEOUT // 60} minutes", flush=True)
            logger.error(f"[INIT] TIMEOUT - Initializer exceeded time limit ({INITIALIZER_TIMEOUT // 60} minutes)")
            proc.kill()
            await proc.wait()
            logger.info("[INIT] Killed timed-out initializer process")
            return False

        logger.info(f"[INIT] Initializer subprocess completed | return_code={proc.returncode}")

        if proc.returncode != 0:
            print(f"ERROR: Initializer failed with exit code {proc.returncode}", flush=True)
            return False

        return True

    def _read_output(
        self,
        feature_id: int | None,
        proc: subprocess.Popen,
        abort: threading.Event,
        agent_type: Literal["coding", "testing"] = "coding",
    ):
        """Read output from subprocess and emit events."""
        try:
            for line in proc.stdout:
                if abort.is_set():
                    break
                line = line.rstrip()
                if self.on_output:
                    self.on_output(feature_id or 0, line)
                else:
                    # Both coding and testing agents now use [Feature #X] format
                    print(f"[Feature #{feature_id}] {line}", flush=True)
            proc.wait()
        finally:
            self._on_agent_complete(feature_id, proc.returncode, agent_type, proc)

    def _signal_agent_completed(self):
        """Signal that an agent has completed, waking the main loop.

        This method is safe to call from any thread. It schedules the event.set()
        call to run on the event loop thread to avoid cross-thread issues with
        asyncio.Event.
        """
        if self._agent_completed_event is not None and self._event_loop is not None:
            try:
                # Use the stored event loop reference to schedule the set() call
                # This is necessary because asyncio.Event is not thread-safe and
                # asyncio.get_event_loop() fails in threads without an event loop
                if self._event_loop.is_running():
                    self._event_loop.call_soon_threadsafe(self._agent_completed_event.set)
                else:
                    # Fallback: set directly if loop isn't running (shouldn't happen during normal operation)
                    self._agent_completed_event.set()
            except RuntimeError:
                # Event loop closed, ignore (orchestrator may be shutting down)
                pass

    async def _wait_for_agent_completion(self, timeout: float = POLL_INTERVAL):
        """Wait for an agent to complete or until timeout expires.

        This replaces fixed `asyncio.sleep(POLL_INTERVAL)` calls with event-based
        waiting. When an agent completes, _signal_agent_completed() sets the event,
        causing this method to return immediately. If no agent completes within
        the timeout, we return anyway to check for ready features.

        Args:
            timeout: Maximum seconds to wait (default: POLL_INTERVAL)
        """
        if self._agent_completed_event is None:
            # Fallback if event not initialized (shouldn't happen in normal operation)
            await asyncio.sleep(timeout)
            return

        try:
            await asyncio.wait_for(self._agent_completed_event.wait(), timeout=timeout)
            # Event was set - an agent completed. Clear it for the next wait cycle.
            self._agent_completed_event.clear()
            logger.debug("[EVENT] Woke up immediately - agent completed")
        except asyncio.TimeoutError:
            # Timeout reached without agent completion - this is normal, just check anyway
            pass

    def _on_agent_complete(
        self,
        feature_id: int | None,
        return_code: int,
        agent_type: Literal["coding", "testing"],
        proc: subprocess.Popen,
    ):
        """Handle agent completion.

        For coding agents:
        - ALWAYS clears in_progress when agent exits, regardless of success/failure.
        - This prevents features from getting stuck if an agent crashes or is killed.
        - The agent marks features as passing BEFORE clearing in_progress, so this
          is safe.

        For testing agents:
        - Remove from running dict (no claim to release - concurrent testing is allowed).

        Process Cleanup:
        - Ensures process is fully terminated before removing from tracking dict
        - This prevents zombie processes from accumulating
        """
        # Ensure process is fully terminated (should already be done by wait() in _read_output)
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5.0)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=2.0)
                except Exception as e:
                    logger.warning(f"[ZOMBIE] Failed to terminate process {proc.pid}: {e}")

        if agent_type == "testing":
            with self._lock:
                # Remove from dict by finding the agent_id for this proc
                # Also clean up any placeholders (None values)
                keys_to_remove = []
                for agent_id, entry in list(self.running_testing_agents.items()):
                    if entry is None:  # Orphaned placeholder
                        keys_to_remove.append(agent_id)
                    elif entry[1] is proc:  # entry is (feature_id, proc)
                        keys_to_remove.append(agent_id)
                for key in keys_to_remove:
                    del self.running_testing_agents[key]

            status = "completed" if return_code == 0 else "failed"
            print(f"Feature #{feature_id} testing {status}", flush=True)
            logger.info(f"[COMPLETE] Testing agent for feature #{feature_id} finished | pid={proc.pid} status={status}")
            # Signal main loop that an agent slot is available
            self._signal_agent_completed()
            return

        # Coding agent completion
        status = "success" if return_code == 0 else "failed"
        logger.info(f"[COMPLETE] Coding agent for feature #{feature_id} finished | return_code={return_code} status={status}")

        with self._lock:
            self.running_coding_agents.pop(feature_id, None)
            self.abort_events.pop(feature_id, None)

        # Refresh database connection to see subprocess commits
        # The coding agent runs as a subprocess and commits changes (e.g., passes=True).
        # For SQLite WAL mode, we need to ensure the connection pool sees fresh data.
        # Disposing and recreating the engine is more reliable than session.expire_all()
        # for cross-process commit visibility, though heavier weight.
        if self._engine is not None:
            self._engine.dispose()
            self._engine, self._session_maker = create_database(self.project_dir)
            logger.debug("[DB] Recreated database connection after agent completion")

        session = self.get_session()
        try:
            session.expire_all()
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            feature_passes = feature.passes if feature else None
            feature_in_progress = feature.in_progress if feature else None
            logger.debug(f"[DB] Feature #{feature_id} state after refresh | passes={feature_passes} in_progress={feature_in_progress}")
            if feature and feature.in_progress and not feature.passes:
                feature.in_progress = False
                session.commit()
                logger.debug(f"[DB] Cleared in_progress for feature #{feature_id} (agent failed)")
        finally:
            session.close()

        # Track failures to prevent infinite retry loops
        if return_code != 0:
            with self._lock:
                self._failure_counts[feature_id] = self._failure_counts.get(feature_id, 0) + 1
                failure_count = self._failure_counts[feature_id]
            if failure_count >= MAX_FEATURE_RETRIES:
                print(f"Feature #{feature_id} has failed {failure_count} times, will not retry", flush=True)
                logger.warning(f"[COMPLETE] Feature #{feature_id} exceeded max retries | failure_count={failure_count}")

        status = "completed" if return_code == 0 else "failed"
        if self.on_status:
            self.on_status(feature_id, status)
        # CRITICAL: This print triggers the WebSocket to emit agent_update with state='error' or 'success'
        print(f"Feature #{feature_id} {status}", flush=True)

        # Signal main loop that an agent slot is available
        self._signal_agent_completed()

        # NOTE: Testing agents are now spawned in start_feature() when coding agents START,
        # not here when they complete. This ensures 1:1 ratio and proper termination.

    def stop_feature(self, feature_id: int) -> tuple[bool, str]:
        """Stop a running coding agent and all its child processes."""
        with self._lock:
            if feature_id not in self.running_coding_agents:
                return False, "Feature not running"

            abort = self.abort_events.get(feature_id)
            proc = self.running_coding_agents.get(feature_id)

        if abort:
            abort.set()
        if proc:
            # Kill entire process tree to avoid orphaned children (e.g., browser instances)
            result = kill_process_tree(proc, timeout=5.0)
            logger.info(
                f"[STOP] Killed feature {feature_id} process tree | status={result.status} "
                f"children_found={result.children_found} terminated={result.children_terminated} killed={result.children_killed}"
            )

        return True, f"Stopped feature {feature_id}"

    def stop_all(self) -> None:
        """Stop all running agents (coding and testing)."""
        self.is_running = False

        # Stop coding agents
        with self._lock:
            feature_ids = list(self.running_coding_agents.keys())

        for fid in feature_ids:
            self.stop_feature(fid)

        # Stop testing agents (no claim to release - concurrent testing is allowed)
        with self._lock:
            testing_items = list(self.running_testing_agents.items())

        for agent_id, entry in testing_items:
            if entry is None:  # Skip placeholders
                continue
            feature_id, proc = entry
            result = kill_process_tree(proc, timeout=5.0)
            logger.info(
                f"[STOP] Killed testing agent for feature #{feature_id} (PID {proc.pid}) | status={result.status} "
                f"children_found={result.children_found} terminated={result.children_terminated} killed={result.children_killed}"
            )

    def _log_startup_info(self) -> None:
        """Log startup banner and settings."""
        log_section(logger, "ORCHESTRATOR STARTUP")
        logger.info("[STARTUP] Orchestrator run_loop starting")
        logger.info(f"    project_dir: {self.project_dir}")
        logger.info(f"    max_concurrency: {self.max_concurrency}")
        logger.info(f"    yolo_mode: {self.yolo_mode}")
        logger.info(f"    testing_agent_ratio: {self.testing_agent_ratio}")
        logger.info(f"    session_start_time: {self.session_start_time.isoformat()}")

        print("=" * 70, flush=True)
        print("  UNIFIED ORCHESTRATOR SETTINGS", flush=True)
        print("=" * 70, flush=True)
        print(f"Project: {self.project_dir}", flush=True)
        print(f"Max concurrency: {self.max_concurrency} coding agents", flush=True)
        print(f"YOLO mode: {self.yolo_mode}", flush=True)
        print(f"Regression agents: {self.testing_agent_ratio} (maintained independently)", flush=True)
        print("=" * 70, flush=True)
        print(flush=True)

    async def _run_initialization_phase(self) -> bool:
        """
        Run initialization phase if no features exist.

        Returns:
            True if initialization succeeded or was not needed, False if failed.
        """
        if has_features(self.project_dir):
            return True

        print("=" * 70, flush=True)
        print("  INITIALIZATION PHASE", flush=True)
        print("=" * 70, flush=True)
        print("No features found - running initializer agent first...", flush=True)
        print("NOTE: This may take 10-20+ minutes to generate features.", flush=True)
        print(flush=True)

        success = await self._run_initializer()

        if not success or not has_features(self.project_dir):
            print("ERROR: Initializer did not create features. Exiting.", flush=True)
            return False

        print(flush=True)
        print("=" * 70, flush=True)
        print("  INITIALIZATION COMPLETE - Starting feature loop", flush=True)
        print("=" * 70, flush=True)
        print(flush=True)

        # CRITICAL: Recreate database connection after initializer subprocess commits
        log_section(logger, "INITIALIZATION COMPLETE")
        logger.info("[INIT] Disposing old database engine and creating fresh connection")
        print("[DEBUG] Recreating database connection after initialization...", flush=True)
        if self._engine is not None:
            self._engine.dispose()
        self._engine, self._session_maker = create_database(self.project_dir)

        # Debug: Show state immediately after initialization
        print("[DEBUG] Post-initialization state check:", flush=True)
        print(f"[DEBUG]   max_concurrency={self.max_concurrency}", flush=True)
        print(f"[DEBUG]   yolo_mode={self.yolo_mode}", flush=True)
        print(f"[DEBUG]   testing_agent_ratio={self.testing_agent_ratio}", flush=True)

        # Verify features were created and are visible
        session = self.get_session()
        try:
            feature_count = session.query(Feature).count()
            all_features = session.query(Feature).all()
            feature_names = [f"{f.id}: {f.name}" for f in all_features[:10]]
            print(f"[DEBUG]   features in database={feature_count}", flush=True)
            logger.info(f"[INIT] Post-initialization database state | feature_count={feature_count}")
            logger.debug(f"    first_10_features: {feature_names}")
        finally:
            session.close()

        return True

    async def _handle_resumable_features(self, slots: int) -> bool:
        """
        Handle resuming features from previous session.

        Args:
            slots: Number of available slots for new agents.

        Returns:
            True if any features were resumed, False otherwise.
        """
        resumable = self.get_resumable_features()
        if not resumable:
            return False

        for feature in resumable[:slots]:
            print(f"Resuming feature #{feature['id']}: {feature['name']}", flush=True)
            self.start_feature(feature["id"], resume=True)
        await asyncio.sleep(2)
        return True

    async def _spawn_ready_features(self, current: int) -> bool:
        """
        Start new ready features up to capacity.

        Args:
            current: Current number of running coding agents.

        Returns:
            True if features were started or we should continue, False if blocked.
        """
        ready = self.get_ready_features()
        if not ready:
            # Wait for running features to complete
            if current > 0:
                await self._wait_for_agent_completion()
                return True

            # No ready features and nothing running
            # Force a fresh database check before declaring blocked
            session = self.get_session()
            try:
                session.expire_all()
            finally:
                session.close()

            # Recheck if all features are now complete
            if self.get_all_complete():
                return False  # Signal to break the loop

            # Still have pending features but all are blocked by dependencies
            print("No ready features available. All remaining features may be blocked by dependencies.", flush=True)
            await self._wait_for_agent_completion(timeout=POLL_INTERVAL * 2)
            return True

        # Start features up to capacity
        slots = self.max_concurrency - current
        print(f"[DEBUG] Spawning loop: {len(ready)} ready, {slots} slots available, max_concurrency={self.max_concurrency}", flush=True)
        print(f"[DEBUG] Will attempt to start {min(len(ready), slots)} features", flush=True)
        features_to_start = ready[:slots]
        print(f"[DEBUG] Features to start: {[f['id'] for f in features_to_start]}", flush=True)

        logger.debug(f"[SPAWN] Starting features batch | ready={len(ready)} slots={slots} to_start={[f['id'] for f in features_to_start]}")

        for i, feature in enumerate(features_to_start):
            print(f"[DEBUG] Starting feature {i+1}/{len(features_to_start)}: #{feature['id']} - {feature['name']}", flush=True)
            success, msg = self.start_feature(feature["id"])
            if not success:
                print(f"[DEBUG] Failed to start feature #{feature['id']}: {msg}", flush=True)
                logger.warning(f"[SPAWN] FAILED to start feature #{feature['id']} ({feature['name']}): {msg}")
            else:
                print(f"[DEBUG] Successfully started feature #{feature['id']}", flush=True)
                with self._lock:
                    running_count = len(self.running_coding_agents)
                    print(f"[DEBUG] Running coding agents after start: {running_count}", flush=True)
                logger.info(f"[SPAWN] Started feature #{feature['id']} ({feature['name']}) | running_agents={running_count}")

        await asyncio.sleep(2)  # Brief pause between starts
        return True

    async def _wait_for_all_agents(self) -> None:
        """Wait for all running agents (coding and testing) to complete."""
        print("Waiting for running agents to complete...", flush=True)
        while True:
            with self._lock:
                coding_done = len(self.running_coding_agents) == 0
                testing_done = len(self.running_testing_agents) == 0
                if coding_done and testing_done:
                    break
            # Use short timeout since we're just waiting for final agents to finish
            await self._wait_for_agent_completion(timeout=1.0)

    async def run_loop(self):
        """Main orchestration loop.

        This method coordinates multiple coding and testing agents:
        1. Initialization phase: Run initializer if no features exist
        2. Feature loop: Continuously spawn agents to work on features
        3. Cleanup: Wait for all agents to complete
        """
        self.is_running = True

        # Initialize async event for agent completion signaling
        self._agent_completed_event = asyncio.Event()
        self._event_loop = asyncio.get_running_loop()

        # Track session start for regression testing (UTC for consistency)
        self.session_start_time = datetime.now(timezone.utc)

        # Initialize the orchestrator logger (creates fresh log file)
        global logger
        DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        logger = setup_orchestrator_logging(DEBUG_LOG_FILE)
        self._log_startup_info()

        # Phase 1: Initialization (if needed)
        if not await self._run_initialization_phase():
            return

        # Phase 2: Feature loop
        await self._run_feature_loop()

        # Phase 3: Cleanup
        await self._wait_for_all_agents()
        print("Orchestrator finished.", flush=True)

    async def _run_feature_loop(self) -> None:
        """Run the main feature processing loop."""
        # Check for features to resume from previous session
        resumable = self.get_resumable_features()
        if resumable:
            print(f"Found {len(resumable)} feature(s) to resume from previous session:", flush=True)
            for f in resumable:
                print(f"  - Feature #{f['id']}: {f['name']}", flush=True)
            print(flush=True)

        log_section(logger, "FEATURE LOOP STARTING")
        loop_iteration = 0

        while self.is_running:
            loop_iteration += 1
            if loop_iteration <= 3:
                print(f"[DEBUG] === Loop iteration {loop_iteration} ===", flush=True)

            self._log_loop_iteration(loop_iteration)

            try:
                # Check if all complete
                if self.get_all_complete():
                    print("\nAll features complete!", flush=True)
                    break

                # Maintain testing agents independently
                self._maintain_testing_agents()

                # Check capacity and get current state
                with self._lock:
                    current = len(self.running_coding_agents)
                    current_testing = len(self.running_testing_agents)
                    running_ids = list(self.running_coding_agents.keys())

                logger.debug(
                    f"[CAPACITY] Checking | coding={current} testing={current_testing} "
                    f"running_ids={running_ids} max={self.max_concurrency} at_capacity={current >= self.max_concurrency}"
                )

                if current >= self.max_concurrency:
                    logger.debug("[CAPACITY] At max capacity, waiting for agent completion...")
                    await self._wait_for_agent_completion()
                    continue

                # Priority 1: Resume features from previous session
                slots = self.max_concurrency - current
                if await self._handle_resumable_features(slots):
                    continue

                # Priority 2: Start new ready features
                should_continue = await self._spawn_ready_features(current)
                if not should_continue:
                    break  # All features complete

            except Exception as e:
                print(f"Orchestrator error: {e}", flush=True)
                await self._wait_for_agent_completion()

    def _log_loop_iteration(self, loop_iteration: int) -> None:
        """Log debug information for the current loop iteration."""
        if loop_iteration <= 10 or loop_iteration % 5 == 0:
            with self._lock:
                running_ids = list(self.running_coding_agents.keys())
                testing_count = len(self.running_testing_agents)
            logger.debug(
                f"[LOOP] Iteration {loop_iteration} | running_coding={running_ids} "
                f"testing={testing_count} max_concurrency={self.max_concurrency}"
            )

            # Full database dump every 5 iterations
            if loop_iteration == 1 or loop_iteration % 5 == 0:
                session = self.get_session()
                try:
                    _dump_database_state(session, f"(iteration {loop_iteration})")
                finally:
                    session.close()

    def get_status(self) -> dict:
        """Get current orchestrator status."""
        with self._lock:
            return {
                "running_features": list(self.running_coding_agents.keys()),
                "coding_agent_count": len(self.running_coding_agents),
                "testing_agent_count": len(self.running_testing_agents),
                "count": len(self.running_coding_agents),  # Legacy compatibility
                "max_concurrency": self.max_concurrency,
                "testing_agent_ratio": self.testing_agent_ratio,
                "is_running": self.is_running,
                "yolo_mode": self.yolo_mode,
            }


async def run_parallel_orchestrator(
    project_dir: Path,
    max_concurrency: int = DEFAULT_CONCURRENCY,
    model: str = None,
    yolo_mode: bool = False,
    testing_agent_ratio: int = 1,
) -> None:
    """Run the unified orchestrator.

    Args:
        project_dir: Path to the project directory
        max_concurrency: Maximum number of concurrent coding agents
        model: Claude model to use
        yolo_mode: Whether to run in YOLO mode (skip testing agents)
        testing_agent_ratio: Number of regression agents to maintain (0-3)
    """
    print(f"[ORCHESTRATOR] run_parallel_orchestrator called with max_concurrency={max_concurrency}", flush=True)
    orchestrator = ParallelOrchestrator(
        project_dir=project_dir,
        max_concurrency=max_concurrency,
        model=model,
        yolo_mode=yolo_mode,
        testing_agent_ratio=testing_agent_ratio,
    )

    try:
        await orchestrator.run_loop()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Stopping agents...", flush=True)
        orchestrator.stop_all()


def main():
    """Main entry point for parallel orchestration."""
    import argparse

    from dotenv import load_dotenv

    from registry import DEFAULT_MODEL, get_project_path

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Parallel Feature Orchestrator - Run multiple agent instances",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Project directory path (absolute) or registered project name",
    )
    parser.add_argument(
        "--max-concurrency",
        "-p",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Maximum concurrent agents (1-{MAX_PARALLEL_AGENTS}, default: {DEFAULT_CONCURRENCY})",
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
        "--testing-agent-ratio",
        type=int,
        default=1,
        help="Number of regression testing agents (0-3, default: 1). Set to 0 to disable testing agents.",
    )

    args = parser.parse_args()

    # Resolve project directory
    project_dir_input = args.project_dir
    project_dir = Path(project_dir_input)

    if project_dir.is_absolute():
        if not project_dir.exists():
            print(f"Error: Project directory does not exist: {project_dir}", flush=True)
            sys.exit(1)
    else:
        registered_path = get_project_path(project_dir_input)
        if registered_path:
            project_dir = registered_path
        else:
            print(f"Error: Project '{project_dir_input}' not found in registry", flush=True)
            sys.exit(1)

    try:
        asyncio.run(run_parallel_orchestrator(
            project_dir=project_dir,
            max_concurrency=args.max_concurrency,
            model=args.model,
            yolo_mode=args.yolo,
            testing_agent_ratio=args.testing_agent_ratio,
        ))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", flush=True)


if __name__ == "__main__":
    main()
