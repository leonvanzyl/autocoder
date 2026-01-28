# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an autonomous coding agent system with a React-based UI. It uses the Claude Agent SDK to build complete applications over multiple sessions using a **multi-agent architecture**:

### Agent Types

1. **Architect Agent** - Designs system architecture, makes high-level technical decisions
2. **Initializer Agent** - First session reads an app spec and creates phases, features, and tasks
3. **Coding Agent** - Implements tasks one by one, following architectural decisions
4. **Reviewer Agent** - Reviews completed code for quality, security, and best practices
5. **Testing Agent** - Runs tests, validates implementations, and reports issues

### Hierarchical Structure

The system uses a four-level hierarchy:
```
Project → Phases → Features → Tasks
```

- **Projects**: Top-level container, stored anywhere and registered in `~/.autocoder/registry.db`
- **Phases**: Development stages with approval gates (e.g., "Foundation", "Core Features", "Polish")
- **Features**: Groupings of related tasks (e.g., "User Authentication", "Dashboard")
- **Tasks**: Individual implementation items with dependencies, complexity estimates, and verification steps

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

# Multi-model: use different models per agent type (cost optimization)
python autonomous_agent_demo.py --project-dir my-app \
  --architect-model claude-opus-4-5-20251101 \
  --coding-model claude-sonnet-4-5-20250929 \
  --reviewer-model claude-sonnet-4-5-20250929 \
  --testing-model claude-3-5-haiku-20241022

# Or use a single model for all agent types
python autonomous_agent_demo.py --project-dir my-app --model claude-sonnet-4-5-20250929
```

### Multi-Model Agent Support

Different agent types can use different Claude models to optimize cost:

| Agent Type | Default Model | Purpose |
|------------|---------------|---------|
| Architect | claude-opus-4-5 | System design (needs deep reasoning) |
| Initializer | claude-opus-4-5 | Spec analysis, feature creation |
| Coding | claude-sonnet-4-5 | Implementation (good balance) |
| Reviewer | claude-sonnet-4-5 | Code review |
| Testing | claude-3-5-haiku | Test execution (cheapest) |

Override per agent type with CLI flags (`--architect-model`, `--coding-model`, etc.)
or set a single model for all with `--model`.

### YOLO Modes (Rapid Prototyping)

YOLO modes offer different trade-offs between speed and verification:

```bash
# CLI - Basic YOLO (no browser testing)
python autonomous_agent_demo.py --project-dir my-app --yolo

# CLI - YOLO with review (AI code review instead of tests)
python autonomous_agent_demo.py --project-dir my-app --yolo-review

# UI: Use the YOLO mode selector dropdown before starting the agent
```

**Available YOLO Modes:**

| Mode | Description | Testing | Review | Use Case |
|------|-------------|---------|--------|----------|
| Standard | Full verification | ✅ | ✅ | Production quality |
| YOLO | Skip browser tests | ❌ | ❌ | Fast prototyping |
| YOLO + Review | AI code review | ❌ | ✅ | Balance speed/quality |
| YOLO Parallel | Concurrent tasks | ❌ | ❌ | Independent features |
| YOLO Staged | Batch verification | Staged | Staged | Large feature sets |

**What's the same across all modes:**
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

### Multi-Agent Modules

- `agent_types.py` - Agent type enum, selection logic, orchestration, and ModelConfig
- `shared_context.py` - Inter-agent communication (messages, decisions, findings)
- `yolo_modes.py` - YOLO mode configurations and feature flags
- `usage_tracking.py` - API usage monitoring with daily/monthly budgets
- `smart_scheduler.py` - Usage-aware task scheduling with strategies

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

### Task & Feature Management

Tasks are stored in SQLite (`features.db`) via SQLAlchemy with a hierarchical structure. The agent interacts through MCP servers:

- `mcp_server/feature_mcp.py` - MCP server for task/feature management
- `mcp_server/agent_mcp.py` - MCP server for inter-agent communication
- `api/database.py` - SQLAlchemy models:
  - `Phase` - Development stages with approval workflow
  - `Feature` - Groups of related tasks
  - `Task` - Individual work items with dependencies
  - `UsageLog` - API usage tracking
  - `LegacyFeature` - Backward compatibility with v1 schema

**Task MCP Tools:**
- `task_get_stats` - Progress statistics by phase/feature
- `task_get_next` - Get highest-priority ready task (respects dependencies)
- `task_get_for_regression` - Random passing tasks for regression testing
- `task_mark_passing` - Mark task complete
- `task_skip` - Move task to end of queue
- `task_create_bulk` - Initialize tasks (used by initializer)
- `task_validate_dependencies` - Check for dependency cycles
- `task_get_critical_path` - Calculate critical path for estimation

**Agent Communication MCP Tools:**
- `agent_send_message` - Send message to another agent type
- `agent_get_messages` - Retrieve messages for current agent
- `agent_record_decision` - Record architectural decisions
- `agent_add_finding` - Add code review findings

### Task Dependencies

Tasks can have dependencies on other tasks, creating a directed acyclic graph (DAG):

```python
# Example: Task B depends on Task A
task_b.depends_on = [task_a.id]

# The system ensures:
# - No circular dependencies (validated on creation)
# - Blocked tasks are skipped in scheduling
# - Critical path calculated for estimation
```

### Phase Workflow

Phases follow a state machine:
```
pending → in_progress → awaiting_approval → completed
                ↓              ↓
            (restart)      (reject)
```

- **pending**: Phase not yet started
- **in_progress**: Tasks being worked on
- **awaiting_approval**: All tasks complete, waiting for human review
- **completed**: Approved and finalized

### React UI (ui/)

- Tech stack: React 18, TypeScript, TanStack Query, Tailwind CSS v4, Radix UI
- `src/App.tsx` - Main app with project selection, kanban board, agent controls
- `src/hooks/useWebSocket.ts` - Real-time updates via WebSocket
- `src/hooks/useProjects.ts` - React Query hooks for API calls
- `src/lib/api.ts` - REST API client
- `src/lib/types.ts` - TypeScript type definitions

**Core Components:**
- `src/components/FolderBrowser.tsx` - Server-side filesystem browser
- `src/components/NewProjectModal.tsx` - Multi-step project creation wizard
- `src/components/AddFeatureModal.tsx` - Add features with task generation

**Navigation & Drill-Down:**
- `src/components/Breadcrumb.tsx` - Hierarchical navigation
- `src/components/DrillDownContainer.tsx` - URL-based navigation state
- `src/components/ProjectGrid.tsx` - Project overview cards
- `src/components/FeatureList.tsx` - Expandable feature groups

**Phase Management:**
- `src/components/PhaseCard.tsx` - Phase status and actions
- `src/components/PhaseTimeline.tsx` - Visual phase progress
- `src/components/PhaseApprovalModal.tsx` - Approval workflow

**Task Visualization:**
- `src/components/FeatureCard.tsx` - Task cards with blocked indicators
- `src/components/DependencyGraph.tsx` - SVG-based DAG visualization
- `src/components/YoloModeSelector.tsx` - YOLO mode dropdown

**Agent Monitoring:**
- `src/components/AgentDashboard.tsx` - Multi-agent status view
- `src/components/AgentTimeline.tsx` - Agent activity events

**Architect Assistant:**
- `src/components/AssistantPanel.tsx` - Slide-in panel for the Architect Assistant
- `src/components/AssistantChat.tsx` - Chat interface with streaming responses
- `src/components/AssistantQuickActions.tsx` - Quick action buttons
- `src/components/ChatMessage.tsx` - Message display with markdown

**Usage Monitoring:**
- `src/components/UsageDashboard.tsx` - Usage overview with budgets
- `src/components/UsageChart.tsx` - Usage timeline visualization
- `src/components/UsageWarning.tsx` - Budget alert banners

### Project Structure for Generated Apps

Projects can be stored in any directory (registered in `~/.autocoder/registry.db`). Each project contains:
- `prompts/app_spec.txt` - Application specification (XML format)
- `prompts/initializer_prompt.md` - First session prompt
- `prompts/coding_prompt.md` - Continuation session prompt
- `features.db` - SQLite database with feature test cases
- `.agent.lock` - Lock file to prevent multiple agent instances

### Security Model

Defense-in-depth approach configured in `client.py`:
1. OS-level sandbox for bash commands
2. Filesystem restricted to project directory only
3. Bash commands validated against `ALLOWED_COMMANDS` in `security.py`

## Claude Code Integration

- `.claude/commands/create-spec.md` - `/create-spec` slash command for interactive spec creation
- `.claude/skills/frontend-design/SKILL.md` - Skill for distinctive UI design
- `.claude/templates/` - Prompt templates copied to new projects

### Agent Prompt Templates

- `architect_prompt.template.md` - Architecture design and decisions
- `initializer_prompt.template.md` - Project setup and task creation
- `coding_prompt.template.md` - Task implementation
- `coding_prompt_yolo_review.template.md` - YOLO mode with AI review
- `reviewer_prompt.template.md` - Code review and findings
- `testing_prompt.template.md` - Test execution and validation

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

### Git Branching Workflow

Agents automatically use feature branches for version control:

- **Initializer** creates `feature/autocoder-dev` branch after `git init`
- **Coding agents** check out `feature/autocoder-dev` at session start
- The `main` branch stays clean and only receives merged code
- The UI displays real-time git status (branch, last commit, dirty state)

**API endpoint:** `GET /api/projects/{name}/agent/git` returns:
- Current branch name
- Last commit hash, message, and time
- Whether there are uncommitted changes
- Total commit count

### Design System

The UI uses a **neobrutalism** design with Tailwind CSS v4:
- CSS variables defined in `ui/src/styles/globals.css` via `@theme` directive
- Custom animations: `animate-slide-in`, `animate-pulse-neo`, `animate-shimmer`
- Color tokens: `--color-neo-pending` (yellow), `--color-neo-progress` (cyan), `--color-neo-done` (green)

### Usage Tracking & Smart Scheduling

The system monitors API usage and adjusts scheduling behavior:

```python
# Usage levels determine scheduling strategy
CRITICAL  # < 5% remaining  → Stop all new work
LOW       # 5-20% remaining → Wind down, finish in-progress only
MODERATE  # 20-50% remaining → Focus on completing features
HEALTHY   # > 50% remaining → Normal operation
```

**Scheduling Strategies:**
- `FULL_SPEED` - Normal priority-based scheduling
- `COMPLETION_FOCUS` - Prioritize nearly-done features
- `WIND_DOWN` - Only complete in-progress tasks
- `STOP` - No new tasks, critical usage

### Multi-Agent Communication

Agents communicate through a shared context system:

```python
# Send message to another agent
shared_context.add_message(
    from_agent="coding",
    to_agent="reviewer",
    message="Feature X implementation complete",
    metadata={"feature_id": 123}
)

# Record architectural decision
shared_context.add_decision(
    category="database",
    decision="Use SQLite for local storage",
    rationale="Simple setup, sufficient for single-user",
    made_by="architect"
)

# Add review finding
shared_context.add_finding(
    file_path="src/auth.py",
    severity="warning",
    finding="Password not hashed before storage",
    suggestion="Use bcrypt for password hashing"
)
```

### Database Migration

The system supports both legacy (v1) and new (v2) schema:

- Legacy projects use the `LegacyFeature` model
- New projects use `Phase → Feature → Task` hierarchy
- Migration script available: `python -m api.migration --project-dir <path>`
- Schema version tracked in database metadata

### Architect Assistant

The Architect Assistant is the central command hub for project management. Access it via the chat icon in the UI.

**Capabilities:**
- **Read & Understand**: Browse code, search patterns, view documentation
- **Create Features**: Design features with tasks through conversation
- **Manage Agents**: Start/stop/pause coding agents, set YOLO modes
- **Track Progress**: View phase status, task completion, dependencies
- **Handle Migrations**: Check and run schema migrations

**Backend Components:**
- `server/services/assistant_chat_session.py` - Claude SDK session with MCP tools
- `server/routers/assistant_chat.py` - WebSocket endpoint for streaming
- `mcp_server/assistant_actions_mcp.py` - Action tools for project management

**Example Interactions:**
```
User: "Add a feature for user authentication"
Assistant: [Creates feature with login, registration, session tasks]

User: "Start the agent in YOLO mode"
Assistant: [Starts coding agent with yolo_mode="yolo"]

User: "What's the project status?"
Assistant: [Shows phases, tasks, completion percentage]
```

**Quick Actions:**
The assistant provides contextual quick action buttons:
- Project Status, Add Feature, Start/Stop Agent
- YOLO Mode, Check Dependencies, Submit Phase
