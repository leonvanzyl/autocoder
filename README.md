# AutoCoder - Autonomous Coding Agent

**Fork of Leon van Zyl's original AutoCoder with parallel agents, knowledge base, and modern packaging.**

This is my fork of [the original AutoCoder project by Leon van Zyl](https://github.com/leonvanzyl/autocoder). Leon built the brilliant foundation (autonomous agent, React UI, MCP architecture), and I added:

- **Parallel Agents** - Orchestrator that runs 3-5 agents simultaneously (3x faster)
- **Knowledge Base** - Agents learn from each other's successes
- **Gatekeeper** - Verification system to keep code quality high
- **Worktree Manager** - Isolated git worktrees for safe parallel work
- **Modern Packaging** - Proper `pyproject.toml` with `src/` layout (2026 standards)
- **Auto-Setup** - CLI handles `npm install && npm run build` automatically
- **Unified CLI** - One `autocoder` command instead of 10 different scripts

Leon's original handles single-agent autonomous coding beautifully. I added the ability to run multiple agents in parallel while they learn from each other.

---

## What This Thing Actually Does

It's an autonomous coding agent powered by Claude that:

1. **Reads your project spec** (you create this first)
2. **Builds features one by one** using the Claude Agent SDK
3. **Tests everything** (auto-detects your test framework)
4. **Can run 3-5 agents in parallel** for 3x faster development (the killer feature)
5. **Learns from patterns** (knowledge base remembers what works)
6. **Has a pretty nice web UI** for watching it work

It's not going to replace your dev team (yet), but it's shockingly good at building features when you give it clear specs.

---

## Prerequisites

### Claude Code CLI (Required)

You need the Claude Code CLI installed. Pick your poison:

**macOS / Linux:**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://claude.ai/install.ps1 | iex
```

### Authentication

You'll need one of these:

- **Claude Pro/Max Subscription** - Run `claude login` (recommended, especially for parallel agents)
- **Anthropic API Key** - From https://console.anthropic.com/ (pay-per-use)

---

## Quick Start (The Easy Way)

### Installation

```bash
# Clone this repo
git clone https://github.com/YOUR-USERNAME/autocoder.git
cd autocoder

# Install everything (including dev tools)
pip install -e '.[dev]'

# That's it. The CLI will auto-setup the UI on first run
```

### Running It

Just run `autocoder` with no arguments:

```bash
autocoder
```

**What happens next:**

1. **Setup check** - It checks if you have Node.js, npm, Claude CLI, etc.
2. **Auto-setup** - If the UI isn't built, it runs `npm install && npm run build` for you
3. **Menu** - Asks if you want the CLI or Web UI
4. **Launch** - Starts whichever you picked

No more remembering 10 different scripts or running setup commands manually. I got tired of that.

---

## CLI Commands

Once installed, you've got these options:

```bash
# Interactive mode (asks if you want CLI or Web UI)
autocoder

# Run single agent directly
autocoder agent --project-dir my-app
autocoder agent --project-dir C:/Projects/my-app --yolo

# Run parallel agents (3x faster!)
autocoder parallel --project-dir my-app --parallel 3 --preset balanced

# Launch Web UI directly
autocoder-ui
```

### Ports

- Web UI server port: set `AUTOCODER_UI_PORT` (default: `8888`).
- UI dev proxy port: set `VITE_API_PORT` (or reuse `AUTOCODER_UI_PORT`) when running `ui/` via Vite.
- Parallel agent runs allocate unique target-app ports per worker via `AUTOCODER_API_PORT` and `AUTOCODER_WEB_PORT` (configurable pools via `AUTOCODER_API_PORT_RANGE_START/END` and `AUTOCODER_WEB_PORT_RANGE_START/END`).
- For common dev servers, workers also export compatibility vars: `PORT` (API) and `VITE_PORT` (web).
- Design/implementation details: `PORT_ALLOCATION_IMPLEMENTATION_REPORT.md`.

### Web UI Settings

- Quick run settings: **Settings** button (or press `S`).
- Full settings hub: open `http://127.0.0.1:8888/#/settings` (Run / Models / Advanced).

### Parallel-Safe Feature Claiming

When running multiple agents (or multiple Claude Agent SDK sessions), feature selection must be atomic to avoid two sessions picking the same work item.

- Prefer `feature_claim_next` (atomic) over `feature_get_next` (legacy, non-atomic).
- In prompts/templates, follow the guidance to claim a feature before implementing it.

### Verified “Passing” in Parallel Mode

In parallel mode, workers should not self-attest `passes=true`. Instead, `feature_mark_passing` submits the feature for Gatekeeper verification, and the orchestrator sets `passes=true` only after deterministic verification and merge.

By default, Gatekeeper rejects features if no test framework is detected (or no tests run). Override with `AUTOCODER_ALLOW_NO_TESTS=1` if you want “merge without tests” for a project.

### Agent Guardrails

To prevent runaway tool loops, the SDK session enforces basic guardrails:

- `AUTOCODER_GUARDRAIL_MAX_TOOL_CALLS` (default `400`)
- `AUTOCODER_GUARDRAIL_MAX_SAME_TOOL_CALLS` (default `50`)
- `AUTOCODER_GUARDRAIL_MAX_CONSECUTIVE_TOOL_ERRORS` (default `25`)
- `AUTOCODER_GUARDRAIL_MAX_TOOL_ERRORS` (default `150`)

### Parallel Worker Logs

Parallel workers write stdout/stderr to `./.autocoder/logs/<agent-id>.log` in the project directory.

Logs are pruned automatically (defaults: keep 7 days, 200 files, 200MB total). Override with:

- `AUTOCODER_LOGS_KEEP_DAYS`
- `AUTOCODER_LOGS_KEEP_FILES`
- `AUTOCODER_LOGS_MAX_TOTAL_MB`

You can also prune manually:

`autocoder logs --project-dir <path> --prune [--dry-run]`

In the Web UI, use **Logs** (press `L`) to view/tail, prune, or delete worker log files.

### SDK Retry/Backoff

Transient Claude SDK errors (rate limits, timeouts, connection blips) use exponential backoff:

- `AUTOCODER_SDK_MAX_ATTEMPTS` (default `3`)
- `AUTOCODER_SDK_INITIAL_DELAY_S` (default `1`)
- `AUTOCODER_SDK_RATE_LIMIT_INITIAL_DELAY_S` (default `30`)
- `AUTOCODER_SDK_MAX_DELAY_S` (default `60`)
- `AUTOCODER_SDK_EXPONENTIAL_BASE` (default `2`)
- `AUTOCODER_SDK_JITTER` (default `true`)

### UI Server Lock

The UI server uses a per-port PID lock to avoid two instances fighting over the same port. Disable with `AUTOCODER_DISABLE_UI_LOCK=1`.

### Model Presets (for Parallel Mode)

- `quality` - Opus only (best quality, highest cost)
- `balanced` - Opus + Haiku (recommended)
- `economy` - Opus + Sonnet + Haiku
- `cheap` - Sonnet + Haiku
- `experimental` - All models

---

## What I Added to Leon's Original

### Major New Features

**1. Parallel Agents (The Big One)**

Leon's original runs one agent at a time. I added:

- **Orchestrator** (`src/autocoder/core/orchestrator.py`) - Spawns 3-5 agents in isolated git worktrees
- **Gatekeeper** (`src/autocoder/core/gatekeeper.py`) - Verifies each feature before merging
- **WorktreeManager** (`src/autocoder/core/worktree_manager.py`) - Manages git worktrees for safe parallel work
- **KnowledgeBase** (`src/autocoder/core/knowledge_base.py`) - Agents share learnings (if Agent 1 figures out React testing, Agent 2 benefits)

Result: 3x faster development without sacrificing quality.

**2. Modern Packaging**

Leon's original: Everything in root, run with `python start.py`

This fork:
- `src/autocoder/` package structure (2026 standards)
- `pyproject.toml` for proper installation
- `autocoder` and `autocoder-ui` entry points
- Dev extras (`[dev]`) with pytest, black, ruff, mypy

**3. Auto-Setup & Unified CLI**

The original expected you to:
1. Create venv manually
2. `pip install -r requirements.txt`
3. `cd ui && npm install && npm run build`
4. Remember which script does what

Now you just:
1. `pip install -e '.[dev]'`
2. `autocoder` (handles setup, asks what you want)

### Package Structure

**Leon's original:**
```
autocoder/
├── agent.py
├── client.py
├── start.py
├── orchestrator_demo.py  # Doesn't exist - I added this
└── ...everything in root...
```

**This fork:**
```
autocoder/
├── pyproject.toml          # Modern packaging
├── src/autocoder/
│   ├── core/               # NEW: Orchestrator, Gatekeeper, WorktreeManager, KnowledgeBase
│   ├── agent/              # From Leon's original (reorganized)
│   ├── server/             # From Leon's original (reorganized)
│   ├── tools/              # From Leon's original (MCP servers)
│   ├── api/                # From Leon's original (reorganized)
│   └── cli.py              # NEW: Unified CLI
├── Root (backward compat)
│   ├── start.py            # From Leon's original (now shim)
│   ├── agent.py            # From Leon's original (now shim)
│   └── ...                 # All old scripts still work
└── ui/                     # From Leon's original (React UI)
```

**What's from Leon:** The basic agent system, React UI, MCP architecture, two-agent pattern.

**What I added:** Parallel execution system, knowledge base, modern packaging, unified CLI, auto-setup.

---

## Development Setup

```bash
# Install with dev tools (pytest, black, ruff, mypy)
pip install -e '.[dev]'

# Run tests
pytest tests/

# Format code
black .

# Lint code
ruff check .

# Type check
mypy src/autocoder
```

---

## Project Structure (Post-Migration)

```
autocoder/
├── pyproject.toml           # Single source of truth
├── src/autocoder/           # Main package
│   ├── cli.py               # Unified CLI
│   ├── core/                # Parallel agent system
│   ├── agent/               # Agent implementation
│   ├── server/              # FastAPI backend
│   ├── tools/               # MCP tools
│   └── api/                 # Database models
├── ui/                      # React frontend
├── docs/                    # Documentation
├── tests/                   # Tests
└── Root                     # Legacy shims (still work!)
```

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for the full breakdown.

---

## Original Project Credits

**Base System by Leon van Zyl:**
- [Original AutoCoder](https://github.com/leonvanzyl/autocoder)
- Autonomous agent using Claude Agent SDK
- Two-agent pattern (initializer + coding agent)
- React-based web UI with real-time updates
- MCP (Model Context Protocol) server architecture
- Project registry and feature database system
- The foundational architecture that makes autonomous coding possible

**My Additions:**
- Parallel agent execution (Orchestrator, Gatekeeper, WorktreeManager)
- Knowledge Base for cross-agent learning
- Test framework auto-detection
- Modern Python packaging (`pyproject.toml`, `src/` layout)
- Unified CLI with auto-setup (`autocoder`, `autocoder-ui`)
- Proper entry points and dev extras

Leon built the brilliant single-agent system. I added the ability to run multiple agents in parallel while they learn from each other.

---

## How the Parallel Agents Work (The Cool Part)

This is the feature that makes this project special:

1. **Orchestrator** spawns 3-5 agents in isolated git worktrees
2. **Each agent** works on a different feature (from your feature database)
3. **Knowledge Base** shares learnings between agents (if Agent 1 figured out how to test React components, Agent 2 benefits)
4. **Gatekeeper** verifies each feature in a temporary worktree (never dirties your main branch)
5. **Smart model routing** - Opus for complex tasks, Haiku for simple ones

Result: 3x faster development without sacrificing quality (thanks to the Gatekeeper).

---

## Known Issues / TODO

- [ ] Auto-setup could handle venv creation too (currently warns but doesn't create it)
- [ ] Some edge cases with Windows paths in the git worktree code
- [ ] Documentation could use more examples of actual project specs

---

## License

Same as the original project (will update once I find the proper upstream).

---

**Built by Gabi at [Booplex](https://booplex.com)** - "I tamed AI so you don't have to"

*Leon's brilliant single-agent system + my parallel execution layer = 3x faster autonomous coding. The hardest part (making AI code autonomously at all) was already solved. I just made it faster and easier to use.*
