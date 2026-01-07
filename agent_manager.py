#!/usr/bin/env python3
"""
Parallel Agent Manager
======================

Orchestrates multiple autonomous agents working on features in parallel.

Key Features:
- Atomic feature claiming (no race conditions)
- Configurable number of parallel agents (1-5)
- Smart model selection per feature
- AI-based dependency detection
- Progress tracking and status updates
- Graceful shutdown and error recovery

Usage:
    # Start with 3 parallel agents (default)
    python agent_manager.py --project-dir ./my-project --parallel 3

    # Use specific model preset
    python agent_manager.py --project-dir ./my-project --parallel 3 --preset balanced

    # Custom model selection
    python agent_manager.py --project-dir ./my-project --parallel 3 --models opus,haiku

    # Maximum parallelism
    python agent_manager.py --project-dir ./my-project --parallel 5
"""

import argparse
import asyncio
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from model_settings import ModelSettings, parse_models_arg, get_preset_info, get_full_model_id
from api.database import Feature, create_database
from prompts import get_coding_prompt
from client import create_client
from agent import run_agent_session


class AgentStatus:
    """Track status of a single agent"""

    def __init__(self, agent_id: str, feature_id: int, feature_name: str):
        self.agent_id = agent_id
        self.feature_id = feature_id
        self.feature_name = feature_name
        self.started_at = datetime.utcnow()
        self.status = "running"  # running, completed, failed
        self.model_used: Optional[str] = None
        self.logs: List[str] = []
        self.progress = 0

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "started_at": self.started_at.isoformat(),
            "status": self.status,
            "model_used": self.model_used,
            "progress": self.progress
        }


class AgentManager:
    """Manages multiple agents working on features in parallel"""

    def __init__(
        self,
        project_dir: str,
        max_agents: int = 3,
        model_settings: Optional[ModelSettings] = None
    ):
        self.project_dir = Path(project_dir).resolve()
        self.max_agents = max_agents
        self.model_settings = model_settings or ModelSettings()

        self.running_agents: Dict[str, AgentStatus] = {}
        self.completed_count = 0
        self.failed_count = 0
        self.start_time = datetime.utcnow()

        # Database path
        self.db_path = self.project_dir / "features.db"

        if not self.db_path.exists():
            raise FileNotFoundError(f"Features database not found: {self.db_path}")

        # Initialize database connection
        _, self._session_maker = create_database(self.project_dir)

        print(f"🚀 Agent Manager initialized")
        print(f"   Project: {self.project_dir}")
        print(f"   Max Agents: {max_agents}")
        print(f"   Model Preset: {self.model_settings.preset}")
        print(f"   Available Models: {', '.join(self.model_settings.available_models)}")
        print()

    @contextmanager
    def get_db(self):
        """Get database session context manager"""
        session = self._session_maker()
        try:
            yield session
        finally:
            session.close()

    async def run_parallel(self):
        """Main execution loop - run features in parallel until complete"""
        print("🎯 Starting parallel feature development...\n")

        try:
            while True:
                # Check if we have pending features
                pending_count = self._get_pending_count()

                if pending_count == 0 and len(self.running_agents) == 0:
                    print("\n✅ All features completed!")
                    self._print_summary()
                    break

                # Calculate available agent slots
                available_slots = self.max_agents - len(self.running_agents)

                if available_slots > 0 and pending_count > 0:
                    # Claim batch of features
                    to_claim = min(available_slots, pending_count)
                    features = self._claim_features(to_claim)

                    if features:
                        # Spawn agents for each feature
                        for feature in features:
                            await self._spawn_agent(feature)
                    else:
                        print(f"⏳ Waiting for available features...")
                        await asyncio.sleep(2)

                # Check for completed agents
                await self._cleanup_completed_agents()

                # Small delay before next iteration
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user. Shutting down gracefully...")
            await self._shutdown_agents()
            self._print_summary()

    async def _spawn_agent(self, feature: dict):
        """Spawn a new agent to work on a feature"""
        agent_id = f"agent-{len(self.running_agents) + 1}"

        # Select model for this feature
        model = self.model_settings.select_model(feature)

        # Create agent status tracker
        status = AgentStatus(agent_id, feature['id'], feature['name'])
        status.model_used = model
        self.running_agents[agent_id] = status

        print(f"🤖 {agent_id}: Started feature #{feature['id']} - {feature['name']}")
        print(f"   Category: {feature.get('category', 'N/A')}")
        print(f"   Model: {model.upper()}")
        print()

        # Start agent in background task
        asyncio.create_task(
            self._run_feature_agent(agent_id, feature, model)
        )

    async def _run_feature_agent(self, agent_id: str, feature: dict, model: str):
        """Run a single agent for one feature"""
        status = self.running_agents[agent_id]

        try:
            print(f"🔧 {agent_id}: Starting agent session...")
            print(f"   Feature: {feature['name']}")
            print(f"   Description: {feature['description'][:100]}...")
            print()

            # Convert short model name to full model ID
            full_model_id = get_full_model_id(model)

            # Create client with selected model
            client = create_client(self.project_dir, full_model_id, yolo_mode=False)

            # Build prompt for this specific feature
            feature_prompt = self._build_feature_prompt(feature)

            # Run the agent session
            print(f"🚀 {agent_id}: Sending prompt to Claude...")
            session_status, response = await run_agent_session(
                client=client,
                message=feature_prompt,
                project_dir=self.project_dir
            )

            # Handle session result
            if session_status == "continue":
                # Agent completed successfully
                status.status = "completed"
                status.progress = 100

                # Release feature in database as passing
                self._release_feature(
                    feature['id'],
                    "passing",
                    f"Completed by {agent_id} using {model}"
                )

                print(f"✅ {agent_id}: Feature #{feature['id']} completed!")
                print()

            elif session_status == "error":
                # Agent encountered an error
                status.status = "failed"
                error_msg = response[:500] if response else "Unknown error"

                print(f"❌ {agent_id}: Feature #{feature['id']} failed: {error_msg}")
                print()

                # Release feature as failed (will be retried)
                self._release_feature(feature['id'], "failed", error_msg)

            else:
                # Unexpected status
                status.status = "failed"
                print(f"❌ {agent_id}: Unexpected status '{session_status}' for feature #{feature['id']}")
                print()

                self._release_feature(feature['id'], "failed", f"Unexpected status: {session_status}")

        except Exception as e:
            status.status = "failed"
            print(f"❌ {agent_id}: Feature #{feature['id']} crashed: {str(e)}")
            import traceback
            traceback.print_exc()
            print()

            # Release feature as failed (will be retried)
            self._release_feature(feature['id'], "failed", f"Crash: {str(e)}")

    def _build_feature_prompt(self, feature: dict) -> str:
        """Build a focused prompt for working on a single feature

        Args:
            feature: Feature dict with keys: id, name, description, category, priority

        Returns:
            Prompt string for the agent
        """
        # Get the base coding prompt
        base_prompt = get_coding_prompt(self.project_dir)

        # Add feature-specific context
        feature_prompt = f"""

---
FEATURE FOCUS
---

You are working on a SINGLE feature right now. Focus exclusively on this:

Feature #{feature['id']}: {feature['name']}
Category: {feature.get('category', 'N/A')}
Priority: {feature.get('priority', 'N/A')}

Description:
{feature['description']}

INSTRUCTIONS:
1. Work ONLY on this feature. Do NOT work on other features.
2. Use the `feature_get_for_regression` tool to get passing features to test.
3. Use the `feature_mark_passing` tool to mark this feature complete when done.
4. If you encounter blocking issues, use `feature_skip` to move to the next feature.
5. Test your changes thoroughly before marking the feature as passing.

Get started on this feature now.
"""

        return base_prompt + feature_prompt

    async def _cleanup_completed_agents(self):
        """Remove completed agents from tracking"""
        completed = []

        for agent_id, status in self.running_agents.items():
            if status.status in ["completed", "failed"]:
                completed.append(agent_id)

                if status.status == "completed":
                    self.completed_count += 1
                else:
                    self.failed_count += 1

        for agent_id in completed:
            status = self.running_agents[agent_id]
            duration = (datetime.utcnow() - status.started_at).total_seconds()
            print(f"🧹 {agent_id}: Removed from tracking (duration: {duration:.1f}s)")
            del self.running_agents[agent_id]

    async def _shutdown_agents(self):
        """Gracefully shutdown all running agents"""
        if not self.running_agents:
            return

        print(f"\n🛑 Stopping {len(self.running_agents)} running agents...")

        # Cancel all agent tasks
        for agent_id, status in self.running_agents.items():
            status.status = "cancelled"

        # Wait for cleanup
        await asyncio.sleep(1)

    def _get_pending_count(self) -> int:
        """Get count of pending features"""
        try:
            with self.get_db() as db:
                return db.query(Feature)\
                    .filter(Feature.passes == False)\
                    .filter(Feature.in_progress == False)\
                    .count()
        except Exception as e:
            print(f"❌ Error getting pending count: {e}")
            return 0

    def _claim_features(self, count: int) -> List[dict]:
        """Claim features from database (with atomic locking)"""
        try:
            with self.get_db() as db:
                # Use with_for_update() for atomic claiming
                features = db.query(Feature)\
                    .filter(Feature.passes == False)\
                    .filter(Feature.in_progress == False)\
                    .order_by(Feature.priority.asc(), Feature.id.asc())\
                    .limit(count)\
                    .with_for_update()\
                    .all()

                # Mark as in_progress
                for feature in features:
                    feature.in_progress = True

                db.commit()

                return [
                    {
                        "id": f.id,
                        "name": f.name,
                        "description": f.description,
                        "category": f.category,
                        "priority": f.priority
                    }
                    for f in features
                ]

        except Exception as e:
            print(f"❌ Error claiming features: {e}")
            return []

    def _release_feature(self, feature_id: int, status: str, notes: str = ""):
        """Release a claimed feature with completion status"""
        try:
            with self.get_db() as db:
                feature = db.query(Feature).filter(Feature.id == feature_id).first()

                if feature:
                    if status == "passing":
                        feature.passes = True
                        feature.in_progress = False
                    else:
                        feature.in_progress = False  # Return to queue

                    # Note: We could append notes to description, but that might clutter it
                    # For now, just print the notes
                    if notes:
                        print(f"   Note: {notes}")

                    db.commit()

        except Exception as e:
            print(f"❌ Error releasing feature {feature_id}: {e}")

    def _print_summary(self):
        """Print execution summary"""
        duration = (datetime.utcnow() - self.start_time).total_seconds()

        print("\n" + "="*60)
        print("📊 EXECUTION SUMMARY")
        print("="*60)
        print(f"✅ Completed: {self.completed_count}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"⏱️  Total Time: {duration:.1f}s")
        print(f"🤖 Max Parallel Agents: {self.max_agents}")
        print(f"🧠 Model Preset: {self.model_settings.preset}")
        print("="*60)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Run multiple autonomous agents in parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with 3 parallel agents (default)
  python agent_manager.py --project-dir ./my-project

  # Use 5 parallel agents
  python agent_manager.py --project-dir ./my-project --parallel 5

  # Use specific model preset
  python agent_manager.py --project-dir ./my-project --preset balanced

  # Custom model selection
  python agent_manager.py --project-dir ./my-project --models opus,haiku

  # Show available presets
  python agent_manager.py --show-presets

Model Presets:
  quality      - Opus only (maximum quality)
  balanced     - Opus + Haiku (recommended for Pro)
  economy      - Opus + Sonnet + Haiku
  cheap        - Sonnet + Haiku (no Opus)
  experimental - All models with AI selection
        """
    )

    parser.add_argument(
        "--project-dir",
        help="Path to project directory"
    )

    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        choices=range(1, 6),
        metavar="1-5",
        help="Number of parallel agents (default: 3)"
    )

    parser.add_argument(
        "--preset",
        choices=["quality", "balanced", "economy", "cheap", "experimental"],
        default="balanced",
        help="Model selection preset (default: balanced)"
    )

    parser.add_argument(
        "--models",
        type=str,
        help="Comma-separated list of models (e.g., opus,haiku) - overrides preset"
    )

    parser.add_argument(
        "--show-presets",
        action="store_true",
        help="Show available presets and exit"
    )

    args = parser.parse_args()

    # Show presets if requested
    if args.show_presets:
        print("\n📦 Available Model Selection Presets\n")
        print("="*70)

        for preset, info in get_preset_info().items():
            print(f"\n📌 {preset.upper()}")
            print(f"   Name: {info['name']}")
            print(f"   Models: {', '.join(info['models'])}")
            print(f"   Best For: {info['best_for']}")
            print(f"   {info['description']}")

        print("\n" + "="*70)
        print("\nUsage:")
        print("  python agent_manager.py --project-dir ./my-app --preset balanced")
        print("  python agent_manager.py --project-dir ./my-app --models opus,haiku")
        return

    # Validate required arguments
    if not args.project_dir:
        parser.error("--project-dir is required (unless using --show-presets)")

    # Load model settings
    settings = ModelSettings.load()

    # Apply model configuration
    if args.models:
        # Custom model selection
        models = parse_models_arg(args.models)
        settings.set_custom_models(models)
        print(f"🎛️  Custom model configuration: {', '.join(models)}")
    else:
        # Use preset
        settings.set_preset(args.preset)
        print(f"📦 Using preset: {args.preset}")

    # Validate project directory
    project_dir = Path(args.project_dir).resolve()
    if not project_dir.exists():
        print(f"❌ Error: Project directory does not exist: {project_dir}")
        sys.exit(1)

    # Create and run agent manager
    try:
        manager = AgentManager(
            project_dir=str(project_dir),
            max_agents=args.parallel,
            model_settings=settings
        )

        asyncio.run(manager.run_parallel())

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
