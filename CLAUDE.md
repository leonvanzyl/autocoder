# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an autonomous coding agent system with a React-based UI. It uses the Claude Agent SDK to build complete applications with **three interactive chat systems** for different phases of development:

1. **Spec Chat** (Project Creation) - Interactive Q&A to create your project specification and initial feature list
2. **Assistant Chat** (Ongoing Development) - Discuss code, manage features, add/modify/delete features from the database
3. **Coding Agent** (Implementation) - Autonomous agent that implements features one by one with full read/write + browser testing access

## Commands

### Quick Start (Recommended)

```bash
# Windows - launches CLI menu
start.bat

# macOS/Linux
./start.sh

# Launch Web UI (serves pre-built React app)
start_ui.bat      # Windows
./start_ui.sh     # macOS/Linux
```

### Python Backend (Manual)

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the main CLI launcher
python start.py

# Run agent directly for a project (use absolute path or registered name)
python autonomous_agent_demo.py --project-dir C:/Projects/my-app
python autonomous_agent_demo.py --project-dir my-app  # if registered

# YOLO mode: rapid prototyping without browser testing
python autonomous_agent_demo.py --project-dir my-app --yolo
```

### YOLO Mode (Rapid Prototyping)

YOLO mode skips all testing for faster feature iteration:

```bash
# CLI
python autonomous_agent_demo.py --project-dir my-app --yolo

# UI: Toggle the lightning bolt button before starting the agent
```

**What's different in YOLO mode:**
- No regression testing (skips `feature_get_for_regression`)
- No Playwright MCP server (browser automation disabled)
- Features marked passing after lint/type-check succeeds
- Faster iteration for prototyping

**What's the same:**
- Lint and type-check still run to verify code compiles
- Feature MCP server for tracking progress
- All other development tools available

**When to use:** Early prototyping when you want to quickly scaffold features without verification overhead. Switch back to standard mode for production-quality development.

### React UI (in ui/ directory)

```bash
cd ui
npm install
npm run dev      # Development server (hot reload)
npm run build    # Production build (required for start_ui.bat)
npm run lint     # Run ESLint
```

**Note:** The `start_ui.bat` script serves the pre-built UI from `ui/dist/`. After making UI changes, run `npm run build` in the `ui/` directory.

## Architecture

### Core Python Modules

- `start.py` - CLI launcher with project creation/selection menu
- `autonomous_agent_demo.py` - Entry point for running the agent
- `agent.py` - Agent session loop using Claude Agent SDK
- `client.py` - ClaudeSDKClient configuration with security hooks and MCP servers
- `security.py` - Bash command allowlist validation (ALLOWED_COMMANDS whitelist)
- `prompts.py` - Prompt template loading with project-specific fallback
- `progress.py` - Progress tracking, database queries, webhook notifications
- `registry.py` - Project registry for mapping names to paths (cross-platform)

### Project Registry

Projects can be stored in any directory. The registry maps project names to paths using SQLite:
- **All platforms**: `~/.autocoder/registry.db`

The registry uses:
- SQLite database with SQLAlchemy ORM
- POSIX path format (forward slashes) for cross-platform compatibility
- SQLite's built-in transaction handling for concurrency safety

### Server API (server/)

The FastAPI server provides REST endpoints for the UI:

- `server/routers/projects.py` - Project CRUD with registry integration
- `server/routers/features.py` - Feature management
- `server/routers/agent.py` - Agent control (start/stop/pause/resume)
- `server/routers/filesystem.py` - Filesystem browser API with security controls
- `server/routers/spec_creation.py` - WebSocket for interactive spec creation
- `server/routers/assistant_chat.py` - WebSocket for project assistant chat

### Feature Management

Features are stored in SQLite (`features.db`) via SQLAlchemy. The agent interacts with features through an MCP server:

- `mcp_server/feature_mcp.py` - MCP server exposing feature management tools
- `api/database.py` - SQLAlchemy models (Feature table with priority, category, name, description, steps, passes)

MCP tools available to the agent:
- `feature_get_stats` - Progress statistics
- `feature_get_next` - Get highest-priority pending feature
- `feature_get_for_regression` - Random passing features for regression testing
- `feature_mark_passing` - Mark feature complete
- `feature_skip` - Move feature to end of queue
- `feature_create_bulk` - Initialize all features (used by initializer)

Additional tools available to Assistant Chat:
- `feature_get_all` - Get all features with full details
- `feature_get_by_id` - Get a specific feature's details
- `feature_update` - Modify an existing feature
- `feature_delete` - Remove a feature

### Assistant Chat (Project Assistant)

The project assistant is a read-only planning assistant that helps manage your feature list:

**Location**: Press `A` in the UI or use `server/routers/assistant_chat.py`

**Capabilities**:
- Read and analyze source code
- Search the codebase (Glob, Grep)
- Look up documentation online (WebFetch, WebSearch)
- **Manage features** (add, modify, delete in database)
- **Browser automation** - Visit pages, take screenshots, test UI (Playwright)
- Track progress and see feature status
- **Cannot modify files** (use coding agent for implementation)

**Key Features**:
1. **Context-Aware** - Loads your `app_spec.txt` to understand project architecture, tech stack, and goals
2. **Smart Feature Management** - Analyzes existing features before suggesting changes
3. **Browser Automation** - Can visit your running app, take screenshots, test functionality
4. **Confirmation Required** - Always asks before adding/modifying/deleting features
5. **Conversation History** - Conversations persist to `assistant.db` for continuity
6. **Image Support** - Can receive and view images for visual context
7. **Visual Debugging** - Uses browser to verify UI state and diagnose issues

**Workflow**:
```
1. Chat with assistant about what you want to build/change
2. Assistant reads current feature list from database
3. If discussing UI, assistant visits the app in browser to see current state
4. Suggests specific changes (add/modify/delete) with visual context
5. You confirm the changes
6. Assistant updates the feature database
7. Start/pause coding agent to implement updated features
```

**When to Use**:
- Planning new features mid-development
- Modifying existing feature requirements
- Removing obsolete features
- Understanding the codebase
- Discussing architecture decisions
- **Debugging UI issues** - Assistant can visit the page, take screenshots, test functionality
- **Verifying features** - Check if something works before suggesting changes

### React UI (ui/)

- Tech stack: React 18, TypeScript, TanStack Query, Tailwind CSS v4, Radix UI
- `src/App.tsx` - Main app with project selection, kanban board, agent controls
- `src/hooks/useWebSocket.ts` - Real-time updates via WebSocket
- `src/hooks/useProjects.ts` - React Query hooks for API calls
- `src/hooks/useAssistantChat.ts` - Hook for assistant chat WebSocket connection
- `src/hooks/useAssistantConversations.ts` - Hook for conversation history management
- `src/lib/api.ts` - REST API client
- `src/lib/types.ts` - TypeScript type definitions
- `src/components/FolderBrowser.tsx` - Server-side filesystem browser for project folder selection
- `src/components/NewProjectModal.tsx` - Multi-step project creation wizard
- `src/components/AssistantChat.tsx` - Chat interface for the project assistant
- `src/components/AssistantPanel.tsx` - Slide-in panel container for assistant chat
- `src/components/ConversationHistory.tsx` - Sidebar showing past assistant conversations
- `src/components/ConfirmationDialog.tsx` - Neobrutalist-styled confirmation modal
- `src/components/ChatMessage.tsx` - Message display with support for images and code blocks

### Project Structure for Generated Apps

Projects can be stored in any directory (registered in `~/.autocoder/registry.db`). Each project contains:
- `prompts/app_spec.txt` - Application specification (XML format)
- `prompts/initializer_prompt.md` - First session prompt
- `prompts/coding_prompt.md` - Continuation session prompt
- `features.db` - SQLite database with feature test cases
- `assistant.db` - SQLite database with assistant conversation history
- `.agent.lock` - Lock file to prevent multiple agent instances

### Security Model

Defense-in-depth approach configured in `client.py`:
1. OS-level sandbox for bash commands
2. Filesystem restricted to project directory only
3. Bash commands validated against `ALLOWED_COMMANDS` in `security.py`

### Three-Chat Architecture

The system uses three different chat interfaces for different development phases:

#### 1. Spec Chat (Project Creation)
- **Purpose**: Create initial project specification
- **When**: First time creating a project
- **Tools**: None (Q&A only)
- **Output**: `app_spec.txt` + initial feature list
- **UI**: Multi-step wizard in NewProjectModal
- **Endpoint**: `server/routers/spec_creation.py` WebSocket

#### 2. Assistant Chat (Ongoing Planning)
- **Purpose**: Manage features, discuss code, plan additions, test UI
- **When**: Anytime during development
- **Tools**: Read, Glob, Grep, WebFetch, WebSearch, feature_get_*, feature_create_bulk, feature_update, feature_delete, **Playwright browser automation**
- **Capabilities**: Read-only for files, can modify feature database, can visit/test running app
- **Context**: Loads `app_spec.txt` for project awareness
- **UI**: Press `A` or click floating button
- **Endpoint**: `server/routers/assistant_chat.py` WebSocket
- **Database**: `assistant.db` for conversation history
- **Browser**: Playwright MCP for visiting pages, taking screenshots, testing UI

#### 3. Coding Agent (Implementation)
- **Purpose**: Implement features autonomously
- **When**: Started manually or via API
- **Tools**: Full access (Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch)
- **Browser**: Playwright MCP for testing (unless YOLO mode)
- **Capabilities**: Read + Write files, run commands, browser automation
- **Endpoint**: `server/routers/agent.py` REST API
- **Session**: Runs via `autonomous_agent_demo.py`

#### Workflow Integration:
```
1. Create Project → Spec Chat creates app_spec.txt + initial features
2. Development → Use Assistant Chat to add/modify features as needed
3. Implement → Start Coding Agent to build features
4. Iterate → Pause agent, chat with assistant, modify features, resume
```

## Claude Code Integration

- `.claude/commands/create-spec.md` - `/create-spec` slash command for interactive spec creation
- `.claude/skills/frontend-design/SKILL.md` - Skill for distinctive UI design
- `.claude/templates/` - Prompt templates copied to new projects

## Key Patterns

### Prompt Loading Fallback Chain

1. Project-specific: `{project_dir}/prompts/{name}.md`
2. Base template: `.claude/templates/{name}.template.md`

### Agent Session Flow

1. Check if `features.db` has features (determines initializer vs coding agent)
2. Create ClaudeSDKClient with security settings
3. Send prompt and stream response
4. Auto-continue with 3-second delay between sessions

### Real-time UI Updates

The UI receives updates via WebSocket (`/ws/projects/{project_name}`):
- `progress` - Test pass counts
- `agent_status` - Running/paused/stopped/crashed
- `log` - Agent output lines (streamed from subprocess stdout)
- `feature_update` - Feature status changes

### Design System

The UI uses a **neobrutalism** design with Tailwind CSS v4:
- CSS variables defined in `ui/src/styles/globals.css` via `@theme` directive
- Custom animations: `animate-slide-in`, `animate-pulse-neo`, `animate-shimmer`
- Color tokens: `--color-neo-pending` (yellow), `--color-neo-progress` (cyan), `--color-neo-done` (green)
