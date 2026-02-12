# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Prerequisites

- Python 3.11+
- Node.js 20+ (for UI development)
- Claude Code CLI

## Project Overview

This is an autonomous coding agent system with a React-based UI. It uses the Claude Agent SDK to build complete applications over multiple sessions using a two-agent pattern:

1. **Initializer Agent** - First session reads an app spec and creates features in a SQLite database
2. **Coding Agent** - Subsequent sessions implement features one by one, marking them as passing

## Commands

### npm Global Install (Recommended)

```bash
npm install -g autoforge-ai
autoforge                    # Start server (first run sets up Python venv)
autoforge config             # Edit ~/.autoforge/.env in $EDITOR
autoforge config --show      # Print active configuration
autoforge --port 9999        # Custom port
autoforge --no-browser       # Don't auto-open browser
autoforge --repair           # Delete and recreate ~/.autoforge/venv/
```

### From Source (Development)

```bash
# Launch Web UI (serves pre-built React app)
start_ui.bat      # Windows
./start_ui.sh     # macOS/Linux

# CLI menu
start.bat         # Windows
./start.sh        # macOS/Linux
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

# Batch mode: implement multiple features per agent session (1-3)
python autonomous_agent_demo.py --project-dir my-app --batch-size 3

# Batch specific features by ID
python autonomous_agent_demo.py --project-dir my-app --batch-features 1,2,3
```

### YOLO Mode (Rapid Prototyping)

YOLO mode skips all testing for faster feature iteration:

```bash
# CLI
python autonomous_agent_demo.py --project-dir my-app --yolo

# UI: Toggle the lightning bolt button before starting the agent
```

**What's different in YOLO mode:**
- No regression testing
- No Playwright CLI (browser automation disabled)
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

## Testing

### Python

```bash
ruff check .                          # Lint
mypy .                                # Type check
python test_security.py               # Security unit tests (12 tests)
python test_security_integration.py   # Integration tests (9 tests)
python -m pytest test_client.py       # Client tests (20 tests)
python -m pytest test_dependency_resolver.py  # Dependency resolver tests (12 tests)
python -m pytest test_rate_limit_utils.py     # Rate limit tests (22 tests)
```

### React UI

```bash
cd ui
npm run lint          # ESLint
npm run build         # Type check + build (Vite 7)
npm run test:e2e      # Playwright end-to-end tests
npm run test:e2e:ui   # Playwright tests with UI
```

### CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to master:
- **Python job**: ruff lint + security tests
- **UI job**: ESLint + TypeScript build

### Code Quality

Configuration in `pyproject.toml`:
- ruff: Line length 120, Python 3.11 target
- mypy: Strict return type checking, ignores missing imports

## Architecture

### npm CLI (bin/, lib/)

The `autoforge` command is a Node.js wrapper that manages the Python environment and server lifecycle:
- `bin/autoforge.js` - Entry point (shebang script)
- `lib/cli.js` - Main CLI logic: Python 3.11+ detection (cross-platform), venv management at `~/.autoforge/venv/` with composite marker (requirements hash + Python version), `.env` config loading from `~/.autoforge/.env`, uvicorn server startup with PID file, and signal handling
- `package.json` - npm package config (`autoforge-ai` on npm), `files` whitelist with `__pycache__` exclusions, `prepublishOnly` builds the UI
- `requirements-prod.txt` - Runtime-only Python deps (excludes ruff, mypy, pytest)
- `.npmignore` - Excludes dev files, tests, UI source from the published tarball

Publishing: `npm publish` (triggers `prepublishOnly` which builds UI, then publishes ~600KB tarball with 84 files)

### Core Python Modules

- `start.py` - CLI launcher with project creation/selection menu
- `autonomous_agent_demo.py` - Entry point for running the agent (supports `--yolo`, `--parallel`, `--batch-size`, `--batch-features`)
- `autoforge_paths.py` - Central path resolution with dual-path backward compatibility and migration
- `agent.py` - Agent session loop using Claude Agent SDK
- `client.py` - ClaudeSDKClient configuration with security hooks, feature MCP server, and Vertex AI support
- `security.py` - Bash command allowlist validation (ALLOWED_COMMANDS whitelist)
- `prompts.py` - Prompt template loading with project-specific fallback and batch feature prompts
- `progress.py` - Progress tracking, database queries, webhook notifications
- `registry.py` - Project registry for mapping names to paths (cross-platform), global settings model
- `parallel_orchestrator.py` - Concurrent agent execution with dependency-aware scheduling
- `auth.py` - Authentication error detection for Claude CLI
- `env_constants.py` - Shared environment variable constants (API_ENV_VARS) used by client.py and chat sessions
- `rate_limit_utils.py` - Rate limit detection, retry parsing, exponential backoff with jitter
- `api/database.py` - SQLAlchemy models (Feature, Schedule, ScheduleOverride)
- `api/dependency_resolver.py` - Cycle detection (Kahn's algorithm + DFS) and dependency validation
- `api/migration.py` - JSON-to-SQLite migration utility

### Project Registry

Projects can be stored in any directory. The registry maps project names to paths using SQLite:
- **All platforms**: `~/.autoforge/registry.db`

The registry uses:
- SQLite database with SQLAlchemy ORM
- POSIX path format (forward slashes) for cross-platform compatibility
- SQLite's built-in transaction handling for concurrency safety

### Server API (server/)

The FastAPI server provides REST and WebSocket endpoints for the UI:

**Routers** (`server/routers/`):
- `projects.py` - Project CRUD with registry integration
- `features.py` - Feature management
- `agent.py` - Agent control (start/stop/pause/resume)
- `filesystem.py` - Filesystem browser API with security controls
- `spec_creation.py` - WebSocket for interactive spec creation
- `expand_project.py` - Interactive project expansion via natural language
- `assistant_chat.py` - Read-only project assistant chat (WebSocket/REST)
- `terminal.py` - Interactive terminal I/O with PTY support (WebSocket bidirectional)
- `devserver.py` - Dev server control (start/stop) and config
- `schedules.py` - CRUD for time-based agent scheduling
- `settings.py` - Global settings management (model selection, YOLO, batch size, headless browser)

**Services** (`server/services/`):
- `process_manager.py` - Agent process lifecycle management
- `project_config.py` - Project type detection and dev command management
- `terminal_manager.py` - Terminal session management with PTY (`pywinpty` on Windows)
- `scheduler_service.py` - APScheduler-based automated agent scheduling
- `dev_server_manager.py` - Dev server lifecycle management
- `assistant_chat_session.py` / `assistant_database.py` - Assistant chat sessions with SQLite persistence
- `spec_chat_session.py` - Spec creation chat sessions
- `expand_chat_session.py` - Expand project chat sessions
- `chat_constants.py` - Shared constants for chat services

**Utilities** (`server/utils/`):
- `process_utils.py` - Process management utilities
- `project_helpers.py` - Project path resolution helpers
- `validation.py` - Project name validation

### Feature Management

Features are stored in SQLite (`features.db`) via SQLAlchemy. The agent interacts with features through an MCP server:

- `mcp_server/feature_mcp.py` - MCP server exposing feature management tools
- `api/database.py` - SQLAlchemy models (Feature table with priority, category, name, description, steps, passes, dependencies)

MCP tools available to the agent:
- `feature_get_stats` - Progress statistics
- `feature_get_by_id` - Get a single feature by ID
- `feature_get_summary` - Get summary of all features
- `feature_get_ready` - Get features ready to work on (dependencies met)
- `feature_get_blocked` - Get features blocked by unmet dependencies
- `feature_get_graph` - Get full dependency graph
- `feature_claim_and_get` - Atomically claim next available feature (for parallel mode)
- `feature_mark_in_progress` - Mark feature as in progress
- `feature_mark_passing` - Mark feature complete
- `feature_mark_failing` - Mark feature as failing
- `feature_skip` - Move feature to end of queue
- `feature_clear_in_progress` - Clear in-progress status
- `feature_create_bulk` - Initialize all features (used by initializer)
- `feature_create` - Create a single feature
- `feature_add_dependency` - Add dependency between features (with cycle detection)
- `feature_remove_dependency` - Remove a dependency
- `feature_set_dependencies` - Set all dependencies for a feature at once

### React UI (ui/)

- Tech stack: React 19, TypeScript, Vite 7, TanStack Query, Tailwind CSS v4, Radix UI, dagre (graph layout), xterm.js (terminal)
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
- `Terminal.tsx` / `TerminalTabs.tsx` - xterm.js-based multi-tab terminal
- `AssistantPanel.tsx` / `AssistantChat.tsx` - AI assistant for project Q&A
- `ExpandProjectModal.tsx` / `ExpandProjectChat.tsx` - Add features via natural language
- `DevServerControl.tsx` - Dev server start/stop control
- `ScheduleModal.tsx` - Schedule management UI
- `SettingsModal.tsx` - Global settings panel

In-app documentation (`/#/docs` route):
- `src/components/docs/sections/` - Content for each doc section (GettingStarted.tsx, AgentSystem.tsx, etc.)
- `src/components/docs/docsData.ts` - Sidebar structure, subsection IDs, search keywords
- `src/components/docs/DocsPage.tsx` - Page layout; `DocsContent.tsx` - section renderer with scroll tracking

Keyboard shortcuts (press `?` for help):
- `D` - Toggle debug panel
- `G` - Toggle Kanban/Graph view
- `N` - Add new feature
- `A` - Toggle AI assistant
- `,` - Open settings

### Project Structure for Generated Apps

Projects can be stored in any directory (registered in `~/.autoforge/registry.db`). Each project contains:
- `.autoforge/prompts/app_spec.txt` - Application specification (XML format)
- `.autoforge/prompts/initializer_prompt.md` - First session prompt
- `.autoforge/prompts/coding_prompt.md` - Continuation session prompt
- `.autoforge/features.db` - SQLite database with feature test cases
- `.autoforge/.agent.lock` - Lock file to prevent multiple agent instances
- `.autoforge/allowed_commands.yaml` - Project-specific bash command allowlist (optional)
- `.autoforge/.gitignore` - Ignores runtime files
- `.claude/skills/playwright-cli/` - Playwright CLI skill for browser automation
- `.playwright/cli.config.json` - Browser configuration (headless, viewport, etc.)
- `.playwright-cli/` - Playwright CLI daemon artifacts (screenshots, snapshots) - gitignored
- `CLAUDE.md` - Stays at project root (SDK convention)
- `app_spec.txt` - Root copy for agent template compatibility

Legacy projects with files at root level (e.g., `features.db`, `prompts/`) are auto-migrated to `.autoforge/` on next agent start. Dual-path resolution ensures old and new layouts work transparently.

### Security Model

Defense-in-depth approach configured in `client.py`:
1. OS-level sandbox for bash commands
2. Filesystem restricted to project directory only
3. Bash commands validated using hierarchical allowlist system

#### Extra Read Paths (Cross-Project File Access)

The agent can optionally read files from directories outside the project folder via the `EXTRA_READ_PATHS` environment variable. This enables referencing documentation, shared libraries, or other projects.

**Configuration:**

```bash
# Single path
EXTRA_READ_PATHS=/Users/me/docs

# Multiple paths (comma-separated)
EXTRA_READ_PATHS=/Users/me/docs,/opt/shared-libs,/Volumes/Data/reference
```

**Security Controls:**

All paths are validated before being granted read access:
- Must be absolute paths (not relative)
- Must exist and be directories
- Paths are canonicalized via `Path.resolve()` to prevent `..` traversal attacks
- Sensitive directories are blocked (see blocklist below)
- Only Read, Glob, and Grep operations are allowed (no Write/Edit)

**Blocked Sensitive Directories:**

The following directories (relative to home) are always blocked:
- `.ssh`, `.aws`, `.azure`, `.kube` - Cloud/SSH credentials
- `.gnupg`, `.gpg`, `.password-store` - Encryption keys
- `.docker`, `.config/gcloud` - Container/cloud configs
- `.npmrc`, `.pypirc`, `.netrc` - Package manager credentials

#### Per-Project Allowed Commands

The agent's bash command access is controlled through a hierarchical configuration system:

**Command Hierarchy (highest to lowest priority):**
1. **Hardcoded Blocklist** (`security.py`) - NEVER allowed (dd, sudo, shutdown, etc.)
2. **Org Blocklist** (`~/.autoforge/config.yaml`) - Cannot be overridden by projects
3. **Org Allowlist** (`~/.autoforge/config.yaml`) - Available to all projects
4. **Global Allowlist** (`security.py`) - Default commands (npm, git, curl, etc.)
5. **Project Allowlist** (`.autoforge/allowed_commands.yaml`) - Project-specific commands

**Project Configuration:**

Each project can define custom allowed commands in `.autoforge/allowed_commands.yaml`:

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

System administrators can set org-wide policies in `~/.autoforge/config.yaml`:

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

**Files:**
- `security.py` - Command validation logic and hardcoded blocklist
- `test_security.py` - Unit tests for security system
- `test_security_integration.py` - Integration tests with real hooks
- `examples/project_allowed_commands.yaml` - Project config example (all commented by default)
- `examples/org_config.yaml` - Org config example (all commented by default)
- `examples/README.md` - Comprehensive guide with use cases, testing, and troubleshooting

### Vertex AI Configuration (Optional)

Run coding agents via Google Cloud Vertex AI:

1. Install and authenticate gcloud CLI: `gcloud auth application-default login`
2. Configure `.env`:
   ```
   CLAUDE_CODE_USE_VERTEX=1
   CLOUD_ML_REGION=us-east5
   ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
   ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-6
   ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-5@20250929
   ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-3-5-haiku@20241022
   ```

**Note:** Use `@` instead of `-` in model names for Vertex AI.

### Alternative API Providers (GLM, Ollama, Kimi, Custom)

Alternative providers are configured via the **Settings UI** (gear icon > API Provider section). Select a provider, set the base URL, auth token, and model — no `.env` changes needed.

**Available providers:** Claude (default), GLM (Zhipu AI), Ollama (local models), Kimi (Moonshot), Custom

**Ollama notes:**
- Requires Ollama v0.14.0+ with Anthropic API compatibility
- Install: https://ollama.com → `ollama serve` → `ollama pull qwen3-coder`
- Recommended models: `qwen3-coder`, `deepseek-coder-v2`, `codellama`
- Performance depends on local hardware (GPU recommended)

## Claude Code Integration

**Slash commands** (`.claude/commands/`):
- `/create-spec` - Interactive spec creation for new projects
- `/expand-project` - Expand existing project with new features
- `/gsd-to-autoforge-spec` - Convert GSD codebase mapping to app_spec.txt
- `/check-code` - Run lint and type-check for code quality
- `/checkpoint` - Create comprehensive checkpoint commit
- `/review-pr` - Review pull requests

**Custom agents** (`.claude/agents/`):
- `coder.md` - Elite software architect agent for code implementation (Opus)
- `code-review.md` - Code review agent for quality/security/performance analysis (Opus)
- `deep-dive.md` - Technical investigator for deep analysis and debugging (Opus)

**Skills** (`.claude/skills/`):
- `frontend-design` - Distinctive, production-grade UI design
- `gsd-to-autoforge-spec` - Convert GSD codebase mapping to AutoForge app_spec format
- `playwright-cli` - Browser automation via Playwright CLI (copied to each project)

**Other:**
- `.claude/templates/` - Prompt templates copied to new projects
- `examples/` - Configuration examples and documentation for security settings

## Key Patterns

### Prompt Loading Fallback Chain

1. Project-specific: `{project_dir}/.autoforge/prompts/{name}.md` (or legacy `{project_dir}/prompts/{name}.md`)
2. Base template: `.claude/templates/{name}.template.md`

### Agent Session Flow

1. Check if `.autoforge/features.db` has features (determines initializer vs coding agent)
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
2. Each agent claims features atomically via `feature_claim_and_get`
3. Features blocked by unmet dependencies are skipped
4. Browser sessions are isolated per agent via `PLAYWRIGHT_CLI_SESSION` environment variable
5. AgentTracker parses output and emits `agent_update` messages for UI

### Process Limits (Parallel Mode)

The orchestrator enforces strict bounds on concurrent processes:
- `MAX_PARALLEL_AGENTS = 5` - Maximum concurrent coding agents
- `MAX_TOTAL_AGENTS = 10` - Hard limit on total agents (coding + testing)
- Testing agents are capped at `max_concurrency` (same as coding agents)
- Total process count never exceeds 11 Python processes (1 orchestrator + 5 coding + 5 testing)

### Multi-Feature Batching

Agents can implement multiple features per session using `--batch-size` (1-3, default: 3):
- `--batch-size N` - Max features per coding agent batch
- `--testing-batch-size N` - Features per testing batch (1-5, default: 3)
- `--batch-features 1,2,3` - Specific feature IDs for batch implementation
- `--testing-batch-features 1,2,3` - Specific feature IDs for batch regression testing
- `prompts.py` provides `get_batch_feature_prompt()` for multi-feature prompt generation
- Configurable in UI via settings panel

### Design System

The UI uses a **neobrutalism** design with Tailwind CSS v4:
- CSS variables defined in `ui/src/styles/globals.css` via `@theme` directive
- Custom animations: `animate-slide-in`, `animate-pulse-neo`, `animate-shimmer`
- Color tokens: `--color-neo-pending` (yellow), `--color-neo-progress` (cyan), `--color-neo-done` (green)
