"""
React Analyzer
==============

Detects React, Vite, and Next.js projects.
Extracts routes from React Router and Next.js file-based routing.
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


class ReactAnalyzer(BaseAnalyzer):
    """Analyzer for React, Vite, and Next.js projects."""

    @property
    def stack_name(self) -> str:
        return self._detected_stack

    def __init__(self, project_dir: Path):
        super().__init__(project_dir)
        self._detected_stack = "react"  # Default, may change to "nextjs"

    def can_analyze(self) -> tuple[bool, float]:
        """Detect if this is a React/Next.js project."""
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

                # Check for Next.js first (more specific)
                if "next" in deps:
                    self._detected_stack = "nextjs"
                    confidence = 0.95
                    return True, confidence

                # Check for React
                if "react" in deps:
                    confidence = 0.85

                    # Check for Vite
                    if "vite" in deps:
                        self._detected_stack = "react-vite"
                        confidence = 0.9

                    # Check for Create React App
                    if "react-scripts" in deps:
                        self._detected_stack = "react-cra"
                        confidence = 0.9

                    return True, confidence

            except (json.JSONDecodeError, OSError):
                pass

        # Check for Next.js config
        if (self.project_dir / "next.config.js").exists() or \
           (self.project_dir / "next.config.mjs").exists() or \
           (self.project_dir / "next.config.ts").exists():
            self._detected_stack = "nextjs"
            return True, 0.95

        # Check for common React files
        if (self.project_dir / "src" / "App.tsx").exists() or \
           (self.project_dir / "src" / "App.jsx").exists():
            return True, 0.7

        return False, 0.0

    def analyze(self) -> AnalysisResult:
        """Analyze the React/Next.js project."""
        # Keep confidence consistent with detection
        _, confidence = self.can_analyze()

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
            "next.config.js", "next.config.mjs", "next.config.ts",
            "vite.config.js", "vite.config.ts",
            "tsconfig.json", "tailwind.config.js", "tailwind.config.ts",
        ]:
            if (self.project_dir / config_name).exists():
                config_files.append(config_name)

        # Detect entry point
        for entry in ["src/main.tsx", "src/main.jsx", "src/index.tsx", "src/index.jsx", "pages/_app.tsx", "app/layout.tsx"]:
            if (self.project_dir / entry).exists():
                entry_point = entry
                break

        # Extract routes based on stack type
        if self._detected_stack == "nextjs":
            routes = self._extract_nextjs_routes()
            endpoints = self._extract_nextjs_api_routes()
        else:
            routes = self._extract_react_router_routes()

        # Extract components
        components = self._extract_components()

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
                "has_tailwind": "tailwindcss" in dependencies,
                "has_react_router": "react-router-dom" in dependencies,
            },
        }

    def _extract_nextjs_routes(self) -> list[RouteInfo]:
        """Extract routes from Next.js file-based routing."""
        routes: list[RouteInfo] = []

        # Check for App Router (Next.js 13+)
        app_dir = self.project_dir / "app"
        if app_dir.exists():
            routes.extend(self._extract_app_router_routes(app_dir))

        # Check for Pages Router
        pages_dir = self.project_dir / "pages"
        if pages_dir.exists():
            routes.extend(self._extract_pages_router_routes(pages_dir))

        # Also check src/app and src/pages
        src_app = self.project_dir / "src" / "app"
        if src_app.exists():
            routes.extend(self._extract_app_router_routes(src_app))

        src_pages = self.project_dir / "src" / "pages"
        if src_pages.exists():
            routes.extend(self._extract_pages_router_routes(src_pages))

        return routes

    def _extract_app_router_routes(self, app_dir: Path) -> list[RouteInfo]:
        """Extract routes from Next.js App Router."""
        routes: list[RouteInfo] = []

        for page_file in app_dir.rglob("page.tsx"):
            rel_path = page_file.relative_to(app_dir)
            route_path = "/" + "/".join(rel_path.parent.parts)

            # Handle dynamic routes: [id] -> :id
            route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)

            # Clean up
            if route_path == "/.":
                route_path = "/"
            route_path = route_path.replace("//", "/")

            routes.append({
                "path": route_path,
                "method": "GET",
                "handler": "Page",
                "file": str(page_file.relative_to(self.project_dir)),
            })

        # Also check .jsx files
        for page_file in app_dir.rglob("page.jsx"):
            rel_path = page_file.relative_to(app_dir)
            route_path = "/" + "/".join(rel_path.parent.parts)
            route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)
            if route_path == "/.":
                route_path = "/"
            route_path = route_path.replace("//", "/")

            routes.append({
                "path": route_path,
                "method": "GET",
                "handler": "Page",
                "file": str(page_file.relative_to(self.project_dir)),
            })

        # Also check .js files
        for page_file in app_dir.rglob("page.js"):
            rel_path = page_file.relative_to(app_dir)
            route_path = "/" + "/".join(rel_path.parent.parts)
            route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)
            if route_path == "/.":
                route_path = "/"
            route_path = route_path.replace("//", "/")

            routes.append({
                "path": route_path,
                "method": "GET",
                "handler": "Page",
                "file": str(page_file.relative_to(self.project_dir)),
            })

        return routes

    def _extract_pages_router_routes(self, pages_dir: Path) -> list[RouteInfo]:
        """Extract routes from Next.js Pages Router."""
        routes: list[RouteInfo] = []

        for page_file in pages_dir.rglob("*.tsx"):
            if page_file.name.startswith("_"):  # Skip _app.tsx, _document.tsx
                continue
            if "api" in page_file.parts:  # Skip API routes
                continue

            rel_path = page_file.relative_to(pages_dir)
            route_path = "/" + rel_path.with_suffix("").as_posix()

            # Handle index files
            route_path = route_path.replace("/index", "")
            if not route_path:
                route_path = "/"

            # Handle dynamic routes
            route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)

            routes.append({
                "path": route_path,
                "method": "GET",
                "handler": page_file.stem,
                "file": str(page_file.relative_to(self.project_dir)),
            })

        # Also check .jsx files
        for page_file in pages_dir.rglob("*.jsx"):
            if page_file.name.startswith("_"):
                continue
            if "api" in page_file.parts:
                continue

            rel_path = page_file.relative_to(pages_dir)
            route_path = "/" + rel_path.with_suffix("").as_posix()
            route_path = route_path.replace("/index", "")
            if not route_path:
                route_path = "/"
            route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)

            routes.append({
                "path": route_path,
                "method": "GET",
                "handler": page_file.stem,
                "file": str(page_file.relative_to(self.project_dir)),
            })

        # Also check .js files
        for page_file in pages_dir.rglob("*.js"):
            if page_file.name.startswith("_"):
                continue
            if "api" in page_file.parts:
                continue

            rel_path = page_file.relative_to(pages_dir)
            route_path = "/" + rel_path.with_suffix("").as_posix()
            route_path = route_path.replace("/index", "")
            if not route_path:
                route_path = "/"
            route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)

            routes.append({
                "path": route_path,
                "method": "GET",
                "handler": page_file.stem,
                "file": str(page_file.relative_to(self.project_dir)),
            })

        return routes

    def _extract_nextjs_api_routes(self) -> list[EndpointInfo]:
        """Extract API routes from Next.js."""
        endpoints: list[EndpointInfo] = []

        # Check pages/api (Pages Router)
        api_dirs = [
            self.project_dir / "pages" / "api",
            self.project_dir / "src" / "pages" / "api",
        ]

        for api_dir in api_dirs:
            if api_dir.exists():
                for api_file in api_dir.rglob("*.ts"):
                    endpoints.extend(self._parse_api_route(api_file, api_dir))
                for api_file in api_dir.rglob("*.js"):
                    endpoints.extend(self._parse_api_route(api_file, api_dir))

        # Check app/api (App Router - route.ts files)
        app_api_dirs = [
            self.project_dir / "app" / "api",
            self.project_dir / "src" / "app" / "api",
        ]

        for app_api in app_api_dirs:
            if app_api.exists():
                for route_file in app_api.rglob("route.ts"):
                    endpoints.extend(self._parse_app_router_api(route_file, app_api))
                for route_file in app_api.rglob("route.js"):
                    endpoints.extend(self._parse_app_router_api(route_file, app_api))

        return endpoints

    def _parse_api_route(self, api_file: Path, api_dir: Path) -> list[EndpointInfo]:
        """Parse a Pages Router API route file."""
        rel_path = api_file.relative_to(api_dir)
        route_path = "/api/" + rel_path.with_suffix("").as_posix()
        route_path = route_path.replace("/index", "")
        route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)

        return [{
            "path": route_path,
            "method": "ALL",  # Default export handles all methods
            "handler": "handler",
            "file": str(api_file.relative_to(self.project_dir)),
            "description": f"API endpoint at {route_path}",
        }]

    def _parse_app_router_api(self, route_file: Path, api_dir: Path) -> list[EndpointInfo]:
        """Parse an App Router API route file."""
        rel_path = route_file.relative_to(api_dir)
        route_path = "/api/" + "/".join(rel_path.parent.parts)
        route_path = re.sub(r"\[([^\]]+)\]", r":\1", route_path)
        if route_path.endswith("/"):
            route_path = route_path[:-1]

        # Try to detect which methods are exported
        content = self._read_file_safe(route_file)
        methods = []
        if content:
            for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                if f"export async function {method}" in content or \
                   f"export function {method}" in content:
                    methods.append(method)

        if not methods:
            methods = ["ALL"]

        return [
            {
                "path": route_path,
                "method": method,
                "handler": method,
                "file": str(route_file.relative_to(self.project_dir)),
                "description": f"{method} {route_path}",
            }
            for method in methods
        ]

    def _extract_react_router_routes(self) -> list[RouteInfo]:
        """Extract routes from React Router configuration."""
        routes: list[RouteInfo] = []

        # Look for route definitions in common files
        route_files = (
            self._find_files("**/*.tsx") +
            self._find_files("**/*.jsx") +
            self._find_files("**/*.js")
        )

        # Pattern for React Router <Route> elements
        route_pattern = re.compile(
            r'<Route\s+[^>]*path=["\']([^"\']+)["\'][^>]*>',
            re.IGNORECASE
        )

        # Pattern for createBrowserRouter routes
        browser_router_pattern = re.compile(
            r'{\s*path:\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        for file in route_files:
            content = self._read_file_safe(file)
            if content is None:
                continue

            # Skip if not likely a routing file
            if "Route" not in content and "createBrowserRouter" not in content:
                continue

            # Extract routes from JSX
            for match in route_pattern.finditer(content):
                routes.append({
                    "path": match.group(1),
                    "method": "GET",
                    "handler": "Route",
                    "file": str(file.relative_to(self.project_dir)),
                })

            # Extract routes from createBrowserRouter
            for match in browser_router_pattern.finditer(content):
                routes.append({
                    "path": match.group(1),
                    "method": "GET",
                    "handler": "RouterRoute",
                    "file": str(file.relative_to(self.project_dir)),
                })

        return routes

    def _extract_components(self) -> list[ComponentInfo]:
        """Extract React components."""
        components: list[ComponentInfo] = []

        # Find component files
        component_files = (
            self._find_files("**/components/**/*.tsx") +
            self._find_files("**/components/**/*.jsx") +
            self._find_files("**/components/**/*.js")
        )

        for file in component_files:
            components.append({
                "name": file.stem,
                "file": str(file.relative_to(self.project_dir)),
                "type": "component",
            })

        # Find page files
        page_files = (
            self._find_files("**/pages/**/*.tsx") +
            self._find_files("**/pages/**/*.jsx") +
            self._find_files("**/pages/**/*.js")
        )

        for file in page_files:
            if not file.name.startswith("_"):
                components.append({
                    "name": file.stem,
                    "file": str(file.relative_to(self.project_dir)),
                    "type": "page",
                })

        return components
