"""
Agent implementation for AutoCoder.

This module contains the agent session management and SDK client:
- agent: Main agent session loop
- client: Claude SDK client configuration with security hooks
- prompts: Prompt template loading
- progress: Progress tracking
- registry: Project name → path mapping
- security: Command validation whitelist
"""

from autocoder.agent.agent import run_autonomous_agent
from autocoder.agent.client import ClaudeSDKClient
from autocoder.agent.prompts import (
    scaffold_project_prompts,
    has_project_prompts,
    get_project_prompts_dir,
)
from autocoder.agent.registry import (
    register_project,
    get_project_path,
    list_registered_projects,
)
from autocoder.agent.security import ALLOWED_COMMANDS

__all__ = [
    "run_autonomous_agent",
    "ClaudeSDKClient",
    "scaffold_project_prompts",
    "has_project_prompts",
    "get_project_prompts_dir",
    "register_project",
    "get_project_path",
    "list_registered_projects",
    "ALLOWED_COMMANDS",
]
