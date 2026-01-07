"""
MCP Knowledge Server
====================

Exposes the Knowledge Base as Model Context Protocol tools.

This allows Claude agents (workers) to:
1. Query the knowledge base for similar features
2. Get reference implementations
3. Store patterns they discover
4. Learn which approaches work best

IMPORTANT: This is for AGENTS (LLMs) to use.
The Orchestrator (Python code) should import KnowledgeBase directly.
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

# Import KnowledgeBase
from autocoder.core.knowledge_base import KnowledgeBase, get_knowledge_base

logger = __import__("logging").getLogger(__name__)

# Initialize MCP Server
if FASTMCP_AVAILABLE:
    mcp = FastMCP("Knowledge Base")
else:
    mcp = None


# ============================================================================
# Synchronous Wrappers (for MCP tools)
# ============================================================================

def get_similar_features_sync(
    feature_category: str,
    feature_name: str,
    feature_description: str,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Find features similar to the current feature.

    Args:
        feature_category: Category of the feature (backend, frontend, etc.)
        feature_name: Name of the feature
        feature_description: Description of what the feature does
        limit: Maximum number of similar features to return

    Returns:
        Dictionary with similar features and lessons learned
    """
    try:
        kb = get_knowledge_base()

        feature = {
            "category": feature_category,
            "name": feature_name,
            "description": feature_description
        }

        similar = kb.get_similar_features(feature, limit=limit)

        return {
            "success": True,
            "current_feature": feature,
            "similar_features": similar,
            "count": len(similar)
        }

    except Exception as e:
        logger.error(f"Failed to find similar features: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_reference_prompt_sync(
    feature_category: str,
    feature_name: str,
    feature_description: str
) -> Dict[str, Any]:
    """
    Generate a prompt enhancement with reference examples from similar features.

    This is the MAIN tool agents should use before implementing a feature.

    Args:
        feature_category: Category of the feature
        feature_name: Name of the feature
        feature_description: Description of what the feature does

    Returns:
        Dictionary with enhanced prompt containing reference examples
    """
    try:
        kb = get_knowledge_base()

        feature = {
            "category": feature_category,
            "name": feature_name,
            "description": feature_description
        }

        reference_prompt = kb.get_reference_prompt(feature)

        return {
            "success": True,
            "feature": feature,
            "reference_prompt": reference_prompt,
            "has_examples": "REFERENCE IMPLEMENTATIONS" in reference_prompt
        }

    except Exception as e:
        logger.error(f"Failed to generate reference prompt: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_best_model_sync(feature_category: str) -> Dict[str, Any]:
    """
    Get the best model to use for a specific feature category.

    Uses historical data to determine which model works best.

    Args:
        feature_category: Category of the feature (backend, frontend, testing, etc.)

    Returns:
        Dictionary with recommended model and success rate
    """
    try:
        kb = get_knowledge_base()

        model_info = kb.get_best_model(feature_category)

        return {
            "success": True,
            "category": feature_category,
            "recommended_model": model_info
        }

    except Exception as e:
        logger.error(f"Failed to get best model: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def store_pattern_sync(
    feature_category: str,
    feature_name: str,
    feature_description: str,
    implementation_approach: str,
    files_changed: List[str],
    model_used: str,
    success: bool,
    attempts: int,
    lessons_learned: str
) -> Dict[str, Any]:
    """
    Store an implementation pattern in the knowledge base.

    Agents should call this after completing a feature.

    Args:
        feature_category: Category of the feature
        feature_name: Name of the feature
        feature_description: Description of the feature
        implementation_approach: How you implemented it
        files_changed: List of files created/modified
        model_used: Which Claude model was used
        success: Whether the feature was successful
        attempts: How many attempts it took
        lessons_learned: What you learned from this implementation

    Returns:
        Dictionary indicating success
    """
    try:
        kb = get_knowledge_base()

        feature = {
            "category": feature_category,
            "name": feature_name,
            "description": feature_description
        }

        implementation = {
            "approach": implementation_approach,
            "files_changed": files_changed,
            "model_used": model_used
        }

        kb.store_pattern(
            feature=feature,
            implementation=implementation,
            success=success,
            attempts=attempts,
            lessons_learned=lessons_learned
        )

        return {
            "success": True,
            "message": "Pattern stored successfully",
            "feature": feature_name
        }

    except Exception as e:
        logger.error(f"Failed to store pattern: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_knowledge_stats_sync() -> Dict[str, Any]:
    """
    Get statistics about the knowledge base.

    Returns:
        Dictionary with knowledge base metrics
    """
    try:
        kb = get_knowledge_base()

        # Get basic stats
        stats = {
            "total_patterns": "N/A",  # Would need to query DB
            "categories": ["backend", "frontend", "testing", "documentation", "infrastructure"],
            "models": ["opus", "sonnet", "haiku"]
        }

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# MCP Tool Definitions (FastMCP)
# ============================================================================

if FASTMCP_AVAILABLE:

    @mcp.tool()
    def get_similar_features(
        feature_category: str,
        feature_name: str,
        feature_description: str,
        limit: int = 5
    ) -> str:
        """
        Find features similar to the current feature in the knowledge base.

        Use this BEFORE implementing to learn from past successful features.

        Args:
            feature_category: Category (backend, frontend, testing, documentation, infrastructure)
            feature_name: Name of the feature you're implementing
            feature_description: What the feature does
            limit: Maximum number of similar features to return (default: 5)

        Returns:
            JSON string with similar features and what approaches they used
        """
        result = get_similar_features_sync(
            feature_category=feature_category,
            feature_name=feature_name,
            feature_description=feature_description,
            limit=limit
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_reference_prompt(
        feature_category: str,
        feature_name: str,
        feature_description: str
    ) -> str:
        """
        Generate an enhanced prompt with reference examples from similar features.

        This is the MOST IMPORTANT tool - use it before implementing any feature!
        It adds examples from past successful implementations to your context.

        Args:
            feature_category: Category (backend, frontend, testing, documentation, infrastructure)
            feature_name: Name of the feature you're implementing
            feature_description: What the feature does

        Returns:
            Enhanced prompt with reference implementations embedded
        """
        result = get_reference_prompt_sync(
            feature_category=feature_category,
            feature_name=feature_name,
            feature_description=feature_description
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_best_model(feature_category: str) -> str:
        """
        Get the best model to use for a specific feature category.

        Uses historical data from the knowledge base to recommend which model
        works best for this type of feature.

        Args:
            feature_category: Category (backend, frontend, testing, documentation, infrastructure)

        Returns:
            JSON string with recommended model and success rate
        """
        result = get_best_model_sync(feature_category)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def store_pattern(
        feature_category: str,
        feature_name: str,
        feature_description: str,
        implementation_approach: str,
        files_changed: str,  # JSON array string
        model_used: str,
        success: bool,
        attempts: int,
        lessons_learned: str
    ) -> str:
        """
        Store an implementation pattern in the knowledge base.

        Use this AFTER completing a feature to teach the system what worked.
        This makes future agents smarter!

        Args:
            feature_category: Category of the feature
            feature_name: Name of the feature
            feature_description: What the feature does
            implementation_approach: How you implemented it (e.g., "JWT with refresh tokens")
            files_changed: JSON array of files you created/modified
            model_used: Which Claude model you used (opus, sonnet, haiku)
            success: Whether the implementation was successful
            attempts: How many attempts it took
            lessons_learned: What you learned (e.g., "Refresh tokens more secure than cookies")

        Returns:
            JSON string confirming the pattern was stored
        """
        # Parse files_changed from JSON
        try:
            files_list = json.loads(files_changed)
        except json.JSONDecodeError:
            files_list = [files_changed]

        result = store_pattern_sync(
            feature_category=feature_category,
            feature_name=feature_name,
            feature_description=feature_description,
            implementation_approach=implementation_approach,
            files_changed=files_list,
            model_used=model_used,
            success=success,
            attempts=attempts,
            lessons_learned=lessons_learned
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_knowledge_stats() -> str:
        """
        Get statistics about the knowledge base.

        Shows how much the system has learned from past features.

        Returns:
            JSON string with knowledge base metrics
        """
        result = get_knowledge_stats_sync()
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
