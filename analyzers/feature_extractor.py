"""
Feature Extractor
=================

Transforms detected routes, endpoints, and components into Autocoder features.
Each feature is marked as pending (passes=False) for verification.

Generates features in the format expected by feature_create_bulk MCP tool.
"""

from pathlib import Path
from typing import TypedDict

from .stack_detector import StackDetectionResult

# Feature extraction thresholds
MIN_FEATURES_BEFORE_COMPONENTS = 10
MAX_COMPONENT_FEATURES = 10


class DetectedFeature(TypedDict):
    """A feature extracted from codebase analysis."""
    category: str
    name: str
    description: str
    steps: list[str]
    source_type: str  # "route", "endpoint", "component", "inferred"
    source_file: str | None
    confidence: float  # 0.0 to 1.0


class FeatureExtractionResult(TypedDict):
    """Result of feature extraction."""
    features: list[DetectedFeature]
    count: int
    by_category: dict[str, int]
    summary: str


def _get_base_stack(stack: str | None) -> str | None:
    """Extract base stack name from variants like 'react-vite' -> 'react'."""
    if not stack:
        return None
    return stack.split("-")[0].lower()


def _route_to_feature_name(path: str, method: str = "GET") -> str:
    """
    Convert a route path to a human-readable feature name.

    Examples:
        "/" -> "View home page"
        "/users" -> "View users page"
        "/users/:id" -> "View user details page"
        "/api/users" -> "API: List users"
    """
    # Clean up path
    path = path.strip("/")

    if not path:
        return "View home page"

    # Handle API routes
    if path.startswith("api/"):
        api_path = path[4:]  # Remove "api/"
        parts = api_path.split("/")

        # Handle dynamic segments
        parts = [p for p in parts if not p.startswith(":") and not p.startswith("[")]

        if not parts:
            return "API: Root endpoint"

        resource = parts[-1].replace("-", " ").replace("_", " ").title()

        if method == "GET":
            if any(p.startswith(":") or p.startswith("[") for p in api_path.split("/")):
                return f"API: Get {resource} details"
            return f"API: List {resource}"
        elif method == "POST":
            return f"API: Create {resource}"
        elif method == "PUT" or method == "PATCH":
            return f"API: Update {resource}"
        elif method == "DELETE":
            return f"API: Delete {resource}"
        else:
            return f"API: {resource} endpoint"

    # Handle page routes
    parts = path.split("/")

    # Handle dynamic segments (remove them from naming)
    clean_parts = [p for p in parts if not p.startswith(":") and not p.startswith("[")]

    if not clean_parts:
        return "View dynamic page"

    # Build name from path parts
    page_name = " ".join(p.replace("-", " ").replace("_", " ") for p in clean_parts)
    page_name = page_name.title()

    # Check if it's a detail page (has dynamic segment)
    has_dynamic = any(p.startswith(":") or p.startswith("[") for p in parts)

    if has_dynamic:
        return f"View {page_name} details page"

    return f"View {page_name} page"


def _generate_page_steps(path: str, stack: str | None) -> list[str]:
    """Generate test steps for a page route."""
    clean_path = path

    # Replace dynamic segments with example values
    if ":id" in clean_path or "[id]" in clean_path:
        clean_path = clean_path.replace(":id", "123").replace("[id]", "123")

    # Generate steps
    steps = [
        f"Navigate to {clean_path}",
        "Verify the page loads without errors",
        "Verify the page title and main content are visible",
    ]

    # Add stack-specific checks (normalize to handle variants like react-vite)
    base_stack = _get_base_stack(stack)
    if base_stack in ("react", "nextjs", "vue", "nuxt", "angular"):
        steps.append("Verify no console errors in browser developer tools")
        steps.append("Verify responsive layout at mobile and desktop widths")

    return steps


def _generate_api_steps(path: str, method: str) -> list[str]:
    """Generate test steps for an API endpoint."""
    # Replace dynamic segments with example values
    test_path = path.replace(":id", "123").replace("[id]", "123")

    steps = []

    if method == "GET":
        steps = [
            f"Send GET request to {test_path}",
            "Verify response status code is 200",
            "Verify response body contains expected data structure",
        ]
    elif method == "POST":
        steps = [
            f"Send POST request to {test_path} with valid payload",
            "Verify response status code is 201 (created)",
            "Verify response contains the created resource",
            f"Send POST request to {test_path} with invalid payload",
            "Verify response status code is 400 (bad request)",
        ]
    elif method in ("PUT", "PATCH"):
        steps = [
            f"Send {method} request to {test_path} with valid payload",
            "Verify response status code is 200",
            "Verify response contains the updated resource",
            "Verify the resource was actually updated",
        ]
    elif method == "DELETE":
        steps = [
            f"Send DELETE request to {test_path}",
            "Verify response status code is 200 or 204",
            "Verify the resource no longer exists",
        ]
    else:
        steps = [
            f"Send {method} request to {test_path}",
            "Verify response status code is appropriate",
        ]

    return steps


def _generate_component_steps(name: str, comp_type: str) -> list[str]:
    """Generate test steps for a component."""
    if comp_type == "page":
        return [
            f"Navigate to the {name} page",
            "Verify all UI elements render correctly",
            "Test user interactions (buttons, forms, etc.)",
            "Verify data is fetched and displayed",
        ]
    elif comp_type == "model":
        return [
            f"Verify {name} model schema matches expected fields",
            "Test CRUD operations on the model",
            "Verify validation rules work correctly",
        ]
    elif comp_type == "middleware":
        return [
            f"Verify {name} middleware processes requests correctly",
            "Test edge cases and error handling",
        ]
    elif comp_type == "service":
        return [
            f"Verify {name} service methods work correctly",
            "Test error handling in service layer",
        ]
    else:
        return [
            f"Verify {name} component renders correctly",
            "Test component props and state",
            "Verify component interactions work",
        ]


def extract_features(detection_result: StackDetectionResult) -> FeatureExtractionResult:
    """
    Extract features from a stack detection result.

    Converts routes, endpoints, and components into Autocoder features.
    Each feature is ready to be created via feature_create_bulk.

    Args:
        detection_result: Result from StackDetector.detect()

    Returns:
        FeatureExtractionResult with list of features
    """
    features: list[DetectedFeature] = []
    primary_frontend = detection_result.get("primary_frontend")

    # Track unique features to avoid duplicates
    seen_features: set[str] = set()

    # Extract features from routes (frontend pages)
    for route in detection_result.get("all_routes", []):
        path = route.get("path", "")
        method = route.get("method", "GET")
        source_file = route.get("file")

        feature_name = _route_to_feature_name(path, method)

        # Skip duplicates
        feature_key = f"route:{path}:{method}"
        if feature_key in seen_features:
            continue
        seen_features.add(feature_key)

        features.append({
            "category": "Navigation",
            "name": feature_name,
            "description": f"User can navigate to and view the {path or '/'} page. The page should load correctly and display the expected content.",
            "steps": _generate_page_steps(path, primary_frontend),
            "source_type": "route",
            "source_file": source_file,
            "confidence": 0.8,
        })

    # Extract features from API endpoints
    for endpoint in detection_result.get("all_endpoints", []):
        path = endpoint.get("path", "")
        method = endpoint.get("method", "ALL")
        source_file = endpoint.get("file")

        # Handle ALL method by creating GET endpoint
        if method == "ALL":
            method = "GET"

        # Ensure API endpoints get API-style naming
        name_path = path
        # Avoid double-prefixing: check for "api" or "api/" at start
        stripped = name_path.lstrip("/")
        if stripped != "api" and not stripped.startswith("api/"):
            name_path = f"/api{name_path if name_path.startswith('/') else '/' + name_path}"
        feature_name = _route_to_feature_name(name_path, method)

        # Skip duplicates
        feature_key = f"endpoint:{path}:{method}"
        if feature_key in seen_features:
            continue
        seen_features.add(feature_key)

        # Determine category based on path
        category = "API"
        path_lower = path.lower()
        if "auth" in path_lower or "login" in path_lower or "register" in path_lower:
            category = "Authentication"
        elif "user" in path_lower or "profile" in path_lower:
            category = "User Management"
        elif "admin" in path_lower:
            category = "Administration"

        features.append({
            "category": category,
            "name": feature_name,
            "description": f"{method} endpoint at {path}. Should handle requests appropriately and return correct responses.",
            "steps": _generate_api_steps(path, method),
            "source_type": "endpoint",
            "source_file": source_file,
            "confidence": 0.85,
        })

    # Extract features from components (with lower priority)
    component_features: list[DetectedFeature] = []
    for component in detection_result.get("all_components", []):
        name = component.get("name", "")
        comp_type = component.get("type", "component")
        source_file = component.get("file")

        # Skip common/generic components
        skip_names = [
            "index", "app", "main", "layout", "_app", "_document",
            "header", "footer", "sidebar", "navbar", "nav",
            "loading", "error", "not-found", "404", "500",
        ]
        if name.lower() in skip_names:
            continue

        # Skip duplicates
        feature_key = f"component:{name}:{comp_type}"
        if feature_key in seen_features:
            continue
        seen_features.add(feature_key)

        # Only include significant components
        if comp_type in ("page", "view", "model", "service"):
            clean_name = name.replace("-", " ").replace("_", " ").title()

            # Determine category
            if comp_type == "model":
                category = "Data Models"
            elif comp_type == "service":
                category = "Services"
            elif comp_type in ("page", "view"):
                category = "Pages"
            else:
                category = "Components"

            component_features.append({
                "category": category,
                "name": f"{clean_name} {comp_type.title()}",
                "description": f"The {clean_name} {comp_type} should function correctly and handle all expected use cases.",
                "steps": _generate_component_steps(name, comp_type),
                "source_type": "component",
                "source_file": source_file,
                "confidence": 0.6,  # Lower confidence for component-based features
            })

    # Add component features if we don't have many from routes/endpoints
    if len(features) < MIN_FEATURES_BEFORE_COMPONENTS:
        features.extend(component_features[:MAX_COMPONENT_FEATURES])

    # Add basic infrastructure features
    basic_features = _generate_basic_features(detection_result)
    features.extend(basic_features)

    # Count by category
    by_category: dict[str, int] = {}
    for f in features:
        cat = f["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

    # Build summary
    summary = f"Extracted {len(features)} features from {len(detection_result.get('detected_stacks', []))} detected stack(s)"

    return {
        "features": features,
        "count": len(features),
        "by_category": by_category,
        "summary": summary,
    }


def _generate_basic_features(detection_result: StackDetectionResult) -> list[DetectedFeature]:
    """Generate basic infrastructure features based on detected stack."""
    features: list[DetectedFeature] = []

    primary_frontend = detection_result.get("primary_frontend")
    primary_backend = detection_result.get("primary_backend")

    # Normalize stack names to handle variants like react-vite, fastify, etc.
    frontend_base = _get_base_stack(primary_frontend)
    backend_base = _get_base_stack(primary_backend)

    # Application startup feature
    if primary_frontend or primary_backend:
        features.append({
            "category": "Infrastructure",
            "name": "Application starts successfully",
            "description": "The application should start without errors and be accessible.",
            "steps": [
                "Run the application start command",
                "Verify the server starts without errors",
                "Access the application URL",
                "Verify the main page loads",
            ],
            "source_type": "inferred",
            "source_file": None,
            "confidence": 1.0,
        })

    # Frontend-specific features (handle variants like react-vite, vue-cli)
    if frontend_base in ("react", "nextjs", "vue", "nuxt", "angular"):
        features.append({
            "category": "Infrastructure",
            "name": "No console errors on page load",
            "description": "The application should load without JavaScript errors in the browser console.",
            "steps": [
                "Open browser developer tools",
                "Navigate to the home page",
                "Check the console for errors",
                "Navigate to other pages and repeat",
            ],
            "source_type": "inferred",
            "source_file": None,
            "confidence": 0.9,
        })

    # Backend-specific features (expanded list for all backend stacks)
    if backend_base in ("express", "fastify", "koa", "nodejs", "node",
                        "fastapi", "django", "flask", "nestjs", "python"):
        features.append({
            "category": "Infrastructure",
            "name": "Health check endpoint responds",
            "description": "The API should have a health check endpoint that responds correctly.",
            "steps": [
                "Send GET request to /health or /api/health",
                "Verify response status is 200",
                "Verify response indicates healthy status",
            ],
            "source_type": "inferred",
            "source_file": None,
            "confidence": 0.7,
        })

    return features


def features_to_bulk_create_format(features: list[DetectedFeature]) -> list[dict]:
    """
    Convert extracted features to the format expected by feature_create_bulk.

    Removes source_type, source_file, and confidence fields.
    Returns a list ready for MCP tool consumption.

    Args:
        features: List of DetectedFeature objects

    Returns:
        List of dicts with category, name, description, steps
    """
    return [
        {
            "category": f["category"],
            "name": f["name"],
            "description": f["description"],
            "steps": f["steps"],
        }
        for f in features
    ]


def extract_from_project(project_dir: str | Path) -> FeatureExtractionResult:
    """
    Convenience function to detect stack and extract features in one step.

    Args:
        project_dir: Path to the project directory

    Returns:
        FeatureExtractionResult with extracted features
    """
    from .stack_detector import StackDetector

    detector = StackDetector(Path(project_dir))
    detection_result = detector.detect()
    return extract_features(detection_result)
