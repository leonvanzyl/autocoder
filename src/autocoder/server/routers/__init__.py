"""
API Routers
===========

FastAPI routers for different API endpoints.
"""

from .projects import router as projects_router
from .features import router as features_router
from .agent import router as agent_router
from .spec_creation import router as spec_creation_router
from .filesystem import router as filesystem_router
from .assistant_chat import router as assistant_chat_router
from .model_settings import router as model_settings_router
from .logs import router as logs_router
from .parallel import router as parallel_router
from .settings import router as settings_router
from .generate import router as generate_router
from .project_config import router as project_config_router

__all__ = [
    "projects_router",
    "features_router",
    "agent_router",
    "spec_creation_router",
    "filesystem_router",
    "assistant_chat_router",
    "model_settings_router",
    "logs_router",
    "parallel_router",
    "settings_router",
    "generate_router",
    "project_config_router",
]
