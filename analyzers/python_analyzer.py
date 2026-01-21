"""
Python Analyzer
===============

Detects FastAPI, Django, and Flask projects.
Extracts API endpoints from route/view definitions.
"""

import re
from pathlib import Path

from .base_analyzer import (
    AnalysisResult,
    BaseAnalyzer,
    ComponentInfo,
    EndpointInfo,
    RouteInfo,
)


class PythonAnalyzer(BaseAnalyzer):
    """Analyzer for FastAPI, Django, and Flask projects."""

    @property
    def stack_name(self) -> str:
        return self._detected_stack

    def __init__(self, project_dir: Path):
        super().__init__(project_dir)
        self._detected_stack = "python"  # Default, may change

    def can_analyze(self) -> tuple[bool, float]:
        """Detect if this is a Python web framework project."""
        confidence = 0.0

        # Check for Django first
        if (self.project_dir / "manage.py").exists():
            self._detected_stack = "django"
            confidence = 0.95
            return True, confidence

        # Check requirements.txt
        requirements = self.project_dir / "requirements.txt"
        if requirements.exists():
            try:
                content = requirements.read_text().lower()

                if "fastapi" in content:
                    self._detected_stack = "fastapi"
                    confidence = 0.9
                    return True, confidence

                if "flask" in content:
                    self._detected_stack = "flask"
                    confidence = 0.85
                    return True, confidence

                if "django" in content:
                    self._detected_stack = "django"
                    confidence = 0.85
                    return True, confidence

            except OSError:
                pass

        # Check pyproject.toml
        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text().lower()

                if "fastapi" in content:
                    self._detected_stack = "fastapi"
                    confidence = 0.9
                    return True, confidence

                if "flask" in content:
                    self._detected_stack = "flask"
                    confidence = 0.85
                    return True, confidence

                if "django" in content:
                    self._detected_stack = "django"
                    confidence = 0.85
                    return True, confidence

            except OSError:
                pass

        # Check for common FastAPI patterns
        main_py = self.project_dir / "main.py"
        if main_py.exists():
            content = self._read_file_safe(main_py)
            if content and "from fastapi import" in content:
                self._detected_stack = "fastapi"
                return True, 0.9

        # Check for Flask patterns
        app_py = self.project_dir / "app.py"
        if app_py.exists():
            content = self._read_file_safe(app_py)
            if content and "from flask import" in content:
                self._detected_stack = "flask"
                return True, 0.85

        return False, 0.0

    def analyze(self) -> AnalysisResult:
        """Analyze the Python project."""
        routes: list[RouteInfo] = []
        components: list[ComponentInfo] = []
        endpoints: list[EndpointInfo] = []
        config_files: list[str] = []
        dependencies: dict[str, str] = {}
        entry_point: str | None = None

        # Load dependencies from requirements.txt
        requirements = self.project_dir / "requirements.txt"
        if requirements.exists():
            try:
                for line in requirements.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Parse package==version or package>=version etc.
                        match = re.match(r"([a-zA-Z0-9_-]+)(?:[=<>!~]+(.+))?", line)
                        if match:
                            dependencies[match.group(1)] = match.group(2) or "*"
            except OSError:
                pass

        # Collect config files
        for config_name in [
            "pyproject.toml", "setup.py", "setup.cfg",
            "requirements.txt", "requirements-dev.txt",
            ".env.example", "alembic.ini", "pytest.ini",
        ]:
            if (self.project_dir / config_name).exists():
                config_files.append(config_name)

        # Extract endpoints based on framework
        if self._detected_stack == "fastapi":
            endpoints = self._extract_fastapi_routes()
            entry_point = "main.py"
        elif self._detected_stack == "django":
            endpoints = self._extract_django_routes()
            entry_point = "manage.py"
        elif self._detected_stack == "flask":
            endpoints = self._extract_flask_routes()
            entry_point = "app.py"

        # Find entry point if not set
        if not entry_point or not (self.project_dir / entry_point).exists():
            for candidate in ["main.py", "app.py", "server.py", "run.py", "src/main.py"]:
                if (self.project_dir / candidate).exists():
                    entry_point = candidate
                    break

        # Extract components (models, services, etc.)
        components = self._extract_components()

        return {
            "stack_name": self._detected_stack,
            "confidence": 0.85,
            "routes": routes,
            "components": components,
            "endpoints": endpoints,
            "entry_point": entry_point,
            "config_files": config_files,
            "dependencies": dependencies,
            "metadata": {
                "has_sqlalchemy": "sqlalchemy" in dependencies,
                "has_alembic": "alembic" in dependencies,
                "has_pytest": "pytest" in dependencies,
                "has_celery": "celery" in dependencies,
            },
        }

    def _extract_fastapi_routes(self) -> list[EndpointInfo]:
        """Extract routes from FastAPI decorators."""
        endpoints: list[EndpointInfo] = []

        # Find Python files
        py_files = self._find_files("**/*.py")

        # Pattern for FastAPI routes
        # @app.get("/path")
        # @router.post("/path")
        route_pattern = re.compile(
            r'@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        # Pattern for APIRouter prefix
        router_prefix_pattern = re.compile(
            r'APIRouter\s*\([^)]*prefix\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        for file in py_files:
            content = self._read_file_safe(file)
            if content is None:
                continue

            # Skip if not a route file
            if "@app." not in content and "@router." not in content:
                continue

            # Try to find router prefix
            prefix = ""
            prefix_match = router_prefix_pattern.search(content)
            if prefix_match:
                prefix = prefix_match.group(1)

            for match in route_pattern.finditer(content):
                method = match.group(1).upper()
                path = match.group(2)

                full_path = prefix + path if prefix else path

                endpoints.append({
                    "path": full_path,
                    "method": method,
                    "handler": "handler",
                    "file": str(file.relative_to(self.project_dir)),
                    "description": f"{method} {full_path}",
                })

        return endpoints

    def _extract_django_routes(self) -> list[EndpointInfo]:
        """Extract routes from Django URL patterns."""
        endpoints: list[EndpointInfo] = []

        # Find urls.py files
        url_files = self._find_files("**/urls.py")

        # Pattern for Django URL patterns
        # path('api/users/', views.user_list)
        # path('api/users/<int:pk>/', views.user_detail)
        path_pattern = re.compile(
            r'path\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        # Pattern for re_path
        re_path_pattern = re.compile(
            r're_path\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        for file in url_files:
            content = self._read_file_safe(file)
            if content is None:
                continue

            for match in path_pattern.finditer(content):
                path = "/" + match.group(1).rstrip("/")
                if path == "/":
                    path = "/"

                # Django uses <type:name> for params, convert to :name
                path = re.sub(r"<\w+:(\w+)>", r":\1", path)
                path = re.sub(r"<(\w+)>", r":\1", path)

                endpoints.append({
                    "path": path,
                    "method": "ALL",  # Django views typically handle multiple methods
                    "handler": "view",
                    "file": str(file.relative_to(self.project_dir)),
                    "description": f"Django view at {path}",
                })

            for match in re_path_pattern.finditer(content):
                # re_path uses regex, just record the pattern
                path = "/" + match.group(1)

                endpoints.append({
                    "path": path,
                    "method": "ALL",
                    "handler": "view",
                    "file": str(file.relative_to(self.project_dir)),
                    "description": f"Django regex route",
                })

        return endpoints

    def _extract_flask_routes(self) -> list[EndpointInfo]:
        """Extract routes from Flask decorators."""
        endpoints: list[EndpointInfo] = []

        # Find Python files
        py_files = self._find_files("**/*.py")

        # Pattern for Flask routes
        # @app.route('/path', methods=['GET', 'POST'])
        # @bp.route('/path')
        route_pattern = re.compile(
            r'@(?:app|bp|blueprint)\s*\.\s*route\s*\(\s*["\']([^"\']+)["\'](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?',
            re.IGNORECASE
        )

        # Pattern for Blueprint prefix
        blueprint_pattern = re.compile(
            r'Blueprint\s*\(\s*[^,]+\s*,\s*[^,]+\s*(?:,\s*url_prefix\s*=\s*["\']([^"\']+)["\'])?',
            re.IGNORECASE
        )

        for file in py_files:
            content = self._read_file_safe(file)
            if content is None:
                continue

            # Skip if not a route file
            if "@app." not in content and "@bp." not in content and "@blueprint" not in content.lower():
                continue

            # Try to find blueprint prefix
            prefix = ""
            prefix_match = blueprint_pattern.search(content)
            if prefix_match and prefix_match.group(1):
                prefix = prefix_match.group(1)

            for match in route_pattern.finditer(content):
                path = match.group(1)
                methods_str = match.group(2)

                full_path = prefix + path if prefix else path

                # Parse methods
                methods = ["GET"]  # Default
                if methods_str:
                    # Parse ['GET', 'POST'] format
                    methods = re.findall(r"['\"](\w+)['\"]", methods_str)

                for method in methods:
                    endpoints.append({
                        "path": full_path,
                        "method": method.upper(),
                        "handler": "view",
                        "file": str(file.relative_to(self.project_dir)),
                        "description": f"{method.upper()} {full_path}",
                    })

        return endpoints

    def _extract_components(self) -> list[ComponentInfo]:
        """Extract models, services, and other components."""
        components: list[ComponentInfo] = []

        # Find model files
        model_files = (
            self._find_files("**/models.py") +
            self._find_files("**/models/**/*.py") +
            self._find_files("**/*_model.py")
        )

        for file in model_files:
            if file.name != "__init__.py":
                components.append({
                    "name": file.stem,
                    "file": str(file.relative_to(self.project_dir)),
                    "type": "model",
                })

        # Find view/controller files
        view_files = (
            self._find_files("**/views.py") +
            self._find_files("**/views/**/*.py") +
            self._find_files("**/routers/**/*.py") +
            self._find_files("**/api/**/*.py")
        )

        for file in view_files:
            if file.name != "__init__.py":
                components.append({
                    "name": file.stem,
                    "file": str(file.relative_to(self.project_dir)),
                    "type": "view",
                })

        # Find service files
        service_files = (
            self._find_files("**/services/**/*.py") +
            self._find_files("**/*_service.py")
        )

        for file in service_files:
            if file.name != "__init__.py":
                components.append({
                    "name": file.stem,
                    "file": str(file.relative_to(self.project_dir)),
                    "type": "service",
                })

        return components
