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
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta

# Direct imports (system code = fast!)
from .knowledge_base import KnowledgeBase, get_knowledge_base
from .model_settings import ModelSettings, ModelPreset, get_full_model_id
from .worktree_manager import WorktreeManager
from .database import Database, get_database
from .gatekeeper import Gatekeeper

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

    # Port ranges
    API_PORT_RANGE = (5000, 5100)  # 100 ports for backend APIs
    WEB_PORT_RANGE = (5173, 5273)  # 100 ports for frontend dev servers

    def __init__(self):
        """Initialize the port allocator with empty pools."""
        self._lock = threading.Lock()

        # Track available and in-use ports
        self._available_api_ports: Set[int] = set(
            range(self.API_PORT_RANGE[0], self.API_PORT_RANGE[1])
        )
        self._available_web_ports: Set[int] = set(
            range(self.WEB_PORT_RANGE[0], self.WEB_PORT_RANGE[1])
        )

        self._in_use_api_ports: Set[int] = set()
        self._in_use_web_ports: Set[int] = set()

        # Track which agent owns which ports
        self._agent_ports: Dict[str, Tuple[int, int]] = {}

        logger.info(f"PortAllocator initialized:")
        logger.info(f"  API ports: {self.API_PORT_RANGE[0]}-{self.API_PORT_RANGE[1]} ({len(self._available_api_ports)} available)")
        logger.info(f"  Web ports: {self.WEB_PORT_RANGE[0]}-{self.WEB_PORT_RANGE[1]} ({len(self._available_web_ports)} available)")

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

            # Allocate next available port from each pool
            api_port = min(self._available_api_ports)
            web_port = min(self._available_web_ports)

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
            self._available_api_ports.add(api_port)
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
                    "total": self.API_PORT_RANGE[1] - self.API_PORT_RANGE[0],
                    "range": f"{self.API_PORT_RANGE[0]}-{self.API_PORT_RANGE[1]}"
                },
                "web_ports": {
                    "available": len(self._available_web_ports),
                    "in_use": len(self._in_use_web_ports),
                    "total": self.WEB_PORT_RANGE[1] - self.WEB_PORT_RANGE[0],
                    "range": f"{self.WEB_PORT_RANGE[0]}-{self.WEB_PORT_RANGE[1]}"
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
        self.model_settings = ModelSettings()
        self.worktree_manager = WorktreeManager(str(self.project_dir))
        self.database = get_database(str(self.project_dir))
        self.gatekeeper = Gatekeeper(str(self.project_dir))

        # Initialize port allocator
        self.port_allocator = PortAllocator()
        port_status = self.port_allocator.get_status()

        # Load model preset
        self.model_preset = ModelPreset(model_preset)
        self.model_settings.preset = model_preset
        self.available_models = self.model_settings.available_models

        logger.info(f"Orchestrator initialized:")
        logger.info(f"  Project: {self.project_dir}")
        logger.info(f"  Max agents: {max_agents}")
        logger.info(f"  Model preset: {model_preset}")
        logger.info(f"  Available models: {self.available_models}")
        logger.info(f"  Port pools:")
        logger.info(f"    API: {port_status['api_ports']['range']} ({port_status['api_ports']['available']} available)")
        logger.info(f"    Web: {port_status['web_ports']['range']} ({port_status['web_ports']['available']} available)")

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

            # Find and claim a pending feature (retry a few times in case of races)
            claimed_feature = None
            claimed_branch = None
            for _ in range(5):
                feature = self.database.get_next_pending_feature()
                if not feature:
                    break

                feature_id = feature["id"]
                branch_name = f"feat/feature-{feature_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                if self.database.claim_feature(feature_id, agent_id, branch_name):
                    claimed_feature = feature
                    claimed_branch = branch_name
                    break

            if not claimed_feature:
                logger.info("No pending features to claim")
                break

            feature_id = claimed_feature["id"]

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

            logger.info(f"🚀 Launching {agent_id}:")
            logger.info(f"   Feature: #{feature_id} - {claimed_feature['name']}")
            logger.info(f"   Model: {model.upper()}")
            logger.info(f"   Worktree: {worktree_info['worktree_path']}")
            logger.info(f"   Ports: API={api_port}, WEB={web_port}")
            logger.info(f"   Command: {' '.join(cmd[:3])}...")

            try:
                # Spawn the process (fire and forget - monitored via DB)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,  # Pass environment with port allocations
                    # Don't wait - let it run in background
                )

                pid = process.pid
                logger.info(f"   PID: {pid}")

                # Register agent in database with PID and ports
                self.database.register_agent(
                    agent_id=agent_id,
                    worktree_path=worktree_info["worktree_path"],
                    feature_id=feature_id,
                    pid=pid,
                    api_port=api_port,
                    web_port=web_port
                )

                spawned_agents.append(agent_id)

            except Exception as e:
                logger.error(f"   ❌ Failed to spawn agent: {e}")
                # Cleanup on failure
                self.database.mark_feature_failed(feature_id=feature_id, reason="Agent spawn failed")
                self.worktree_manager.delete_worktree(agent_id, force=True)
                self.port_allocator.release_ports(agent_id)
                continue

        return spawned_agents

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
        Release ports from completed agents.

        This is called periodically to clean up port allocations from agents
        that completed successfully (not crashed).
        """
        completed_agents = self.database.get_completed_agents()

        for agent in completed_agents:
            logger.info(f"Releasing ports from completed agent: {agent['agent_id']}")

            if self.port_allocator.release_ports(agent['agent_id']):
                logger.info(f"   Released ports for {agent['agent_id']}")

                # Mark as cleaned up to avoid repeated releases
                self.database.unregister_agent(agent['agent_id'])

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
                p = self.port_allocator.get_agent_ports(agent)
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
