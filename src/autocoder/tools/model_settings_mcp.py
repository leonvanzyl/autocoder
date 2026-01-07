"""
MCP Model Settings Server
=========================

Exposes model selection settings as Model Context Protocol tools.

This allows Claude agents (workers) to:
1. Get available model presets
2. Apply a model preset (quality, balanced, economy, etc.)
3. Get the best model for a specific feature category
4. Configure model settings programmatically

IMPORTANT: This is for AGENTS (LLMs) to use.
The Orchestrator (Python code) should import ModelSettings directly.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to import FastMCP
try:
    from mcp.server.fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    print("WARNING: FastMCP not available. Install with: pip install fastmcp")

# Import ModelSettings
from autocoder.core.model_settings import ModelSettings, ModelPreset, get_full_model_id

logger = __import__("logging").getLogger(__name__)

# Initialize MCP Server
if FASTMCP_AVAILABLE:
    mcp = FastMCP("Model Settings")
else:
    mcp = None


# ============================================================================
# Synchronous Wrappers (for MCP tools)
# ============================================================================

def get_presets_sync() -> Dict[str, Any]:
    """
    Get all available model presets.

    Returns:
        Dictionary with all presets and their configurations
    """
    try:
        presets = []

        for preset in ModelPreset:
            preset_info = {
                "name": preset.value,
                "description": _get_preset_description(preset),
                "models": _get_preset_models(preset)
            }
            presets.append(preset_info)

        return {
            "success": True,
            "presets": presets,
            "count": len(presets)
        }

    except Exception as e:
        logger.error(f"Failed to get presets: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def apply_preset_sync(preset_name: str) -> Dict[str, Any]:
    """
    Apply a model preset.

    Args:
        preset_name: Name of the preset (quality, balanced, economy, cheap, experimental)

    Returns:
        Dictionary with the applied preset configuration
    """
    try:
        # Validate preset
        try:
            preset = ModelPreset(preset_name)
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid preset: {preset_name}. Valid options: {[p.value for p in ModelPreset]}"
            }

        # Get preset configuration
        config = _get_preset_config(preset)

        # Apply settings (in real usage, would save to file)
        # For now, just return what would be applied
        return {
            "success": True,
            "preset": preset_name,
            "applied_settings": config
        }

    except Exception as e:
        logger.error(f"Failed to apply preset: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_best_model_sync(category: str) -> Dict[str, Any]:
    """
    Get the recommended model for a feature category.

    Args:
        category: Feature category (backend, frontend, testing, documentation, infrastructure)

    Returns:
        Dictionary with recommended model and reasoning
    """
    try:
        # Default model mapping (could be enhanced with knowledge base)
        category_mapping = {
            "backend": "opus",
            "frontend": "opus",
            "testing": "haiku",
            "documentation": "haiku",
            "infrastructure": "opus",
            "database": "opus"
        }

        recommended = category_mapping.get(category.lower(), "sonnet")

        reasoning = {
            "backend": "Security-critical, complex architecture decisions",
            "frontend": "Complex UI logic, state management",
            "testing": "Simple patterns, fast iteration",
            "documentation": "Straightforward, fast generation",
            "infrastructure": "Complex configurations",
            "database": "Schema design critical"
        }.get(category.lower(), "General purpose")

        return {
            "success": True,
            "category": category,
            "recommended_model": recommended,
            "full_model_id": get_full_model_id(recommended),
            "reasoning": reasoning
        }

    except Exception as e:
        logger.error(f"Failed to get best model: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_settings_sync() -> Dict[str, Any]:
    """
    Get current model settings.

    Returns:
        Dictionary with current settings
    """
    try:
        # In real usage, would load from ~/.autocoder/model_settings.json
        # For now, return defaults
        return {
            "success": True,
            "settings": {
                "preset": "balanced",
                "available_models": ["opus", "haiku"],
                "auto_detect_simple": True,
                "category_mapping": {
                    "backend": "opus",
                    "frontend": "opus",
                    "testing": "haiku",
                    "documentation": "haiku"
                }
            }
        }

    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def update_settings_sync(
    preset: Optional[str] = None,
    available_models: Optional[str] = None,
    auto_detect_simple: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Update model settings.

    Args:
        preset: Preset name (optional)
        available_models: JSON array of model names (optional)
        auto_detect_simple: Boolean for simple task detection (optional)

    Returns:
        Dictionary with updated settings
    """
    try:
        updates = {}

        if preset:
            updates["preset"] = preset

        if available_models:
            try:
                models_list = json.loads(available_models)
                updates["available_models"] = models_list
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "available_models must be a JSON array"
                }

        if auto_detect_simple is not None:
            updates["auto_detect_simple"] = auto_detect_simple

        return {
            "success": True,
            "updated_settings": updates
        }

    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# Helper Functions
# ============================================================================

def _get_preset_description(preset: ModelPreset) -> str:
    """Get human-readable description for a preset."""
    descriptions = {
        ModelPreset.QUALITY: "Opus only - Maximum quality, highest cost",
        ModelPreset.BALANCED: "Opus + Haiku - Best value for Pro users (recommended)",
        ModelPreset.ECONOMY: "Opus + Sonnet + Haiku - Cost optimization",
        ModelPreset.CHEAP: "Sonnet + Haiku - Budget-friendly",
        ModelPreset.EXPERIMENTAL: "All models - Experimental AI selection"
    }
    return descriptions.get(preset, "Unknown preset")


def _get_preset_models(preset: ModelPreset) -> List[str]:
    """Get models used in a preset."""
    models = {
        ModelPreset.QUALITY: ["opus"],
        ModelPreset.BALANCED: ["opus", "haiku"],
        ModelPreset.ECONOMY: ["opus", "sonnet", "haiku"],
        ModelPreset.CHEAP: ["sonnet", "haiku"],
        ModelPreset.EXPERIMENTAL: ["opus", "sonnet", "haiku"]
    }
    return models.get(preset, [])


def _get_preset_config(preset: ModelPreset) -> Dict[str, Any]:
    """Get full configuration for a preset."""
    return {
        "preset": preset.value,
        "available_models": _get_preset_models(preset),
        "auto_detect_simple": True,
        "category_mapping": {
            "backend": "opus",
            "frontend": "opus",
            "testing": "haiku",
            "documentation": "haiku",
            "infrastructure": "opus"
        }
    }


# ============================================================================
# MCP Tool Definitions (FastMCP)
# ============================================================================

if FASTMCP_AVAILABLE:

    @mcp.tool()
    def get_presets() -> str:
        """
        Get all available model presets.

        A preset is a pre-configured set of models optimized for different use cases:
        - quality: Opus only (maximum quality)
        - balanced: Opus + Haiku (recommended for Pro users)
        - economy: Opus + Sonnet + Haiku (cost optimization)
        - cheap: Sonnet + Haiku (budget-friendly)
        - experimental: All models with AI selection

        Returns:
            JSON string with all presets and their model configurations
        """
        result = get_presets_sync()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def apply_preset(preset_name: str) -> str:
        """
        Apply a model preset configuration.

        Args:
            preset_name: Name of the preset to apply
                (quality, balanced, economy, cheap, experimental)

        Returns:
            JSON string with the applied configuration

        Example:
            apply_preset("balanced")
            → Applies Opus + Haiku configuration
        """
        result = apply_preset_sync(preset_name)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_best_model(category: str) -> str:
        """
        Get the recommended Claude model for a feature category.

        Uses category-based mapping to recommend which model works best:
        - backend/infrastructure/database: opus (complex, security-critical)
        - frontend: opus (complex UI logic)
        - testing/documentation: haiku (simple, fast)

        Args:
            category: Feature category
                (backend, frontend, testing, documentation, infrastructure, database)

        Returns:
            JSON string with recommended model and reasoning

        Example:
            get_best_model("testing")
            → Returns haiku (fast for simple test patterns)
        """
        result = get_best_model_sync(category)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_settings() -> str:
        """
        Get current model selection settings.

        Returns:
            JSON string with current configuration including preset,
            available models, and category mapping
        """
        result = get_settings_sync()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def update_settings(
        preset: Optional[str] = None,
        available_models: Optional[str] = None,
        auto_detect_simple: Optional[bool] = None
    ) -> str:
        """
        Update model selection settings.

        Args:
            preset: Preset name to apply (optional)
            available_models: JSON array of model names (optional)
                Example: '["opus", "haiku"]'
            auto_detect_simple: Enable simple task detection (optional)

        Returns:
            JSON string with updated settings

        Example:
            update_settings(
                preset="balanced",
                available_models='["opus", "haiku"]',
                auto_detect_simple=true
            )
        """
        result = update_settings_sync(
            preset=preset,
            available_models=available_models,
            auto_detect_simple=auto_detect_simple
        )
        return json.dumps(result, indent=2)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the MCP server."""
    if not FASTMCP_AVAILABLE:
        print("ERROR: FastMCP is not installed!")
        print("Install it with: pip install fastmcp")
        return 1

    if mcp:
        mcp.run()
    else:
        print("ERROR: MCP server not initialized")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
