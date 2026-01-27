"""
Auto Documentation Generator
============================

Automatically generates documentation for projects:
- README.md from app_spec.txt
- API documentation from route analysis
- Setup guide from dependencies and scripts
- Component documentation from source files

Triggers:
- After initialization (optional)
- After all features pass (optional)
- On-demand via API

Configuration:
- docs.enabled: Enable/disable auto-generation
- docs.generate_on_init: Generate after project init
- docs.generate_on_complete: Generate when all features pass
- docs.output_dir: Output directory (default: "docs")
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class APIEndpoint:
    """Represents an API endpoint for documentation."""

    method: str
    path: str
    description: str = ""
    parameters: list[dict] = field(default_factory=list)
    response_type: str = ""
    auth_required: bool = False


@dataclass
class ComponentDoc:
    """Represents a component for documentation."""

    name: str
    file_path: str
    description: str = ""
    props: list[dict] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)


@dataclass
class ProjectDocs:
    """Complete project documentation."""

    project_name: str
    description: str
    tech_stack: dict
    setup_steps: list[str]
    features: list[dict]
    api_endpoints: list[APIEndpoint]
    components: list[ComponentDoc]
    environment_vars: list[dict]
    scripts: dict
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.utcnow().isoformat() + "Z"


class DocumentationGenerator:
    """
    Generates documentation for a project.

    Usage:
        generator = DocumentationGenerator(project_dir)
        docs = generator.generate()
        generator.write_readme(docs)
        generator.write_api_docs(docs)
    """

    def __init__(self, project_dir: Path, output_dir: str = "docs"):
        self.project_dir = Path(project_dir)
        self.output_dir = self.project_dir / output_dir
        self.app_spec: Optional[dict] = None

    def generate(self) -> ProjectDocs:
        """
        Generate complete project documentation.

        Returns:
            ProjectDocs with all documentation data
        """
        # Parse app spec
        self.app_spec = self._parse_app_spec()

        # Gather information
        tech_stack = self._detect_tech_stack()
        setup_steps = self._extract_setup_steps()
        features = self._extract_features()
        api_endpoints = self._extract_api_endpoints()
        components = self._extract_components()
        env_vars = self._extract_environment_vars()
        scripts = self._extract_scripts()

        return ProjectDocs(
            project_name=self.app_spec.get("name", self.project_dir.name) if self.app_spec else self.project_dir.name,
            description=self.app_spec.get("description", "") if self.app_spec else "",
            tech_stack=tech_stack,
            setup_steps=setup_steps,
            features=features,
            api_endpoints=api_endpoints,
            components=components,
            environment_vars=env_vars,
            scripts=scripts,
        )

    def _parse_app_spec(self) -> Optional[dict]:
        """Parse app_spec.txt XML file."""
        spec_path = self.project_dir / "prompts" / "app_spec.txt"
        if not spec_path.exists():
            return None

        try:
            content = spec_path.read_text()

            # Extract key elements from XML
            result = {}

            # App name
            name_match = re.search(r"<app_name[^>]*>([^<]+)</app_name>", content)
            if name_match:
                result["name"] = name_match.group(1).strip()

            # Description
            desc_match = re.search(r"<description[^>]*>(.*?)</description>", content, re.DOTALL)
            if desc_match:
                result["description"] = desc_match.group(1).strip()

            # Tech stack
            stack_match = re.search(r"<tech_stack[^>]*>(.*?)</tech_stack>", content, re.DOTALL)
            if stack_match:
                result["tech_stack_raw"] = stack_match.group(1).strip()

            # Features
            features_match = re.search(r"<features[^>]*>(.*?)</features>", content, re.DOTALL)
            if features_match:
                result["features_raw"] = features_match.group(1).strip()

            return result

        except Exception as e:
            logger.warning(f"Error parsing app_spec.txt: {e}")
            return None

    def _detect_tech_stack(self) -> dict:
        """Detect tech stack from project files."""
        stack = {
            "frontend": [],
            "backend": [],
            "database": [],
            "tools": [],
        }

        # Check package.json
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                if "react" in deps:
                    stack["frontend"].append("React")
                if "next" in deps:
                    stack["frontend"].append("Next.js")
                if "vue" in deps:
                    stack["frontend"].append("Vue.js")
                if "express" in deps:
                    stack["backend"].append("Express")
                if "fastify" in deps:
                    stack["backend"].append("Fastify")
                if "@nestjs/core" in deps:
                    stack["backend"].append("NestJS")
                if "typescript" in deps:
                    stack["tools"].append("TypeScript")
                if "tailwindcss" in deps:
                    stack["tools"].append("Tailwind CSS")
                if "prisma" in deps:
                    stack["database"].append("Prisma")
            except Exception:
                pass

        # Check Python
        requirements = self.project_dir / "requirements.txt"
        pyproject = self.project_dir / "pyproject.toml"

        if requirements.exists() or pyproject.exists():
            content = ""
            if requirements.exists():
                content = requirements.read_text()
            if pyproject.exists():
                content += pyproject.read_text()

            if "fastapi" in content.lower():
                stack["backend"].append("FastAPI")
            if "django" in content.lower():
                stack["backend"].append("Django")
            if "flask" in content.lower():
                stack["backend"].append("Flask")
            if "sqlalchemy" in content.lower():
                stack["database"].append("SQLAlchemy")
            if "postgresql" in content.lower() or "psycopg" in content.lower():
                stack["database"].append("PostgreSQL")

        return stack

    def _extract_setup_steps(self) -> list[str]:
        """Extract setup steps from init.sh and package.json."""
        steps = []

        # Prerequisites
        package_json = self.project_dir / "package.json"
        requirements = self.project_dir / "requirements.txt"

        if package_json.exists():
            steps.append("Ensure Node.js is installed (v18+ recommended)")
        if requirements.exists():
            steps.append("Ensure Python 3.10+ is installed")

        # Installation
        if package_json.exists():
            steps.append("Run `npm install` to install dependencies")
        if requirements.exists():
            steps.append("Create virtual environment: `python -m venv venv`")
            steps.append("Activate venv: `source venv/bin/activate` (Unix) or `venv\\Scripts\\activate` (Windows)")
            steps.append("Install dependencies: `pip install -r requirements.txt`")

        # Check for init.sh
        init_sh = self.project_dir / "init.sh"
        if init_sh.exists():
            steps.append("Run initialization script: `./init.sh`")

        # Check for .env.example
        env_example = self.project_dir / ".env.example"
        if env_example.exists():
            steps.append("Copy `.env.example` to `.env` and configure environment variables")

        # Development server
        if package_json.exists():
            steps.append("Start development server: `npm run dev`")
        elif (self.project_dir / "main.py").exists():
            steps.append("Start server: `python main.py` or `uvicorn main:app --reload`")

        return steps

    def _extract_features(self) -> list[dict]:
        """Extract features from database or app_spec."""
        features = []

        # Try to read from features.db
        db_path = self.project_dir / "features.db"
        if db_path.exists():
            try:
                from api.database import Feature, get_session

                session = get_session(db_path)
                db_features = session.query(Feature).order_by(Feature.priority).all()

                for f in db_features:
                    features.append(
                        {
                            "category": f.category,
                            "name": f.name,
                            "description": f.description,
                            "status": "completed" if f.passes else "pending",
                        }
                    )
                session.close()
            except Exception as e:
                logger.warning(f"Error reading features.db: {e}")

        # If no features from DB, try app_spec
        if not features and self.app_spec and self.app_spec.get("features_raw"):
            # Parse feature items from raw text
            raw = self.app_spec["features_raw"]
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("-") or line.startswith("*"):
                    features.append(
                        {
                            "category": "Feature",
                            "name": line.lstrip("-* "),
                            "description": "",
                            "status": "pending",
                        }
                    )

        return features

    def _extract_api_endpoints(self) -> list[APIEndpoint]:
        """Extract API endpoints from source files."""
        endpoints = []

        # Check for Express routes (JS and TS files)
        from itertools import chain
        js_ts_routes = chain(
            self.project_dir.glob("**/routes/**/*.js"),
            self.project_dir.glob("**/routes/**/*.ts"),
        )
        for route_file in js_ts_routes:
            try:
                content = route_file.read_text()
                # Match router.get/post/put/delete
                matches = re.findall(
                    r'router\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                    content,
                    re.IGNORECASE,
                )
                for method, path in matches:
                    endpoints.append(
                        APIEndpoint(
                            method=method.upper(),
                            path=path,
                            description=f"Endpoint from {route_file.name}",
                        )
                    )
            except Exception:
                pass

        # Check for FastAPI routes
        for py_file in self.project_dir.glob("**/*.py"):
            if "node_modules" in str(py_file) or "venv" in str(py_file):
                continue
            try:
                content = py_file.read_text()
                # Match @app.get/post/etc or @router.get/post/etc
                matches = re.findall(
                    r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                    content,
                    re.IGNORECASE,
                )
                for method, path in matches:
                    endpoints.append(
                        APIEndpoint(
                            method=method.upper(),
                            path=path,
                            description=f"Endpoint from {py_file.name}",
                        )
                    )
            except Exception:
                pass

        return endpoints

    def _extract_components(self) -> list[ComponentDoc]:
        """Extract component documentation from source files."""
        components = []

        # React/Vue components
        for ext in ["tsx", "jsx", "vue"]:
            for comp_file in self.project_dir.glob(f"**/components/**/*.{ext}"):
                if "node_modules" in str(comp_file):
                    continue
                try:
                    content = comp_file.read_text()
                    name = comp_file.stem

                    # Try to extract description from JSDoc
                    description = ""
                    jsdoc_match = re.search(r"/\*\*\s*(.*?)\s*\*/", content, re.DOTALL)
                    if jsdoc_match:
                        description = jsdoc_match.group(1).strip()
                        # Clean up JSDoc syntax
                        description = re.sub(r"\s*\*\s*", " ", description)
                        description = re.sub(r"@\w+.*", "", description).strip()

                    # Extract props from TypeScript interface
                    props = []
                    props_match = re.search(r"interface\s+\w*Props\s*{([^}]+)}", content)
                    if props_match:
                        props_content = props_match.group(1)
                        for line in props_content.split("\n"):
                            line = line.strip()
                            if ":" in line and not line.startswith("//"):
                                prop_match = re.match(r"(\w+)\??:\s*(.+?)[;,]?$", line)
                                if prop_match:
                                    props.append(
                                        {
                                            "name": prop_match.group(1),
                                            "type": prop_match.group(2),
                                        }
                                    )

                    components.append(
                        ComponentDoc(
                            name=name,
                            file_path=str(comp_file.relative_to(self.project_dir)),
                            description=description,
                            props=props,
                        )
                    )
                except Exception:
                    pass

        return components

    def _extract_environment_vars(self) -> list[dict]:
        """Extract environment variables from .env.example or .env."""
        env_vars = []

        for env_file in [".env.example", ".env.sample", ".env"]:
            env_path = self.project_dir / env_file
            if env_path.exists():
                try:
                    for line in env_path.read_text().split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            # Mask sensitive values
                            if any(
                                s in key.lower() for s in ["secret", "password", "key", "token"]
                            ):
                                value = "***"
                            elif env_file == ".env":
                                value = "***"  # Mask all values from actual .env

                            env_vars.append(
                                {
                                    "name": key.strip(),
                                    "example": value.strip(),
                                    "required": not value.strip() or value == "***",
                                }
                            )
                    break  # Only process first found env file
                except Exception:
                    pass

        return env_vars

    def _extract_scripts(self) -> dict:
        """Extract npm scripts from package.json."""
        scripts = {}

        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                scripts = data.get("scripts", {})
            except Exception:
                pass

        return scripts

    def write_readme(self, docs: ProjectDocs) -> Path:
        """
        Write README.md file.

        Args:
            docs: ProjectDocs data

        Returns:
            Path to written file
        """
        readme_path = self.project_dir / "README.md"

        lines = []
        lines.append(f"# {docs.project_name}\n")

        if docs.description:
            lines.append(f"{docs.description}\n")

        # Tech Stack
        if any(docs.tech_stack.values()):
            lines.append("## Tech Stack\n")
            for category, items in docs.tech_stack.items():
                if items:
                    lines.append(f"**{category.title()}:** {', '.join(items)}\n")
            lines.append("")

        # Features
        if docs.features:
            lines.append("## Features\n")
            # Group by category
            categories = {}
            for f in docs.features:
                cat = f.get("category", "General")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(f)

            for cat, features in categories.items():
                lines.append(f"### {cat}\n")
                for f in features:
                    status = "[x]" if f.get("status") == "completed" else "[ ]"
                    lines.append(f"- {status} {f['name']}")
                lines.append("")

        # Getting Started
        if docs.setup_steps:
            lines.append("## Getting Started\n")
            lines.append("### Prerequisites\n")
            for step in docs.setup_steps[:2]:  # First few are usually prerequisites
                lines.append(f"- {step}")
            lines.append("")
            lines.append("### Installation\n")
            for i, step in enumerate(docs.setup_steps[2:], 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        # Environment Variables
        if docs.environment_vars:
            lines.append("## Environment Variables\n")
            lines.append("| Variable | Required | Example |")
            lines.append("|----------|----------|---------|")
            for var in docs.environment_vars:
                required = "Yes" if var.get("required") else "No"
                lines.append(f"| `{var['name']}` | {required} | `{var['example']}` |")
            lines.append("")

        # Available Scripts
        if docs.scripts:
            lines.append("## Available Scripts\n")
            for name, command in docs.scripts.items():
                lines.append(f"- `npm run {name}` - {command}")
            lines.append("")

        # API Endpoints
        if docs.api_endpoints:
            lines.append("## API Endpoints\n")
            lines.append("| Method | Path | Description |")
            lines.append("|--------|------|-------------|")
            for ep in docs.api_endpoints[:20]:  # Limit to 20
                lines.append(f"| {ep.method} | `{ep.path}` | {ep.description} |")
            if len(docs.api_endpoints) > 20:
                lines.append(f"\n*...and {len(docs.api_endpoints) - 20} more endpoints*")
            lines.append("")

        # Components
        if docs.components:
            lines.append("## Components\n")
            for comp in docs.components[:15]:  # Limit to 15
                lines.append(f"### {comp.name}\n")
                if comp.description:
                    lines.append(f"{comp.description}\n")
                lines.append(f"**File:** `{comp.file_path}`\n")
                if comp.props:
                    lines.append("**Props:**")
                    for prop in comp.props:
                        lines.append(f"- `{prop['name']}`: {prop['type']}")
                lines.append("")

        # Footer
        lines.append("---\n")
        lines.append(f"*Generated on {docs.generated_at[:10]} by Autocoder*\n")

        readme_path.write_text("\n".join(lines))
        return readme_path

    def write_api_docs(self, docs: ProjectDocs) -> Optional[Path]:
        """
        Write API documentation file.

        Args:
            docs: ProjectDocs data

        Returns:
            Path to written file or None if no API endpoints
        """
        if not docs.api_endpoints:
            return None

        self.output_dir.mkdir(parents=True, exist_ok=True)
        api_docs_path = self.output_dir / "API.md"

        lines = []
        lines.append(f"# {docs.project_name} API Documentation\n")

        # Group endpoints by base path
        grouped = {}
        for ep in docs.api_endpoints:
            base = ep.path.split("/")[1] if "/" in ep.path else "root"
            if base not in grouped:
                grouped[base] = []
            grouped[base].append(ep)

        for base, endpoints in sorted(grouped.items()):
            lines.append(f"## {base.title()}\n")
            for ep in endpoints:
                lines.append(f"### {ep.method} `{ep.path}`\n")
                if ep.description:
                    lines.append(f"{ep.description}\n")
                if ep.parameters:
                    lines.append("**Parameters:**")
                    for param in ep.parameters:
                        lines.append(f"- `{param['name']}` ({param.get('type', 'any')})")
                    lines.append("")
                if ep.response_type:
                    lines.append(f"**Response:** `{ep.response_type}`\n")
                lines.append("")

        lines.append("---\n")
        lines.append(f"*Generated on {docs.generated_at[:10]} by Autocoder*\n")

        api_docs_path.write_text("\n".join(lines))
        return api_docs_path

    def write_setup_guide(self, docs: ProjectDocs) -> Path:
        """
        Write detailed setup guide.

        Args:
            docs: ProjectDocs data

        Returns:
            Path to written file
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        setup_path = self.output_dir / "SETUP.md"

        lines = []
        lines.append(f"# {docs.project_name} Setup Guide\n")

        # Prerequisites
        lines.append("## Prerequisites\n")
        if docs.tech_stack.get("frontend"):
            lines.append("- Node.js 18 or later")
            lines.append("- npm, yarn, or pnpm")
        if docs.tech_stack.get("backend") and any(
            "Fast" in b or "Django" in b or "Flask" in b for b in docs.tech_stack.get("backend", [])
        ):
            lines.append("- Python 3.10 or later")
            lines.append("- pip or pipenv")
        lines.append("")

        # Installation
        lines.append("## Installation\n")
        for i, step in enumerate(docs.setup_steps, 1):
            lines.append(f"### Step {i}: {step.split(':')[0] if ':' in step else 'Setup'}\n")
            lines.append(f"{step}\n")
            # Add code block for command steps
            if "`" in step:
                cmd = re.search(r"`([^`]+)`", step)
                if cmd:
                    lines.append(f"```bash\n{cmd.group(1)}\n```\n")

        # Environment Configuration
        if docs.environment_vars:
            lines.append("## Environment Configuration\n")
            lines.append("Create a `.env` file in the project root:\n")
            lines.append("```env")
            for var in docs.environment_vars:
                lines.append(f"{var['name']}={var['example']}")
            lines.append("```\n")

        # Running the Application
        lines.append("## Running the Application\n")
        if docs.scripts:
            if "dev" in docs.scripts:
                lines.append("### Development\n")
                lines.append("```bash\nnpm run dev\n```\n")
            if "build" in docs.scripts:
                lines.append("### Production Build\n")
                lines.append("```bash\nnpm run build\n```\n")
            if "start" in docs.scripts:
                lines.append("### Start Production Server\n")
                lines.append("```bash\nnpm start\n```\n")

        lines.append("---\n")
        lines.append(f"*Generated on {docs.generated_at[:10]} by Autocoder*\n")

        setup_path.write_text("\n".join(lines))
        return setup_path

    def generate_all(self) -> dict:
        """
        Generate all documentation files.

        Returns:
            Dict with paths to generated files
        """
        docs = self.generate()

        results = {
            "readme": str(self.write_readme(docs)),
            "setup": str(self.write_setup_guide(docs)),
        }

        api_path = self.write_api_docs(docs)
        if api_path:
            results["api"] = str(api_path)

        return results


def generate_documentation(project_dir: Path, output_dir: str = "docs") -> dict:
    """
    Generate all documentation for a project.

    Args:
        project_dir: Project directory
        output_dir: Output directory for docs

    Returns:
        Dict with paths to generated files
    """
    generator = DocumentationGenerator(project_dir, output_dir)
    return generator.generate_all()
