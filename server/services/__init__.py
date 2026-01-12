"""
Backend Services
================

Business logic and process management services.
"""

from .process_manager import AgentProcessManager
from .project_config import (
    clear_dev_command,
    detect_project_type,
    get_default_dev_command,
    get_dev_command,
    get_project_config,
    set_dev_command,
)
from .terminal_manager import (
    TerminalSession,
    cleanup_all_terminals,
    get_terminal_session,
    remove_terminal_session,
)

__all__ = [
    "AgentProcessManager",
    "TerminalSession",
    "cleanup_all_terminals",
    "clear_dev_command",
    "detect_project_type",
    "get_default_dev_command",
    "get_dev_command",
    "get_project_config",
    "get_terminal_session",
    "remove_terminal_session",
    "set_dev_command",
]
