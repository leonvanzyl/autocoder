"""
Orchestrator - Parallel Agent Coordination
============================================

The Orchestrator is the "brain" that coordinates multiple agents working
in parallel on different features.

Key responsibilities:
- Spawn and manage 3-5 parallel agents
- Create isolated worktrees for each agent
- Monitor heartbeats (detect crashes)
- Soft scheduling (avoid conflicting work)
- Coordinate with Gatekeeper for verification

Architecture:
- Uses direct imports for system logic (FAST!)
- Provides MCP tools to agents (CAPABILITY!)
- Tracks state in database (RELIABILITY!)
"""

import asyncio
import os
import sys
import logging
import subprocess
import psutil
import threading
import socket
import contextlib
import errno
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta

# Direct imports (system code = fast!)
from .knowledge_base import KnowledgeBase, get_knowledge_base
from .model_settings import ModelSettings, ModelPreset, get_full_model_id
from .worktree_manager import WorktreeManager
from .database import Database, get_database
from .gatekeeper import Gatekeeper
from .project_config import load_project_config
from .logs import prune_worker_logs_from_env, prune_gatekeeper_artifacts_from_env
from autocoder.generation.multi_model import (
    MultiModelGenerateConfig,
    generate_multi_model_artifact,
    generate_multi_model_text,
)
from autocoder.generation.feature_backlog import build_backlog_prompt, parse_feature_backlog, infer_feature_count

# Agent imports (for initializer)
from autocoder.agent import run_autonomous_agent
from autocoder.agent.prompts import get_app_spec

# MCP server imports (for agents)
from autocoder.tools import test_mcp, knowledge_mcp, model_settings_mcp, feature_mcp

logger = logging.getLogger(__name__)

# ============================================================================
# Port Allocator - Thread-safe port pool management
# ============================================================================

class PortAllocator:
    """
    Thread-safe port pool allocator for parallel agents.

    Manages two port pools:
    - Backend API ports: 5000-5100 (100 ports)
    - Frontend web ports: 5173-5273 (100 ports)

    Each agent gets a unique pair of ports (api_port, web_port) to avoid
    conflicts when running multiple agents in parallel.
    """

    # Default port ranges (end is exclusive, like Python's range()).
    DEFAULT_API_PORT_RANGE = (5000, 5100)  # 5000-5099
    DEFAULT_WEB_PORT_RANGE = (5173, 5273)  # 5173-5272

    def __init__(
        self,
        *,
        api_port_range: Optional[Tuple[int, int]] = None,
        web_port_range: Optional[Tuple[int, int]] = None,
        bind_host_ipv4: str = "127.0.0.1",
        bind_host_ipv6: str = "::1",
        verify_availability: Optional[bool] = None,
    ):
        """Initialize the port allocator with pools and optional bind checks."""
        self._lock = threading.Lock()

        self.api_port_range = api_port_range or self._range_from_env(
            "AUTOCODER_API_PORT_RANGE_START",
            "AUTOCODER_API_PORT_RANGE_END",
            self.DEFAULT_API_PORT_RANGE,
        )
        self.web_port_range = web_port_range or self._range_from_env(
            "AUTOCODER_WEB_PORT_RANGE_START",
            "AUTOCODER_WEB_PORT_RANGE_END",
            self.DEFAULT_WEB_PORT_RANGE,
        )

        if verify_availability is None:
            verify_availability = os.environ.get("AUTOCODER_SKIP_PORT_CHECK", "").lower() not in (
                "1",
                "true",
                "yes",
            )
        self._verify_availability = verify_availability
        self._bind_host_ipv4 = bind_host_ipv4
        self._bind_host_ipv6 = bind_host_ipv6

        # Track available and in-use ports
        self._available_api_ports: Set[int] = set(
            range(self.api_port_range[0], self.api_port_range[1])
        )
        self._available_web_ports: Set[int] = set(
            range(self.web_port_range[0], self.web_port_range[1])
        )

        self._in_use_api_ports: Set[int] = set()
        self._in_use_web_ports: Set[int] = set()
        self._blocked_api_ports: Set[int] = set()
        self._blocked_web_ports: Set[int] = set()

        # Track which agent owns which ports
        self._agent_ports: Dict[str, Tuple[int, int]] = {}

        logger.info(f"PortAllocator initialized:")
        logger.info(
            f"  API ports: {self.api_port_range[0]}-{self.api_port_range[1]} "
            f"({len(self._available_api_ports)} available)"
        )
        logger.info(
            f"  Web ports: {self.web_port_range[0]}-{self.web_port_range[1]} "
            f"({len(self._available_web_ports)} available)"
        )
        logger.info(f"  Port availability verification: {self._verify_availability}")

    @staticmethod
    def _range_from_env(start_env: str, end_env: str, default: Tuple[int, int]) -> Tuple[int, int]:
        start_raw = os.environ.get(start_env)
        end_raw = os.environ.get(end_env)
        if not start_raw and not end_raw:
            return default
        try:
            start = int(start_raw) if start_raw else default[0]
            end = int(end_raw) if end_raw else default[1]
        except ValueError:
            logger.warning(f"Invalid {start_env}/{end_env} values; using default {default}")
            return default
        if start < 1024 or end <= start or end > 65536:
            logger.warning(f"Invalid port range {start}-{end}; using default {default}")
            return default
        return (start, end)

    def _port_is_available(self, port: int) -> bool:
        """Best-effort check whether a port is bindable on localhost."""
        if not self._verify_availability:
            return True

        # Check IPv4
        try:
            s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s4.bind((self._bind_host_ipv4, port))
        except OSError:
            return False
        finally:
            with contextlib.suppress(Exception):
                s4.close()

        # Check IPv6 as well (common dev servers bind to ::)
        try:
            s6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            with contextlib.suppress(Exception):
                s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s6.bind((self._bind_host_ipv6, port))
        except OSError as e:
            # If IPv6 isn't supported/available on this machine, don't fail allocation.
            if e.errno in (errno.EAFNOSUPPORT, errno.EADDRNOTAVAIL):
                return True
            return False
        finally:
            with contextlib.suppress(Exception):
                s6.close()

        return True

    def reserve_ports(self, agent_id: str, api_port: int, web_port: int) -> bool:
        """Reserve an explicit port pair (used when bootstrapping from DB)."""
        if not (self.api_port_range[0] <= api_port < self.api_port_range[1]):
            logger.warning(f"Cannot reserve API port {api_port}: outside allocator range")
            return False
        if not (self.web_port_range[0] <= web_port < self.web_port_range[1]):
            logger.warning(f"Cannot reserve web port {web_port}: outside allocator range")
            return False

        with self._lock:
            if agent_id in self._agent_ports:
                return True

            if api_port in self._available_api_ports:
                self._available_api_ports.remove(api_port)
                self._in_use_api_ports.add(api_port)
            if web_port in self._available_web_ports:
                self._available_web_ports.remove(web_port)
                self._in_use_web_ports.add(web_port)

            self._agent_ports[agent_id] = (api_port, web_port)
            return True

    def allocate_ports(self, agent_id: str) -> Optional[Tuple[int, int]]:
        """
        Allocate a port pair for an agent.

        Args:
            agent_id: Unique agent identifier

        Returns:
            Tuple of (api_port, web_port) or None if no ports available
        """
        with self._lock:
            # Check if agent already has ports allocated
            if agent_id in self._agent_ports:
                logger.warning(f"Agent {agent_id} already has ports allocated: {self._agent_ports[agent_id]}")
                return self._agent_ports[agent_id]

            # Check if we have available ports
            if not self._available_api_ports or not self._available_web_ports:
                logger.error(f"No ports available! API: {len(self._available_api_ports)}, Web: {len(self._available_web_ports)}")
                return None

            def pick_port(available: Set[int], blocked: Set[int]) -> Optional[int]:
                for candidate in sorted(available):
                    if self._port_is_available(candidate):
                        return candidate
                    # Permanently avoid ports already occupied by other processes.
                    available.discard(candidate)
                    blocked.add(candidate)
                return None

            api_port = pick_port(self._available_api_ports, self._blocked_api_ports)
            web_port = pick_port(self._available_web_ports, self._blocked_web_ports)

            if api_port is None or web_port is None:
                logger.error(
                    "No bindable ports available "
                    f"(API remaining={len(self._available_api_ports)}, Web remaining={len(self._available_web_ports)})"
                )
                return None

            # Move to in-use sets
            self._available_api_ports.remove(api_port)
            self._available_web_ports.remove(web_port)
            self._in_use_api_ports.add(api_port)
            self._in_use_web_ports.add(web_port)

            # Track allocation
            self._agent_ports[agent_id] = (api_port, web_port)

            logger.info(f"Allocated ports for {agent_id}: API={api_port}, WEB={web_port}")
            logger.info(f"  Available ports: API={len(self._available_api_ports)}, Web={len(self._available_web_ports)}")

            return (api_port, web_port)

    def release_ports(self, agent_id: str) -> bool:
        """
        Release ports allocated to an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            True if ports were released, False if agent had no ports allocated
        """
        with self._lock:
            if agent_id not in self._agent_ports:
                logger.warning(f"Agent {agent_id} has no ports allocated")
                return False

            api_port, web_port = self._agent_ports[agent_id]

            # Remove from in-use and add back to available
            self._in_use_api_ports.discard(api_port)
            self._in_use_web_ports.discard(web_port)
            if self.api_port_range[0] <= api_port < self.api_port_range[1]:
                self._available_api_ports.add(api_port)
            if self.web_port_range[0] <= web_port < self.web_port_range[1]:
                self._available_web_ports.add(web_port)

            # Remove from tracking
            del self._agent_ports[agent_id]

            logger.info(f"Released ports for {agent_id}: API={api_port}, WEB={web_port}")
            logger.info(f"  Available ports: API={len(self._available_api_ports)}, Web={len(self._available_web_ports)}")

            return True

    def get_agent_ports(self, agent_id: str) -> Optional[Tuple[int, int]]:
        """
        Get the ports allocated to an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Tuple of (api_port, web_port) or None if not allocated
        """
        with self._lock:
            return self._agent_ports.get(agent_id)

    def get_status(self) -> Dict[str, Any]:
        """Get current allocator status."""
        with self._lock:
            return {
                "api_ports": {
                    "available": len(self._available_api_ports),
                    "in_use": len(self._in_use_api_ports),
                    "blocked": len(self._blocked_api_ports),
                    "total": self.api_port_range[1] - self.api_port_range[0],
                    "range": f"{self.api_port_range[0]}-{self.api_port_range[1]}"
                },
                "web_ports": {
                    "available": len(self._available_web_ports),
                    "in_use": len(self._in_use_web_ports),
                    "blocked": len(self._blocked_web_ports),
                    "total": self.web_port_range[1] - self.web_port_range[0],
                    "range": f"{self.web_port_range[0]}-{self.web_port_range[1]}"
                },
                "active_allocations": len(self._agent_ports),
                "agents": list(self._agent_ports.keys())
            }



class Orchestrator:
    """
    Orchestrator manages parallel autonomous coding agents.

    Uses direct imports for system logic and provides MCP tools to agents.
    Includes port pool allocator for managing parallel agent server ports.
    """

    def __init__(
        self,
        project_dir: str,
        max_agents: int = 3,
        model_preset: str = "balanced"
    ):
        """
        Initialize the orchestrator.

        Args:
            project_dir: Path to the project
            max_agents: Maximum number of parallel agents
            model_preset: Model preset to use (quality, balanced, economy, cheap, experimental)
        """
        self.project_dir = Path(project_dir).resolve()
        self.max_agents = max_agents

        # Direct imports (system logic)
        self.kb = get_knowledge_base()
        # Load persisted model settings (e.g., from Web UI), then optionally override with preset.
        self.model_settings = ModelSettings.load_for_project(self.project_dir)
        self.worktree_manager = WorktreeManager(str(self.project_dir))
        self.database = get_database(str(self.project_dir))
        self.gatekeeper = Gatekeeper(str(self.project_dir))
        with contextlib.suppress(Exception):
            self.project_config = load_project_config(self.project_dir)
        if not hasattr(self, "project_config"):
            self.project_config = None

        # Initialize port allocator
        self.port_allocator = PortAllocator()
        self._bootstrap_ports_from_database()
        port_status = self.port_allocator.get_status()
        self._last_logs_prune_at: Optional[datetime] = None
        self._last_dependency_check_at: Optional[datetime] = None

        # Apply model preset override (workers may pass 'custom' to use persisted available_models).
        self.model_preset = model_preset
        if model_preset and model_preset != "custom":
            try:
                self.model_settings.set_preset(model_preset)
            except ValueError:
                logger.warning("Unknown model_preset=%s; falling back to persisted settings", model_preset)
        self.available_models = self.model_settings.available_models

        logger.info(f"Orchestrator initialized:")
        logger.info(f"  Project: {self.project_dir}")
        logger.info(f"  Max agents: {max_agents}")
        logger.info(f"  Model preset: {self.model_settings.preset}")
        logger.info(f"  Available models: {self.available_models}")
        logger.info(f"  Port pools:")
        logger.info(f"    API: {port_status['api_ports']['range']} ({port_status['api_ports']['available']} available)")
        logger.info(f"    Web: {port_status['web_ports']['range']} ({port_status['web_ports']['available']} available)")

    def _bootstrap_ports_from_database(self) -> None:
        """
        Reserve ports for already-running agents.

        This prevents port reuse after orchestrator restarts while workers are still running.
        """
        try:
            active_agents = self.database.get_active_agents()
        except Exception as e:
            logger.warning(f"Failed to bootstrap port allocations from database: {e}")
            return

        reserved = 0
        for agent in active_agents:
            agent_id = agent.get("agent_id")
            api_port = agent.get("api_port")
            web_port = agent.get("web_port")
            pid = agent.get("pid")

            if not agent_id or api_port is None or web_port is None:
                continue

            if pid and psutil.pid_exists(pid):
                if self.port_allocator.reserve_ports(agent_id, int(api_port), int(web_port)):
                    reserved += 1
            else:
                # Agent record exists but process is gone: mark crashed and release feature.
                logger.warning(f"Active agent {agent_id} has no live PID; marking crashed")
                with contextlib.suppress(Exception):
                    self.database.mark_agent_crashed(agent_id)
                if agent.get("feature_id"):
                    with contextlib.suppress(Exception):
                        self.database.mark_feature_failed(
                            feature_id=agent["feature_id"],
                            reason="Agent process missing on orchestrator startup",
                        )
                with contextlib.suppress(Exception):
                    self.worktree_manager.delete_worktree(agent_id, force=True)

        if reserved:
            logger.info(f"Bootstrapped {reserved} port allocation(s) from database")

    async def _run_initializer(self) -> bool:
        """
        Run the initializer agent to create features if the database is empty.

        The initializer scans the codebase, creates a feature list, and prepares
        the project for parallel execution. Runs on the main branch (no worktree).

        Returns:
            True if initializer succeeded, False otherwise
        """
        logger.info("📝 No features found, running initializer agent...")

        try:
            init_provider = self._initializer_provider()
            if init_provider == "claude":
                # Select model for initializer (use best available model)
                model = self.available_models[0] if self.available_models else "opus"

                logger.info(f"   Provider: CLAUDE")
                logger.info(f"   Model: {model.upper()}")
                logger.info(f"   Location: Main branch (no worktree needed)")

                # Run initializer with max_iterations=1 (only initializer session)
                await run_autonomous_agent(
                    project_dir=self.project_dir,
                    model=model,
                    max_iterations=1,  # Only run initializer
                    yolo_mode=False     # Full testing for initializer
                )
            else:
                logger.info(f"   Provider: {init_provider.upper()} (multi-model backlog)")
                self._run_initializer_multi_model(provider=init_provider)

            # Verify features were created
            stats = self.database.get_stats()
            total_features = stats["features"].get("total_all") or stats["features"]["total"]

            if total_features == 0:
                logger.error("   ❌ Initializer completed but no features were created!")
                return False

            # Apply staging if the backlog is large
            self._maybe_stage_initializer_backlog(total_features=int(total_features))

            logger.info(f"   ✅ Initializer completed successfully!")
            logger.info(f"   📊 Created {total_features} features")
            return True

        except Exception as e:
            logger.error(f"   ❌ Initializer failed: {e}")
            return False

    def _run_initializer_multi_model(self, *, provider: str) -> None:
        """
        Generate a feature backlog using Codex/Gemini CLIs (optionally synthesized).
        """
        spec_text = ""
        try:
            spec_text = get_app_spec(self.project_dir)
        except Exception as e:
            raise RuntimeError(f"Could not load app_spec.txt: {e}") from e

        feature_count = infer_feature_count(self.project_dir)
        prompt = build_backlog_prompt(spec_text, feature_count)

        agents = self._initializer_agents()
        if provider == "codex_cli":
            agents = ["codex"]
        elif provider == "gemini_cli":
            agents = ["gemini"]

        cfg = MultiModelGenerateConfig.from_env(
            agents=agents,
            synthesizer=self._initializer_synthesizer(),
            timeout_s=self._initializer_timeout_s(),
        )

        drafts_root = self.project_dir / ".autocoder" / "drafts" / "initializer"
        drafts_root.mkdir(parents=True, exist_ok=True)
        output_path = drafts_root / f"features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        result = generate_multi_model_text(
            prompt=prompt,
            cfg=cfg,
            output_path=output_path,
            drafts_root=drafts_root / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            synthesize=True,
        )

        text = Path(result["output_path"]).read_text(encoding="utf-8", errors="replace")
        backlog = parse_feature_backlog(text)
        features = backlog.features
        if not features:
            raise RuntimeError("Initializer generated no valid features (empty parse)")

        total = len(features)
        for idx, feature in enumerate(features):
            if feature.get("priority") is None:
                feature["priority"] = total - idx

        created = self.database.create_features_bulk(features)
        if created <= 0:
            raise RuntimeError("Failed to insert features into database")

        logger.info(f"   ✅ Multi-model initializer created {created} features")

    def _maybe_stage_initializer_backlog(self, *, total_features: int) -> None:
        stage_threshold = self._initializer_stage_threshold()
        enqueue_count = self._initializer_enqueue_count()
        if stage_threshold <= 0 or total_features <= stage_threshold:
            return

        keep = enqueue_count if enqueue_count > 0 else min(stage_threshold, max(1, stage_threshold // 3))
        staged = self.database.stage_features_excluding_top(keep)
        logger.info(
            f"   🧊 Staged {staged} features (threshold={stage_threshold}, kept_enabled={keep})"
        )

    async def run_parallel_agents(self) -> Dict[str, Any]:
        """
        Run multiple agents in parallel until all features are complete.

        This is the main entry point for parallel execution.

        Returns:
            Summary statistics
        """
        logger.info("🚀 Starting parallel agent execution...")

        start_time = datetime.now()
        total_completed = 0
        total_failed = 0
        idle_cycles = 0

        try:
            # Check if we need to run initializer first
            stats = self.database.get_stats()
            total_features = stats["features"]["total"]
            staged_features = stats["features"].get("staged", 0)

            if total_features == 0:
                if staged_features > 0:
                    enqueue_count = self._initializer_enqueue_count() or 1
                    enabled = self.database.enqueue_staged_features(enqueue_count)
                    logger.info(
                        f"🧊 Enabled {enabled} staged feature(s) (initial enqueue) out of {staged_features}"
                    )
                    stats = self.database.get_stats()
                    total_features = stats["features"]["total"]
                    if total_features > 0:
                        # Continue to normal flow.
                        pass
                    else:
                        logger.error("❌ No active features after enqueueing staged backlog")
                        return {
                            "duration_seconds": 0,
                            "features_completed": 0,
                            "features_failed": 0,
                            "error": "No active features after staging enqueue",
                        }
                else:
                    logger.info("📝 No features found, running initializer agent...")
                    initializer_success = await self._run_initializer()
                    if not initializer_success:
                        logger.error("❌ Initializer failed, cannot continue with parallel execution")
                        return {
                            "duration_seconds": 0,
                            "features_completed": 0,
                            "features_failed": 0,
                            "error": "Initializer failed"
                        }
                    # Refresh stats after initializer
                    stats = self.database.get_stats()

            while True:
                # Check if there are pending features
                stats = self.database.get_stats()

                total_features = stats["features"]["total"]
                if total_features == 0:
                    logger.error("❌ No features in database!")
                    break

                if stats["features"]["pending"] == 0 and stats["features"]["in_progress"] == 0:
                    staged = int(stats["features"].get("staged", 0) or 0)
                    if staged > 0:
                        enqueue_count = self._initializer_enqueue_count() or 1
                        enabled = self.database.enqueue_staged_features(enqueue_count)
                        logger.info(
                            f"🧊 Enabled {enabled} staged feature(s) (remaining staged: {staged})"
                        )
                        if enabled > 0:
                            continue
                    logger.info("✅ All features complete!")
                    break

                # Check for crashed agents and recover
                self._recover_crashed_agents()

                # Release ports from completed agents
                self._recover_completed_agents()

                # Periodic log maintenance
                self._prune_worker_logs_if_needed()
                # Periodic deferred cleanup (Windows file locks)
                with contextlib.suppress(Exception):
                    self.worktree_manager.process_cleanup_queue()
                # Periodic dependency health check (prevents DAG deadlocks)
                with contextlib.suppress(Exception):
                    self._block_unresolvable_dependencies_if_needed()

                # Any time Gatekeeper advances or retries clear, reset idle backoff.
                idle_cycles = 0

                # Get count of active agents
                active_count = stats["agents"]["active"]
                available_slots = self.max_agents - active_count

                if available_slots > 0:
                    queue_state = {}
                    with contextlib.suppress(Exception):
                        queue_state = self.database.get_pending_queue_state()

                    claimable_now = int((queue_state or {}).get("claimable_now") or 0)
                    pending_total = int((queue_state or {}).get("pending_total") or stats["features"]["pending"] or 0)

                    if claimable_now > 0:
                        idle_cycles = 0
                        # Spawn more agents
                        self._spawn_agents(min(available_slots, claimable_now))
                    else:
                        # Avoid tight polling when there are pending features but none are currently claimable.
                        idle_cycles += 1
                        waiting_backoff = int((queue_state or {}).get("waiting_backoff") or 0)
                        waiting_deps = int((queue_state or {}).get("waiting_deps") or 0)

                        # Exponential idle backoff: 5s, 10s, 20s, 40s, 60s...
                        base_sleep = 5
                        sleep_s = min(60, base_sleep * (2 ** min(4, idle_cycles)))

                        # If we're waiting on a scheduled retry, don't sleep longer than the earliest retry.
                        earliest = (queue_state or {}).get("earliest_next_attempt_at")
                        if earliest:
                            with contextlib.suppress(Exception):
                                # SQLite timestamps are in local time; treat them as "naive" local.
                                dt = datetime.fromisoformat(str(earliest))
                                seconds_until = max(1, int((dt - datetime.now()).total_seconds()))
                                sleep_s = min(sleep_s, max(1, seconds_until))

                        # Log a periodic reason (every ~1 minute of idle backoff).
                        if idle_cycles == 1 or idle_cycles % 6 == 0:
                            reason = []
                            if pending_total > 0 and waiting_deps > 0:
                                reason.append(f"waiting on deps ({waiting_deps})")
                            if pending_total > 0 and waiting_backoff > 0:
                                reason.append(f"waiting on retry window ({waiting_backoff})")
                            msg = ", ".join(reason) if reason else "no claimable features"
                            logger.info(f"⏳ No claimable pending features; sleeping {sleep_s}s ({msg})")

                        await asyncio.sleep(sleep_s)
                        continue

                # Wait a bit before checking again
                idle_cycles = 0
                await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("\n⚠️ Interrupted by user")

        finally:
            # Cleanup
            self._cleanup_all_agents()

        # Final stats
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        final_stats = self.database.get_stats()

        return {
            "duration_seconds": duration,
            "features_completed": final_stats["features"]["completed"],
            "features_failed": total_failed,
            "stats": final_stats
        }

    def _spawn_agents(self, count: int) -> List[str]:
        """
        Spawn new agents to work on pending features.

        Args:
            count: Number of agents to spawn

        Returns:
            List of agent IDs that were spawned
        """
        if count <= 0:
            return []
        logger.info(f"🤖 Spawning {count} agent(s)...")

        spawned_agents = []

        # Each spawned agent gets its own unique agent_id.
        agent_id_prefix = f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        for i in range(count):
            agent_id = f"{agent_id_prefix}-{i}"

            claimed_feature = self.database.claim_next_pending_feature(
                agent_id,
                branch_prefix="feat",
                prioritize_blockers=self._env_truthy("AUTOCODER_DAG_PRIORITIZE_BLOCKERS"),
            )
            if not claimed_feature:
                logger.debug("No pending features to claim")
                break

            feature_id = claimed_feature["id"]
            claimed_branch = claimed_feature.get("branch_name") or f"feat/{feature_id}"

            # Select model for this feature
            model = self._select_model_for_feature(claimed_feature)

            # Allocate ports for this agent
            port_pair = self.port_allocator.allocate_ports(agent_id)
            if not port_pair:
                logger.error(f"   ❌ Failed to allocate ports for {agent_id}")
                self.database.mark_feature_failed(feature_id=feature_id, reason="No ports available")
                continue

            api_port, web_port = port_pair

            # Create worktree for the claimed branch
            try:
                worktree_info = self.worktree_manager.create_worktree(
                    agent_id=agent_id,
                    feature_id=feature_id,
                    feature_name=claimed_feature["name"],
                    branch_name=claimed_branch,
                )
            except Exception as e:
                logger.error(f"   ❌ Failed to create worktree for {agent_id}: {e}")
                self.database.mark_feature_failed(feature_id=feature_id, reason="Worktree creation failed")
                # Release ports on failure
                self.port_allocator.release_ports(agent_id)
                continue

            plan_path = None
            with contextlib.suppress(Exception):
                plan_path = self._maybe_generate_feature_plan(
                    feature=claimed_feature, worktree_path=Path(worktree_info["worktree_path"])
                )

            # Spawn actual worker process.
            #
            # Providers:
            # - AUTOCODER_E2E_DUMMY_WORKER=1: deterministic fixture worker (no LLM)
            # - project autocoder.yaml: worker.provider / worker.patch_* (per-project defaults)
            # - AUTOCODER_WORKER_PROVIDER=claude: Claude Agent SDK worker
            # - AUTOCODER_WORKER_PROVIDER=codex_cli|gemini_cli|multi_cli: patch-based worker via qa_worker.py
            cmd: list[str] = []
            provider_for_env = "claude"
            cfg_patch_agents: Optional[list[str]] = None
            if self._env_truthy("AUTOCODER_E2E_DUMMY_WORKER"):
                worker_script = Path(__file__).resolve().parents[1] / "e2e_dummy_worker.py"
                provider_for_env = "dummy"
                cmd = [
                    sys.executable,
                    str(worker_script),
                    "--project-dir",
                    str(self.project_dir),
                    "--agent-id",
                    agent_id,
                    "--feature-id",
                    str(feature_id),
                    "--worktree-path",
                    worktree_info["worktree_path"],
                    "--api-port",
                    str(api_port),
                    "--web-port",
                    str(web_port),
                ]
            else:
                cfg_provider: Optional[str] = None
                cfg_patch_iters: Optional[int] = None
                with contextlib.suppress(Exception):
                    cfg = load_project_config(self.project_dir)
                    worker_cfg = getattr(cfg, "worker", None) if cfg is not None else None
                    if worker_cfg is not None:
                        cfg_provider = getattr(worker_cfg, "provider", None)
                        cfg_patch_iters = getattr(worker_cfg, "patch_max_iterations", None)
                        cfg_patch_agents = getattr(worker_cfg, "patch_agents", None)

                env_provider = str(os.environ.get("AUTOCODER_WORKER_PROVIDER", "")).strip().lower()
                # Allow shorthand.
                if env_provider == "codex":
                    env_provider = "codex_cli"
                elif env_provider == "gemini":
                    env_provider = "gemini_cli"

                provider = (cfg_provider or env_provider or "claude").strip().lower()
                if provider == "codex":
                    provider = "codex_cli"
                elif provider == "gemini":
                    provider = "gemini_cli"
                provider_for_env = provider

                if provider == "claude":
                    worker_script = Path(__file__).parent.parent / "agent_worker.py"
                    cmd = [
                        sys.executable,
                        str(worker_script),
                        "--project-dir",
                        str(self.project_dir),
                        "--agent-id",
                        agent_id,
                        "--feature-id",
                        str(feature_id),
                        "--worktree-path",
                        worktree_info["worktree_path"],
                        "--model",
                        model,
                        "--max-iterations",
                        "5",  # Each worker gets 5 iterations
                        "--api-port",
                        str(api_port),
                        "--web-port",
                        str(web_port),
                        "--yolo",  # Use YOLO mode for parallel execution (speed)
                    ]
                elif provider in {"codex_cli", "gemini_cli", "multi_cli"}:
                    worker_script = Path(__file__).parent.parent / "qa_worker.py"
                    patch_iters_raw = str(os.environ.get("AUTOCODER_WORKER_PATCH_MAX_ITERATIONS", "")).strip()
                    env_patch_iters: Optional[int] = None
                    if patch_iters_raw:
                        with contextlib.suppress(Exception):
                            env_patch_iters = int(patch_iters_raw)
                    if env_patch_iters is not None:
                        env_patch_iters = max(1, min(20, env_patch_iters))
                    patch_iters = cfg_patch_iters if cfg_patch_iters is not None else (env_patch_iters if env_patch_iters is not None else 2)
                    cmd = [
                        sys.executable,
                        str(worker_script),
                        "--mode",
                        "implement",
                        "--project-dir",
                        str(self.project_dir),
                        "--agent-id",
                        agent_id,
                        "--feature-id",
                        str(feature_id),
                        "--worktree-path",
                        worktree_info["worktree_path"],
                        "--provider",
                        provider,
                        "--max-iterations",
                        str(patch_iters),
                    ]
                else:
                    logger.error(f"   ❌ Unknown AUTOCODER_WORKER_PROVIDER='{provider}', falling back to claude")
                    worker_script = Path(__file__).parent.parent / "agent_worker.py"
                    cmd = [
                        sys.executable,
                        str(worker_script),
                        "--project-dir",
                        str(self.project_dir),
                        "--agent-id",
                        agent_id,
                        "--feature-id",
                        str(feature_id),
                        "--worktree-path",
                        worktree_info["worktree_path"],
                        "--model",
                        model,
                        "--max-iterations",
                        "5",
                        "--api-port",
                        str(api_port),
                        "--web-port",
                        str(web_port),
                        "--yolo",
                    ]

            # Prepare environment with port allocations (redundant with CLI args)
            env = os.environ.copy()
            # Make the effective provider visible to workers/subprocesses.
            env["AUTOCODER_WORKER_PROVIDER"] = provider_for_env
            with contextlib.suppress(Exception):
                if provider_for_env in {"multi_cli"} and cfg_patch_agents:
                    env["AUTOCODER_WORKER_PATCH_AGENTS"] = ",".join([str(x) for x in cfg_patch_agents if str(x).strip()])
            env["AUTOCODER_API_PORT"] = str(api_port)
            env["AUTOCODER_WEB_PORT"] = str(web_port)
            # Compatibility for common dev servers that read generic port env vars.
            env["API_PORT"] = str(api_port)
            env["WEB_PORT"] = str(web_port)
            env["PORT"] = str(api_port)
            env["VITE_PORT"] = str(web_port)
            # Prevent workers from self-attesting `passes=True`; require Gatekeeper verification.
            env["AUTOCODER_REQUIRE_GATEKEEPER"] = "1"
            # Identify this worker for hooks/tools (locks, etc.).
            env.setdefault("AUTOCODER_AGENT_ID", str(agent_id))
            if plan_path:
                env["AUTOCODER_FEATURE_PLAN_PATH"] = str(plan_path)

            # Per-agent logs (for debugging and post-mortems)
            logs_dir = (self.project_dir / ".autocoder" / "logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = logs_dir / f"{agent_id}.log"

            logger.info(f"🚀 Launching {agent_id}:")
            logger.info(f"   Feature: #{feature_id} - {claimed_feature['name']}")
            logger.info(f"   Model: {model.upper()}")
            logger.info(f"   Worktree: {worktree_info['worktree_path']}")
            logger.info(f"   Ports: API={api_port}, WEB={web_port}")
            logger.info(f"   Logs: {log_file_path}")
            logger.info(f"   Command: {' '.join(cmd[:3])}...")

            try:
                log_handle = open(log_file_path, "w", encoding="utf-8", errors="replace")
                # Spawn the process (fire and forget - monitored via DB)
                process = subprocess.Popen(
                    cmd,
                    stdout=log_handle,
                    stderr=log_handle,
                    env=env,  # Pass environment with port allocations
                    # Don't wait - let it run in background
                )
                with contextlib.suppress(Exception):
                    log_handle.close()

                pid = process.pid
                logger.info(f"   PID: {pid}")

                # Register agent in database with PID and ports
                self.database.register_agent(
                    agent_id=agent_id,
                    worktree_path=worktree_info["worktree_path"],
                    feature_id=feature_id,
                    pid=pid,
                    api_port=api_port,
                    web_port=web_port,
                    log_file_path=str(log_file_path),
                )
                with contextlib.suppress(Exception):
                    self.database.create_branch(claimed_branch, feature_id=feature_id, agent_id=agent_id)

                spawned_agents.append(agent_id)

            except Exception as e:
                logger.error(f"   ❌ Failed to spawn agent: {e}")
                # Cleanup on failure
                self.database.mark_feature_failed(feature_id=feature_id, reason="Agent spawn failed")
                self.worktree_manager.delete_worktree(agent_id, force=True)
                self.port_allocator.release_ports(agent_id)
                continue

        return spawned_agents

    def _maybe_generate_feature_plan(self, *, feature: dict, worktree_path: Path) -> str | None:
        """
        Optionally generate a per-feature plan artifact and return its path.

        The plan is written into the agent worktree under `.autocoder/feature_plan.md` so the worker
        can read it without accessing paths outside its worktree sandbox.
        """
        if not self._planner_enabled():
            return None
        feature_id = int(feature.get("id") or 0)
        if feature_id <= 0:
            return None

        out_path = (Path(worktree_path) / ".autocoder" / "feature_plan.md").resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        drafts_root = (
            self.project_dir
            / ".autocoder"
            / "features"
            / str(feature_id)
            / "planner"
            / datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        drafts_root.mkdir(parents=True, exist_ok=True)

        prompt = (
            "Create a concise implementation plan for this feature.\n\n"
            f"Feature #{feature_id}: {feature.get('name')}\n"
            f"Category: {feature.get('category')}\n\n"
            f"Description:\n{feature.get('description')}\n\n"
            f"Steps:\n"
            + "\n".join([f"- {s}" for s in (feature.get('steps') or [])])
            + "\n\n"
            "Constraints:\n"
            "- Keep it small and actionable.\n"
            "- Include the verification commands to run.\n"
            "- Do not invent dependencies that aren't in the repo.\n"
        )

        cfg = MultiModelGenerateConfig(
            agents=[a for a in self._planner_agents() if a in {"codex", "gemini"}],  # type: ignore[list-item]
            synthesizer=self._planner_synthesizer(),  # type: ignore[arg-type]
            timeout_s=self._planner_timeout_s(),
            codex_model=str(os.environ.get("AUTOCODER_CODEX_MODEL", "")).strip(),
            codex_reasoning_effort=str(os.environ.get("AUTOCODER_CODEX_REASONING_EFFORT", "")).strip(),
            gemini_model=str(os.environ.get("AUTOCODER_GEMINI_MODEL", "")).strip(),
            claude_model=self._planner_model(),
        )

        try:
            generate_multi_model_artifact(
                project_dir=worktree_path,
                kind="plan",
                user_prompt=prompt,
                cfg=cfg,
                output_path=out_path,
                drafts_root=drafts_root,
                synthesize=True,
            )
            return str(out_path)
        except Exception as e:
            logger.warning(f"Planner failed for feature #{feature_id}: {e}")
            return None

    @staticmethod
    def _env_truthy(name: str) -> bool:
        raw = str(os.environ.get(name, "")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _controller_enabled(self) -> bool:
        return self._env_truthy("AUTOCODER_CONTROLLER_ENABLED")

    def _planner_enabled(self) -> bool:
        return self._env_truthy("AUTOCODER_PLANNER_ENABLED")

    def _planner_timeout_s(self) -> int:
        raw = str(os.environ.get("AUTOCODER_PLANNER_TIMEOUT_S", "")).strip()
        try:
            v = int(raw) if raw else 180
        except Exception:
            v = 180
        return max(30, min(3600, v))

    def _planner_agents(self) -> list[str]:
        raw = str(os.environ.get("AUTOCODER_PLANNER_AGENTS", "")).strip().lower()
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        out: list[str] = []
        for p in parts:
            if p in {"codex", "gemini"}:
                out.append(p)
        return out or ["codex", "gemini"]

    def _planner_synthesizer(self) -> str:
        raw = str(os.environ.get("AUTOCODER_PLANNER_SYNTHESIZER", "")).strip().lower()
        if raw in {"none", "claude", "codex", "gemini"}:
            return raw
        return "claude"

    def _planner_model(self) -> str:
        return str(os.environ.get("AUTOCODER_PLANNER_MODEL", "")).strip().lower()

    def _initializer_provider(self) -> str:
        cfg_provider = None
        with contextlib.suppress(Exception):
            if getattr(self, "project_config", None) is not None:
                cfg_provider = getattr(getattr(self.project_config, "initializer", None), "provider", None)
        raw = str(cfg_provider or os.environ.get("AUTOCODER_INITIALIZER_PROVIDER", "") or "claude").strip().lower()
        if raw == "codex":
            raw = "codex_cli"
        elif raw == "gemini":
            raw = "gemini_cli"
        if raw not in {"claude", "codex_cli", "gemini_cli", "multi_cli"}:
            return "claude"
        return raw

    def _initializer_agents(self) -> list[str]:
        cfg_agents = None
        with contextlib.suppress(Exception):
            if getattr(self, "project_config", None) is not None:
                cfg_agents = getattr(getattr(self.project_config, "initializer", None), "agents", None)
        if cfg_agents:
            return [str(x).strip().lower() for x in cfg_agents if str(x).strip()]
        raw = str(os.environ.get("AUTOCODER_INITIALIZER_AGENTS", "")).strip().lower()
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        return [p for p in parts if p in {"codex", "gemini"}] or ["codex", "gemini"]

    def _initializer_synthesizer(self) -> str:
        cfg_synth = None
        with contextlib.suppress(Exception):
            if getattr(self, "project_config", None) is not None:
                cfg_synth = getattr(getattr(self.project_config, "initializer", None), "synthesizer", None)
        raw = str(cfg_synth or os.environ.get("AUTOCODER_INITIALIZER_SYNTHESIZER", "")).strip().lower()
        return raw if raw in {"none", "claude", "codex", "gemini"} else "claude"

    def _initializer_timeout_s(self) -> int:
        cfg_timeout = None
        with contextlib.suppress(Exception):
            if getattr(self, "project_config", None) is not None:
                cfg_timeout = getattr(getattr(self.project_config, "initializer", None), "timeout_s", None)
        raw = str(cfg_timeout if cfg_timeout is not None else os.environ.get("AUTOCODER_INITIALIZER_TIMEOUT_S", "")).strip()
        try:
            v = int(raw) if raw else 300
        except Exception:
            v = 300
        return max(30, min(3600, v))

    def _initializer_stage_threshold(self) -> int:
        cfg_stage = None
        with contextlib.suppress(Exception):
            if getattr(self, "project_config", None) is not None:
                cfg_stage = getattr(getattr(self.project_config, "initializer", None), "stage_threshold", None)
        raw = str(cfg_stage if cfg_stage is not None else os.environ.get("AUTOCODER_INITIALIZER_STAGE_THRESHOLD", "")).strip()
        try:
            v = int(raw) if raw else 120
        except Exception:
            v = 120
        return max(0, v)

    def _initializer_enqueue_count(self) -> int:
        cfg_enqueue = None
        with contextlib.suppress(Exception):
            if getattr(self, "project_config", None) is not None:
                cfg_enqueue = getattr(getattr(self.project_config, "initializer", None), "enqueue_count", None)
        raw = str(cfg_enqueue if cfg_enqueue is not None else os.environ.get("AUTOCODER_INITIALIZER_ENQUEUE_COUNT", "")).strip()
        try:
            v = int(raw) if raw else 30
        except Exception:
            v = 30
        return max(0, v)

    def _qa_subagent_enabled(self) -> bool:
        return self._env_truthy("AUTOCODER_QA_SUBAGENT_ENABLED")

    def _qa_subagent_max_iterations(self) -> int:
        raw = str(os.environ.get("AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS", "")).strip()
        try:
            v = int(raw) if raw else 2
        except Exception:
            v = 2
        return max(1, min(20, v))

    def _qa_subagent_model(self) -> str:
        raw = str(os.environ.get("AUTOCODER_QA_MODEL", "")).strip().lower()
        if raw in self.available_models:
            return raw
        # QA is short-lived; default to a fast/strong middle tier.
        return "sonnet" if "sonnet" in self.available_models else (self.available_models[0] if self.available_models else "opus")

    def _qa_subagent_provider(self) -> str:
        raw = str(os.environ.get("AUTOCODER_QA_SUBAGENT_PROVIDER", "")).strip().lower()
        if raw in {"claude", "codex_cli", "gemini_cli", "multi_cli"}:
            return raw
        return "claude"

    def _spawn_qa_subagent(self, *, feature_id: int, feature_name: str, branch_name: str) -> str | None:
        """
        Spawn a short-lived QA fixer worker for a rejected feature branch.

        This reuses the existing branch and relies on QA Fix Mode prompts (enabled via env),
        but runs in a fresh process/worktree with a smaller iteration budget and YOLO off.
        """
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        qa_agent_id = f"qa-{feature_id}-{stamp}"

        port_pair = self.port_allocator.allocate_ports(qa_agent_id)
        if not port_pair:
            logger.error(f"   ❌ Failed to allocate ports for {qa_agent_id} (QA sub-agent)")
            return None
        api_port, web_port = port_pair

        try:
            worktree_info = self.worktree_manager.create_worktree(
                agent_id=qa_agent_id,
                feature_id=feature_id,
                feature_name=feature_name,
                branch_name=branch_name,
            )
        except Exception as e:
            logger.error(f"   ❌ Failed to create QA worktree for {qa_agent_id}: {e}")
            self.port_allocator.release_ports(qa_agent_id)
            return None

        # Mark assigned before spawn to avoid other claims (best-effort).
        if not self.database.assign_feature_to_agent(feature_id, qa_agent_id):
            logger.error(f"   ❌ Failed to assign feature #{feature_id} to QA agent {qa_agent_id}")
            with contextlib.suppress(Exception):
                self.worktree_manager.delete_worktree(qa_agent_id, force=True)
            self.port_allocator.release_ports(qa_agent_id)
            return None

        provider = self._qa_subagent_provider()
        max_iterations = self._qa_subagent_max_iterations()
        model = self._qa_subagent_model()

        if provider == "claude":
            worker_script = Path(__file__).parent.parent / "agent_worker.py"
            cmd = [
                sys.executable,
                str(worker_script),
                "--project-dir",
                str(self.project_dir),
                "--agent-id",
                qa_agent_id,
                "--feature-id",
                str(feature_id),
                "--worktree-path",
                worktree_info["worktree_path"],
                "--model",
                model,
                "--max-iterations",
                str(max_iterations),
                "--api-port",
                str(api_port),
                "--web-port",
                str(web_port),
            ]
        else:
            # External CLI patch fixer (Codex/Gemini).
            worker_script = Path(__file__).parent.parent / "qa_worker.py"
            cmd = [
                sys.executable,
                str(worker_script),
                "--project-dir",
                str(self.project_dir),
                "--agent-id",
                qa_agent_id,
                "--feature-id",
                str(feature_id),
                "--worktree-path",
                worktree_info["worktree_path"],
                "--provider",
                provider,
                "--max-iterations",
                str(max_iterations),
            ]

        env = os.environ.copy()
        env["AUTOCODER_API_PORT"] = str(api_port)
        env["AUTOCODER_WEB_PORT"] = str(web_port)
        env["API_PORT"] = str(api_port)
        env["WEB_PORT"] = str(web_port)
        env["PORT"] = str(api_port)
        env["VITE_PORT"] = str(web_port)
        env["AUTOCODER_REQUIRE_GATEKEEPER"] = "1"
        # QA fix prompt injection (used by Claude worker; harmless for CLI fixers).
        env["AUTOCODER_QA_FIX_ENABLED"] = "1"

        logs_dir = (self.project_dir / ".autocoder" / "logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = logs_dir / f"{qa_agent_id}.log"

        logger.info(f"🧪 Launching QA sub-agent {qa_agent_id}:")
        logger.info(f"   Feature: #{feature_id} - {feature_name}")
        logger.info(f"   Branch: {branch_name}")
        logger.info(f"   Provider: {provider}")
        if provider == "claude":
            logger.info(f"   Model: {model.upper()}")
        logger.info(f"   Max iters: {max_iterations}")
        logger.info(f"   Ports: API={api_port}, WEB={web_port}")
        logger.info(f"   Logs: {log_file_path}")

        try:
            log_handle = open(log_file_path, "w", encoding="utf-8", errors="replace")
            process = subprocess.Popen(
                cmd,
                stdout=log_handle,
                stderr=log_handle,
                env=env,
            )
            with contextlib.suppress(Exception):
                log_handle.close()

            pid = process.pid
            self.database.register_agent(
                agent_id=qa_agent_id,
                worktree_path=worktree_info["worktree_path"],
                feature_id=feature_id,
                pid=pid,
                api_port=api_port,
                web_port=web_port,
                log_file_path=str(log_file_path),
            )
            return qa_agent_id
        except Exception as e:
            logger.error(f"   ❌ Failed to spawn QA sub-agent process: {e}")
            with contextlib.suppress(Exception):
                self.database.requeue_feature(feature_id, preserve_branch=True)
            with contextlib.suppress(Exception):
                self.worktree_manager.delete_worktree(qa_agent_id, force=True)
            self.port_allocator.release_ports(qa_agent_id)
            return None

    def _detect_main_branch(self) -> str:
        env_branch = os.environ.get("AUTOCODER_MAIN_BRANCH")
        if env_branch:
            return env_branch
        for candidate in ("main", "master"):
            try:
                subprocess.run(
                    ["git", "rev-parse", "--verify", candidate],
                    cwd=self.project_dir,
                    check=True,
                    capture_output=True,
                )
                return candidate
            except subprocess.CalledProcessError:
                continue
        return "main"

    async def run_feature_lifecycle(
        self,
        feature_id: int,
        agent_id: str,
        model: str
    ) -> Dict[str, Any]:
        """
        Run the complete lifecycle for a single feature.

        Workflow:
        1. Create worktree
        2. Get reference prompt from knowledge base
        3. Detect test framework
        4. Spawn Claude agent with MCP tools
        5. Monitor agent progress
        6. Submit to Gatekeeper for verification
        7. Handle merge/reject

        Args:
            feature_id: Feature ID from database
            agent_id: Agent identifier
            model: Claude model to use

        Returns:
            Lifecycle result
        """
        logger.info(f"🔄 Starting lifecycle for feature #{feature_id}")

        # Get feature details
        feature = self.database.get_feature(feature_id)
        if not feature:
            return {
                "success": False,
                "error": f"Feature {feature_id} not found"
            }

        # Step 1: Create worktree
        logger.info(f"📁 Creating worktree for {agent_id}...")
        worktree_info = self.worktree_manager.create_worktree(
            agent_id=agent_id,
            feature_id=feature_id,
            feature_name=feature["name"]
        )

        worktree_path = worktree_info["worktree_path"]
        branch_name = worktree_info["branch_name"]

        logger.info(f"   Worktree: {worktree_path}")
        logger.info(f"   Branch: {branch_name}")

        # Step 2: Get reference prompt from knowledge base
        logger.info("🧠 Getting reference prompt from knowledge base...")
        similar = self.kb.get_similar_features(feature, limit=3)
        logger.info(f"   Found {len(similar)} similar features")

        # Step 3: Spawn agent with MCP tools
        logger.info(f"🤖 Spawning Claude agent (model: {model})...")

        # Note: In real implementation, this would spawn actual agent process
        # For now, we simulate the workflow
        try:
            # Simulate agent working
            await self._simulate_agent_work(
                worktree_path=worktree_path,
                feature=feature,
                model=model
            )

            # Step 4: Submit to Gatekeeper
            logger.info("🛡️ Submitting to Gatekeeper...")

            verification = self.gatekeeper.verify_and_merge(
                branch_name=branch_name,
                worktree_path=worktree_path,
                agent_id=agent_id,
                feature_id=int(feature_id),
            )

            if verification["approved"]:
                logger.info("✅ Feature approved and merged!")
                self.database.mark_feature_passing(feature_id)
                return {
                    "success": True,
                    "feature_id": feature_id,
                    "agent_id": agent_id,
                    "verification": verification
                }
            else:
                logger.warning(f"❌ Feature rejected: {verification['reason']}")
                self.database.mark_feature_failed(
                    feature_id=feature_id,
                    reason=str(verification.get("reason") or "Gatekeeper rejected feature"),
                    artifact_path=verification.get("artifact_path"),
                    diff_fingerprint=verification.get("diff_fingerprint"),
                )
                return {
                    "success": False,
                    "feature_id": feature_id,
                    "agent_id": agent_id,
                    "verification": verification
                }

        except Exception as e:
            logger.error(f"❌ Error during lifecycle: {e}")
            return {
                "success": False,
                "feature_id": feature_id,
                "agent_id": agent_id,
                "error": str(e)
            }

        finally:
            # Cleanup
            logger.info(f"🧹 Cleaning up worktree for {agent_id}...")
            self.worktree_manager.delete_worktree(agent_id, force=True)
            self.database.unregister_agent(agent_id)

    def _select_model_for_feature(self, feature: Dict[str, Any]) -> str:
        """
        Select the best model for a feature using knowledge base.

        Args:
            feature: Feature dictionary

        Returns:
            Model name (opus, sonnet, or haiku)
        """
        category = feature.get("category", "backend")

        # Try to get best model from knowledge base
        try:
            kb_choice = self.kb.get_best_model(category)
            recommended: str | None = None
            if isinstance(kb_choice, dict):
                recommended = str(kb_choice.get("model_used") or "").strip() or None
            elif isinstance(kb_choice, str):
                recommended = kb_choice.strip() or None

            if recommended:
                # Normalize full model ids (e.g. "claude-opus-4-5") into short family names.
                lowered = recommended.lower()
                for fam in ("opus", "sonnet", "haiku"):
                    if fam in lowered:
                        recommended = fam
                        break
                if recommended in self.available_models:
                    logger.info(f"   Knowledge base recommends: {recommended}")
                    return recommended
        except Exception as e:
            logger.warning(f"Could not query knowledge base: {e}")

        # Fallback to category mapping
        category_mapping = {
            "backend": "opus",
            "frontend": "opus",
            "testing": "haiku",
            "documentation": "haiku",
            "infrastructure": "opus"
        }

        recommended = category_mapping.get(category, "sonnet")
        logger.info(f"   Category mapping recommends: {recommended}")
        return recommended

    async def _simulate_agent_work(
        self,
        worktree_path: str,
        feature: Dict[str, Any],
        model: str
    ):
        """
        Simulate agent working on a feature.

        In real implementation, this would spawn an actual Claude Agent SDK process
        with MCP tools available.

        For now, we simulate the workflow.
        """
        logger.info(f"   🤖 Agent (model: {model}) working on: {feature['name']}")
        logger.info(f"   Category: {feature['category']}")
        logger.info(f"   Description: {feature['description']}")

        # Simulate work time
        await asyncio.sleep(2)

        # Simulate creating a file
        test_file = Path(worktree_path) / "test_example.txt"
        test_file.write_text(f"Feature: {feature['name']}\nModel: {model}\n")

        # Simulate checkpoint
        self.worktree_manager.commit_checkpoint(
            agent_id="simulation",
            message="Initial implementation"
        )

        logger.info(f"   ✅ Agent completed work (simulated)")

    def _recover_crashed_agents(self):
        """
        Check for crashed agents and recover their features.

        An agent is considered crashed if:
        - It hasn't pinged in 10 minutes
        - The process is no longer running (PID doesn't exist)

        Also releases allocated ports from crashed agents.
        """
        stale_agents = self.database.get_stale_agents(timeout_minutes=10)

        for agent in stale_agents:
            logger.warning(f"⚠️ Detected stale agent: {agent['agent_id']}")

            # Check if process is still running using psutil
            if agent.get("pid"):
                pid = agent["pid"]
                if not psutil.pid_exists(pid):
                    # Process is dead
                    logger.warning(f"   Process {pid} is dead (PID no longer exists)")

                    # Release allocated ports
                    agent_id = agent["agent_id"]
                    if self.port_allocator.release_ports(agent_id):
                        logger.info(f"   Released ports for {agent_id}")

                    # Mark as crashed
                    self.database.mark_agent_crashed(agent_id)

                    # Reset feature for retry
                    if agent.get("feature_id"):
                        feature = self.database.get_feature(agent["feature_id"])
                        logger.info(f"   Resetting feature #{feature['id']} for retry")

                        self.database.mark_feature_failed(
                            feature_id=agent["feature_id"],
                            reason="Agent crashed"
                        )

                    # Delete worktree
                    if agent.get("agent_id"):
                        self.worktree_manager.delete_worktree(
                            agent_id,
                            force=True
                        )
                else:
                    logger.info(f"   Process {pid} still running, waiting for heartbeat...")
            else:
                # No PID recorded - likely old-style agent, mark as crashed
                logger.warning(f"   No PID recorded, marking as crashed")

                # Release allocated ports if any
                agent_id = agent["agent_id"]
                if self.port_allocator.release_ports(agent_id):
                    logger.info(f"   Released ports for {agent_id}")

                self.database.mark_agent_crashed(agent_id)

    def _recover_completed_agents(self):
        """
        Verify+merge and cleanup completed agents.

        This is called periodically to clean up port allocations from agents
        that completed successfully (not crashed).
        """
        completed_agents = self.database.get_completed_agents()

        for agent in completed_agents:
            agent_id = agent["agent_id"]
            feature_id = agent.get("feature_id")
            worktree_path = agent.get("worktree_path")

            logger.info(f"Processing completed agent: {agent_id}")

            if feature_id:
                feature = self.database.get_feature(feature_id)
                if feature:
                    assigned_agent = feature.get("assigned_agent_id")
                    review_status = feature.get("review_status")
                    passes = bool(feature.get("passes"))
                    branch_name = feature.get("branch_name")

                    needs_verification = (
                        (assigned_agent == agent_id)
                        and (not passes)
                        and (review_status == "READY_FOR_VERIFICATION")
                        and bool(branch_name)
                    )

                    if needs_verification:
                        logger.info(f"🧪 Gatekeeper verifying feature #{feature_id} ({branch_name})...")
                        # Refuse to verify "empty" branches (no commits beyond base).
                        base = self._detect_main_branch()
                        try:
                            commit_count = int(
                                subprocess.run(
                                    ["git", "rev-list", "--count", f"{base}..{branch_name}"],
                                    cwd=self.project_dir,
                                    check=True,
                                    capture_output=True,
                                    text=True,
                                ).stdout.strip()
                            )
                        except Exception:
                            commit_count = 0
                        if commit_count <= 0:
                            logger.warning(
                                f"Feature #{feature_id} branch {branch_name} has no commits beyond {base}; requeuing"
                            )
                            self.database.mark_feature_failed(
                                feature_id=feature_id,
                                reason="No commits on branch for verification",
                            )
                            continue

                        allow_no_tests = os.environ.get("AUTOCODER_ALLOW_NO_TESTS", "").lower() in (
                            "1",
                            "true",
                            "yes",
                        )
                        if self._controller_enabled() and worktree_path:
                            pre = self.gatekeeper.verify_commands_only(
                                worktree_path=str(worktree_path),
                                allow_no_tests=allow_no_tests,
                                feature_id=int(feature_id),
                                agent_id=agent_id,
                            )
                            if not pre.get("approved"):
                                excerpt = self._format_gatekeeper_failure_excerpt(pre)
                                self._handle_verification_rejection(
                                    feature_id=int(feature_id),
                                    feature=feature,
                                    agent_id=agent_id,
                                    branch_name=str(branch_name),
                                    excerpt=excerpt,
                                    artifact_path=pre.get("artifact_path"),
                                    diff_fingerprint=pre.get("diff_fingerprint"),
                                )
                                released = self.port_allocator.release_ports(agent_id)
                                if released:
                                    logger.info(f"   Released ports for {agent_id}")
                                with contextlib.suppress(Exception):
                                    self.worktree_manager.delete_worktree(agent_id, force=True)
                                self.database.unregister_agent(agent_id)
                                continue
                        verification = self.gatekeeper.verify_and_merge(
                            branch_name=branch_name,
                            worktree_path=worktree_path,
                            agent_id=agent_id,
                            feature_id=int(feature_id),
                            fetch_remote=False,
                            push_remote=False,
                            allow_no_tests=allow_no_tests,
                            delete_feature_branch=True,
                        )

                        if verification.get("approved"):
                            logger.info(f"✅ Gatekeeper approved feature #{feature_id}")
                            self.database.mark_feature_passing(feature_id)
                            merge_commit = verification.get("merge_commit")
                            if merge_commit:
                                with contextlib.suppress(Exception):
                                    self.database.mark_branch_merged(branch_name, merge_commit)
                        else:
                            reason = verification.get("reason") or "Gatekeeper rejected feature"
                            logger.warning(f"❌ Gatekeeper rejected feature #{feature_id}: {reason}")
                            excerpt = self._format_gatekeeper_failure_excerpt(verification)
                            self._handle_verification_rejection(
                                feature_id=int(feature_id),
                                feature=feature,
                                agent_id=agent_id,
                                branch_name=str(branch_name),
                                excerpt=excerpt,
                                artifact_path=verification.get("artifact_path"),
                                diff_fingerprint=verification.get("diff_fingerprint"),
                            )
                    elif assigned_agent == agent_id and not passes and review_status == "READY_FOR_VERIFICATION":
                        # READY but missing branch_name is unrecoverable; requeue.
                        logger.warning(f"Feature #{feature_id} ready for verification but missing branch_name; requeuing")
                        self.database.mark_feature_failed(
                            feature_id=feature_id,
                            reason="Missing branch_name for verification",
                        )

            released = self.port_allocator.release_ports(agent_id)
            if released:
                logger.info(f"   Released ports for {agent_id}")

            # Always cleanup the agent worktree after completion.
            with contextlib.suppress(Exception):
                self.worktree_manager.delete_worktree(agent_id, force=True)

            # Mark as cleaned up to avoid repeated processing (even if allocator restarted)
            self.database.unregister_agent(agent_id)

    def _cleanup_all_agents(self):
        """Clean up all agent worktrees and release ports."""
        logger.info("🧹 Cleaning up all agents...")

        stats = self.database.get_stats()
        active_agents = stats["agents"]["active"]

        if active_agents > 0:
            logger.info(f"   {active_agents} agents still registered")

        # Release all allocated ports
        port_status = self.port_allocator.get_status()
        if port_status["active_allocations"] > 0:
            logger.info(f"   Releasing {port_status['active_allocations']} port allocations...")
            for agent_id in list(port_status["agents"]):
                self.port_allocator.release_ports(agent_id)

        # Note: In production, you might want to keep agents running
        # This is just for cleanup when stopping the orchestrator

    def _prune_worker_logs_if_needed(self) -> None:
        # Default: once per minute.
        now = datetime.now()
        if self._last_logs_prune_at and (now - self._last_logs_prune_at) < timedelta(seconds=60):
            return
        self._last_logs_prune_at = now
        try:
            result = prune_worker_logs_from_env(self.project_dir)
            if result.deleted_files:
                logger.info(
                    f"Pruned worker logs: deleted_files={result.deleted_files}, deleted_bytes={result.deleted_bytes}"
                )
            if str(os.environ.get("AUTOCODER_LOGS_PRUNE_ARTIFACTS", "")).strip().lower() in {"1", "true", "yes", "on"}:
                a = prune_gatekeeper_artifacts_from_env(self.project_dir)
                if a.deleted_files:
                    logger.info(
                        f"Pruned gatekeeper artifacts: deleted_files={a.deleted_files}, deleted_bytes={a.deleted_bytes}"
                    )
        except Exception as e:
            logger.warning(f"Failed to prune worker logs: {e}")

    def _block_unresolvable_dependencies_if_needed(self) -> None:
        # Default: once per minute.
        now = datetime.now()
        if self._last_dependency_check_at and (now - self._last_dependency_check_at) < timedelta(seconds=60):
            return
        self._last_dependency_check_at = now
        n = int(self.database.block_unresolvable_dependencies() or 0)
        if n > 0:
            logger.warning(f"Dependency health check: blocked {n} feature(s) due to unresolvable dependencies")

    @staticmethod
    def _format_gatekeeper_failure_excerpt(verification: dict) -> str:
        """
        Build a concise, actionable error excerpt for retrying agents and UI display.
        """
        def _first_text(obj: object, limit: int) -> str:
            s = str(obj or "")
            s = s.replace("\r\n", "\n").strip()
            if len(s) <= limit:
                return s
            return s[:limit].rstrip() + "\n…(truncated)…"

        reason = str(verification.get("reason") or "Gatekeeper rejected feature").strip()
        artifact_path = str(verification.get("artifact_path") or "").strip()

        lines: list[str] = [f"Gatekeeper rejected: {reason}"]
        if artifact_path:
            lines.append(f"Artifact: {artifact_path}")

        # Prefer deterministic verification command failures.
        ver = verification.get("verification")
        if isinstance(ver, dict):
            # Choose first failed command.
            for name, res in ver.items():
                if not isinstance(res, dict):
                    continue
                passed = bool(res.get("passed", False))
                allow_fail = bool(res.get("allow_fail", False))
                if passed or allow_fail:
                    continue
                cmd = res.get("command")
                exit_code = res.get("exit_code")
                out = _first_text(res.get("output", ""), 800)
                err = _first_text(res.get("errors", ""), 800)
                lines.append(f"Command [{name}]: {cmd}")
                if exit_code is not None:
                    lines.append(f"Exit code: {exit_code}")
                if err:
                    lines.append("Errors:\n" + err)
                elif out:
                    lines.append("Output:\n" + out)
                break

        # Fallback: legacy test_results shape.
        tr = verification.get("test_results")
        if isinstance(tr, dict) and not any("Command [" in ln for ln in lines):
            cmd = tr.get("command")
            exit_code = tr.get("exit_code")
            out = _first_text(tr.get("output", ""), 800)
            err = _first_text(tr.get("errors", ""), 800)
            if cmd:
                lines.append(f"Command: {cmd}")
            if exit_code is not None:
                lines.append(f"Exit code: {exit_code}")
            if err:
                lines.append("Errors:\n" + err)
            elif out:
                lines.append("Output:\n" + out)

        # Review gate context if present.
        rv = verification.get("review")
        if isinstance(rv, dict) and rv.get("approved") is False:
            lines.append(f"Review: {rv.get('reason') or 'rejected'}")

        return "\n".join([ln for ln in lines if ln.strip()])[:4000]

    def _handle_verification_rejection(
        self,
        *,
        feature_id: int,
        feature: dict,
        agent_id: str,
        branch_name: str,
        excerpt: str,
        artifact_path: object = None,
        diff_fingerprint: object = None,
    ) -> None:
        """
        Handle a deterministic verification rejection (Gatekeeper or preflight).

        If the QA sub-agent is enabled, this preserves the branch and spawns a QA fixer.
        Otherwise it records the failure and schedules a retry.
        """
        qa_spawned = False
        failure_recorded = False

        if self._qa_subagent_enabled():
            qa_max_sessions_raw = str(os.environ.get("AUTOCODER_QA_MAX_SESSIONS", "")).strip()
            try:
                qa_max_sessions = int(qa_max_sessions_raw) if qa_max_sessions_raw else 0
            except Exception:
                qa_max_sessions = 0

            if qa_max_sessions > 0:
                qa_attempt = self.database.increment_qa_attempts(int(feature_id))
                if qa_attempt is None:
                    qa_attempt = 0
                if qa_attempt > qa_max_sessions:
                    logger.info(
                        f"QA sub-agent disabled for feature #{feature_id}: qa_attempts={qa_attempt} > max={qa_max_sessions}"
                    )
                else:
                    self.database.mark_feature_failed(
                        feature_id=feature_id,
                        reason=excerpt,
                        artifact_path=str(artifact_path) if artifact_path is not None else None,
                        diff_fingerprint=str(diff_fingerprint) if diff_fingerprint is not None else None,
                        preserve_branch=True,
                        next_status="IN_PROGRESS",
                    )
                    failure_recorded = True
                    refreshed = self.database.get_feature(int(feature_id)) or {}
                    if str(refreshed.get("status") or "").upper() == "BLOCKED":
                        logger.info(f"Feature #{feature_id} is BLOCKED; skipping QA sub-agent spawn")
                    else:
                        qa_id = self._spawn_qa_subagent(
                            feature_id=int(feature_id),
                            feature_name=str(feature.get("name") or f"feature-{feature_id}"),
                            branch_name=str(branch_name),
                        )
                        qa_spawned = bool(qa_id)
                        if not qa_spawned:
                            with contextlib.suppress(Exception):
                                self.database.requeue_feature(int(feature_id), preserve_branch=True)

        if (not qa_spawned) and (not failure_recorded):
            self.database.mark_feature_failed(
                feature_id=feature_id,
                reason=excerpt,
                artifact_path=str(artifact_path) if artifact_path is not None else None,
                diff_fingerprint=str(diff_fingerprint) if diff_fingerprint is not None else None,
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        stats = self.database.get_stats()
        progress = self.database.get_progress()
        port_status = self.port_allocator.get_status()

        return {
            "project_dir": str(self.project_dir),
            "max_agents": self.max_agents,
            "model_preset": self.model_preset.value,
            "available_models": self.available_models,
            "stats": stats,
            "progress": progress,
            "active_agents": stats["agents"]["active"],
            "ports": port_status,
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def create_orchestrator(
    project_dir: str,
    max_agents: int = 3,
    model_preset: str = "balanced"
) -> Orchestrator:
    """
    Create an orchestrator instance.

    Args:
        project_dir: Path to the project
        max_agents: Maximum number of parallel agents
        model_preset: Model preset (quality, balanced, economy, cheap, experimental)

    Returns:
        Orchestrator instance
    """
    return Orchestrator(
        project_dir=project_dir,
        max_agents=max_agents,
        model_preset=model_preset
    )


async def main():
    """CLI interface for the orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Orchestrator - Run parallel autonomous coding agents"
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Path to project directory (default: current directory)"
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        help="Number of parallel agents (default: 3)"
    )
    parser.add_argument(
        "--preset",
        default="balanced",
        choices=["quality", "balanced", "economy", "cheap", "experimental"],
        help="Model preset (default: balanced)"
    )
    parser.add_argument(
        "--show-status",
        action="store_true",
        help="Show current status and exit"
    )
    parser.add_argument(
        "--show-ports",
        action="store_true",
        help="Show port allocation status and exit"
    )

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = create_orchestrator(
        project_dir=args.project_dir,
        max_agents=args.parallel,
        model_preset=args.preset
    )

    # Show port status?
    if args.show_ports:
        status = orchestrator.get_status()
        print("\n" + "=" * 60)
        print("PORT ALLOCATION STATUS")
        print("=" * 60)
        ports = status["ports"]
        print(f"\nAPI Ports:")
        print(f"  Range: {ports['api_ports']['range']}")
        print(f"  Available: {ports['api_ports']['available']}")
        print(f"  In Use: {ports['api_ports']['in_use']}")
        print(f"\nWeb Ports:")
        print(f"  Range: {ports['web_ports']['range']}")
        print(f"  Available: {ports['web_ports']['available']}")
        print(f"  In Use: {ports['web_ports']['in_use']}")
        print(f"\nActive Allocations: {ports['active_allocations']}")
        if ports["agents"]:
            print(f"Agents with ports:")
            for agent in ports["agents"]:
                p = orchestrator.port_allocator.get_agent_ports(agent)
                if not p:
                    print(f"  {agent}: (no ports found)")
                else:
                    print(f"  {agent}: API={p[0]}, WEB={p[1]}")
        print("=" * 60)
        return 0

    # Show status?
    if args.show_status:
        status = orchestrator.get_status()
        print("\n" + "=" * 60)
        print("ORCHESTRATOR STATUS")
        print("=" * 60)
        print(f"Project: {status['project_dir']}")
        print(f"Max Agents: {status['max_agents']}")
        print(f"Model Preset: {status['model_preset']}")
        print(f"Available Models: {', '.join(status['available_models'])}")
        print(f"\nProgress: {status['progress']['passing']}/{status['progress']['total']} ({status['progress']['percentage']}%)")
        print(f"Active Agents: {status['active_agents']}")
        ports = status["ports"]
        print(f"\nPort Usage:")
        print(f"  API: {ports['api_ports']['in_use']}/{ports['api_ports']['total']}")
        print(f"  Web: {ports['web_ports']['in_use']}/{ports['web_ports']['total']}")
        print("=" * 60)
        return 0

    # Run parallel agents
    print("\n" + "=" * 60)
    print("PARALLEL AGENT EXECUTION")
    print("=" * 60)
    print(f"Project: {args.project_dir}")
    print(f"Agents: {args.parallel}")
    print(f"Preset: {args.preset}")
    print("=" * 60)
    print()

    result = await orchestrator.run_parallel_agents()

    # Print summary
    print("\n" + "=" * 60)
    print("EXECUTION COMPLETE")
    print("=" * 60)
    print(f"Duration: {result['duration_seconds']:.1f} seconds")
    print(f"Features Completed: {result['features_completed']}")
    print(f"Features Failed: {result['features_failed']}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
