"""
Node.js Analyzer
================

Detects Node.js/Express/NestJS projects.
Extracts API endpoints from Express router definitions.
"""

import json
import re
from pathlib import Path

from .base_analyzer import (
    AnalysisResult,
    BaseAnalyzer,
    ComponentInfo,
    EndpointInfo,
    RouteInfo,
)


class NodeAnalyzer(BaseAnalyzer):
    """Analyzer for Node.js/Express/NestJS projects."""

    @property
    def stack_name(self) -> str:
        return self._detected_stack

    def __init__(self, project_dir: Path):
        super().__init__(project_dir)
        self._detected_stack = "nodejs"  # Default, may change to "express" or "nestjs"
        self._detection_confidence: float | None = None  # Store confidence from can_analyze()

    def can_analyze(self) -> tuple[bool, float]:
        """Detect if this is a Node.js/Express/NestJS project."""
        confidence = 0.0

        # Check package.json
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }

                # Check for NestJS first (more specific)
                if "@nestjs/core" in deps:
                    self._detected_stack = "nestjs"
                    confidence = 0.95
                    self._detection_confidence = confidence
                    return True, confidence

                # Check for Express
                if "express" in deps:
                    self._detected_stack = "express"
                    confidence = 0.85

                    # Bonus for having typical Express structure
                    if (self.project_dir / "routes").exists() or \
                       (self.project_dir / "src" / "routes").exists():
                        confidence = 0.9

                    self._detection_confidence = confidence
                    return True, confidence

                # Check for Fastify
                if "fastify" in deps:
                    self._detected_stack = "fastify"
                    confidence = 0.85
                    self._detection_confidence = confidence
                    return True, confidence

                # Check for Koa
                if "koa" in deps:
                    self._detected_stack = "koa"
                    confidence = 0.85
                    self._detection_confidence = confidence
                    return True, confidence

                # Generic Node.js (has node-specific files but no specific framework)
                if "type" in data and data["type"] == "module":
                    self._detected_stack = "nodejs"
                    confidence = 0.5
                    self._detection_confidence = confidence
                    return True, confidence

            except (json.JSONDecodeError, OSError):
                pass

        # Check for common Node.js files
        common_files = ["app.js", "server.js", "index.js", "src/app.js", "src/server.js"]
        for file in common_files:
            if (self.project_dir / file).exists():
                self._detected_stack = "nodejs"
                confidence = 0.5
                self._detection_confidence = confidence
                return True, confidence

        return False, 0.0

    def analyze(self) -> AnalysisResult:
        """Analyze the Node.js project."""
        routes: list[RouteInfo] = []
        components: list[ComponentInfo] = []
        endpoints: list[EndpointInfo] = []
        config_files: list[str] = []
        dependencies: dict[str, str] = {}
        entry_point: str | None = None

        # Load dependencies from package.json
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                dependencies = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }

                # Detect entry point from package.json
                entry_point = data.get("main")
                if not entry_point:
                    scripts = data.get("scripts", {})
                    start_script = scripts.get("start", "")
                    if "node" in start_script:
                        # Extract file from "node src/index.js" etc.
                        match = re.search(r"node\s+(\S+)", start_script)
                        if match:
                            entry_point = match.group(1)

            except (json.JSONDecodeError, OSError):
                pass

        # Collect config files
        for config_name in [
            "tsconfig.json", ".eslintrc.js", ".eslintrc.json",
            "jest.config.js", "nodemon.json", ".env.example",
        ]:
            if (self.project_dir / config_name).exists():
                config_files.append(config_name)

        # Detect entry point if not found
        if not entry_point:
            for candidate in ["src/index.js", "src/index.ts", "src/app.js", "src/app.ts",
                             "index.js", "app.js", "server.js"]:
                if (self.project_dir / candidate).exists():
                    entry_point = candidate
                    break

        # Extract endpoints based on stack type
        if self._detected_stack == "express":
            endpoints = self._extract_express_routes()
        elif self._detected_stack == "nestjs":
            endpoints = self._extract_nestjs_routes()
        elif self._detected_stack == "fastify":
            endpoints = self._extract_fastify_routes()
        else:
            # Generic Node.js - try Express patterns
            endpoints = self._extract_express_routes()

        # Extract middleware/components
        components = self._extract_components()

        # Routes is the same as endpoints for Node.js analyzers
        routes = endpoints

        # Use stored detection confidence with fallback to 0.85, clamped to [0.0, 1.0]
        confidence = float(self._detection_confidence) if self._detection_confidence is not None else 0.85
        confidence = max(0.0, min(1.0, confidence))

        return {
            "stack_name": self._detected_stack,
            "confidence": confidence,
            "routes": routes,
            "components": components,
            "endpoints": endpoints,
            "entry_point": entry_point,
            "config_files": config_files,
            "dependencies": dependencies,
            "metadata": {
                "has_typescript": "typescript" in dependencies,
                "has_prisma": "prisma" in dependencies or "@prisma/client" in dependencies,
                "has_mongoose": "mongoose" in dependencies,
                "has_sequelize": "sequelize" in dependencies,
            },
        }

    def _extract_express_routes(self) -> list[EndpointInfo]:
        """Extract routes from Express router definitions."""
        endpoints: list[EndpointInfo] = []

        # Find route files
        route_files = (
            self._find_files("**/routes/**/*.js") +
            self._find_files("**/routes/**/*.ts") +
            self._find_files("**/router/**/*.js") +
            self._find_files("**/router/**/*.ts") +
            self._find_files("**/controllers/**/*.js") +
            self._find_files("**/controllers/**/*.ts")
        )

        # Also check main files
        for main_file in ["app.js", "app.ts", "server.js", "server.ts",
                         "src/app.js", "src/app.ts", "index.js", "index.ts"]:
            main_path = self.project_dir / main_file
            if main_path.exists():
                route_files.append(main_path)

        # Pattern for Express routes
        # router.get('/path', handler)
        # app.post('/path', handler)
        route_pattern = re.compile(
            r'(?:router|app)\.(get|post|put|patch|delete|all)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        for file in route_files:
            content = self._read_file_safe(file)
            if content is None:
                continue

            for match in route_pattern.finditer(content):
                method = match.group(1).upper()
                path = match.group(2)

                endpoints.append({
                    "path": path,
                    "method": method,
                    "handler": "handler",
                    "file": str(file.relative_to(self.project_dir)),
                    "description": f"{method} {path}",
                })

        return endpoints

    def _extract_nestjs_routes(self) -> list[EndpointInfo]:
        """Extract routes from NestJS controllers."""
        endpoints: list[EndpointInfo] = []

        # Find controller files
        controller_files = (
            self._find_files("**/*.controller.ts") +
            self._find_files("**/*.controller.js")
        )

        # Pattern for NestJS decorators
        # @Get('/path'), @Post(), etc.
        decorator_pattern = re.compile(
            r'@(Get|Post|Put|Patch|Delete|All)\s*\(\s*["\']?([^"\')\s]*)["\']?\s*\)',
            re.IGNORECASE
        )

        # Pattern for controller path
        controller_pattern = re.compile(
            r'@Controller\s*\(\s*["\']?([^"\')\s]*)["\']?\s*\)',
            re.IGNORECASE
        )

        for file in controller_files:
            content = self._read_file_safe(file)
            if content is None:
                continue

            # Get controller base path
            controller_match = controller_pattern.search(content)
            base_path = "/" + controller_match.group(1) if controller_match else ""

            for match in decorator_pattern.finditer(content):
                method = match.group(1).upper()
                path = match.group(2) or ""

                full_path = base_path
                if path:
                    full_path = f"{base_path}/{path}".replace("//", "/")

                endpoints.append({
                    "path": full_path or "/",
                    "method": method,
                    "handler": "controller",
                    "file": str(file.relative_to(self.project_dir)),
                    "description": f"{method} {full_path or '/'}",
                })

        return endpoints

    def _extract_fastify_routes(self) -> list[EndpointInfo]:
        """Extract routes from Fastify route definitions."""
        endpoints: list[EndpointInfo] = []

        # Find route files
        route_files = (
            self._find_files("**/routes/**/*.js") +
            self._find_files("**/routes/**/*.ts") +
            self._find_files("**/*.routes.js") +
            self._find_files("**/*.routes.ts")
        )

        # Pattern for Fastify routes
        # fastify.get('/path', handler)
        route_pattern = re.compile(
            r'(?:fastify|server|app)\.(get|post|put|patch|delete|all)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        for file in route_files:
            content = self._read_file_safe(file)
            if content is None:
                continue

            for match in route_pattern.finditer(content):
                method = match.group(1).upper()
                path = match.group(2)

                endpoints.append({
                    "path": path,
                    "method": method,
                    "handler": "handler",
                    "file": str(file.relative_to(self.project_dir)),
                    "description": f"{method} {path}",
                })

        return endpoints

    def _extract_components(self) -> list[ComponentInfo]:
        """Extract middleware and service components."""
        components: list[ComponentInfo] = []

        # Find middleware files
        middleware_files = self._find_files("**/middleware/**/*.js") + \
                          self._find_files("**/middleware/**/*.ts")

        for file in middleware_files:
            components.append({
                "name": file.stem,
                "file": str(file.relative_to(self.project_dir)),
                "type": "middleware",
            })

        # Find service files
        service_files = self._find_files("**/services/**/*.js") + \
                       self._find_files("**/services/**/*.ts") + \
                       self._find_files("**/*.service.js") + \
                       self._find_files("**/*.service.ts")

        for file in service_files:
            components.append({
                "name": file.stem,
                "file": str(file.relative_to(self.project_dir)),
                "type": "service",
            })

        # Find model files
        model_files = self._find_files("**/models/**/*.js") + \
                     self._find_files("**/models/**/*.ts") + \
                     self._find_files("**/*.model.js") + \
                     self._find_files("**/*.model.ts")

        for file in model_files:
            components.append({
                "name": file.stem,
                "file": str(file.relative_to(self.project_dir)),
                "type": "model",
            })

        return components
