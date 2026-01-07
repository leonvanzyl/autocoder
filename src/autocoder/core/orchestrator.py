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
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Direct imports (system code = fast!)
from .knowledge_base import KnowledgeBase, get_knowledge_base
from .model_settings import ModelSettings, ModelPreset, get_full_model_id
from .worktree_manager import WorktreeManager
from .database import Database, get_database
from .gatekeeper import Gatekeeper

# MCP server imports (for agents)
from autocoder.tools import test_mcp, knowledge_mcp, model_settings_mcp, feature_mcp

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Orchestrator manages parallel autonomous coding agents.

    Uses direct imports for system logic and provides MCP tools to agents.
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

        # Load model preset
        self.model_preset = ModelPreset(model_preset)
        self.available_models = self.model_settings.get_available_models(self.model_preset)

        logger.info(f"Orchestrator initialized:")
        logger.info(f"  Project: {self.project_dir}")
        logger.info(f"  Max agents: {max_agents}")
        logger.info(f"  Model preset: {model_preset}")
        logger.info(f"  Available models: {self.available_models}")

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
            while True:
                # Check if there are pending features
                stats = self.database.get_stats()

                if stats["features"]["pending"] == 0 and stats["features"]["in_progress"] == 0:
                    logger.info("✅ All features complete!")
                    break

                # Check for crashed agents and recover
                self._recover_crashed_agents()

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

        # Claim features atomically
        agent_id = f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        branch_names = []

        # Claim batch of features
        feature_ids = self.database.claim_batch(
            count=count,
            agent_id=agent_id,
            branch_names=branch_names
        )

        if not feature_ids:
            logger.info("No pending features to claim")
            return []

        for i, feature_id in enumerate(feature_ids):
            # Get feature details
            feature = self.database.get_feature(feature_id)

            # Select model for this feature
            model = self._select_model_for_feature(feature)

            # Create worktree
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            branch_name = f"feat/{feature_id}-{timestamp}"

            worktree_info = self.worktree_manager.create_worktree(
                agent_id=f"{agent_id}-{i}",
                feature_id=feature_id,
                feature_name=feature["name"]
            )

            # Register agent in database
            self.database.register_agent(
                agent_id=f"{agent_id}-{i}",
                worktree_path=worktree_info["worktree_path"],
                feature_id=feature_id
            )

            # Run feature lifecycle (async)
            # Note: In real implementation, this would spawn actual agent process
            # For now, we'll mark as completed for testing
            logger.info(f"🤖 {agent_id}-{i}: Started feature #{feature_id} - {feature['name']}")
            logger.info(f"   Model: {model.upper()}")
            logger.info(f"   Worktree: {worktree_info['worktree_path']}")

            spawned_agents.append(f"{agent_id}-{i}")

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
        - The process is no longer running
        """
        stale_agents = self.database.get_stale_agents(timeout_minutes=10)

        for agent in stale_agents:
            logger.warning(f"⚠️ Detected stale agent: {agent['agent_id']}")

            # Check if process is still running
            if agent.get("pid"):
                try:
                    os.kill(agent["pid"], 0)  # Check if process exists
                except OSError:
                    # Process is dead
                    logger.warning(f"   Process {agent['pid']} is dead")

                    # Mark as crashed
                    self.database.mark_agent_crashed(agent["agent_id"])

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
                            agent["agent_id"],
                            force=True
                        )

    def _cleanup_all_agents(self):
        """Clean up all agent worktrees."""
        logger.info("🧹 Cleaning up all agents...")

        stats = self.database.get_stats()
        active_agents = stats["agents"]["active"]

        if active_agents > 0:
            logger.info(f"   {active_agents} agents still registered")

        # Note: In production, you might want to keep agents running
        # This is just for cleanup when stopping the orchestrator

    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        stats = self.database.get_stats()
        progress = self.database.get_progress()

        return {
            "project_dir": str(self.project_dir),
            "max_agents": self.max_agents,
            "model_preset": self.model_preset.value,
            "available_models": self.available_models,
            "stats": stats,
            "progress": progress,
            "active_agents": stats["agents"]["active"],
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

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = create_orchestrator(
        project_dir=args.project_dir,
        max_agents=args.parallel,
        model_preset=args.preset
    )

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
