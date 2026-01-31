"""
Design Tokens Generator
=======================

Generates design tokens based on visual style selection.
These tokens are used by the coding agent to apply consistent styling.
"""

import json
from pathlib import Path
from typing import Any

from app_spec_parser import VALID_VISUAL_STYLES, get_ui_config_from_spec

# Style presets with design tokens
# Each preset defines CSS-friendly values for consistent styling
STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "neobrutalism": {
        "description": "Bold colors, hard shadows, no border-radius",
        "borders": {
            "width": "4px",
            "radius": "0",
            "style": "solid",
            "color": "currentColor",
        },
        "shadows": {
            "default": "4px 4px 0 0 currentColor",
            "hover": "6px 6px 0 0 currentColor",
            "active": "2px 2px 0 0 currentColor",
        },
        "colors": {
            "primary": "#ff6b6b",
            "secondary": "#4ecdc4",
            "accent": "#ffe66d",
            "background": "#ffffff",
            "surface": "#f8f9fa",
            "text": "#000000",
            "border": "#000000",
        },
        "typography": {
            "fontFamily": "'Inter', 'Helvetica Neue', sans-serif",
            "fontWeight": {
                "normal": "500",
                "bold": "800",
            },
        },
        "spacing": {
            "base": "8px",
            "scale": 1.5,
        },
        "effects": {
            "transition": "all 0.1s ease-in-out",
        },
    },
    "glassmorphism": {
        "description": "Frosted glass effects, blur, transparency",
        "borders": {
            "width": "1px",
            "radius": "16px",
            "style": "solid",
            "color": "rgba(255, 255, 255, 0.2)",
        },
        "shadows": {
            "default": "0 8px 32px 0 rgba(31, 38, 135, 0.15)",
            "hover": "0 12px 40px 0 rgba(31, 38, 135, 0.2)",
            "active": "0 4px 16px 0 rgba(31, 38, 135, 0.1)",
        },
        "colors": {
            "primary": "#8b5cf6",
            "secondary": "#06b6d4",
            "accent": "#f472b6",
            "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "surface": "rgba(255, 255, 255, 0.1)",
            "text": "#ffffff",
            "border": "rgba(255, 255, 255, 0.2)",
        },
        "typography": {
            "fontFamily": "'Inter', system-ui, sans-serif",
            "fontWeight": {
                "normal": "400",
                "bold": "600",
            },
        },
        "spacing": {
            "base": "8px",
            "scale": 1.5,
        },
        "effects": {
            "backdropBlur": "12px",
            "backdropSaturate": "180%",
            "transition": "all 0.3s ease",
        },
    },
    "retro": {
        "description": "Pixel-art inspired, vibrant neons, 8-bit aesthetic",
        "borders": {
            "width": "3px",
            "radius": "0",
            "style": "solid",
            "color": "#00ffff",
        },
        "shadows": {
            "default": "0 0 10px #ff00ff, 0 0 20px #00ffff",
            "hover": "0 0 15px #ff00ff, 0 0 30px #00ffff",
            "active": "0 0 5px #ff00ff, 0 0 10px #00ffff",
        },
        "colors": {
            "primary": "#ff00ff",
            "secondary": "#00ffff",
            "accent": "#ffff00",
            "background": "#0a0a0a",
            "surface": "#1a1a2e",
            "text": "#00ff00",
            "border": "#00ffff",
        },
        "typography": {
            "fontFamily": "'Press Start 2P', 'Courier New', monospace",
            "fontWeight": {
                "normal": "400",
                "bold": "400",
            },
            "letterSpacing": "0.05em",
            "textTransform": "uppercase",
        },
        "spacing": {
            "base": "8px",
            "scale": 2,
        },
        "effects": {
            "textShadow": "0 0 5px currentColor",
            "transition": "all 0.15s steps(3)",
        },
    },
}


def get_style_preset(style: str) -> dict[str, Any] | None:
    """
    Get design tokens for a specific visual style.

    Args:
        style: The style name (neobrutalism, glassmorphism, retro)

    Returns:
        Design tokens dict or None if style is not found or is 'default'.
    """
    if style == "default" or style not in STYLE_PRESETS:
        return None
    return STYLE_PRESETS[style]


def generate_design_tokens(project_dir: Path, style: str) -> Path | None:
    """
    Generate design tokens JSON file for a project.

    Args:
        project_dir: Path to the project directory
        style: The visual style to use

    Returns:
        Path to the generated tokens file, or None if style is default/custom
        or if file write fails.
    """
    # "default" uses library defaults, no tokens needed
    # "custom" means user will define their own tokens manually
    if style == "default" or style == "custom":
        return None

    preset = get_style_preset(style)
    if not preset:
        return None

    # Create .autocoder directory if it doesn't exist
    autocoder_dir = project_dir / ".autocoder"
    autocoder_dir.mkdir(parents=True, exist_ok=True)

    # Write design tokens
    tokens_path = autocoder_dir / "design-tokens.json"
    try:
        tokens_path.write_text(json.dumps(preset, indent=2), encoding="utf-8")
    except OSError:
        # File write failed (permissions, disk full, etc.)
        return None

    return tokens_path


def generate_design_tokens_from_spec(project_dir: Path) -> Path | None:
    """
    Generate design tokens based on project's app_spec.txt.

    Args:
        project_dir: Path to the project directory

    Returns:
        Path to the generated tokens file, or None if no tokens needed.
    """
    ui_config = get_ui_config_from_spec(project_dir)
    if not ui_config:
        return None

    style = ui_config.get("style", "default")
    return generate_design_tokens(project_dir, style)


def validate_visual_style(style: str) -> bool:
    """
    Check if a visual style is valid.

    Args:
        style: The style name to validate

    Returns:
        True if valid, False otherwise.
    """
    return style in VALID_VISUAL_STYLES
