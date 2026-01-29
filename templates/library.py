"""
Template Library Module
=======================

Load and manage application templates for quick project scaffolding.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

import yaml

# Directory containing template files
TEMPLATES_DIR = Path(__file__).parent / "catalog"


def sanitize_xml_tag_name(name: str) -> str:
    """
    Sanitize a string to be a valid XML tag name.

    XML tag names must start with a letter or underscore and can only contain
    letters, digits, hyphens, underscores, and periods.
    """
    if not name:
        return "unnamed"

    # Replace invalid characters with underscores
    sanitized = ""
    for i, char in enumerate(name):
        if char.isalnum() or char in "-._":
            sanitized += char
        else:
            sanitized += "_"

    # Ensure first character is a letter or underscore
    if sanitized and sanitized[0].isdigit():
        sanitized = "n_" + sanitized
    elif not sanitized or sanitized[0] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_":
        sanitized = "_" + sanitized

    # Avoid reserved "xml" prefix
    if sanitized.lower().startswith("xml"):
        sanitized = "_" + sanitized

    return sanitized or "unnamed"


@dataclass
class DesignTokens:
    """Design tokens for consistent styling."""

    colors: dict[str, str] = field(default_factory=dict)
    spacing: list[int] = field(default_factory=list)
    fonts: dict[str, str] = field(default_factory=dict)
    border_radius: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "DesignTokens":
        """Create from dictionary."""
        return cls(
            colors=data.get("colors", {}),
            spacing=data.get("spacing", [4, 8, 12, 16, 24, 32]),
            fonts=data.get("fonts", {}),
            border_radius=data.get("border_radius", {}),
        )


@dataclass
class TechStack:
    """Technology stack configuration."""

    frontend: Optional[str] = None
    backend: Optional[str] = None
    database: Optional[str] = None
    auth: Optional[str] = None
    styling: Optional[str] = None
    hosting: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "TechStack":
        """Create from dictionary."""
        return cls(
            frontend=data.get("frontend"),
            backend=data.get("backend"),
            database=data.get("database"),
            auth=data.get("auth"),
            styling=data.get("styling"),
            hosting=data.get("hosting"),
        )


@dataclass
class TemplateFeature:
    """A feature in a template."""

    name: str
    description: str
    category: str
    steps: list[str] = field(default_factory=list)
    priority: int = 0

    @classmethod
    def from_dict(cls, data: dict, category: str, priority: int) -> "TemplateFeature":
        """Create from dictionary."""
        steps = data.get("steps", [])
        if not steps:
            # Generate default steps
            steps = [f"Implement {data['name']}"]

        return cls(
            name=data["name"],
            description=data.get("description", data["name"]),
            category=category,
            steps=steps,
            priority=priority,
        )


@dataclass
class TemplateCategory:
    """A category of features in a template."""

    name: str
    features: list[str]
    description: Optional[str] = None


@dataclass
class Template:
    """An application template."""

    id: str
    name: str
    description: str
    tech_stack: TechStack
    feature_categories: dict[str, list[str]]
    design_tokens: DesignTokens
    estimated_features: int
    tags: list[str] = field(default_factory=list)
    difficulty: str = "intermediate"
    preview_image: Optional[str] = None

    @classmethod
    def from_dict(cls, template_id: str, data: dict) -> "Template":
        """Create from dictionary."""
        return cls(
            id=template_id,
            name=data["name"],
            description=data["description"],
            tech_stack=TechStack.from_dict(data.get("tech_stack", {})),
            feature_categories=data.get("feature_categories", {}),
            design_tokens=DesignTokens.from_dict(data.get("design_tokens", {})),
            estimated_features=data.get("estimated_features", 0),
            tags=data.get("tags", []),
            difficulty=data.get("difficulty", "intermediate"),
            preview_image=data.get("preview_image"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tech_stack": {
                "frontend": self.tech_stack.frontend,
                "backend": self.tech_stack.backend,
                "database": self.tech_stack.database,
                "auth": self.tech_stack.auth,
                "styling": self.tech_stack.styling,
                "hosting": self.tech_stack.hosting,
            },
            "feature_categories": self.feature_categories,
            "design_tokens": {
                "colors": self.design_tokens.colors,
                "spacing": self.design_tokens.spacing,
                "fonts": self.design_tokens.fonts,
                "border_radius": self.design_tokens.border_radius,
            },
            "estimated_features": self.estimated_features,
            "tags": self.tags,
            "difficulty": self.difficulty,
        }


def load_template(template_id: str) -> Optional[Template]:
    """
    Load a template by ID.

    Args:
        template_id: Template identifier (filename without extension)

    Returns:
        Template instance or None if not found
    """
    template_path = TEMPLATES_DIR / f"{template_id}.yaml"

    if not template_path.exists():
        return None

    try:
        with open(template_path) as f:
            data = yaml.safe_load(f)
        return Template.from_dict(template_id, data)
    except Exception:
        return None


def list_templates() -> list[Template]:
    """
    List all available templates.

    Returns:
        List of Template instances
    """
    templates = []

    if not TEMPLATES_DIR.exists():
        return templates

    for file in TEMPLATES_DIR.glob("*.yaml"):
        template = load_template(file.stem)
        if template:
            templates.append(template)

    return sorted(templates, key=lambda t: t.name)


def get_template(template_id: str) -> Optional[Template]:
    """
    Get a specific template by ID.

    Args:
        template_id: Template identifier

    Returns:
        Template instance or None
    """
    return load_template(template_id)


def generate_features(template: Template) -> list[dict]:
    """
    Generate feature list from a template.

    Returns features in the format expected by feature_create_bulk.

    Args:
        template: Template instance

    Returns:
        List of feature dictionaries
    """
    features = []
    priority = 1

    for category, feature_names in template.feature_categories.items():
        for feature_name in feature_names:
            features.append({
                "priority": priority,
                "category": category.replace("_", " ").title(),
                "name": feature_name,
                "description": f"{feature_name} functionality for the application",
                "steps": [f"Implement {feature_name}"],
                "passes": False,
            })
            priority += 1

    return features


def generate_app_spec(
    template: Template,
    app_name: str,
    customizations: Optional[dict] = None,
) -> str:
    """
    Generate app_spec.txt content from a template.

    Args:
        template: Template instance
        app_name: Application name
        customizations: Optional customizations to apply

    Returns:
        XML content for app_spec.txt
    """
    customizations = customizations or {}

    # Merge design tokens with customizations
    colors = {**template.design_tokens.colors, **customizations.get("colors", {})}

    # Build XML (escape all user-provided content to prevent XML injection)
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<app_spec>",
        f"  <name>{xml_escape(app_name)}</name>",
        f"  <description>{xml_escape(template.description)}</description>",
        "",
        "  <tech_stack>",
    ]

    if template.tech_stack.frontend:
        xml_parts.append(f"    <frontend>{xml_escape(template.tech_stack.frontend)}</frontend>")
    if template.tech_stack.backend:
        xml_parts.append(f"    <backend>{xml_escape(template.tech_stack.backend)}</backend>")
    if template.tech_stack.database:
        xml_parts.append(f"    <database>{xml_escape(template.tech_stack.database)}</database>")
    if template.tech_stack.auth:
        xml_parts.append(f"    <auth>{xml_escape(template.tech_stack.auth)}</auth>")
    if template.tech_stack.styling:
        xml_parts.append(f"    <styling>{xml_escape(template.tech_stack.styling)}</styling>")

    xml_parts.extend([
        "  </tech_stack>",
        "",
        "  <design_tokens>",
        "    <colors>",
    ])

    for color_name, color_value in colors.items():
        # Sanitize color name for use as XML tag name
        safe_tag_name = sanitize_xml_tag_name(color_name)
        # Only escape the value, not the tag name (which is already sanitized)
        safe_value = xml_escape(color_value)
        xml_parts.append(f"      <{safe_tag_name}>{safe_value}</{safe_tag_name}>")

    xml_parts.extend([
        "    </colors>",
        "  </design_tokens>",
        "",
        "  <features>",
    ])

    for category, feature_names in template.feature_categories.items():
        category_title = category.replace("_", " ").title()
        # Escape attribute value using quoteattr pattern
        safe_category = xml_escape(category_title, {'"': '&quot;'})
        xml_parts.append(f'    <category name="{safe_category}">')
        for feature_name in feature_names:
            xml_parts.append(f"      <feature>{xml_escape(feature_name)}</feature>")
        xml_parts.append("    </category>")

    xml_parts.extend([
        "  </features>",
        "</app_spec>",
    ])

    return "\n".join(xml_parts)
