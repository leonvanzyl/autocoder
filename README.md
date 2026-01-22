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
- **Global settings (your machine):** stored in `~/.autocoder/settings.db` (Web UI **Advanced Settings**: ports, retry/backoff, QA/Controller toggles, log retention, diagnostics, etc.). Override path with `AUTOCODER_SETTINGS_DB_PATH`.
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

When creating a new project in the Web UI, AutoCoder includes an optional **Project Setup** step that can create (or copy) a per-project `autocoder.yaml` with verification commands and review settings. Engine chains (feature worker/QA/review/spec) live in the project DB and are configured in **Settings → Engines**.

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
- Dashboard navigation: click the **Autonomous Coder** logo (or choose **Dashboard** in the project dropdown) to go back without stopping any running agents. If something is still running, the Dashboard shows a “running in the background” card with a one-click return.
- Global settings (no project selected): from the Dashboard click **Settings** (or press `S`) to open **Advanced** + **Diagnostics**.
- Full settings hub: open `http://127.0.0.1:8888/#/settings` (Run / Models / Engines / Advanced / Diagnostics).
- Advanced settings (Run/Advanced/Diagnostics defaults) are stored globally in `~/.autocoder/settings.db` (override path with `AUTOCODER_SETTINGS_DB_PATH`). Legacy `~/.autocoder/ui_settings.json` is read once and auto-migrated.
- When the UI starts a run, **saved** advanced settings override `.env`/shell env vars. If you’ve never saved Advanced Settings, the UI does not override env vars.
- Provider badge: when a project is selected, the header shows **ALT API** (custom endpoint) or **GLM** (z.ai/GLM-style endpoint) if configured via `.env`.
- Diagnostics: open `http://127.0.0.1:8888/#/settings/diagnostics` (system status, deterministic E2E fixtures, recent run logs, UI build id + backend git SHA, “Copy debug info”).
- The UI auto-opens your browser on launch (disable with `AUTOCODER_OPEN_UI=0`).
- On Windows, terminal sessions auto-install `pywinpty` (disable with `AUTOCODER_AUTO_INSTALL_WINPTY=0`).
- Hide the startup banner/checklist with `AUTOCODER_UI_BANNER=0` (set it before running `autocoder-ui`/`start_ui`).
- If `ui/src` is newer than `ui/dist`, AutoCoder will auto-rebuild the UI on launch (disable with `AUTOCODER_UI_AUTO_BUILD=0`).
- If the UI looks stale after an update, hit refresh (we serve `index.html` with `Cache-Control: no-store` so rebuilds should invalidate cleanly).
- If you run from a FAT32/exFAT drive and auto-build gets “sticky”, set `AUTOCODER_UI_MTIME_TOLERANCE_S=2` (or any non-negative seconds).
- Scheduled runs: use the **Settings** modal (press `S`) to schedule a start time; schedules persist across UI restarts.
- Settings UX: most Settings sections have a small ⓘ button for “what does this do?” context help. Save buttons briefly show **Saved** so you know it actually applied.
- Stop-when-done: default is **stop** when the queue is empty; set `AUTOCODER_STOP_WHEN_DONE=0` to keep the agent alive for new features.
- LAN access: set `AUTOCODER_UI_HOST=0.0.0.0` and `AUTOCODER_UI_ALLOW_REMOTE=1` (restart required).
- Playwright MCP runs with an isolated in-memory profile by default (set `AUTOCODER_PLAYWRIGHT_ISOLATED=0` to disable).

### Project Setup & Reset (Web UI)

- If a project spec is missing or still the placeholder template, the dashboard shows **Project setup required** with a one-click Spec Creation chat.
- You can snooze the banner for 24h, but **Expand** stays disabled until the spec is real.
- Settings → **Project Config** → **Danger Zone**:
  - **Reset** clears runtime artifacts (`agent_system.db`, `.autocoder/`, `worktrees/`).
  - **Full reset** also wipes `prompts/` so the spec must be recreated.
  - **Delete** shows a safety summary (git status, non-runtime files) and requires typed confirmation before deleting on disk.
  - On Windows, delete may queue a cleanup if files are locked; use **Settings → Diagnostics → Worktree Cleanup** to retry.

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

Gatekeeper also refuses to merge if your main working tree has uncommitted changes — but it ignores known runtime artifacts like `.autocoder/`, `worktrees/`, `agent_system.db`, plus common Claude Code CLI leftovers (e.g. `.claude_settings.json`, `claude-progress.txt`).

Skipping features is only for **external blockers** (missing credentials, service down, etc.). Refactor/cleanup/tech-debt features are **required work** and should not be skipped. When a refactor feature conflicts with the original spec, the **feature database wins** (it’s the living source of truth).

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

### Knowledge Files (project context)

Add project-specific notes in `<project>/knowledge/*.md`. These files are automatically injected into:

- initializer + coding prompts
- QA patch workers (codex/gemini)
- assistant chat + expand/spec creation

In the Web UI: click **Knowledge** (shortcut `K`) to create/edit/delete knowledge files.

#### Initializer backlog + staging

Initializer drafts now use the **engine chain** in Settings → Engines (project‑scoped). Global knobs still live in Advanced Settings:

- `AUTOCODER_INITIALIZER_SYNTHESIZER` (default `claude`)
- `AUTOCODER_INITIALIZER_TIMEOUT_S` (default `300`)
- `AUTOCODER_INITIALIZER_STAGE_THRESHOLD` (default `120`)
- `AUTOCODER_INITIALIZER_ENQUEUE_COUNT` (default `30`)

Notes:
- Large backlogs are **staged** (not dropped). Only `enqueue_count` features are active at a time.
- UI: **Settings → Advanced → Initializer** sets the global defaults; **Settings → Engines** controls draft engines.
- Staged features show in a separate column and can be enqueued in batches.

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

Mission Control activity events are stored in the project DB (`agent_system.db`) and pruned periodically during runs:

- `AUTOCODER_ACTIVITY_KEEP_DAYS` (default `14`)
- `AUTOCODER_ACTIVITY_KEEP_ROWS` (default `5000`)

Gatekeeper writes verification artifacts under `.autocoder/**/gatekeeper/*.json`. To prune those periodically, set `AUTOCODER_LOGS_PRUNE_ARTIFACTS=1` (uses the same retention knobs by default, or set `AUTOCODER_ARTIFACTS_KEEP_*` separately).
In the Web UI: Settings -> Advanced -> Logs -> **Auto-prune Gatekeeper artifacts**.

You can also prune manually:

`autocoder logs --project-dir <path> --prune [--dry-run] [--include-artifacts]`

In the Web UI, use **Logs** (press `L`) to view/tail, prune, or delete worker log files.
In the Web UI, press `M` (or open the drawer and click **Activity**) for a cross-agent **Mission Control** timeline (Gatekeeper/QA/regressions included).

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

### Engine Chains (per-project)

Feature implementation, QA fixers, review, spec/plan drafts, and initializer drafts are controlled by **engine chains** stored in each project’s `agent_system.db`:

- Configure in **Settings → Engines** or via `GET/PUT /api/engine-settings?project=...`.
- Order matters: engines run in sequence until a patch/decision succeeds.
- Patch workers use `src/autocoder/qa_worker.py --mode implement --engines '["codex_cli","gemini_cli","claude_patch"]'`.
- Defaults are Claude‑first; add Codex/Gemini only when the CLIs are detected and you explicitly enable them.

**Codex defaults (nice quality-of-life):** if you leave Codex model settings blank, AutoCoder will try to read Codex CLI defaults from `~/.codex/config.toml` (`model` and `model_reasoning_effort`). You can still override via env (`AUTOCODER_CODEX_MODEL`, `AUTOCODER_CODEX_REASONING_EFFORT`) or in the Web UI (Advanced Settings).

Codex reasoning effort accepts: `low|medium|high|xlow|xmedium|xhigh` (Codex CLI uses `model_reasoning_effort`).

Per-project engine chains live in the project’s `agent_system.db` (use **Settings → Engines**).

### QA Fix Mode (optional)

When enabled, parallel workers will automatically switch to a "fix the last failure" prompt after a Gatekeeper rejection (using `features.last_error` / `features.last_artifact_path`).

- Enable: `AUTOCODER_QA_FIX_ENABLED=1`
- Limit: `AUTOCODER_QA_MAX_SESSIONS` (default `3`)

In the Web UI: Settings -> Advanced -> Automation -> QA auto-fix.

### QA Sub-Agent (optional)

When enabled, the orchestrator will spawn a short-lived QA worker immediately after a Gatekeeper rejection. The QA worker reuses the same feature branch and is capped by a small iteration budget.

- Enable: `AUTOCODER_QA_SUBAGENT_ENABLED=1`
- Iterations: `AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS` (default `2`)
- Engines are configured in **Settings → Engines** (QA Fix chain).

In the Web UI: Settings -> Advanced -> Automation -> QA sub-agent (toggle only).

### Regression Pool (optional)

When enabled, the orchestrator spawns short-lived **Claude+Playwright** regression testers when there are **no claimable pending features**. Each tester picks a least-tested passing feature (`feature_get_for_regression`) and verifies it still works. If it finds a regression, it creates a new issue-like `REGRESSION` feature linked by `regression_of_id`.

- Enable: `AUTOCODER_REGRESSION_POOL_ENABLED=1`
- Max testers: `AUTOCODER_REGRESSION_POOL_MAX_AGENTS` (default `1`)
- Min interval: `AUTOCODER_REGRESSION_POOL_MIN_INTERVAL_S` (default `600`)
- Max iterations: `AUTOCODER_REGRESSION_POOL_MAX_ITERATIONS` (default `1`)
- Model (optional): `AUTOCODER_REGRESSION_POOL_MODEL` (e.g. `sonnet`)

In the Web UI: Settings -> Advanced -> Automation -> Regression Pool.

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

- Node fixture: `python scripts/e2e_qa_provider.py --out-dir "G:/Apps/autocoder-e2e-fixtures" --fixture node --engines '["codex_cli","gemini_cli","claude_patch"]'`
- Python/pytest fixture: `python scripts/e2e_qa_provider.py --out-dir "G:/Apps/autocoder-e2e-fixtures" --fixture python --engines '["codex_cli"]'`

This creates a minimal repo that intentionally fails verification on `feat/1`, then relies on the selected QA engine chain to generate a patch and resubmit until Gatekeeper merges.

You can also run this via the CLI (same codepath as the Diagnostics UI):

- `autocoder diagnostics --fixture node --engines '["codex_cli","gemini_cli","claude_patch"]' --out-dir "G:/Apps/autocoder-e2e-fixtures"`

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
