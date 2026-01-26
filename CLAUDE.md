# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an autonomous coding agent system with a React-based UI. It uses the Claude Agent SDK to build complete applications over multiple sessions using a two-agent pattern:

1. **Initializer Agent** - First session reads an app spec and creates features in a SQLite database
2. **Coding Agent** - Subsequent sessions implement features one by one, marking them as passing

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

# Parallel mode: run multiple agents concurrently (1-5 agents)
python autonomous_agent_demo.py --project-dir my-app --parallel --max-concurrency 3
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
- `parallel_orchestrator.py` - Concurrent agent execution with dependency-aware scheduling
- `api/dependency_resolver.py` - Cycle detection (Kahn's algorithm + DFS) and dependency validation

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

### Feature Management

Features are stored in SQLite (`features.db`) via SQLAlchemy. The agent interacts with features through an MCP server:

- `mcp_server/feature_mcp.py` - MCP server exposing feature management tools
- `api/database.py` - SQLAlchemy models (Feature table with priority, category, name, description, steps, passes, dependencies)

MCP tools available to the agent:
- `feature_get_stats` - Progress statistics
- `feature_get_next` - Get highest-priority pending feature (respects dependencies)
- `feature_claim_next` - Atomically claim next available feature (for parallel mode)
- `feature_get_for_regression` - Random passing features for regression testing
- `feature_mark_passing` - Mark feature complete
- `feature_skip` - Move feature to end of queue
- `feature_create_bulk` - Initialize all features (used by initializer)
- `feature_add_dependency` - Add dependency between features (with cycle detection)
- `feature_remove_dependency` - Remove a dependency

### React UI (ui/)

- Tech stack: React 18, TypeScript, TanStack Query, Tailwind CSS v4, Radix UI, dagre (graph layout)
- `src/App.tsx` - Main app with project selection, kanban board, agent controls
- `src/hooks/useWebSocket.ts` - Real-time updates via WebSocket (progress, agent status, logs, agent updates)
- `src/hooks/useProjects.ts` - React Query hooks for API calls
- `src/lib/api.ts` - REST API client
- `src/lib/types.ts` - TypeScript type definitions

Key components:
- `AgentMissionControl.tsx` - Dashboard showing active agents with mascots (Spark, Fizz, Octo, Hoot, Buzz)
- `DependencyGraph.tsx` - Interactive node graph visualization with dagre layout
- `CelebrationOverlay.tsx` - Confetti animation on feature completion
- `FolderBrowser.tsx` - Server-side filesystem browser for project folder selection

Keyboard shortcuts (press `?` for help):
- `D` - Toggle debug panel
- `G` - Toggle Kanban/Graph view
- `N` - Add new feature
- `A` - Toggle AI assistant
- `,` - Open settings

### Project Structure for Generated Apps

Projects can be stored in any directory (registered in `~/.autocoder/registry.db`). Each project contains:
- `prompts/app_spec.txt` - Application specification (XML format)
- `prompts/initializer_prompt.md` - First session prompt
- `prompts/coding_prompt.md` - Continuation session prompt
- `features.db` - SQLite database with feature test cases
- `.agent.lock` - Lock file to prevent multiple agent instances
- `.autocoder/allowed_commands.yaml` - Project-specific bash command allowlist (optional)

### Security Model

Defense-in-depth approach configured in `client.py`:
1. OS-level sandbox for bash commands
2. Filesystem restricted to project directory only
3. Bash commands validated using hierarchical allowlist system

#### Per-Project Allowed Commands

The agent's bash command access is controlled through a hierarchical configuration system:

**Command Hierarchy (highest to lowest priority):**
1. **Hardcoded Blocklist** (`security.py`) - NEVER allowed (dd, sudo, shutdown, etc.)
2. **Org Blocklist** (`~/.autocoder/config.yaml`) - Cannot be overridden by projects
3. **Org Allowlist** (`~/.autocoder/config.yaml`) - Available to all projects
4. **Global Allowlist** (`security.py`) - Default commands (npm, git, curl, etc.)
5. **Project Allowlist** (`.autocoder/allowed_commands.yaml`) - Project-specific commands

**Project Configuration:**

Each project can define custom allowed commands in `.autocoder/allowed_commands.yaml`:

```yaml
version: 1
commands:
  # Exact command names
  - name: swift
    description: Swift compiler

  # Prefix wildcards (matches swiftc, swiftlint, swiftformat)
  - name: swift*
    description: All Swift development tools

  # Local project scripts
  - name: ./scripts/build.sh
    description: Project build script
```

**Organization Configuration:**

System administrators can set org-wide policies in `~/.autocoder/config.yaml`:

```yaml
version: 1

# Commands available to ALL projects
allowed_commands:
  - name: jq
    description: JSON processor

# Commands blocked across ALL projects (cannot be overridden)
blocked_commands:
  - aws        # Prevent accidental cloud operations
  - kubectl    # Block production deployments
```

**Pattern Matching:**
- Exact: `swift` matches only `swift`
- Wildcard: `swift*` matches `swift`, `swiftc`, `swiftlint`, etc.
- Scripts: `./scripts/build.sh` matches the script by name from any directory

**Limits:**
- Maximum 100 commands per project config
- Blocklisted commands (sudo, dd, shutdown, etc.) can NEVER be allowed
- Org-level blocked commands cannot be overridden by project configs

**Testing:**
```bash
# Unit tests (136 tests - fast)
python test_security.py

# Integration tests (9 tests - uses real hooks)
python test_security_integration.py
```

**Files:**
- `security.py` - Command validation logic and hardcoded blocklist
- `test_security.py` - Unit tests for security system (136 tests)
- `test_security_integration.py` - Integration tests with real hooks (9 tests)
- `TEST_SECURITY.md` - Quick testing reference guide
- `examples/project_allowed_commands.yaml` - Project config example (all commented by default)
- `examples/org_config.yaml` - Org config example (all commented by default)
- `examples/README.md` - Comprehensive guide with use cases, testing, and troubleshooting
- `PHASE3_SPEC.md` - Specification for mid-session approval feature (future enhancement)

### Ollama Local Models (Optional)

Run coding agents using local models via Ollama v0.14.0+:

1. Install Ollama: https://ollama.com
2. Start Ollama: `ollama serve`
3. Pull a coding model: `ollama pull qwen3-coder`
4. Configure `.env`:
   ```
   ANTHROPIC_BASE_URL=http://localhost:11434
   ANTHROPIC_AUTH_TOKEN=ollama
   API_TIMEOUT_MS=3000000
   ANTHROPIC_DEFAULT_SONNET_MODEL=qwen3-coder
   ANTHROPIC_DEFAULT_OPUS_MODEL=qwen3-coder
   ANTHROPIC_DEFAULT_HAIKU_MODEL=qwen3-coder
   ```
5. Run autocoder normally - it will use your local Ollama models

**Recommended coding models:**
- `qwen3-coder` - Good balance of speed and capability
- `deepseek-coder-v2` - Strong coding performance
- `codellama` - Meta's code-focused model

**Model tier mapping:**
- Use the same model for all tiers, or map different models per capability level
- Larger models (70B+) work best for Opus tier
- Smaller models (7B-20B) work well for Haiku tier

**Known limitations:**
- Smaller context windows than Claude (model-dependent)
- Extended context beta disabled (not supported by Ollama)
- Performance depends on local hardware (GPU recommended)

## Claude Code Integration

- `.claude/commands/create-spec.md` - `/create-spec` slash command for interactive spec creation
- `.claude/skills/frontend-design/SKILL.md` - Skill for distinctive UI design
- `.claude/templates/` - Prompt templates copied to new projects
- `examples/` - Configuration examples and documentation for security settings

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
- `progress` - Test pass counts (passing, in_progress, total)
- `agent_status` - Running/paused/stopped/crashed
- `log` - Agent output lines with optional featureId/agentIndex for attribution
- `feature_update` - Feature status changes
- `agent_update` - Multi-agent state updates (thinking/working/testing/success/error) with mascot names

### Parallel Mode

When running with `--parallel`, the orchestrator:
1. Spawns multiple Claude agents as subprocesses (up to `--max-concurrency`)
2. Each agent claims features atomically via `feature_claim_next`
3. Features blocked by unmet dependencies are skipped
4. Browser contexts are isolated per agent using `--isolated` flag
5. AgentTracker parses output and emits `agent_update` messages for UI

### Process Limits (Parallel Mode)

The orchestrator enforces strict bounds on concurrent processes:
- `MAX_PARALLEL_AGENTS = 5` - Maximum concurrent coding agents
- `MAX_TOTAL_AGENTS = 10` - Hard limit on total agents (coding + testing)
- Testing agents are capped at `max_concurrency` (same as coding agents)

**Expected process count during normal operation:**
- 1 orchestrator process
- Up to 5 coding agents
- Up to 5 testing agents
- Total: never exceeds 11 Python processes

**Stress Test Verification:**

```bash
# Windows - verify process bounds
# 1. Note baseline count
tasklist | findstr python | find /c /v ""

# 2. Start parallel agent (max concurrency)
python autonomous_agent_demo.py --project-dir test --parallel --max-concurrency 5

# 3. During run - should NEVER exceed baseline + 11
tasklist | findstr python | find /c /v ""

# 4. After stop via UI - should return to baseline
tasklist | findstr python | find /c /v ""
```

```bash
# macOS/Linux - verify process bounds
# 1. Note baseline count
pgrep -c python

# 2. Start parallel agent
python autonomous_agent_demo.py --project-dir test --parallel --max-concurrency 5

# 3. During run - should NEVER exceed baseline + 11
pgrep -c python

# 4. After stop - should return to baseline
pgrep -c python
```

**Log Verification:**

```bash
# Check spawn vs completion balance
grep "Started testing agent" orchestrator_debug.log | wc -l
grep "Testing agent.*completed\|failed" orchestrator_debug.log | wc -l

# Watch for cap enforcement messages
grep "at max testing agents\|At max total agents" orchestrator_debug.log
```

### Design System

The UI uses a **neobrutalism** design with Tailwind CSS v4:
- CSS variables defined in `ui/src/styles/globals.css` via `@theme` directive
- Custom animations: `animate-slide-in`, `animate-pulse-neo`, `animate-shimmer`
- Color tokens: `--color-neo-pending` (yellow), `--color-neo-progress` (cyan), `--color-neo-done` (green)
