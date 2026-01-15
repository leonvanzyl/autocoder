"""
Compatibility shim for `python -m mcp_server.feature_mcp`.

The real implementation lives at `autocoder.tools.feature_mcp`.
"""

from autocoder.tools.feature_mcp import mcp


if __name__ == "__main__":
    mcp.run()

