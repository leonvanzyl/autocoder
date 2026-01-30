"""
API Routers
===========

FastAPI routers for different API endpoints.
"""

from .agent import router as agent_router
from .assistant_chat import router as assistant_chat_router
from .deploy import router as deploy_router
from .devserver import router as devserver_router
from .expand_project import router as expand_project_router
from .features import router as features_router
from .filesystem import router as filesystem_router
from .git import router as git_router
from .models import router as models_router
from .pr import router as pr_router
from .projects import router as projects_router
from .scheduler import router as scheduler_router
from .schedules import router as schedules_router
from .settings import router as settings_router
from .settings_v2 import router as settings_v2_router
from .spec_creation import router as spec_creation_router
from .terminal import router as terminal_router
from .usage import router as usage_router
from .version import router as version_router

__all__ = [
    "projects_router",
    "features_router",
    "agent_router",
    "schedules_router",
    "scheduler_router",
    "devserver_router",
    "spec_creation_router",
    "expand_project_router",
    "filesystem_router",
    "assistant_chat_router",
    "settings_router",
    "settings_v2_router",
    "terminal_router",
    "version_router",
    "models_router",
    "git_router",
    "usage_router",
    "pr_router",
    "deploy_router",
]
