"""
GitHub Actions Workflow Generator
=================================

Generate GitHub Actions workflows based on detected tech stack.

Workflow types:
- CI: Lint, type-check, test on push/PR
- Deploy: Build and deploy on merge to main
- Security: Dependency audit and code scanning
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

import yaml


class WorkflowTrigger(str, Enum):
    """Workflow trigger types."""

    PUSH = "push"
    PULL_REQUEST = "pull_request"
    WORKFLOW_DISPATCH = "workflow_dispatch"
    SCHEDULE = "schedule"


@dataclass
class WorkflowJob:
    """A job in a GitHub Actions workflow."""

    name: str
    runs_on: str = "ubuntu-latest"
    steps: list[dict] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    if_condition: Optional[str] = None
    env: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to workflow YAML format."""
        result = {
            "name": self.name,
            "runs-on": self.runs_on,
            "steps": self.steps,
        }
        if self.needs:
            result["needs"] = self.needs
        if self.if_condition:
            result["if"] = self.if_condition
        if self.env:
            result["env"] = self.env
        return result


@dataclass
class GitHubWorkflow:
    """A GitHub Actions workflow."""

    name: str
    filename: str
    on: dict[str, Any]
    jobs: dict[str, WorkflowJob]
    env: dict[str, str] = field(default_factory=dict)
    permissions: dict[str, str] = field(default_factory=dict)

    def to_yaml(self) -> str:
        """Convert to YAML string."""
        workflow = {
            "name": self.name,
            "on": self.on,
            "jobs": {name: job.to_dict() for name, job in self.jobs.items()},
        }
        if self.env:
            workflow["env"] = self.env
        if self.permissions:
            workflow["permissions"] = self.permissions

        return yaml.dump(workflow, default_flow_style=False, sort_keys=False)

    def save(self, project_dir: Path) -> Path:
        """Save workflow to .github/workflows directory."""
        workflows_dir = project_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        output_path = workflows_dir / self.filename
        with open(output_path, "w") as f:
            f.write(self.to_yaml())

        return output_path


def _detect_stack(project_dir: Path) -> dict:
    """Detect tech stack from project files."""
    stack = {
        "has_node": False,
        "has_python": False,
        "has_typescript": False,
        "has_react": False,
        "has_nextjs": False,
        "has_vue": False,
        "has_fastapi": False,
        "has_django": False,
        "node_version": "20",
        "python_version": "3.11",
        "package_manager": "npm",
    }

    # Check for Node.js
    package_json = project_dir / "package.json"
    if package_json.exists():
        stack["has_node"] = True
        try:
            with open(package_json) as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "typescript" in deps:
                    stack["has_typescript"] = True
                if "react" in deps:
                    stack["has_react"] = True
                if "next" in deps:
                    stack["has_nextjs"] = True
                if "vue" in deps:
                    stack["has_vue"] = True

                # Detect package manager
                if (project_dir / "pnpm-lock.yaml").exists():
                    stack["package_manager"] = "pnpm"
                elif (project_dir / "yarn.lock").exists():
                    stack["package_manager"] = "yarn"
                elif (project_dir / "bun.lockb").exists():
                    stack["package_manager"] = "bun"

                # Node version from engines
                engines = pkg.get("engines", {})
                if "node" in engines:
                    version = engines["node"].strip(">=^~")
                    if version and version[0].isdigit():
                        stack["node_version"] = version.split(".")[0]
        except (json.JSONDecodeError, KeyError):
            pass

    # Check for Python
    if (project_dir / "requirements.txt").exists() or (project_dir / "pyproject.toml").exists():
        stack["has_python"] = True

        # Check for FastAPI
        requirements_path = project_dir / "requirements.txt"
        if requirements_path.exists():
            content = requirements_path.read_text().lower()
            if "fastapi" in content:
                stack["has_fastapi"] = True
            if "django" in content:
                stack["has_django"] = True

        # Python version from pyproject.toml
        pyproject = project_dir / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "python_requires" in content or "requires-python" in content:
                import re
                match = re.search(r'["\']>=?3\.(\d+)', content)
                if match:
                    stack["python_version"] = f"3.{match.group(1)}"

    return stack


def _checkout_step() -> dict:
    """Standard checkout step."""
    return {
        "name": "Checkout code",
        "uses": "actions/checkout@v4",
    }


def _setup_node_step(version: str, cache: str = "npm") -> dict:
    """Setup Node.js step."""
    return {
        "name": "Setup Node.js",
        "uses": "actions/setup-node@v4",
        "with": {
            "node-version": version,
            "cache": cache,
        },
    }


def _setup_python_step(version: str) -> dict:
    """Setup Python step."""
    return {
        "name": "Setup Python",
        "uses": "actions/setup-python@v5",
        "with": {
            "python-version": version,
            "cache": "pip",
        },
    }


def _install_deps_step(package_manager: str = "npm") -> dict:
    """Install dependencies step."""
    commands = {
        "npm": "npm ci",
        "yarn": "yarn install --frozen-lockfile",
        "pnpm": "pnpm install --frozen-lockfile",
        "bun": "bun install --frozen-lockfile",
    }
    return {
        "name": "Install dependencies",
        "run": commands.get(package_manager, "npm ci"),
    }


def _python_install_step() -> dict:
    """Python install dependencies step."""
    return {
        "name": "Install dependencies",
        "run": "pip install -r requirements.txt",
    }


def generate_ci_workflow(project_dir: Path) -> GitHubWorkflow:
    """
    Generate CI workflow for lint, type-check, and tests.

    Triggers on push to feature branches and PRs to main.
    """
    stack = _detect_stack(project_dir)

    jobs = {}

    # Node.js jobs
    if stack["has_node"]:
        lint_steps = [
            _checkout_step(),
            _setup_node_step(stack["node_version"], stack["package_manager"]),
            _install_deps_step(stack["package_manager"]),
            {
                "name": "Run linter",
                "run": f"{stack['package_manager']} run lint" if stack["package_manager"] != "npm" else "npm run lint",
            },
        ]

        jobs["lint"] = WorkflowJob(
            name="Lint",
            steps=lint_steps,
        )

        if stack["has_typescript"]:
            typecheck_steps = [
                _checkout_step(),
                _setup_node_step(stack["node_version"], stack["package_manager"]),
                _install_deps_step(stack["package_manager"]),
                {
                    "name": "Type check",
                    "run": "npx tsc --noEmit",
                },
            ]

            jobs["typecheck"] = WorkflowJob(
                name="Type Check",
                steps=typecheck_steps,
            )

        test_steps = [
            _checkout_step(),
            _setup_node_step(stack["node_version"], stack["package_manager"]),
            _install_deps_step(stack["package_manager"]),
            {
                "name": "Run tests",
                "run": f"{stack['package_manager']} test" if stack["package_manager"] != "npm" else "npm test",
            },
        ]

        jobs["test"] = WorkflowJob(
            name="Test",
            steps=test_steps,
            needs=["lint"] + (["typecheck"] if stack["has_typescript"] else []),
        )

        build_steps = [
            _checkout_step(),
            _setup_node_step(stack["node_version"], stack["package_manager"]),
            _install_deps_step(stack["package_manager"]),
            {
                "name": "Build",
                "run": f"{stack['package_manager']} run build" if stack["package_manager"] != "npm" else "npm run build",
            },
        ]

        jobs["build"] = WorkflowJob(
            name="Build",
            steps=build_steps,
            needs=["test"],
        )

    # Python jobs
    if stack["has_python"]:
        python_lint_steps = [
            _checkout_step(),
            _setup_python_step(stack["python_version"]),
            _python_install_step(),
            {
                "name": "Run ruff",
                "run": "pip install ruff && ruff check .",
            },
        ]

        jobs["python-lint"] = WorkflowJob(
            name="Python Lint",
            steps=python_lint_steps,
        )

        python_test_steps = [
            _checkout_step(),
            _setup_python_step(stack["python_version"]),
            _python_install_step(),
            {
                "name": "Run tests",
                "run": "pip install pytest && pytest",
            },
        ]

        jobs["python-test"] = WorkflowJob(
            name="Python Test",
            steps=python_test_steps,
            needs=["python-lint"],
        )

    return GitHubWorkflow(
        name="CI",
        filename="ci.yml",
        on={
            "push": {
                "branches": ["main", "master", "feature/*"],
            },
            "pull_request": {
                "branches": ["main", "master"],
            },
        },
        jobs=jobs,
    )


def generate_security_workflow(project_dir: Path) -> GitHubWorkflow:
    """
    Generate security scanning workflow.

    Runs dependency audit and code scanning.
    """
    stack = _detect_stack(project_dir)

    jobs = {}

    if stack["has_node"]:
        audit_steps = [
            _checkout_step(),
            _setup_node_step(stack["node_version"], stack["package_manager"]),
            {
                "name": "Run npm audit",
                "run": "npm audit --audit-level=moderate",
                "continue-on-error": True,
            },
        ]

        jobs["npm-audit"] = WorkflowJob(
            name="NPM Audit",
            steps=audit_steps,
        )

    if stack["has_python"]:
        pip_audit_steps = [
            _checkout_step(),
            _setup_python_step(stack["python_version"]),
            {
                "name": "Run pip-audit",
                "run": "pip install pip-audit && pip-audit -r requirements.txt",
                "continue-on-error": True,
            },
        ]

        jobs["pip-audit"] = WorkflowJob(
            name="Pip Audit",
            steps=pip_audit_steps,
        )

    # CodeQL analysis
    codeql_steps = [
        _checkout_step(),
        {
            "name": "Initialize CodeQL",
            "uses": "github/codeql-action/init@v3",
            "with": {
                "languages": ",".join(
                    filter(None, [
                        "javascript-typescript" if stack["has_node"] else None,
                        "python" if stack["has_python"] else None,
                    ])
                ),
            },
        },
        {
            "name": "Autobuild",
            "uses": "github/codeql-action/autobuild@v3",
        },
        {
            "name": "Perform CodeQL Analysis",
            "uses": "github/codeql-action/analyze@v3",
        },
    ]

    jobs["codeql"] = WorkflowJob(
        name="CodeQL Analysis",
        steps=codeql_steps,
    )

    return GitHubWorkflow(
        name="Security",
        filename="security.yml",
        on={
            "push": {
                "branches": ["main", "master"],
            },
            "pull_request": {
                "branches": ["main", "master"],
            },
            "schedule": [
                {"cron": "0 0 * * 0"},  # Weekly on Sunday
            ],
        },
        jobs=jobs,
        permissions={
            "security-events": "write",
            "actions": "read",
            "contents": "read",
        },
    )


def generate_deploy_workflow(project_dir: Path) -> GitHubWorkflow:
    """
    Generate deployment workflow.

    Builds and deploys on merge to main.
    """
    stack = _detect_stack(project_dir)

    jobs = {}

    # Build job
    build_steps = [_checkout_step()]

    if stack["has_node"]:
        build_steps.extend([
            _setup_node_step(stack["node_version"], stack["package_manager"]),
            _install_deps_step(stack["package_manager"]),
            {
                "name": "Build",
                "run": f"{stack['package_manager']} run build" if stack["package_manager"] != "npm" else "npm run build",
            },
            {
                "name": "Upload build artifacts",
                "uses": "actions/upload-artifact@v4",
                "with": {
                    "name": "build",
                    "path": "dist/",
                    "retention-days": 7,
                },
            },
        ])

    if stack["has_python"]:
        build_steps.extend([
            _setup_python_step(stack["python_version"]),
            _python_install_step(),
            {
                "name": "Build package",
                "run": "pip install build && python -m build",
            },
            {
                "name": "Upload build artifacts",
                "uses": "actions/upload-artifact@v4",
                "with": {
                    "name": "build",
                    "path": "dist/",
                    "retention-days": 7,
                },
            },
        ])

    jobs["build"] = WorkflowJob(
        name="Build",
        steps=build_steps,
    )

    # Deploy staging job (placeholder)
    deploy_staging_steps = [
        _checkout_step(),
        {
            "name": "Download build artifacts",
            "uses": "actions/download-artifact@v4",
            "with": {
                "name": "build",
                "path": "dist/",
            },
        },
        {
            "name": "Deploy to staging",
            "run": "echo 'Add your staging deployment commands here'",
            "env": {
                "DEPLOY_ENV": "staging",
            },
        },
    ]

    jobs["deploy-staging"] = WorkflowJob(
        name="Deploy to Staging",
        steps=deploy_staging_steps,
        needs=["build"],
        env={"DEPLOY_ENV": "staging"},
    )

    # Deploy production job (manual trigger)
    deploy_prod_steps = [
        _checkout_step(),
        {
            "name": "Download build artifacts",
            "uses": "actions/download-artifact@v4",
            "with": {
                "name": "build",
                "path": "dist/",
            },
        },
        {
            "name": "Deploy to production",
            "run": "echo 'Add your production deployment commands here'",
            "env": {
                "DEPLOY_ENV": "production",
            },
        },
    ]

    jobs["deploy-production"] = WorkflowJob(
        name="Deploy to Production",
        steps=deploy_prod_steps,
        needs=["deploy-staging"],
        if_condition="github.event_name == 'workflow_dispatch'",
        env={"DEPLOY_ENV": "production"},
    )

    return GitHubWorkflow(
        name="Deploy",
        filename="deploy.yml",
        on={
            "push": {
                "branches": ["main", "master"],
            },
            "workflow_dispatch": {},
        },
        jobs=jobs,
    )


def generate_github_workflow(
    project_dir: Path,
    workflow_type: Literal["ci", "security", "deploy"] = "ci",
    save: bool = True,
) -> GitHubWorkflow:
    """
    Generate a GitHub Actions workflow.

    Args:
        project_dir: Project directory
        workflow_type: Type of workflow (ci, security, deploy)
        save: Whether to save the workflow file

    Returns:
        GitHubWorkflow instance
    """
    generators = {
        "ci": generate_ci_workflow,
        "security": generate_security_workflow,
        "deploy": generate_deploy_workflow,
    }

    generator = generators.get(workflow_type)
    if not generator:
        raise ValueError(f"Unknown workflow type: {workflow_type}")

    workflow = generator(Path(project_dir))

    if save:
        workflow.save(Path(project_dir))

    return workflow


def generate_all_workflows(project_dir: Path, save: bool = True) -> dict[str, GitHubWorkflow]:
    """
    Generate all workflow types for a project.

    Args:
        project_dir: Project directory
        save: Whether to save workflow files

    Returns:
        Dict mapping workflow type to GitHubWorkflow
    """
    workflows = {}
    for workflow_type in ["ci", "security", "deploy"]:
        workflows[workflow_type] = generate_github_workflow(
            project_dir, workflow_type, save
        )
    return workflows
