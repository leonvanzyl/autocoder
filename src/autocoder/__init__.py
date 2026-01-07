"""
AutoCoder - Autonomous Coding Agent System

A powerful autonomous coding system with parallel agents, web UI, and MCP tools.
"""

__version__ = "0.1.0"

# Core system exports
from autocoder.core.orchestrator import Orchestrator, create_orchestrator
from autocoder.core.gatekeeper import Gatekeeper
from autocoder.core.worktree_manager import WorktreeManager
from autocoder.core.knowledge_base import KnowledgeBase, get_knowledge_base
from autocoder.core.model_settings import ModelSettings, ModelPreset, get_full_model_id
from autocoder.core.test_framework_detector import TestFrameworkDetector
from autocoder.core.database import Database, get_database

# Agent exports
from autocoder.agent.agent import run_autonomous_agent
from autocoder.agent.client import ClaudeSDKClient

__all__ = [
    # Core system
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
    # Agent
    "run_autonomous_agent",
    "ClaudeSDKClient",
]
