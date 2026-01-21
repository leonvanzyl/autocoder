"""
API Routers
===========

FastAPI routers for different API endpoints.
"""

from .agent import router as agent_router
from .assistant_chat import router as assistant_chat_router
from .devserver import router as devserver_router
from .expand_project import router as expand_project_router
from .features import router as features_router
from .filesystem import router as filesystem_router
from .projects import router as projects_router
from .settings import router as settings_router
from .spec_creation import router as spec_creation_router
from .terminal import router as terminal_router
from .import_project import router as import_project_router
from .logs import router as logs_router
from .security import router as security_router
from .git_workflow import router as git_workflow_router
from .cicd import router as cicd_router
from .templates import router as templates_router
from .review import router as review_router
from .documentation import router as documentation_router
from .design_tokens import router as design_tokens_router
from .visual_regression import router as visual_regression_router

__all__ = [
    "projects_router",
    "features_router",
    "agent_router",
    "devserver_router",
    "spec_creation_router",
    "expand_project_router",
    "filesystem_router",
    "assistant_chat_router",
    "settings_router",
    "terminal_router",
    "import_project_router",
    "logs_router",
    "security_router",
    "git_workflow_router",
    "cicd_router",
    "templates_router",
    "review_router",
    "documentation_router",
    "design_tokens_router",
    "visual_regression_router",
]
