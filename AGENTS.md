# Repository Guidelines

AutoCoder is built on the Claude Agent SDK + MCP tools. It supports single-agent and parallel (git worktree) runs; coordination uses SQLite (`agent_system.db`).

## Project Structure & Module Organization

- `src/autocoder/`: main Python package.
- `src/autocoder/core/`: orchestrator, DB, gatekeeper, worktrees, knowledge base.
- `src/autocoder/agent/`: agent loop, SDK client, hooks/guardrails, security allowlist.
- `src/autocoder/tools/`: MCP servers (notably `feature_mcp.py`).
- `src/autocoder/server/`: FastAPI backend for the Web UI.
- `ui/`: React UI (built artifacts served by `src/autocoder/server/`).
- `tests/`: pytest-based smoke/integration tests.

## Build, Test, and Development Commands

- Install (dev): `pip install -e '.[dev]'`
- Run interactive CLI: `autocoder`
- Run single agent: `autocoder agent --project-dir <path> [--yolo]`
- Run parallel agents: `autocoder parallel --project-dir <path> --parallel 3`
- Launch Web UI: `autocoder-ui`
- Prune worker logs: `autocoder logs --project-dir <path> --prune [--dry-run]`
- Run tests: `pytest -q`
- Format/lint: `black .` and `ruff check .`

## Coding Style & Naming Conventions

- Python: 4-space indentation; Black (line length 100).
- Prefer `pathlib.Path`; keep changes focused and small.
- Status values in the unified DB are uppercase: `PENDING`, `IN_PROGRESS`, `DONE`.
- Naming: modules/functions `snake_case`, classes `CapWords`, constants `UPPER_SNAKE_CASE`.

## Testing Guidelines

- Framework: `pytest` (`tests/test_*.py`).
- Keep tests hermetic: temp dirs, no network, no real API keys.
- For orchestration/DB changes, add/update a focused state-transition test.

## Commit & Pull Request Guidelines

- Commits: short, imperative summaries (e.g., `core: fix feature claiming race`), one logical change per commit.
- PRs: include a short description, how to verify, and test output; add UI screenshots when relevant.

## Security & Agent-Specific Notes

- Shared coordination DB is `agent_system.db` in the project directory; do not commit runtime DB files or `worktrees/`.
- SQLite is tuned for multi-process (WAL + busy timeout); avoid ad-hoc connections without these settings.
- UI server port uses `AUTOCODER_UI_PORT` (default `8888`); parallel agents use per-worker `AUTOCODER_API_PORT` / `AUTOCODER_WEB_PORT` to avoid port conflicts.
- Parallel workers run in isolated git worktrees but share `PROJECT_DIR` (for `agent_system.db`) so all agents see the same queue.
- Worker stdout/stderr is written to `./.autocoder/logs/*.log` (not stored in SQLite); manage via CLI or the Web UI **Logs** modal (`L`).
- Prefer `feature_claim_next` for atomic feature assignment; `feature_get_next` is legacy/non-atomic.
- In parallel mode, `feature_mark_passing` submits for Gatekeeper verification; `passes=true` is set only after deterministic verification/merge.
- Bash tool usage is restricted by an allowlist in `src/autocoder/agent/security.py`; treat changes there as security-sensitive and test thoroughly.
