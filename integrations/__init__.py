"""
Integrations Package
====================

External integrations for Autocoder including CI/CD, deployment, etc.
"""

from .ci import generate_ci_config, generate_github_workflow

__all__ = [
    "generate_ci_config",
    "generate_github_workflow",
]
