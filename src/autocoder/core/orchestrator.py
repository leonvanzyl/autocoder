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
from .logs import prune_worker_logs_from_env

# Agent imports (for initializer)
from autocoder.agent import run_autonomous_agent

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
        self.model_settings = ModelSettings.load()
        self.worktree_manager = WorktreeManager(str(self.project_dir))
        self.database = get_database(str(self.project_dir))
        self.gatekeeper = Gatekeeper(str(self.project_dir))

        # Initialize port allocator
        self.port_allocator = PortAllocator()
        self._bootstrap_ports_from_database()
        port_status = self.port_allocator.get_status()
        self._last_logs_prune_at: Optional[datetime] = None

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
            # Select model for initializer (use best available model)
            model = self.available_models[0] if self.available_models else "opus"

            logger.info(f"   Model: {model.upper()}")
            logger.info(f"   Location: Main branch (no worktree needed)")

            # Run initializer with max_iterations=1 (only initializer session)
            await run_autonomous_agent(
                project_dir=self.project_dir,
                model=model,
                max_iterations=1,  # Only run initializer
                yolo_mode=False     # Full testing for initializer
            )

            # Verify features were created
            stats = self.database.get_stats()
            total_features = stats["features"]["total"]

            if total_features == 0:
                logger.error("   ❌ Initializer completed but no features were created!")
                return False

            logger.info(f"   ✅ Initializer completed successfully!")
            logger.info(f"   📊 Created {total_features} features")
            return True

        except Exception as e:
            logger.error(f"   ❌ Initializer failed: {e}")
            return False

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

        try:
            # Check if we need to run initializer first
            stats = self.database.get_stats()
            total_features = stats["features"]["total"]

            if total_features == 0:
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
                    logger.info("✅ All features complete!")
                    break

                # Check for crashed agents and recover
                self._recover_crashed_agents()

                # Release ports from completed agents
                self._recover_completed_agents()

                # Periodic log maintenance
                self._prune_worker_logs_if_needed()

                # Get count of active agents
                active_count = stats["agents"]["active"]
                available_slots = self.max_agents - active_count

                if available_slots > 0:
                    # Spawn more agents
                    self._spawn_agents(available_slots)

                # Wait a bit before checking again
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
        logger.info(f"🤖 Spawning {count} agent(s)...")

        spawned_agents = []

        # Each spawned agent gets its own unique agent_id.
        agent_id_prefix = f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        for i in range(count):
            agent_id = f"{agent_id_prefix}-{i}"

            claimed_feature = self.database.claim_next_pending_feature(agent_id, branch_prefix="feat")
            if not claimed_feature:
                logger.info("No pending features to claim")
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

            # Spawn actual agent process
            worker_script = Path(__file__).parent.parent / "agent_worker.py"
            cmd = [
                sys.executable,
                str(worker_script),
                "--project-dir", str(self.project_dir),
                "--agent-id", agent_id,
                "--feature-id", str(feature_id),
                "--worktree-path", worktree_info["worktree_path"],
                "--model", model,
                "--max-iterations", "5",  # Each worker gets 5 iterations
                "--api-port", str(api_port),  # Pass API port via CLI argument
                "--web-port", str(web_port),  # Pass web port via CLI argument
                "--yolo"  # Use YOLO mode for parallel execution (speed)
            ]

            # Prepare environment with port allocations (redundant with CLI args)
            env = os.environ.copy()
            env["AUTOCODER_API_PORT"] = str(api_port)
            env["AUTOCODER_WEB_PORT"] = str(web_port)
            # Compatibility for common dev servers that read generic port env vars.
            env["API_PORT"] = str(api_port)
            env["WEB_PORT"] = str(web_port)
            env["PORT"] = str(api_port)
            env["VITE_PORT"] = str(web_port)
            # Prevent workers from self-attesting `passes=True`; require Gatekeeper verification.
            env["AUTOCODER_REQUIRE_GATEKEEPER"] = "1"

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
                agent_id=agent_id
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
                    reason=verification["reason"]
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
            model_info = self.kb.get_best_model(category)
            if model_info:
                recommended = model_info.get("model_used")
                if recommended and recommended in self.available_models:
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
                        verification = self.gatekeeper.verify_and_merge(
                            branch_name=branch_name,
                            worktree_path=worktree_path,
                            agent_id=agent_id,
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
                            self.database.mark_feature_failed(feature_id=feature_id, reason=reason)
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
        except Exception as e:
            logger.warning(f"Failed to prune worker logs: {e}")

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
