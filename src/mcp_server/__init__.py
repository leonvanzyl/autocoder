"""
Compatibility package for MCP servers.

Some parts of the codebase (and upstream) invoke MCP servers via:

  `python -m mcp_server.<name>`

This repo keeps the MCP implementations under `autocoder.tools.*`, but we ship this
shim package so those module paths remain valid.
"""

