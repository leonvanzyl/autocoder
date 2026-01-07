# Project Structure

Clean organization of the autonomous coding system.

## 📁 Directory Layout

```
autocoder/
├── src/                           # ⚙️ Core System
│   ├── __init__.py
│   ├── orchestrator.py            # 🧠 Parallel agent coordination
│   ├── gatekeeper.py              # 🛡️ Verification & merge
│   ├── worktree_manager.py        # 🌳 Git worktree management
│   ├── knowledge_base.py          # 📚 Learning system
│   ├── model_settings.py          # ⚙️ Model configuration
│   ├── test_framework_detector.py # 🧪 Test detection
│   └── database.py                # 💾 SQLite wrapper
│
├── Root (Python Files - Entry Points & Agent)
│   ├── start.py                   # 🖥️ Main CLI launcher
│   ├── start_ui.py                # 🌐 Web UI launcher
│   ├── autonomous_agent_demo.py   # 🤖 Single agent entry
│   ├── orchestrator_demo.py       # 🧠 Parallel agents entry
│   ├── agent.py                   # 🤖 Agent session loop
│   ├── client.py                  # 📡 Claude SDK client
│   ├── prompts.py                 # 📝 Prompt templates
│   ├── progress.py                # 📊 Progress tracking
│   ├── registry.py                # 🗂️ Project registry
│   ├── security.py                # 🛡️ Command validation
│   └── __init__.py                # Package init
│
├── server/                        # 🌐 FastAPI Server
│   ├── routers/                   # API endpoints
│   ├── services/                  # Business logic
│   ├── schemas.py                 # Pydantic models
│   └── websocket.py               # WebSocket handler
│
├── mcp_server/                    # 🔌 MCP Servers
│   ├── test_mcp.py                # Test framework tools
│   ├── knowledge_mcp.py           # Knowledge base tools
│   ├── model_settings_mcp.py      # Model selection tools
│   └── feature_mcp.py             # Feature management tools
│
├── ui/                            # 🎨 React UI
│   ├── src/                       # TypeScript source
│   ├── dist/                      # Built UI (served by server)
│   ├── package.json
│   └── vite.config.ts
│
├── api/                           # 📡 API Database (Legacy)
│   ├── database.py                # Feature database schema
│   └── migration.py               # Database migrations
│
├── docs/                          # 📚 Documentation
│   ├── README.md                  # Documentation index
│   ├── PARALLEL_MODE_UI.md        # Parallel mode usage guide
│   ├── SYSTEM_COMPLETE.md         # Complete system overview
│   ├── MCP_ARCHITECTURE.md        # MCP hybrid architecture
│   ├── TDD_WORKFLOW_WITH_MCP.md   # TDD workflow
│   ├── TEST_DETECTION_IMPROVEMENTS.md
│   ├── CRITICAL_FIXES.md          # Recent fixes
│   ├── KNOWLEDGE_BASE.md
│   ├── KNOWLEDGE_BASE_INTEGRATION.md
│   ├── KNOWLEDGE_BASE_SUMMARY.md
│   ├── PROMPT_FOR_OTHER_AI.md
│   └── SAMPLE_PROMPT.md
│
├── tests/                         # 🧪 Test Files
│   ├── README.md
│   └── test_security.py           # Security validation tests
│
├── dev_archive/                   # 📦 Archived Development Files
│   ├── README.md
│   ├── agent_manager.py           # Superseded by orchestrator.py
│   ├── inspect_knowledge.py       # Development tool
│   ├── knowledge_base_demo.py     # Demo script
│   ├── test_knowledge_base.py     # Old test script
│   └── verify_knowledge_base.py   # Verification script
│
├── research/                      # 🔬 Research Notes
└── to_check/                      # 📋 External Reference Repos
│
├── Root (Essential Files Only)
├── README.md                      # Main documentation
├── LICENSE.md                     # License
├── CHANGELOG.md                   # Version history
├── CLAUDE.md                      # Instructions for Claude Code
├── PROJECT_STRUCTURE.md           # This file
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment template
```

**Note:** Entry points and agent implementation files are in the root directory to maintain compatibility with the main repository structure. Only core system components are in `src/`.

## 📊 Module Organization

### src/ - Core System Components
The brain of the autonomous coding system.

**Key Files:**
- `orchestrator.py` - Coordinates parallel agents
- `gatekeeper.py` - Verifies and merges code
- `worktree_manager.py` - Manages git worktrees
- `knowledge_base.py` - Learns from patterns
- `model_settings.py` - Model selection logic
- `test_framework_detector.py` - Auto-detects test frameworks
- `database.py` - SQLite operations

**Usage:**
```python
from src import Orchestrator, Gatekeeper, WorktreeManager
```

### Root Directory - Entry Points & Agent Implementation
Command-line tools and agent session management (maintained in root for compatibility with main repository).

**Files:**
- `start.py` - Interactive CLI launcher
- `start_ui.py` - Web UI launcher
- `autonomous_agent_demo.py` - Single agent (sequential)
- `orchestrator_demo.py` - Parallel agents (3x faster)
- `agent.py` - Agent session loop
- `client.py` - Claude SDK client configuration
- `prompts.py` - Prompt template loading
- `progress.py` - Progress tracking
- `registry.py` - Project name → path mapping
- `security.py` - Command validation whitelist

**Usage:**
```bash
# Run CLI launcher
python start.py

# Run agent directly
python autonomous_agent_demo.py --project-dir my-app

# Run parallel agents
python orchestrator_demo.py --parallel 3 --preset balanced
```

**Import Examples:**
```python
# Import agent components
from agent import run_autonomous_agent, ClaudeSDKClient
from registry import get_project_path
from prompts import scaffold_project_prompts
```

### server/ - Web API
FastAPI server for React UI.

**Components:**
- `routers/` - API endpoints (projects, features, agent, filesystem)
- `services/` - Business logic (process manager, sessions)
- `schemas.py` - Pydantic models
- `websocket.py` - Real-time updates

### mcp_server/ - MCP Tools
Model Context Protocol servers for agents.

**Tools:**
- `test_mcp.py` - Test detection/execution
- `knowledge_mcp.py` - Knowledge base queries
- `model_settings_mcp.py` - Model selection
- `feature_mcp.py` - Feature management

## 🎯 Quick Reference

| What you need | Where to find it |
|----------------|------------------|
| **Start using** | [README.md](README.md) |
| **Architecture** | [docs/SYSTEM_COMPLETE.md](docs/SYSTEM_COMPLETE.md) |
| **Parallel mode** | [docs/PARALLEL_MODE_UI.md](docs/PARALLEL_MODE_UI.md) |
| **Run agents** | `autonomous_agent_demo.py` or `orchestrator_demo.py` |
| **Launch UI** | `start_ui.bat` or `python start_ui.py` |
| **Core system** | `src/` directory |
| **Agent code** | Root directory (`agent.py`, `client.py`, etc.) |
| **API server** | `server/` directory |
| **MCP tools** | `mcp_server/` directory |

## 🧹 Clean Structure Principles

1. **Root contains:**
   - Entry points and agent implementation (start.py, agent.py, client.py, etc.)
   - Essential documentation (README, LICENSE, CHANGELOG, CLAUDE.md)
   - Configuration files (requirements.txt, .env.example)
   - **Maintained for compatibility with main repository structure**

2. **src/ contains:**
   - Core system components (orchestrator, gatekeeper, worktree_manager, etc.)
   - No entry points or CLI tools
   - Pure business logic
   - Importable as a package

3. **docs/ contains:**
   - All documentation
   - Organized by topic

4. **tests/ contains:**
   - Test files
   - Test documentation

5. **dev_archive/ contains:**
   - Superseded code
   - Historical reference
   - NOT for production use

6. **server/ contains:**
   - FastAPI web server
   - API endpoints
   - Business logic for UI

7. **mcp_server/ contains:**
   - MCP server implementations
   - Tools for agents

## ✅ Benefits

- **Modular** - Clear separation of concerns
- **Maintainable** - Easy to find what you need
- **Scalable** - Room to grow without clutter
- **Professional** - Production-ready structure
- **Importable** - Can `import src` as a package
- **Compatible** - Root structure maintains compatibility with main repository

## 📦 Import Examples

```python
# Import core system
from src import Orchestrator, Gatekeeper, WorktreeManager

# Import agent components (from root)
from agent import run_autonomous_agent, ClaudeSDKClient
from registry import get_project_path
from prompts import scaffold_project_prompts

# Use from CLI scripts
from src.orchestrator import Orchestrator
from agent import run_autonomous_agent
```

