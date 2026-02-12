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
import atexit
import logging
import os
import re
import signal
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from sqlalchemy import text

from api.database import Feature, create_database
from api.dependency_resolver import are_dependencies_satisfied, compute_scheduling_scores
from progress import has_features
from server.utils.process_utils import kill_process_tree

logger = logging.getLogger(__name__)

# Root directory of autoforge (where this script and autonomous_agent_demo.py live)
AUTOFORGE_ROOT = Path(__file__).parent.resolve()

# Debug log file path
DEBUG_LOG_FILE = AUTOFORGE_ROOT / "orchestrator_debug.log"


class DebugLogger:
    """Thread-safe debug logger that writes to a file."""

    def __init__(self, log_file: Path = DEBUG_LOG_FILE):
        self.log_file = log_file
        self._lock = threading.Lock()
        self._session_started = False
        # DON'T clear on import - only mark session start when run_loop begins

    def start_session(self):
        """Mark the start of a new orchestrator session. Clears previous logs."""
        with self._lock:
            self._session_started = True
            with open(self.log_file, "w") as f:
                f.write(f"=== Orchestrator Debug Log Started: {datetime.now().isoformat()} ===\n")
                f.write(f"=== PID: {os.getpid()} ===\n\n")

    def log(self, category: str, message: str, **kwargs):
        """Write a timestamped log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with self._lock:
            with open(self.log_file, "a") as f:
                f.write(f"[{timestamp}] [{category}] {message}\n")
                for key, value in kwargs.items():
                    f.write(f"    {key}: {value}\n")
                f.write("\n")

    def section(self, title: str):
        """Write a section header."""
        with self._lock:
            with open(self.log_file, "a") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"  {title}\n")
                f.write(f"{'='*60}\n\n")


# Global debug logger instance
debug_log = DebugLogger()


def _dump_database_state(feature_dicts: list[dict], label: str = ""):
    """Helper to dump full database state to debug log.

    Args:
        feature_dicts: Pre-fetched list of feature dicts.
        label: Optional label for the dump entry.
    """
    passing = [f for f in feature_dicts if f.get("passes")]
    in_progress = [f for f in feature_dicts if f.get("in_progress") and not f.get("passes")]
    pending = [f for f in feature_dicts if not f.get("passes") and not f.get("in_progress")]

    debug_log.log("DB_DUMP", f"Full database state {label}",
        total_features=len(feature_dicts),
        passing_count=len(passing),
        passing_ids=[f["id"] for f in passing],
        in_progress_count=len(in_progress),
        in_progress_ids=[f["id"] for f in in_progress],
        pending_count=len(pending),
        pending_ids=[f["id"] for f in pending[:10]])  # First 10 pending only

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
DEFAULT_TESTING_BATCH_SIZE = 3  # Number of features per testing batch (1-5)
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
        model: str | None = None,
        yolo_mode: bool = False,
        testing_agent_ratio: int = 1,
        testing_batch_size: int = DEFAULT_TESTING_BATCH_SIZE,
        batch_size: int = 3,
        on_output: Callable[[int, str], None] | None = None,
        on_status: Callable[[int, str], None] | None = None,
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
            testing_batch_size: Number of features to include per testing session (1-5).
                Each testing agent receives this many features to regression test.
            on_output: Callback for agent output (feature_id, line)
            on_status: Callback for agent status changes (feature_id, status)
        """
        self.project_dir = project_dir
        self.max_concurrency = min(max(max_concurrency, 1), MAX_PARALLEL_AGENTS)
        self.model = model
        self.yolo_mode = yolo_mode
        self.testing_agent_ratio = min(max(testing_agent_ratio, 0), 3)  # Clamp 0-3
        self.testing_batch_size = min(max(testing_batch_size, 1), 5)  # Clamp 1-5
        self.batch_size = min(max(batch_size, 1), 3)  # Clamp 1-3
        self.on_output = on_output
        self.on_status = on_status

        # Thread-safe state
        self._lock = threading.Lock()
        # Coding agents: feature_id -> process
        # Safe to key by feature_id because start_feature() checks for duplicates before spawning
        self.running_coding_agents: dict[int, subprocess.Popen] = {}
        # Testing agents: pid -> (feature_id, process)
        # Keyed by PID (not feature_id) because multiple agents can test the same feature
        self.running_testing_agents: dict[int, tuple[int, subprocess.Popen]] = {}
        # Legacy alias for backward compatibility
        self.running_agents = self.running_coding_agents
        self.abort_events: dict[int, threading.Event] = {}
        self._testing_session_counter = 0
        self.is_running = False

        # Track feature failures to prevent infinite retry loops
        self._failure_counts: dict[int, int] = {}

        # Track recently tested feature IDs to avoid redundant re-testing.
        # Cleared when all passing features have been covered at least once.
        self._recently_tested: set[int] = set()

        # Batch tracking: primary feature_id -> all feature IDs in batch
        self._batch_features: dict[int, list[int]] = {}
        # Reverse mapping: any feature_id -> primary feature_id
        self._feature_to_primary: dict[int, int] = {}

        # Shutdown flag for async-safe signal handling
        # Signal handlers only set this flag; cleanup happens in the main loop
        self._shutdown_requested = False

        # Session tracking for logging/debugging
        self.session_start_time: datetime | None = None

        # Event signaled when any agent completes, allowing the main loop to wake
        # immediately instead of waiting for the full POLL_INTERVAL timeout.
        # This reduces latency when spawning the next feature after completion.
        self._agent_completed_event: asyncio.Event | None = None  # Created in run_loop
        self._event_loop: asyncio.AbstractEventLoop | None = None  # Stored for thread-safe signaling

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

        Note: Prefer _get_test_batch() for batch testing mode. This method is
        retained for backward compatibility.
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

    def _get_test_batch(self, batch_size: int = 3) -> list[int]:
        """Select a prioritized batch of passing features for regression testing.

        Uses weighted scoring to prioritize features that:
        1. Haven't been tested recently in this orchestrator session
        2. Are depended on by many other features (higher impact if broken)
        3. Have more dependencies themselves (complex integration points)

        When all passing features have been recently tested, the tracking set
        is cleared so the cycle starts fresh.

        Args:
            batch_size: Maximum number of feature IDs to return (1-5).

        Returns:
            List of feature IDs to test, may be shorter than batch_size if
            fewer passing features are available. Empty list if none available.
        """
        session = self.get_session()
        try:
            session.expire_all()
            passing = (
                session.query(Feature)
                .filter(Feature.passes == True)
                .filter(Feature.in_progress == False)  # Don't test while coding
                .all()
            )

            # Extract data from ORM objects before closing the session to avoid
            # DetachedInstanceError when accessing attributes after session.close().
            passing_data: list[dict] = []
            for f in passing:
                passing_data.append({
                    'id': f.id,
                    'dependencies': f.get_dependencies_safe() if hasattr(f, 'get_dependencies_safe') else [],
                })
        finally:
            session.close()

        if not passing_data:
            return []

        # Build a reverse dependency map: feature_id -> count of features that depend on it.
        # The Feature model stores dependencies (what I depend ON), so we invert to find
        # dependents (what depends ON me).
        dependent_counts: dict[int, int] = {}
        for fd in passing_data:
            for dep_id in fd['dependencies']:
                dependent_counts[dep_id] = dependent_counts.get(dep_id, 0) + 1

        # Exclude features that are already being tested by running testing agents
        # to avoid redundant concurrent testing of the same features.
        # running_testing_agents is dict[pid, (primary_feature_id, process)]
        with self._lock:
            currently_testing_ids: set[int] = set()
            for _pid, (feat_id, _proc) in self.running_testing_agents.items():
                currently_testing_ids.add(feat_id)

        # If all passing features have been recently tested, reset the tracker
        # so we cycle through them again rather than returning empty batches.
        passing_ids = {fd['id'] for fd in passing_data}
        if passing_ids.issubset(self._recently_tested):
            self._recently_tested.clear()

        # Score each feature by testing priority
        scored: list[tuple[int, int]] = []
        for fd in passing_data:
            f_id = fd['id']

            # Skip features already being tested by a running testing agent
            if f_id in currently_testing_ids:
                continue

            score = 0

            # Weight 1: Features depended on by many others are higher impact
            # if they regress, so test them more often
            score += dependent_counts.get(f_id, 0) * 2

            # Weight 2: Strongly prefer features not tested recently
            if f_id not in self._recently_tested:
                score += 5

            # Weight 3: Features with more dependencies are integration points
            # that are more likely to regress when other code changes
            dep_count = len(fd['dependencies'])
            score += min(dep_count, 3)  # Cap at 3 to avoid over-weighting

            scored.append((f_id, score))

        # Sort by score descending (highest priority first)
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [fid for fid, _ in scored[:batch_size]]

        # Track what we've tested to avoid re-testing the same features next batch
        self._recently_tested.update(selected)

        debug_log.log("TEST_BATCH", f"Selected {len(selected)} features for testing batch",
            selected_ids=selected,
            recently_tested_count=len(self._recently_tested),
            total_passing=len(passing_data))

        return selected

    def build_feature_batches(
        self,
        ready: list[dict],
        all_features: list[dict],
        scheduling_scores: dict[int, float],
    ) -> list[list[dict]]:
        """Build dependency-aware feature batches for coding agents.

        Each batch contains up to `batch_size` features. The algorithm:
        1. Start with a ready feature (sorted by scheduling score)
        2. Chain extension: find dependents whose deps are satisfied if earlier batch features pass
        3. Same-category fill: fill remaining slots with ready features from the same category

        Args:
            ready: Ready features (sorted by scheduling score)
            all_features: All features for dependency checking
            scheduling_scores: Pre-computed scheduling scores

        Returns:
            List of batches, each batch is a list of feature dicts
        """
        if self.batch_size <= 1:
            # No batching - return each feature as a single-item batch
            return [[f] for f in ready]

        # Build children adjacency: parent_id -> [child_ids]
        children: dict[int, list[int]] = {f["id"]: [] for f in all_features}
        feature_map: dict[int, dict] = {f["id"]: f for f in all_features}
        for f in all_features:
            for dep_id in (f.get("dependencies") or []):
                if dep_id in children:
                    children[dep_id].append(f["id"])

        # Pre-compute passing IDs
        passing_ids = {f["id"] for f in all_features if f.get("passes")}

        used_ids: set[int] = set()  # Features already assigned to a batch
        batches: list[list[dict]] = []

        for feature in ready:
            if feature["id"] in used_ids:
                continue

            batch = [feature]
            used_ids.add(feature["id"])
            # Simulate passing set = real passing + batch features
            simulated_passing = passing_ids | {feature["id"]}

            # Phase 1: Chain extension - find dependents whose deps are met
            for _ in range(self.batch_size - 1):
                best_candidate = None
                best_score = -1.0
                # Check children of all features currently in the batch
                candidate_ids: set[int] = set()
                for bf in batch:
                    for child_id in children.get(bf["id"], []):
                        if child_id not in used_ids and child_id not in simulated_passing:
                            candidate_ids.add(child_id)

                for cid in candidate_ids:
                    cf = feature_map.get(cid)
                    if not cf or cf.get("passes") or cf.get("in_progress"):
                        continue
                    # Check if ALL deps are satisfied by simulated passing set
                    deps = cf.get("dependencies") or []
                    if all(d in simulated_passing for d in deps):
                        score = scheduling_scores.get(cid, 0)
                        if score > best_score:
                            best_score = score
                            best_candidate = cf

                if best_candidate:
                    batch.append(best_candidate)
                    used_ids.add(best_candidate["id"])
                    simulated_passing.add(best_candidate["id"])
                else:
                    break

            # Phase 2: Same-category fill
            if len(batch) < self.batch_size:
                category = feature.get("category", "")
                for rf in ready:
                    if len(batch) >= self.batch_size:
                        break
                    if rf["id"] in used_ids:
                        continue
                    if rf.get("category", "") == category:
                        batch.append(rf)
                        used_ids.add(rf["id"])

            batches.append(batch)

        debug_log.log("BATCH", f"Built {len(batches)} batches from {len(ready)} ready features",
            batch_sizes=[len(b) for b in batches],
            batch_ids=[[f['id'] for f in b] for b in batches[:5]])

        return batches

    def get_resumable_features(
        self,
        feature_dicts: list[dict] | None = None,
        scheduling_scores: dict[int, float] | None = None,
    ) -> list[dict]:
        """Get features that were left in_progress from a previous session.

        These are features where in_progress=True but passes=False, and they're
        not currently being worked on by this orchestrator. This handles the case
        where a previous session was interrupted before completing the feature.

        Args:
            feature_dicts: Pre-fetched list of feature dicts. If None, queries the database.
            scheduling_scores: Pre-computed scheduling scores. If None, computed from feature_dicts.
        """
        if feature_dicts is None:
            session = self.get_session()
            try:
                session.expire_all()
                all_features = session.query(Feature).all()
                feature_dicts = [f.to_dict() for f in all_features]
            finally:
                session.close()

        # Snapshot running IDs once (include all batch feature IDs)
        with self._lock:
            running_ids = set(self.running_coding_agents.keys())
            for batch_ids in self._batch_features.values():
                running_ids.update(batch_ids)

        resumable = []
        for fd in feature_dicts:
            if not fd.get("in_progress") or fd.get("passes"):
                continue
            # Skip if already running in this orchestrator instance
            if fd["id"] in running_ids:
                continue
            # Skip if feature has failed too many times
            if self._failure_counts.get(fd["id"], 0) >= MAX_FEATURE_RETRIES:
                continue
            resumable.append(fd)

        # Sort by scheduling score (higher = first), then priority, then id
        if scheduling_scores is None:
            scheduling_scores = compute_scheduling_scores(feature_dicts)
        resumable.sort(key=lambda f: (-scheduling_scores.get(f["id"], 0), f["priority"], f["id"]))
        return resumable

    def get_ready_features(
        self,
        feature_dicts: list[dict] | None = None,
        scheduling_scores: dict[int, float] | None = None,
    ) -> list[dict]:
        """Get features with satisfied dependencies, not already running.

        Args:
            feature_dicts: Pre-fetched list of feature dicts. If None, queries the database.
            scheduling_scores: Pre-computed scheduling scores. If None, computed from feature_dicts.
        """
        if feature_dicts is None:
            session = self.get_session()
            try:
                session.expire_all()
                all_features = session.query(Feature).all()
                feature_dicts = [f.to_dict() for f in all_features]
            finally:
                session.close()

        # Pre-compute passing_ids once to avoid O(n^2) in the loop
        passing_ids = {fd["id"] for fd in feature_dicts if fd.get("passes")}

        # Snapshot running IDs once (include all batch feature IDs)
        with self._lock:
            running_ids = set(self.running_coding_agents.keys())
            for batch_ids in self._batch_features.values():
                running_ids.update(batch_ids)

        ready = []
        skipped_reasons = {"passes": 0, "in_progress": 0, "running": 0, "failed": 0, "deps": 0}
        for fd in feature_dicts:
            if fd.get("passes"):
                skipped_reasons["passes"] += 1
                continue
            if fd.get("in_progress"):
                skipped_reasons["in_progress"] += 1
                continue
            # Skip if already running in this orchestrator
            if fd["id"] in running_ids:
                skipped_reasons["running"] += 1
                continue
            # Skip if feature has failed too many times
            if self._failure_counts.get(fd["id"], 0) >= MAX_FEATURE_RETRIES:
                skipped_reasons["failed"] += 1
                continue
            # Check dependencies (pass pre-computed passing_ids)
            if are_dependencies_satisfied(fd, feature_dicts, passing_ids):
                ready.append(fd)
            else:
                skipped_reasons["deps"] += 1

        # Sort by scheduling score (higher = first), then priority, then id
        if scheduling_scores is None:
            scheduling_scores = compute_scheduling_scores(feature_dicts)
        ready.sort(key=lambda f: (-scheduling_scores.get(f["id"], 0), f["priority"], f["id"]))

        # Summary counts for logging
        passing = skipped_reasons["passes"]
        in_progress = skipped_reasons["in_progress"]
        total = len(feature_dicts)

        debug_log.log("READY", "get_ready_features() called",
            ready_count=len(ready),
            ready_ids=[f['id'] for f in ready[:5]],  # First 5 only
            passing=passing,
            in_progress=in_progress,
            total=total,
            skipped=skipped_reasons)

        return ready

    def get_all_complete(self, feature_dicts: list[dict] | None = None) -> bool:
        """Check if all features are complete or permanently failed.

        Returns False if there are no features (initialization needed).

        Args:
            feature_dicts: Pre-fetched list of feature dicts. If None, queries the database.
        """
        if feature_dicts is None:
            session = self.get_session()
            try:
                session.expire_all()
                all_features = session.query(Feature).all()
                feature_dicts = [f.to_dict() for f in all_features]
            finally:
                session.close()

        # No features = NOT complete, need initialization
        if len(feature_dicts) == 0:
            return False

        passing_count = 0
        failed_count = 0
        pending_count = 0
        for fd in feature_dicts:
            if fd.get("passes"):
                passing_count += 1
                continue  # Completed successfully
            if self._failure_counts.get(fd["id"], 0) >= MAX_FEATURE_RETRIES:
                failed_count += 1
                continue  # Permanently failed, count as "done"
            pending_count += 1

        total = len(feature_dicts)
        is_complete = pending_count == 0
        debug_log.log("COMPLETE_CHECK", f"get_all_complete: {passing_count}/{total} passing, "
            f"{failed_count} failed, {pending_count} pending -> {is_complete}")
        return is_complete

    def get_passing_count(self, feature_dicts: list[dict] | None = None) -> int:
        """Get the number of passing features.

        Args:
            feature_dicts: Pre-fetched list of feature dicts. If None, queries the database.
        """
        if feature_dicts is None:
            session = self.get_session()
            try:
                session.expire_all()
                count: int = session.query(Feature).filter(Feature.passes == True).count()
                return count
            finally:
                session.close()
        return sum(1 for fd in feature_dicts if fd.get("passes"))

    def _maintain_testing_agents(self, feature_dicts: list[dict] | None = None) -> None:
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

        Args:
            feature_dicts: Pre-fetched list of feature dicts. If None, queries the database.
        """
        # Skip if testing is disabled
        if self.yolo_mode or self.testing_agent_ratio == 0:
            return

        # No testing until there are passing features
        passing_count = self.get_passing_count(feature_dicts)
        if passing_count == 0:
            return

        # Don't spawn testing agents if all features are already complete
        if self.get_all_complete(feature_dicts):
            return

        # Spawn testing agents one at a time, re-checking limits each time
        # This avoids TOCTOU race by holding lock during the decision
        while True:
            # Check limits and decide whether to spawn (atomically)
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

                # We're going to spawn - log while still holding lock
                spawn_index = current_testing + 1
                debug_log.log("TESTING", f"Spawning testing agent ({spawn_index}/{desired})",
                    passing_count=passing_count)

            # Spawn outside lock (I/O bound operation)
            logger.debug("Spawning testing agent (%d/%d)", spawn_index, desired)
            success, msg = self._spawn_testing_agent()
            if not success:
                debug_log.log("TESTING", f"Spawn failed, stopping: {msg}")
                return

    def start_feature(self, feature_id: int, resume: bool = False) -> tuple[bool, str]:
        """Start a single coding agent for a feature.

        Args:
            feature_id: ID of the feature to start
            resume: If True, resume a feature that's already in_progress from a previous session

        Returns:
            Tuple of (success, message)
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
        finally:
            session.close()

        # Start coding agent subprocess
        success, message = self._spawn_coding_agent(feature_id)
        if not success:
            return False, message

        # NOTE: Testing agents are now maintained independently via _maintain_testing_agents()
        # called in the main loop, rather than being spawned when coding agents start.

        return True, f"Started feature {feature_id}"

    def start_feature_batch(self, feature_ids: list[int], resume: bool = False) -> tuple[bool, str]:
        """Start a coding agent for a batch of features.

        Args:
            feature_ids: List of feature IDs to implement in batch
            resume: If True, resume features already in_progress

        Returns:
            Tuple of (success, message)
        """
        if not feature_ids:
            return False, "No features to start"

        # Single feature falls back to start_feature
        if len(feature_ids) == 1:
            return self.start_feature(feature_ids[0], resume=resume)

        with self._lock:
            # Check if any feature in batch is already running
            for fid in feature_ids:
                if fid in self.running_coding_agents or fid in self._feature_to_primary:
                    return False, f"Feature {fid} already running"
            if len(self.running_coding_agents) >= self.max_concurrency:
                return False, "At max concurrency"
            total_agents = len(self.running_coding_agents) + len(self.running_testing_agents)
            if total_agents >= MAX_TOTAL_AGENTS:
                return False, f"At max total agents ({total_agents}/{MAX_TOTAL_AGENTS})"

        # Mark all features as in_progress in a single transaction
        session = self.get_session()
        try:
            features_to_mark = []
            for fid in feature_ids:
                feature = session.query(Feature).filter(Feature.id == fid).first()
                if not feature:
                    return False, f"Feature {fid} not found"
                if feature.passes:
                    return False, f"Feature {fid} already complete"
                if not resume:
                    if feature.in_progress:
                        return False, f"Feature {fid} already in progress"
                    features_to_mark.append(feature)
                else:
                    if not feature.in_progress:
                        return False, f"Feature {fid} not in progress, cannot resume"

            for feature in features_to_mark:
                feature.in_progress = True
            session.commit()
        finally:
            session.close()

        # Spawn batch coding agent
        success, message = self._spawn_coding_agent_batch(feature_ids)
        if not success:
            # Clear in_progress on failure
            session = self.get_session()
            try:
                for fid in feature_ids:
                    feature = session.query(Feature).filter(Feature.id == fid).first()
                    if feature and not resume:
                        feature.in_progress = False
                session.commit()
            finally:
                session.close()
            return False, message

        return True, f"Started batch [{', '.join(str(fid) for fid in feature_ids)}]"

    def _spawn_coding_agent(self, feature_id: int) -> tuple[bool, str]:
        """Spawn a coding agent subprocess for a specific feature."""
        # Create abort event
        abort_event = threading.Event()

        # Start subprocess for this feature
        cmd = [
            sys.executable,
            "-u",  # Force unbuffered stdout/stderr
            str(AUTOFORGE_ROOT / "autonomous_agent_demo.py"),
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
            # CREATE_NO_WINDOW on Windows prevents console window pop-ups
            # stdin=DEVNULL prevents blocking on stdin reads
            # encoding="utf-8" and errors="replace" fix Windows CP1252 issues
            popen_kwargs: dict[str, Any] = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "cwd": str(self.project_dir),  # Run from project dir so CLI creates .claude/ in project
                "env": {**os.environ, "PYTHONUNBUFFERED": "1", "NODE_COMPILE_CACHE": "", "PLAYWRIGHT_CLI_SESSION": f"coding-{feature_id}"},
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(cmd, **popen_kwargs)
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

        if self.on_status is not None:
            self.on_status(feature_id, "running")

        print(f"Started coding agent for feature #{feature_id}", flush=True)
        return True, f"Started feature {feature_id}"

    def _spawn_coding_agent_batch(self, feature_ids: list[int]) -> tuple[bool, str]:
        """Spawn a coding agent subprocess for a batch of features."""
        primary_id = feature_ids[0]
        abort_event = threading.Event()

        cmd = [
            sys.executable,
            "-u",
            str(AUTOFORGE_ROOT / "autonomous_agent_demo.py"),
            "--project-dir", str(self.project_dir),
            "--max-iterations", "1",
            "--agent-type", "coding",
            "--feature-ids", ",".join(str(fid) for fid in feature_ids),
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.yolo_mode:
            cmd.append("--yolo")

        try:
            popen_kwargs: dict[str, Any] = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "cwd": str(self.project_dir),  # Run from project dir so CLI creates .claude/ in project
                "env": {**os.environ, "PYTHONUNBUFFERED": "1", "NODE_COMPILE_CACHE": "", "PLAYWRIGHT_CLI_SESSION": f"coding-{primary_id}"},
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(cmd, **popen_kwargs)
        except Exception as e:
            # Reset in_progress on failure
            session = self.get_session()
            try:
                for fid in feature_ids:
                    feature = session.query(Feature).filter(Feature.id == fid).first()
                    if feature:
                        feature.in_progress = False
                        session.commit()
            finally:
                session.close()
            return False, f"Failed to start batch agent: {e}"

        with self._lock:
            self.running_coding_agents[primary_id] = proc
            self.abort_events[primary_id] = abort_event
            self._batch_features[primary_id] = list(feature_ids)
            for fid in feature_ids:
                self._feature_to_primary[fid] = primary_id

        # Start output reader thread
        threading.Thread(
            target=self._read_output,
            args=(primary_id, proc, abort_event, "coding"),
            daemon=True
        ).start()

        if self.on_status is not None:
            for fid in feature_ids:
                self.on_status(fid, "running")

        ids_str = ", ".join(f"#{fid}" for fid in feature_ids)
        print(f"Started coding agent for features {ids_str}", flush=True)
        return True, f"Started batch [{ids_str}]"

    def _spawn_testing_agent(self) -> tuple[bool, str]:
        """Spawn a testing agent subprocess for batch regression testing.

        Selects a prioritized batch of passing features using weighted scoring
        (via _get_test_batch) and passes them as --testing-feature-ids to the
        subprocess. Falls back to single --testing-feature-id for batches of one.

        Multiple testing agents can test the same feature concurrently - this is
        intentional and simplifies the architecture by removing claim coordination.
        """
        # Check limits first (under lock)
        with self._lock:
            current_testing_count = len(self.running_testing_agents)
            if current_testing_count >= self.max_concurrency:
                debug_log.log("TESTING", f"Skipped spawn - at max testing agents ({current_testing_count}/{self.max_concurrency})")
                return False, f"At max testing agents ({current_testing_count})"
            total_agents = len(self.running_coding_agents) + len(self.running_testing_agents)
            if total_agents >= MAX_TOTAL_AGENTS:
                debug_log.log("TESTING", f"Skipped spawn - at max total agents ({total_agents}/{MAX_TOTAL_AGENTS})")
                return False, f"At max total agents ({total_agents})"

        # Select a weighted batch of passing features for regression testing
        batch = self._get_test_batch(self.testing_batch_size)
        if not batch:
            debug_log.log("TESTING", "No features available for testing")
            return False, "No features available for testing"

        # Use the first feature ID as the representative for logging/tracking
        primary_feature_id = batch[0]
        batch_str = ",".join(str(fid) for fid in batch)
        debug_log.log("TESTING", f"Selected batch for testing: [{batch_str}]")

        # Spawn the testing agent
        with self._lock:
            # Re-check limits in case another thread spawned while we were selecting
            current_testing_count = len(self.running_testing_agents)
            if current_testing_count >= self.max_concurrency:
                return False, f"At max testing agents ({current_testing_count})"

            cmd = [
                sys.executable,
                "-u",
                str(AUTOFORGE_ROOT / "autonomous_agent_demo.py"),
                "--project-dir", str(self.project_dir),
                "--max-iterations", "1",
                "--agent-type", "testing",
                "--testing-feature-ids", batch_str,
            ]
            if self.model:
                cmd.extend(["--model", self.model])

            try:
                # CREATE_NO_WINDOW on Windows prevents console window pop-ups
                # stdin=DEVNULL prevents blocking on stdin reads
                # encoding="utf-8" and errors="replace" fix Windows CP1252 issues
                popen_kwargs: dict[str, Any] = {
                    "stdin": subprocess.DEVNULL,
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.STDOUT,
                    "text": True,
                    "encoding": "utf-8",
                    "errors": "replace",
                    "cwd": str(self.project_dir),  # Run from project dir so CLI creates .claude/ in project
                    "env": {**os.environ, "PYTHONUNBUFFERED": "1", "NODE_COMPILE_CACHE": "", "PLAYWRIGHT_CLI_SESSION": f"testing-{self._testing_session_counter}"},
                }
                self._testing_session_counter += 1
                if sys.platform == "win32":
                    popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

                proc = subprocess.Popen(cmd, **popen_kwargs)
            except Exception as e:
                debug_log.log("TESTING", f"FAILED to spawn testing agent: {e}")
                return False, f"Failed to start testing agent: {e}"

            # Register process by PID (not feature_id) to avoid overwrites
            # when multiple agents test the same feature
            self.running_testing_agents[proc.pid] = (primary_feature_id, proc)
            testing_count = len(self.running_testing_agents)

        # Start output reader thread with primary feature ID for log attribution
        threading.Thread(
            target=self._read_output,
            args=(primary_feature_id, proc, threading.Event(), "testing"),
            daemon=True
        ).start()

        print(f"Started testing agent for features [{batch_str}] (PID {proc.pid})", flush=True)
        debug_log.log("TESTING", f"Successfully spawned testing agent for batch [{batch_str}]",
            pid=proc.pid,
            feature_ids=batch,
            total_testing_agents=testing_count)
        return True, f"Started testing agent for features [{batch_str}]"

    async def _run_initializer(self) -> bool:
        """Run initializer agent as blocking subprocess.

        Returns True if initialization succeeded (features were created).
        """
        debug_log.section("INITIALIZER PHASE")
        debug_log.log("INIT", "Starting initializer subprocess",
            project_dir=str(self.project_dir))

        cmd = [
            sys.executable, "-u",
            str(AUTOFORGE_ROOT / "autonomous_agent_demo.py"),
            "--project-dir", str(self.project_dir),
            "--agent-type", "initializer",
            "--max-iterations", "1",
        ]
        if self.model:
            cmd.extend(["--model", self.model])

        print("Running initializer agent...", flush=True)

        # CREATE_NO_WINDOW on Windows prevents console window pop-ups
        # stdin=DEVNULL prevents blocking on stdin reads
        # encoding="utf-8" and errors="replace" fix Windows CP1252 issues
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "cwd": str(AUTOFORGE_ROOT),
            "env": {**os.environ, "PYTHONUNBUFFERED": "1", "NODE_COMPILE_CACHE": ""},
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        proc = subprocess.Popen(cmd, **popen_kwargs)

        debug_log.log("INIT", "Initializer subprocess started", pid=proc.pid)

        # Stream output with timeout
        loop = asyncio.get_running_loop()
        try:
            async def stream_output():
                while True:
                    line = await loop.run_in_executor(None, proc.stdout.readline)
                    if not line:
                        break
                    print(line.rstrip(), flush=True)
                    if self.on_output is not None:
                        self.on_output(0, line.rstrip())  # Use 0 as feature_id for initializer
                proc.wait()

            await asyncio.wait_for(stream_output(), timeout=INITIALIZER_TIMEOUT)

        except asyncio.TimeoutError:
            print(f"ERROR: Initializer timed out after {INITIALIZER_TIMEOUT // 60} minutes", flush=True)
            debug_log.log("INIT", "TIMEOUT - Initializer exceeded time limit",
                timeout_minutes=INITIALIZER_TIMEOUT // 60)
            result = kill_process_tree(proc)
            debug_log.log("INIT", "Killed timed-out initializer process tree",
                status=result.status, children_found=result.children_found)
            return False

        debug_log.log("INIT", "Initializer subprocess completed",
            return_code=proc.returncode,
            success=proc.returncode == 0)

        if proc.returncode != 0:
            print(f"ERROR: Initializer failed with exit code {proc.returncode}", flush=True)
            return False

        return True

    # Pattern to detect when a batch agent claims a new feature
    _CLAIM_FEATURE_PATTERN = re.compile(
        r"feature_claim_and_get\b.*?['\"]?feature_id['\"]?\s*[:=]\s*(\d+)"
    )

    def _read_output(
        self,
        feature_id: int | None,
        proc: subprocess.Popen,
        abort: threading.Event,
        agent_type: Literal["coding", "testing"] = "coding",
    ):
        """Read output from subprocess and emit events."""
        current_feature_id = feature_id
        try:
            if proc.stdout is None:
                proc.wait()
                return
            for line in proc.stdout:
                if abort.is_set():
                    break
                line = line.rstrip()
                # Detect when a batch agent claims a new feature
                claim_match = self._CLAIM_FEATURE_PATTERN.search(line)
                if claim_match:
                    claimed_id = int(claim_match.group(1))
                    if claimed_id != current_feature_id:
                        current_feature_id = claimed_id
                if self.on_output is not None:
                    self.on_output(current_feature_id or 0, line)
                else:
                    # Both coding and testing agents now use [Feature #X] format
                    print(f"[Feature #{current_feature_id}] {line}", flush=True)
            proc.wait()
        finally:
            # CRITICAL: Kill the process tree to clean up any child processes (e.g., Claude CLI)
            # This prevents zombie processes from accumulating
            try:
                kill_process_tree(proc, timeout=2.0)
            except Exception as e:
                debug_log.log("CLEANUP", f"Error killing process tree for {agent_type} agent", error=str(e))
            self._on_agent_complete(feature_id, proc.returncode, agent_type, proc)

    def _run_inter_session_cleanup(self):
        """Run lightweight cleanup between agent sessions.

        Removes stale temp files and project screenshots to prevent
        disk space accumulation during long overnight runs.
        """
        try:
            from temp_cleanup import cleanup_project_screenshots, cleanup_stale_temp
            cleanup_stale_temp()
            cleanup_project_screenshots(self.project_dir)
        except Exception as e:
            debug_log.log("CLEANUP", f"Inter-session cleanup failed (non-fatal): {e}")

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
            debug_log.log("EVENT", "Woke up immediately - agent completed")
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
        """
        if agent_type == "testing":
            with self._lock:
                # Remove by PID
                self.running_testing_agents.pop(proc.pid, None)

            status = "completed" if return_code == 0 else "failed"
            print(f"Feature #{feature_id} testing {status}", flush=True)
            debug_log.log("COMPLETE", f"Testing agent for feature #{feature_id} finished",
                pid=proc.pid,
                feature_id=feature_id,
                status=status)
            # Run lightweight cleanup between sessions
            self._run_inter_session_cleanup()
            # Signal main loop that an agent slot is available
            self._signal_agent_completed()
            return

        # feature_id is required for coding agents (always passed from start_feature)
        assert feature_id is not None, "feature_id must not be None for coding agents"

        # Coding agent completion - handle both single and batch features
        batch_ids = None
        with self._lock:
            batch_ids = self._batch_features.pop(feature_id, None)
            if batch_ids:
                # Clean up reverse mapping
                for fid in batch_ids:
                    self._feature_to_primary.pop(fid, None)
            self.running_coding_agents.pop(feature_id, None)
            self.abort_events.pop(feature_id, None)

        all_feature_ids = batch_ids or [feature_id]

        debug_log.log("COMPLETE", f"Coding agent for feature(s) {all_feature_ids} finished",
            return_code=return_code,
            status="success" if return_code == 0 else "failed",
            batch_size=len(all_feature_ids))

        # Refresh session cache to see subprocess commits
        session = self.get_session()
        try:
            session.expire_all()
            for fid in all_feature_ids:
                feature = session.query(Feature).filter(Feature.id == fid).first()
                feature_passes = feature.passes if feature else None
                feature_in_progress = feature.in_progress if feature else None
                debug_log.log("DB", f"Feature #{fid} state after session.expire_all()",
                    passes=feature_passes,
                    in_progress=feature_in_progress)
                if feature and feature.in_progress and not feature.passes:
                    feature.in_progress = False
                    session.commit()
                    debug_log.log("DB", f"Cleared in_progress for feature #{fid} (agent failed)")
        finally:
            session.close()

        # Track failures for features still in_progress at exit
        if return_code != 0:
            with self._lock:
                for fid in all_feature_ids:
                    self._failure_counts[fid] = self._failure_counts.get(fid, 0) + 1
                    failure_count = self._failure_counts[fid]
                    if failure_count >= MAX_FEATURE_RETRIES:
                        print(f"Feature #{fid} has failed {failure_count} times, will not retry", flush=True)
                        debug_log.log("COMPLETE", f"Feature #{fid} exceeded max retries",
                            failure_count=failure_count)

        status = "completed" if return_code == 0 else "failed"
        if self.on_status is not None:
            for fid in all_feature_ids:
                self.on_status(fid, status)

        # CRITICAL: Print triggers WebSocket to emit agent_update
        if batch_ids and len(batch_ids) > 1:
            ids_str = ", ".join(f"#{fid}" for fid in batch_ids)
            print(f"Features {ids_str} {status}", flush=True)
        else:
            print(f"Feature #{feature_id} {status}", flush=True)

        # Run lightweight cleanup between sessions
        self._run_inter_session_cleanup()
        # Signal main loop that an agent slot is available
        self._signal_agent_completed()

    def stop_feature(self, feature_id: int) -> tuple[bool, str]:
        """Stop a running coding agent and all its child processes."""
        with self._lock:
            # Check if this feature is part of a batch
            primary_id = self._feature_to_primary.get(feature_id, feature_id)
            if primary_id not in self.running_coding_agents:
                return False, "Feature not running"

            abort = self.abort_events.get(primary_id)
            proc = self.running_coding_agents.get(primary_id)

        if abort:
            abort.set()
        if proc:
            result = kill_process_tree(proc, timeout=5.0)
            debug_log.log("STOP", f"Killed feature {feature_id} (primary {primary_id}) process tree",
                status=result.status, children_found=result.children_found,
                children_terminated=result.children_terminated, children_killed=result.children_killed)

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

        for pid, (feature_id, proc) in testing_items:
            result = kill_process_tree(proc, timeout=5.0)
            debug_log.log("STOP", f"Killed testing agent for feature #{feature_id} (PID {pid})",
                status=result.status, children_found=result.children_found,
                children_terminated=result.children_terminated, children_killed=result.children_killed)

        # Clear dict so get_status() doesn't report stale agents while
        # _on_agent_complete callbacks are still in flight.
        with self._lock:
            self.running_testing_agents.clear()

    async def run_loop(self):
        """Main orchestration loop."""
        self.is_running = True

        # Initialize the agent completion event for this run
        # Must be created in the async context where it will be used
        self._agent_completed_event = asyncio.Event()
        # Store the event loop reference for thread-safe signaling from output reader threads
        self._event_loop = asyncio.get_running_loop()

        # Track session start for regression testing (UTC for consistency with last_tested_at)
        self.session_start_time = datetime.now(timezone.utc)

        # Start debug logging session FIRST (clears previous logs)
        # Must happen before any debug_log.log() calls
        debug_log.start_session()

        # Log startup to debug file
        debug_log.section("ORCHESTRATOR STARTUP")
        debug_log.log("STARTUP", "Orchestrator run_loop starting",
            project_dir=str(self.project_dir),
            max_concurrency=self.max_concurrency,
            yolo_mode=self.yolo_mode,
            testing_agent_ratio=self.testing_agent_ratio,
            session_start_time=self.session_start_time.isoformat())

        print("=" * 70, flush=True)
        print("  UNIFIED ORCHESTRATOR SETTINGS", flush=True)
        print("=" * 70, flush=True)
        print(f"Project: {self.project_dir}", flush=True)
        print(f"Max concurrency: {self.max_concurrency} coding agents", flush=True)
        print(f"YOLO mode: {self.yolo_mode}", flush=True)
        print(f"Regression agents: {self.testing_agent_ratio} (maintained independently)", flush=True)
        print(f"Batch size: {self.batch_size} features per agent", flush=True)
        print("=" * 70, flush=True)
        print(flush=True)

        # Phase 1: Check if initialization needed
        if not has_features(self.project_dir):
            print("=" * 70, flush=True)
            print("  INITIALIZATION PHASE", flush=True)
            print("=" * 70, flush=True)
            print("No features found - running initializer agent first...", flush=True)
            print("NOTE: This may take 10-20+ minutes to generate features.", flush=True)
            print(flush=True)

            success = await self._run_initializer()

            if not success or not has_features(self.project_dir):
                print("ERROR: Initializer did not create features. Exiting.", flush=True)
                return

            print(flush=True)
            print("=" * 70, flush=True)
            print("  INITIALIZATION COMPLETE - Starting feature loop", flush=True)
            print("=" * 70, flush=True)
            print(flush=True)

            # CRITICAL: Recreate database connection after initializer subprocess commits
            # The initializer runs as a subprocess and commits to the database file.
            # SQLAlchemy may have stale connections or cached state. Disposing the old
            # engine and creating a fresh engine/session_maker ensures we see all the
            # newly created features.
            debug_log.section("INITIALIZATION COMPLETE")
            debug_log.log("INIT", "Disposing old database engine and creating fresh connection")
            logger.debug("Recreating database connection after initialization")
            if self._engine is not None:
                self._engine.dispose()
            self._engine, self._session_maker = create_database(self.project_dir)

            # Debug: Show state immediately after initialization
            logger.debug("Post-initialization state check")
            logger.debug("Post-initialization state: max_concurrency=%d, yolo_mode=%s, testing_agent_ratio=%d",
                self.max_concurrency, self.yolo_mode, self.testing_agent_ratio)

            # Verify features were created and are visible
            session = self.get_session()
            try:
                feature_count = session.query(Feature).count()
                all_features = session.query(Feature).all()
                feature_names = [f"{f.id}: {f.name}" for f in all_features[:10]]
                logger.debug("Features in database: %d", feature_count)
                debug_log.log("INIT", "Post-initialization database state",
                    max_concurrency=self.max_concurrency,
                    yolo_mode=self.yolo_mode,
                    testing_agent_ratio=self.testing_agent_ratio,
                    feature_count=feature_count,
                    first_10_features=feature_names)
            finally:
                session.close()

        # Phase 2: Feature loop
        # Check for features to resume from previous session
        resumable = self.get_resumable_features()
        if resumable:
            print(f"Found {len(resumable)} feature(s) to resume from previous session:", flush=True)
            for f in resumable:
                print(f"  - Feature #{f['id']}: {f['name']}", flush=True)
            print(flush=True)

        debug_log.section("FEATURE LOOP STARTING")
        loop_iteration = 0
        while self.is_running and not self._shutdown_requested:
            loop_iteration += 1
            if loop_iteration <= 3:
                logger.debug("=== Loop iteration %d ===", loop_iteration)

            # Query all features ONCE per iteration and build reusable snapshot.
            # Every sub-method receives this snapshot instead of re-querying the DB.
            session = self.get_session()
            session.expire_all()
            all_features = session.query(Feature).all()
            feature_dicts = [f.to_dict() for f in all_features]
            session.close()

            # Pre-compute scheduling scores once (BFS + reverse topo sort)
            scheduling_scores = compute_scheduling_scores(feature_dicts)

            # Log every iteration to debug file (first 10, then every 5th)
            if loop_iteration <= 10 or loop_iteration % 5 == 0:
                with self._lock:
                    running_ids = list(self.running_coding_agents.keys())
                    testing_count = len(self.running_testing_agents)
                debug_log.log("LOOP", f"Iteration {loop_iteration}",
                    running_coding_agents=running_ids,
                    running_testing_agents=testing_count,
                    max_concurrency=self.max_concurrency)

                # Full database dump every 5 iterations
                if loop_iteration == 1 or loop_iteration % 5 == 0:
                    _dump_database_state(feature_dicts, f"(iteration {loop_iteration})")

            try:
                # Check if all complete
                if self.get_all_complete(feature_dicts):
                    print("\nAll features complete!", flush=True)
                    break

                # Maintain testing agents independently (runs every iteration)
                self._maintain_testing_agents(feature_dicts)

                # Check capacity
                with self._lock:
                    current = len(self.running_coding_agents)
                    current_testing = len(self.running_testing_agents)
                    running_ids = list(self.running_coding_agents.keys())

                debug_log.log("CAPACITY", "Checking capacity",
                    current_coding=current,
                    current_testing=current_testing,
                    running_coding_ids=running_ids,
                    max_concurrency=self.max_concurrency,
                    at_capacity=(current >= self.max_concurrency))

                if current >= self.max_concurrency:
                    debug_log.log("CAPACITY", "At max capacity, waiting for agent completion...")
                    await self._wait_for_agent_completion()
                    continue

                # Priority 1: Resume features from previous session
                resumable = self.get_resumable_features(feature_dicts, scheduling_scores)
                if resumable:
                    slots = self.max_concurrency - current
                    for feature in resumable[:slots]:
                        print(f"Resuming feature #{feature['id']}: {feature['name']}", flush=True)
                        self.start_feature(feature["id"], resume=True)
                    await asyncio.sleep(0.5)  # Brief delay for subprocess to claim feature before re-querying
                    continue

                # Priority 2: Start new ready features
                ready = self.get_ready_features(feature_dicts, scheduling_scores)
                if not ready:
                    # Wait for running features to complete
                    if current > 0:
                        await self._wait_for_agent_completion()
                        continue
                    else:
                        # No ready features and nothing running
                        # Force a fresh database check before declaring blocked
                        # This handles the case where subprocess commits weren't visible yet
                        session = self.get_session()
                        try:
                            session.expire_all()
                            fresh_dicts = [f.to_dict() for f in session.query(Feature).all()]
                        finally:
                            session.close()

                        # Recheck if all features are now complete
                        if self.get_all_complete(fresh_dicts):
                            print("\nAll features complete!", flush=True)
                            break

                        # Still have pending features but all are blocked by dependencies
                        print("No ready features available. All remaining features may be blocked by dependencies.", flush=True)
                        await self._wait_for_agent_completion(timeout=POLL_INTERVAL * 2)
                        continue

                # Build dependency-aware batches from ready features
                slots = self.max_concurrency - current
                batches = self.build_feature_batches(ready, feature_dicts, scheduling_scores)

                logger.debug("Spawning loop: %d ready, %d slots available, %d batches built",
                    len(ready), slots, len(batches))

                debug_log.log("SPAWN", "Starting feature batches",
                    ready_count=len(ready),
                    slots_available=slots,
                    batch_count=len(batches),
                    batches=[[f['id'] for f in b] for b in batches[:slots]])

                for batch in batches[:slots]:
                    batch_ids = [f["id"] for f in batch]
                    batch_names = [f"{f['id']}:{f['name']}" for f in batch]
                    logger.debug("Starting batch: %s", batch_ids)
                    success, msg = self.start_feature_batch(batch_ids)
                    if not success:
                        logger.debug("Failed to start batch %s: %s", batch_ids, msg)
                        debug_log.log("SPAWN", f"FAILED to start batch {batch_ids}",
                            batch_names=batch_names,
                            error=msg)
                    else:
                        logger.debug("Successfully started batch %s", batch_ids)
                        with self._lock:
                            running_count = len(self.running_coding_agents)
                            logger.debug("Running coding agents after start: %d", running_count)
                        debug_log.log("SPAWN", f"Successfully started batch {batch_ids}",
                            batch_names=batch_names,
                            running_coding_agents=running_count)

                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"Orchestrator error: {e}", flush=True)
                await self._wait_for_agent_completion()

        # Wait for remaining agents to complete
        print("Waiting for running agents to complete...", flush=True)
        while True:
            with self._lock:
                coding_done = len(self.running_coding_agents) == 0
                testing_done = len(self.running_testing_agents) == 0
                if coding_done and testing_done:
                    break
            # Use short timeout since we're just waiting for final agents to finish
            await self._wait_for_agent_completion(timeout=1.0)

        print("Orchestrator finished.", flush=True)

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

    def cleanup(self) -> None:
        """Clean up database resources. Safe to call multiple times.

        Forces WAL checkpoint to flush pending writes to main database file,
        then disposes engine to close all connections. Prevents stale cache
        issues when the orchestrator restarts.
        """
        # Atomically grab and clear the engine reference to prevent re-entry
        engine = self._engine
        self._engine = None

        if engine is None:
            return  # Already cleaned up

        try:
            debug_log.log("CLEANUP", "Forcing WAL checkpoint before dispose")
            with engine.connect() as conn:
                conn.execute(text("PRAGMA wal_checkpoint(FULL)"))
                conn.commit()
            debug_log.log("CLEANUP", "WAL checkpoint completed, disposing engine")
        except Exception as e:
            debug_log.log("CLEANUP", f"WAL checkpoint failed (non-fatal): {e}")

        try:
            engine.dispose()
            debug_log.log("CLEANUP", "Engine disposed successfully")
        except Exception as e:
            debug_log.log("CLEANUP", f"Engine dispose failed: {e}")


async def run_parallel_orchestrator(
    project_dir: Path,
    max_concurrency: int = DEFAULT_CONCURRENCY,
    model: str | None = None,
    yolo_mode: bool = False,
    testing_agent_ratio: int = 1,
    testing_batch_size: int = DEFAULT_TESTING_BATCH_SIZE,
    batch_size: int = 3,
) -> None:
    """Run the unified orchestrator.

    Args:
        project_dir: Path to the project directory
        max_concurrency: Maximum number of concurrent coding agents
        model: Claude model to use
        yolo_mode: Whether to run in YOLO mode (skip testing agents)
        testing_agent_ratio: Number of regression agents to maintain (0-3)
        testing_batch_size: Number of features per testing batch (1-5)
        batch_size: Max features per coding agent batch (1-3)
    """
    print(f"[ORCHESTRATOR] run_parallel_orchestrator called with max_concurrency={max_concurrency}", flush=True)
    orchestrator = ParallelOrchestrator(
        project_dir=project_dir,
        max_concurrency=max_concurrency,
        model=model,
        yolo_mode=yolo_mode,
        testing_agent_ratio=testing_agent_ratio,
        testing_batch_size=testing_batch_size,
        batch_size=batch_size,
    )

    # Set up cleanup to run on exit (handles normal exit, exceptions)
    def cleanup_handler():
        debug_log.log("CLEANUP", "atexit cleanup handler invoked")
        orchestrator.cleanup()

    atexit.register(cleanup_handler)

    # Set up async-safe signal handler for graceful shutdown
    # Only sets flags - everything else is unsafe in signal context
    def signal_handler(signum, frame):
        orchestrator._shutdown_requested = True
        orchestrator.is_running = False

    # Register SIGTERM handler for process termination signals
    # Note: On Windows, SIGTERM handlers only fire from os.kill() calls within Python.
    # External termination (Task Manager, taskkill, Popen.terminate()) uses
    # TerminateProcess() which bypasses signal handlers entirely.
    signal.signal(signal.SIGTERM, signal_handler)

    # Note: We intentionally do NOT register SIGINT handler
    # Let Python raise KeyboardInterrupt naturally so the except block works

    try:
        await orchestrator.run_loop()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Stopping agents...", flush=True)
        orchestrator.stop_all()
    finally:
        # CRITICAL: Always clean up database resources on exit
        # This forces WAL checkpoint and disposes connections
        orchestrator.cleanup()


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
    parser.add_argument(
        "--testing-batch-size",
        type=int,
        default=DEFAULT_TESTING_BATCH_SIZE,
        help=f"Number of features per testing batch (1-5, default: {DEFAULT_TESTING_BATCH_SIZE})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Max features per coding agent batch (1-5, default: 3)",
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
            testing_batch_size=args.testing_batch_size,
            batch_size=args.batch_size,
        ))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", flush=True)


if __name__ == "__main__":
    main()
