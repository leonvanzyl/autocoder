"""
Agent Package

Agent implementation and session management.
"""

from .agent import run_autonomous_agent
from .client import ClaudeSDKClient
from .prompts import load_prompt, load_project_prompt
from .progress import get_database, ProjectProgress
from .registry import get_project_path, register_project, unregister_project
from .security import ALLOWED_COMMANDS, validate_command

__all__ = [
    "run_autonomous_agent",
    "ClaudeSDKClient",
    "load_prompt",
    "load_project_prompt",
    "get_database",
    "ProjectProgress",
    "get_project_path",
    "register_project",
    "unregister_project",
    "ALLOWED_COMMANDS",
    "validate_command",
]
