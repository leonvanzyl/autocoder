"""
Core system components for AutoCoder.

This module contains the core parallel agent coordination system:
- Orchestrator: Coordinates multiple parallel agents
- Gatekeeper: Verifies and merges code changes
- WorktreeManager: Manages git worktrees for isolation
- KnowledgeBase: Learns from patterns across iterations
- ModelSettings: Model selection and configuration
- TestFrameworkDetector: Auto-detects testing frameworks
- Database: SQLite database wrapper
"""

from autocoder.core.orchestrator import Orchestrator, create_orchestrator
from autocoder.core.gatekeeper import Gatekeeper
from autocoder.core.worktree_manager import WorktreeManager
from autocoder.core.knowledge_base import KnowledgeBase, get_knowledge_base
from autocoder.core.model_settings import ModelSettings, ModelPreset, get_full_model_id
from autocoder.core.test_framework_detector import TestFrameworkDetector
from autocoder.core.database import Database, get_database

__all__ = [
    "Orchestrator",
    "create_orchestrator",
    "Gatekeeper",
    "WorktreeManager",
    "KnowledgeBase",
    "get_knowledge_base",
    "ModelSettings",
    "ModelPreset",
    "get_full_model_id",
    "TestFrameworkDetector",
    "Database",
    "get_database",
]
