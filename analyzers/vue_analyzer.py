"""
Vue.js Analyzer
===============

Detects Vue.js and Nuxt.js projects.
Extracts routes from Vue Router and Nuxt file-based routing.
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


class VueAnalyzer(BaseAnalyzer):
    """Analyzer for Vue.js and Nuxt.js projects."""

    @property
    def stack_name(self) -> str:
        return self._detected_stack

    def __init__(self, project_dir: Path):
        super().__init__(project_dir)
        self._detected_stack = "vue"  # Default, may change to "nuxt"

    def can_analyze(self) -> tuple[bool, float]:
        """Detect if this is a Vue.js/Nuxt.js project."""
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

                # Check for Nuxt first (more specific)
                if "nuxt" in deps or "nuxt3" in deps:
                    self._detected_stack = "nuxt"
                    confidence = 0.95
                    return True, confidence

                # Check for Vue
                if "vue" in deps:
                    confidence = 0.85

                    # Check for Vite
                    if "vite" in deps:
                        self._detected_stack = "vue-vite"
                        confidence = 0.9

                    # Check for Vue CLI
                    if "@vue/cli-service" in deps:
                        self._detected_stack = "vue-cli"
                        confidence = 0.9

                    return True, confidence

            except (json.JSONDecodeError, OSError):
                pass

        # Check for Nuxt config
        if (self.project_dir / "nuxt.config.js").exists() or \
           (self.project_dir / "nuxt.config.ts").exists():
            self._detected_stack = "nuxt"
            return True, 0.95

        # Check for common Vue files
        if (self.project_dir / "src" / "App.vue").exists():
            return True, 0.7

        return False, 0.0

    def analyze(self) -> AnalysisResult:
        """Analyze the Vue.js/Nuxt.js project."""
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
            except (json.JSONDecodeError, OSError):
                pass

        # Collect config files
        for config_name in [
            "nuxt.config.js", "nuxt.config.ts",
            "vite.config.js", "vite.config.ts",
            "vue.config.js", "tsconfig.json",
            "tailwind.config.js", "tailwind.config.ts",
        ]:
            if (self.project_dir / config_name).exists():
                config_files.append(config_name)

        # Detect entry point
        for entry in ["src/main.ts", "src/main.js", "app.vue", "src/App.vue"]:
            if (self.project_dir / entry).exists():
                entry_point = entry
                break

        # Extract routes based on stack type
        if self._detected_stack == "nuxt":
            routes = self._extract_nuxt_routes()
            endpoints = self._extract_nuxt_api_routes()
        else:
            routes = self._extract_vue_router_routes()

        # Extract components
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
                "has_typescript": "typescript" in dependencies,
                "has_tailwind": "tailwindcss" in dependencies,
                "has_vue_router": "vue-router" in dependencies,
                "has_pinia": "pinia" in dependencies,
                "has_vuex": "vuex" in dependencies,
            },
        }

    def _extract_nuxt_routes(self) -> list[RouteInfo]:
        """Extract routes from Nuxt file-based routing."""
        routes: list[RouteInfo] = []

        # Check for pages directory
        pages_dirs = [
            self.project_dir / "pages",
            self.project_dir / "src" / "pages",
        ]

        for pages_dir in pages_dirs:
            if pages_dir.exists():
                routes.extend(self._extract_pages_routes(pages_dir))

        return routes

    def _extract_pages_routes(self, pages_dir: Path) -> list[RouteInfo]:
        """Extract routes from Nuxt pages directory."""
        routes: list[RouteInfo] = []

        for page_file in pages_dir.rglob("*.vue"):
            rel_path = page_file.relative_to(pages_dir)
            route_path = "/" + str(rel_path.with_suffix(""))

            # Handle index files
            route_path = route_path.replace("/index", "")
            if not route_path:
                route_path = "/"

            # Handle dynamic routes: [id].vue or _id.vue -> :id
            route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)
            route_path = re.sub(r"/_([^/]+)", r"/:\1", route_path)

            routes.append({
                "path": route_path,
                "method": "GET",
                "handler": page_file.stem,
                "file": str(page_file.relative_to(self.project_dir)),
            })

        return routes

    def _extract_nuxt_api_routes(self) -> list[EndpointInfo]:
        """Extract API routes from Nuxt server directory."""
        endpoints: list[EndpointInfo] = []

        # Nuxt 3 uses server/api directory
        api_dirs = [
            self.project_dir / "server" / "api",
            self.project_dir / "server" / "routes",
        ]

        for api_dir in api_dirs:
            if not api_dir.exists():
                continue

            for api_file in api_dir.rglob("*.ts"):
                rel_path = api_file.relative_to(api_dir)
                route_path = "/api/" + str(rel_path.with_suffix(""))

                # Handle index files
                route_path = route_path.replace("/index", "")

                # Handle dynamic routes
                route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)

                # Try to detect method from filename
                method = "ALL"
                for m in ["get", "post", "put", "patch", "delete"]:
                    if api_file.stem.endswith(f".{m}") or api_file.stem == m:
                        method = m.upper()
                        route_path = route_path.replace(f".{m}", "")
                        break

                endpoints.append({
                    "path": route_path,
                    "method": method,
                    "handler": "handler",
                    "file": str(api_file.relative_to(self.project_dir)),
                    "description": f"{method} {route_path}",
                })

            # Also check .js files
            for api_file in api_dir.rglob("*.js"):
                rel_path = api_file.relative_to(api_dir)
                route_path = "/api/" + str(rel_path.with_suffix(""))
                route_path = route_path.replace("/index", "")
                route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)

                endpoints.append({
                    "path": route_path,
                    "method": "ALL",
                    "handler": "handler",
                    "file": str(api_file.relative_to(self.project_dir)),
                    "description": f"API endpoint at {route_path}",
                })

        return endpoints

    def _extract_vue_router_routes(self) -> list[RouteInfo]:
        """Extract routes from Vue Router configuration."""
        routes: list[RouteInfo] = []

        # Look for router configuration files
        router_files = (
            self._find_files("**/router/**/*.js") +
            self._find_files("**/router/**/*.ts") +
            self._find_files("**/router.js") +
            self._find_files("**/router.ts") +
            self._find_files("**/routes.js") +
            self._find_files("**/routes.ts")
        )

        # Pattern for Vue Router routes
        # { path: '/about', ... }
        route_pattern = re.compile(
            r'{\s*path:\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        for file in router_files:
            content = self._read_file_safe(file)
            if content is None:
                continue

            for match in route_pattern.finditer(content):
                routes.append({
                    "path": match.group(1),
                    "method": "GET",
                    "handler": "RouterRoute",
                    "file": str(file.relative_to(self.project_dir)),
                })

        return routes

    def _extract_components(self) -> list[ComponentInfo]:
        """Extract Vue components."""
        components: list[ComponentInfo] = []

        # Find component files
        component_files = (
            self._find_files("**/components/**/*.vue") +
            self._find_files("**/views/**/*.vue")
        )

        for file in component_files:
            # Determine component type
            if "views" in file.parts:
                comp_type = "view"
            elif "layouts" in file.parts:
                comp_type = "layout"
            else:
                comp_type = "component"

            components.append({
                "name": file.stem,
                "file": str(file.relative_to(self.project_dir)),
                "type": comp_type,
            })

        # Find page files (Nuxt)
        page_files = self._find_files("**/pages/**/*.vue")

        for file in page_files:
            components.append({
                "name": file.stem,
                "file": str(file.relative_to(self.project_dir)),
                "type": "page",
            })

        return components
