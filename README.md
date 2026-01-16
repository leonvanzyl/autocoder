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

### Settings: project vs global (and who wins)

- **Project settings (portable):** stored in the target project’s `agent_system.db` (notably **Model Settings**). This means each project can carry its own model preset/mapping without touching `.env`.
- **Global settings (your machine):** stored in `~/.autocoder/settings.db` (Web UI **Advanced Settings**: ports, retry/backoff, QA provider defaults, log retention, diagnostics, etc.). Override path with `AUTOCODER_SETTINGS_DB_PATH`.
- **Precedence when the UI launches a run:** saved Advanced Settings override `.env`/shell env vars (but only if you actually saved settings). If you never saved Advanced Settings, the UI won’t override your env.

---

## Prerequisites

### Claude Code CLI (Recommended)

AutoCoder can use Claude via API keys, but the Claude Code CLI is still recommended (and required for some UI chat features like Assistant / Expand Project).

Pick your poison:

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
- **Anthropic API Key** - Set `ANTHROPIC_API_KEY` (pay-per-use)
- **Anthropic-compatible endpoint / proxy** - Set `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL` (the Web UI shows an **ALT API** badge; it shows **GLM** for common z.ai/GLM endpoints)

If you installed a Claude-compatible CLI under a different name/path, set `AUTOCODER_CLI_COMMAND` (legacy: `CLI_COMMAND`).

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

On Windows, you can also use `start.bat` / `start_ui.bat`. These scripts now first check the command exists (so a non-zero exit code isn’t misreported as “command not found”).

### New Project Setup Wizard (Web UI)

When creating a new project in the Web UI, AutoCoder includes an optional **Project Setup** step that can create (or copy) a per-project `autocoder.yaml`, including the `worker:` defaults (feature worker provider, patch iterations/order). You can always edit this later in Settings → Project Config.

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
- Advanced settings (Run/Advanced/Diagnostics defaults) are stored globally in `~/.autocoder/settings.db` (override path with `AUTOCODER_SETTINGS_DB_PATH`). Legacy `~/.autocoder/ui_settings.json` is read once and auto-migrated.
- When the UI starts a run, **saved** advanced settings override `.env`/shell env vars. If you’ve never saved Advanced Settings, the UI does not override env vars.
- Provider badge: when a project is selected, the header shows **ALT API** (custom endpoint) or **GLM** (z.ai/GLM-style endpoint) if configured via `.env`.
- Diagnostics: open `http://127.0.0.1:8888/#/settings/diagnostics` (system status, configurable fixtures dir, deterministic E2E fixtures, recent run logs).

If the agent fails due to missing authentication, the UI log stream will emit a short fix-it hint (e.g. `claude login` or env var guidance).

### Model Settings

Model selection is configured in Settings → Models:

- Feature workers use the configured preset/custom selection (`opus|sonnet|haiku` tiers).
- The Web UI **Assistant Chat Model** can be overridden separately (Auto/Opus/Sonnet/Haiku).
- Full provider model IDs can be overridden via `.env` with `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`.

Model settings are stored per-project in that project’s `agent_system.db` (so they travel with the project and don’t require editing `.env` for non-secret config).

### Parallel-Safe Feature Claiming

When running multiple agents (or multiple Claude Agent SDK sessions), feature selection must be atomic to avoid two sessions picking the same work item.

- Prefer `feature_claim_next` (atomic) over `feature_get_next` (legacy, non-atomic).
- In prompts/templates, follow the guidance to claim a feature before implementing it.

### Verified “Passing” in Parallel Mode

In parallel mode, workers should not self-attest `passes=true`. Instead, `feature_mark_passing` submits the feature for Gatekeeper verification, and the orchestrator sets `passes=true` only after deterministic verification and merge.

By default, Gatekeeper rejects features when it cannot run a deterministic verification command (or when verification fails). For Node projects without a `test` script, Gatekeeper falls back to other available scripts like `build`/`typecheck`/`lint` when present. Override with `AUTOCODER_ALLOW_NO_TESTS=1` only if you explicitly want “merge without tests” for a project (YOLO-only).

### Project Config (`autocoder.yaml`)

For framework-agnostic verification, put an `autocoder.yaml` in the **target project** root to tell Gatekeeper exactly what to run:

- `commands.setup` (optional): install deps / build
- `commands.test` (required for non-YOLO merges)
- `commands.lint`, `commands.typecheck`, etc. (optional; can be `allow_fail: true`)
- `commands.acceptance` (optional): deterministic E2E/smoke checks (e.g., Playwright)

This is preferred over auto-detection for non-Python stacks and monorepos.

Optional multi-model workflows (Codex/Gemini via local CLIs):
- Review in Gatekeeper: `docs/multi_model_review.md`
- Spec/plan drafting: `docs/multi_model_generate.md`

### Onboarding Existing Projects (GSD → Spec)

If you have a Claude/GSD-style codebase mapping under `./.planning/codebase/*.md`, the Web UI can convert it into an AutoCoder spec:

- Settings → Generate → **GSD → app_spec.txt**
- Requires: `STACK.md`, `ARCHITECTURE.md`, `STRUCTURE.md`

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

Gatekeeper writes verification artifacts under `.autocoder/**/gatekeeper/*.json`. To prune those periodically, set `AUTOCODER_LOGS_PRUNE_ARTIFACTS=1` (uses the same retention knobs by default, or set `AUTOCODER_ARTIFACTS_KEEP_*` separately).
In the Web UI: Settings -> Advanced -> Logs -> **Auto-prune Gatekeeper artifacts**.

You can also prune manually:

`autocoder logs --project-dir <path> --prune [--dry-run] [--include-artifacts]`

In the Web UI, use **Logs** (press `L`) to view/tail, prune, or delete worker log files.

### Dev Server Control (Web UI)

For projects with a runnable dev server (e.g. `package.json` has `dev`/`start`, or you set `commands.dev` in `autocoder.yaml`), you can start/stop it from the UI:

- Open the bottom drawer (press `D` or click the logs icon)
- Switch to the **Dev** tab
- Click **Start** (optional: provide a command override)

The UI will stream dev server output and show the latest detected localhost URL.

### Interactive Terminal (Web UI)

Use the bottom drawer to open an interactive shell rooted in the project directory:

- Open the bottom drawer (press `D`)
- Switch to the **Term** tab (shortcut: press `T`)
- Create/rename/close terminal tabs as needed

### Reliability & Retry Loop Prevention

Parallel mode is designed to be self-healing without getting stuck in infinite retries:

- **Feature retry backoff**: failed features schedule `next_attempt_at` with exponential backoff.
- **No-progress loop breaker (same error)**: repeated identical Gatekeeper failures increment `same_error_streak`; the feature becomes `BLOCKED` after `AUTOCODER_FEATURE_MAX_SAME_ERROR_STREAK` (default `3`).
- **No-progress loop breaker (same diff)**: Gatekeeper computes a `diff_fingerprint`; if retries keep producing the same diff and still fail, the feature becomes `BLOCKED` after `AUTOCODER_FEATURE_MAX_SAME_DIFF_STREAK` (default `3`).
- **Actionable failure context**: Gatekeeper writes a JSON artifact and AutoCoder stores `features.last_error` + `features.last_artifact_path` for the next retry.
- **Windows worktree cleanup queue**: locked `node_modules` cleanups are queued and retried so `worktrees/` doesn’t grow unbounded.

Details: `docs/RELIABILITY_PIPELINE.md`.

### SDK Retry/Backoff

Transient Claude SDK errors (rate limits, timeouts, connection blips) use exponential backoff:

- `AUTOCODER_SDK_MAX_ATTEMPTS` (default `3`)
- `AUTOCODER_SDK_INITIAL_DELAY_S` (default `1`)
- `AUTOCODER_SDK_RATE_LIMIT_INITIAL_DELAY_S` (default `30`)
- `AUTOCODER_SDK_MAX_DELAY_S` (default `60`)
- `AUTOCODER_SDK_EXPONENTIAL_BASE` (default `2`)
- `AUTOCODER_SDK_JITTER` (default `true`)

### Feature Worker Provider (optional)

By default, feature implementation uses the **Claude Agent SDK** worker. You can optionally switch feature implementation to a patch worker that generates unified diffs via external CLIs.

- Provider: `AUTOCODER_WORKER_PROVIDER` (`claude|codex_cli|gemini_cli|multi_cli`)
- Iterations (patch worker): `AUTOCODER_WORKER_PATCH_MAX_ITERATIONS` (default `2`)
- Provider order (multi): `AUTOCODER_WORKER_PATCH_AGENTS` (default `codex,gemini`)

Per-project (recommended): store these under `worker:` in the target repo’s `autocoder.yaml` so each project carries its own defaults.

In the Web UI: Settings -> Advanced -> Automation -> Feature Workers.

### QA Fix Mode (optional)

When enabled, parallel workers will automatically switch to a "fix the last failure" prompt after a Gatekeeper rejection (using `features.last_error` / `features.last_artifact_path`).

- Enable: `AUTOCODER_QA_FIX_ENABLED=1`
- Limit: `AUTOCODER_QA_MAX_SESSIONS` (default `3`)

In the Web UI: Settings -> Advanced -> Automation -> QA auto-fix.

### QA Sub-Agent (optional)

When enabled, the orchestrator will spawn a short-lived QA worker immediately after a Gatekeeper rejection. The QA worker reuses the same feature branch and is capped by a small iteration budget.

- Enable: `AUTOCODER_QA_SUBAGENT_ENABLED=1`
- Iterations: `AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS` (default `2`)
- Provider: `AUTOCODER_QA_SUBAGENT_PROVIDER` (`claude|codex_cli|gemini_cli|multi_cli`)
- Provider order (multi): `AUTOCODER_QA_SUBAGENT_AGENTS` (default `codex,gemini`)

In the Web UI: Settings -> Advanced -> Automation -> QA sub-agent.

### Editing features (pending/in-progress)

You can edit feature details (category/name/description/steps/priority) for non-completed features to help unblock the agent.

- Web UI: open a feature → click the pencil icon → edit and save.

### Expand Project (add features via chat)

If a project already has a spec, you can add more features without manually writing them:

- Web UI: click **Expand** (press `E`) → chat → **Finish** to add the new features to the queue.

### Controller Preflight (optional)

When enabled, the orchestrator runs deterministic verification commands in the agent worktree before Gatekeeper merge verification.

- Enable: `AUTOCODER_CONTROLLER_ENABLED=1`

### Feature Planner (optional)

When enabled, AutoCoder generates a short per-feature plan (Codex/Gemini drafts, optional Claude synthesis) and prepends it to the worker prompt.

- Enable: `AUTOCODER_PLANNER_ENABLED=1`

### E2E QA Provider Fixture (deterministic)

To validate the Gatekeeper -> QA sub-agent -> re-verify loop without relying on a full feature-implementation agent, run:

- Node fixture: `python scripts/e2e_qa_provider.py --out-dir "G:/Apps/autocoder-e2e-fixtures" --fixture node --provider multi_cli`
- Python/pytest fixture: `python scripts/e2e_qa_provider.py --out-dir "G:/Apps/autocoder-e2e-fixtures" --fixture python --provider multi_cli`

This creates a minimal repo that intentionally fails verification on `feat/1`, then relies on the selected QA provider to generate a patch and resubmit until Gatekeeper merges.

You can also run this via the CLI (same codepath as the Diagnostics UI):

- `autocoder diagnostics --fixture node --provider multi_cli --out-dir "G:/Apps/autocoder-e2e-fixtures"`

Notes:

- Diagnostics run logs are written under `<out_dir>/diagnostics_runs/*.log`.
- In the Web UI, the default `out_dir` is repo-local `dev_archive/e2e-fixtures` (override via Diagnostics -> Fixtures Directory, or `AUTOCODER_DIAGNOSTICS_FIXTURES_DIR`).

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

- [x] Auto-setup can bootstrap a local venv for this repo (run `autocoder setup`)
- [x] Windows worktree edge cases: enable git `core.longpaths` automatically per repo
- [x] More real spec examples: see `docs/examples/` (Node + Python + SEO affiliate)

---

## License

Same as the original project (will update once I find the proper upstream).

---

**Built by Gabi at [Booplex](https://booplex.com)** - "I tamed AI so you don't have to"

*Leon's brilliant single-agent system + my parallel execution layer = 3x faster autonomous coding. The hardest part (making AI code autonomously at all) was already solved. I just made it faster and easier to use.*
