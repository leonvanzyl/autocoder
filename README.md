# AutoCoder - Autonomous Coding Agent

**Fork of the original Autonomous Coding Agent with modern packaging, auto-setup, and a unified CLI.**

This is my fork of [the original AutoCoder project](https://github.com/original-repo/autocoder) (I'll update this when I find the actual upstream). I loved the concept but wanted it to feel more like a proper, installable tool instead of a collection of scripts. So I:

- **Modernized the packaging** - Now it's a proper Python package with `pyproject.toml` (the 2025 way, not the 2015 way)
- **Added auto-setup** - Because running `npm install && npm run build` manually 47 times was driving me nuts
- **Unified the CLI** - One command (`autocoder`) that asks what you want instead of remembering 10 different scripts
- **Fixed import hell** - Everything is now properly organized in `src/autocoder/` instead of scattered everywhere
- **Kept backward compatibility** - All the old scripts still work because I'm not a monster

The core magic (parallel agents, knowledge base, Claude integration) is all from the original project. I just made it easier to install and use.

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

### Model Presets (for Parallel Mode)

- `quality` - Opus only (best quality, highest cost)
- `balanced` - Opus + Haiku (recommended)
- `economy` - Opus + Sonnet + Haiku
- `cheap` - Sonnet + Haiku
- `experimental` - All models

---

## What I Changed from the Original

### Package Structure (The Big One)

**Before (original):**
```
autocoder/
├── agent.py
├── client.py
├── start.py
├── orchestrator.py
├── ...everything in root...
```

**After (this fork):**
```
autocoder/
├── pyproject.toml          # Modern packaging config
├── src/autocoder/          # Proper package structure
│   ├── core/               # Orchestrator, Gatekeeper, etc.
│   ├── agent/              # Agent implementation
│   ├── server/             # FastAPI backend
│   ├── tools/              # MCP tools
│   └── cli.py              # Unified CLI
├── Root (backward compat)
│   ├── start.py            # Still works (shim)
│   ├── agent.py            # Still works (shim)
│   └── ...                 # All old scripts still work
```

**Why?** Because Python packaging in 2025 shouldn't look like 2015. The `src/` layout is the modern standard, and it makes the codebase way more maintainable.

### Auto-Setup Feature

The original project expected you to:
1. Create venv manually
2. Run `pip install -r requirements.txt`
3. `cd ui && npm install && npm run build`
4. Hope nothing broke

Now you just:
1. Run `autocoder`
2. It checks everything and fixes what it can
3. You answer one question (CLI or UI?)
4. Done

### Unified CLI

Instead of:
- `python start.py`
- `python autonomous_agent_demo.py`
- `python orchestrator_demo.py`
- `python start_ui.py`

You've got:
- `autocoder` (does everything, asks what you want)
- `autocoder agent --project-dir ...`
- `autocoder parallel --project-dir ...`
- `autocoder-ui`

All your old scripts still work (I made shims), but you don't need them anymore.

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

This fork is built on top of the original Autonomous Coding Agent. All the core ideas (two-agent pattern, parallel execution, knowledge base, test framework detection, etc.) come from the original project. I just:

- Modernized the packaging
- Added auto-setup
- Unified the CLI
- Fixed a bunch of import issues
- Made it feel like a proper tool instead of a collection of scripts

**Original concept and architecture:** [Link to original repo when I find it]

**My contributions:** The packaging, auto-setup, and unified CLI layer on top of that solid foundation.

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

- [ ] Need to find and link the original upstream repo
- [ ] Auto-setup could handle venv creation too (currently warns but doesn't create it)
- [ ] Some edge cases with Windows paths in the git worktree code
- [ ] Documentation could use more examples of actual project specs

---

## License

Same as the original project (will update once I find the proper upstream).

---

**Built by Gabi at [Booplex](https://booplex.com)** - "I tamed AI so you don't have to"

*I only forked this because the original was brilliant but needed some UX love. All the hard stuff (making AI code autonomously) is theirs. I just made it easier to use.*
