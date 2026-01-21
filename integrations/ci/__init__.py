"""
CI/CD Integration Module
========================

Generate CI/CD configuration based on detected tech stack.

Supported providers:
- GitHub Actions
- GitLab CI (planned)

Features:
- Auto-detect tech stack and generate appropriate workflows
- Lint, type-check, test, build, deploy stages
- Environment management (staging, production)
"""

from .github_actions import (
    generate_github_workflow,
    generate_all_workflows,
    GitHubWorkflow,
    WorkflowTrigger,
)

__all__ = [
    "generate_github_workflow",
    "generate_all_workflows",
    "GitHubWorkflow",
    "WorkflowTrigger",
]


def generate_ci_config(project_dir, provider: str = "github") -> dict:
    """
    Generate CI configuration based on detected tech stack.

    Args:
        project_dir: Project directory
        provider: CI provider ("github" or "gitlab")

    Returns:
        Dict with generated configuration and file paths
    """
    from pathlib import Path

    project_dir = Path(project_dir)

    if provider == "github":
        workflows = generate_all_workflows(project_dir)
        return {
            "provider": "github",
            "workflows": workflows,
            "output_dir": str(project_dir / ".github" / "workflows"),
        }

    elif provider == "gitlab":
        # GitLab CI support planned
        return {
            "provider": "gitlab",
            "error": "GitLab CI not yet implemented",
        }

    else:
        return {
            "provider": provider,
            "error": f"Unknown provider: {provider}",
        }
