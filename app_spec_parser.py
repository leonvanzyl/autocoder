"""
App Spec Parser
===============

Shared utilities for parsing app_spec.txt sections.
Used by client.py, prompts.py, and design_tokens.py to avoid code duplication.

This module provides functions to:
- Extract XML sections from app_spec.txt
- Parse UI component library configuration
- Parse visual style configuration
- Combine configurations for the coding agent
"""

import re
from pathlib import Path
from typing import TypedDict

# =============================================================================
# Constants
# =============================================================================

# Valid UI library options
VALID_UI_LIBRARIES = {"shadcn-ui", "ark-ui", "radix-ui", "none"}

# Libraries that have MCP server support
MCP_SUPPORTED_LIBRARIES = {"shadcn-ui", "ark-ui"}

# Valid visual style options
VALID_VISUAL_STYLES = {"default", "neobrutalism", "glassmorphism", "retro", "custom"}

# Valid frameworks
VALID_FRAMEWORKS = {"react", "vue", "solid", "svelte"}

# Regex pattern to match XML comments (<!-- ... -->)
XML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)

# =============================================================================
# Type Definitions
# =============================================================================


class UIComponentsConfig(TypedDict, total=False):
    """Configuration for UI component library."""
    library: str  # shadcn-ui, ark-ui, radix-ui, none
    framework: str  # react, vue, solid, svelte
    has_mcp: bool  # Whether MCP server is available


class VisualStyleConfig(TypedDict, total=False):
    """Configuration for visual style."""
    style: str  # default, neobrutalism, glassmorphism, retro, custom
    design_tokens_path: str  # Path to custom design tokens JSON


class UIConfig(TypedDict, total=False):
    """Combined UI configuration."""
    library: str
    framework: str
    has_mcp: bool
    style: str
    design_tokens_path: str


# =============================================================================
# Parsing Functions
# =============================================================================


def parse_section(content: str, section_name: str) -> str | None:
    """
    Parse an XML section from app_spec.txt content.

    Args:
        content: The full app_spec.txt content
        section_name: The XML tag name to extract (e.g., "ui_components")

    Returns:
        The content inside the section tags, or None if not found.
    """
    pattern = rf"<{section_name}[^>]*>(.*?)</{section_name}>"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else None


def parse_xml_value(content: str, tag_name: str) -> str | None:
    """
    Parse a single XML value from content.

    Extracts the text content from an XML tag, filtering out any XML comments.
    Returns None if the tag is not found or contains only whitespace/comments.

    Args:
        content: XML content to search
        tag_name: The tag name to extract value from

    Returns:
        The value inside the tags, or None if not found or empty.

    Example:
        >>> parse_xml_value("<library>shadcn-ui</library>", "library")
        'shadcn-ui'
        >>> parse_xml_value("<library><!-- comment --></library>", "library")
        None
    """
    pattern = rf"<{tag_name}[^>]*>(.*?)</{tag_name}>"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        value = match.group(1)
        # Remove XML comments using regex pattern
        value = XML_COMMENT_PATTERN.sub("", value).strip()
        if value:
            return value
    return None


def parse_ui_components(content: str) -> UIComponentsConfig:
    """
    Parse <ui_components> section from app_spec.txt content.

    Args:
        content: The full app_spec.txt content

    Returns:
        UIComponentsConfig with library, framework, and has_mcp fields.
        Returns sensible defaults if section is not found.
    """
    section = parse_section(content, "ui_components")
    if not section:
        return UIComponentsConfig(
            library="none",
            framework="react",
            has_mcp=False,
        )

    library = parse_xml_value(section, "library") or "none"
    framework = parse_xml_value(section, "framework") or "react"
    has_mcp_str = parse_xml_value(section, "has_mcp") or "false"
    has_mcp = has_mcp_str.lower() == "true"

    return UIComponentsConfig(
        library=library,
        framework=framework,
        has_mcp=has_mcp,
    )


def parse_visual_style(content: str) -> VisualStyleConfig:
    """
    Parse <visual_style> section from app_spec.txt content.

    Args:
        content: The full app_spec.txt content

    Returns:
        VisualStyleConfig with style and design_tokens_path fields.
        Returns sensible defaults if section is not found.
    """
    section = parse_section(content, "visual_style")
    if not section:
        return VisualStyleConfig(
            style="default",
            design_tokens_path="",
        )

    style = parse_xml_value(section, "style") or "default"
    design_tokens_path = parse_xml_value(section, "design_tokens_path") or ""

    return VisualStyleConfig(
        style=style,
        design_tokens_path=design_tokens_path,
    )


def parse_ui_config(content: str) -> UIConfig:
    """
    Parse both UI components and visual style configuration.

    Args:
        content: The full app_spec.txt content

    Returns:
        Combined UIConfig with all UI-related settings.
    """
    ui_components = parse_ui_components(content)
    visual_style = parse_visual_style(content)

    return UIConfig(
        library=ui_components.get("library", "none"),
        framework=ui_components.get("framework", "react"),
        has_mcp=ui_components.get("has_mcp", False),
        style=visual_style.get("style", "default"),
        design_tokens_path=visual_style.get("design_tokens_path", ""),
    )


def get_ui_config_from_spec(project_dir: Path) -> UIConfig | None:
    """
    Read and parse UI configuration from a project's app_spec.txt.

    Args:
        project_dir: Path to the project directory

    Returns:
        UIConfig if app_spec.txt exists and can be parsed, None otherwise.
    """
    spec_path = project_dir / "prompts" / "app_spec.txt"
    if not spec_path.exists():
        return None

    try:
        content = spec_path.read_text(encoding="utf-8")
        return parse_ui_config(content)
    except (OSError, UnicodeDecodeError):
        return None
