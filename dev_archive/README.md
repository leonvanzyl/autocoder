# Development Archive

This directory contains obsolete or superseded development files that are kept for historical reference but are no longer used in the active codebase.

## 📦 Archived Files

### `agent_manager.py` (Superseded)
**Status:** Replaced by `orchestrator.py`

**Why archived:**
- Used database locking approach for parallel agents
- Only simulated work (TODO comment in code)
- Replaced by production-ready orchestrator with:
  - Git worktrees for isolation
  - Real agent execution
  - Gatekeeper verification
  - Crash recovery

**Replaced by:** `orchestrator.py` (in root)

### `inspect_knowledge.py` (Development Tool)
**Status:** Development/testing tool

**Why archived:**
- Used for inspecting knowledge base during development
- Manual inspection script
- No longer needed in production

**Functionality now:** Available through MCP tools and database queries

### `knowledge_base_demo.py` (Demo Script)
**Status:** Demo/prototype script

**Why archived:**
- Early demonstration script for knowledge base
- Prototype code
- Functionality integrated into main system

**Functionality now:** Part of `knowledge_base.py` and MCP server

### `test_knowledge_base.py` (Test Script)
**Status:** Development test script

**Why archived:**
- Early testing script for knowledge base
- Manual testing
- Superseded by automated tests

**Testing now:** Use `test_framework_detector.py` and MCP test tools

### `verify_knowledge_base.py` (Verification Script)
**Status:** Development verification script

**Why archived:**
- Used to verify knowledge base integrity
- One-off verification script
- No longer needed

**Functionality now:** Integrated into system health checks

## 🔄 Migration Path

If you're looking for functionality from these archived files:

| Old File | New Location | Notes |
|----------|--------------|-------|
| `agent_manager.py` | `orchestrator.py` | Production-ready implementation |
| `inspect_knowledge.py` | `mcp_server/knowledge_mcp.py` | MCP tools for querying |
| `knowledge_base_demo.py` | `knowledge_base.py` | Core implementation |
| `test_knowledge_base.py` | `test_framework_detector.py` | Test framework detection |
| `verify_knowledge_base.py` | `database.py` | Database operations |

## 📋 Historical Notes

These files were created during the research and development phase of the parallel agent system. They represent:
- Early prototypes and experiments
- Development and testing utilities
- Superseded implementations

**Why keep them?**
- Historical reference
- Understanding development decisions
- Learning from early iterations

**Why not in main codebase?**
- Superseded by better implementations
- Could confuse users
- Not production-ready
- Maintenance burden

## 🚫 Do Not Use

**⚠️ These files are NOT maintained and should NOT be used in production.**

They are kept for:
- Historical reference
- Understanding development journey
- Learning from past iterations

For current functionality, see the main codebase files in the root directory.

## 📚 See Also

- [docs/README.md](../docs/README.md) - Active documentation
- [README.md](../README.md) - Main project README
- [CHANGELOG.md](../CHANGELOG.md) - Version history
