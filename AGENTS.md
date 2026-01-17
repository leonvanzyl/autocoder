# Repository Guidelines

AutoCoder is a Claude Agent SDK + MCP based coding agent. It supports single-agent and parallel runs via isolated git worktrees, coordinated through SQLite (`agent_system.db`).

## Project Structure & Module Organization

- `src/autocoder/`: Python package root.
- `src/autocoder/core/`: orchestrator, DB, Gatekeeper, worktrees, port allocation.
- `src/autocoder/agent/`: Claude Agent SDK loop, hooks/guardrails, security allowlist.
- `src/autocoder/server/`: FastAPI API + WebSocket + UI static serving.
- `ui/`: React UI (build to `ui/dist`).
- `tests/`: `pytest` tests.

## Build, Test, and Development Commands

- Install (dev): `pip install -e '.[dev]'`
- Run single agent: `autocoder agent --project-dir <path>`
- Run parallel: `autocoder parallel --project-dir <path> --parallel 3`
- Start Web UI: `autocoder-ui` (then open `http://127.0.0.1:8888/`)
- Tests: `pytest -q`
- Format/lint: `black .` and `ruff check .`

## Coding Style & Naming Conventions

- Python: 4-space indentation; Black (line length 100).
- Prefer `pathlib.Path`; keep changes small and focused.
- Naming: `snake_case` for functions/modules, `CapWords` for classes.

## Testing Guidelines

- Framework: `pytest` (`tests/test_*.py`).
- Keep tests hermetic: temp dirs, no network, no real API keys.
- For orchestration/DB changes: add a state-transition test (claim -> work -> verify -> merge/retry).

## Orchestrator Reliability Notes

- When there are pending features but **none are claimable** (waiting on dependencies or `next_attempt_at` backoff), the orchestrator uses an **idle backoff** sleep (up to 60s) instead of tight polling.
- Use `features.last_error` and Gatekeeper artifacts under `.autocoder/features/<id>/gatekeeper/` to debug retries.
 - Feature implementation worker is configurable: `AUTOCODER_WORKER_PROVIDER=claude|codex_cli|gemini_cli|multi_cli` (patch workers use `src/autocoder/qa_worker.py --mode implement`).
- Large backlogs may be **staged** (disabled) to keep active queues manageable; staged features can be enqueued from the UI or via `POST /features/enqueue`.
- Skipping is for **external blockers only**; refactor/cleanup features are required work and should not be skipped.

## Project Maintenance (UI)

- Settings → Project Config includes a **Danger Zone**:
  - **Reset**: clears runtime artifacts (`agent_system.db`, `.autocoder/`, `worktrees/`).
  - **Full reset**: also wipes `prompts/` so the spec must be recreated.
  - **Delete**: removes the project from the registry (optional delete-on-disk).
- Projects with placeholder specs are flagged as **setup required** in the UI.

## Knowledge Files (Project Context)

- Add project-specific notes under `<project>/knowledge/*.md`.
- These are injected into initializer/coding prompts, assistant chat, and QA patch workers.
- Web UI: open **Knowledge** (shortcut `K`) to manage files.

## Settings Persistence

- **Per-project**: model settings are stored in the target project’s `agent_system.db` (so settings travel with the project).
- **Global**: UI “Advanced Settings” are stored in `~/.autocoder/settings.db` (override with `AUTOCODER_SETTINGS_DB_PATH`). Legacy `~/.autocoder/ui_settings.json` is auto-migrated on first load.

## Commit & Pull Request Guidelines

- Commits: short, imperative summaries (e.g., `core: fix feature claiming race`).
- PRs: include what changed, how to verify, and test output; add UI screenshots for UI changes.
- After a PR is merged, delete the feature branch locally and on `origin` to keep the repo clean.

## Security & Agent-Specific Notes

- Don’t commit runtime artifacts: `agent_system.db`, `.autocoder/`, `worktrees/`.
- Gatekeeper is deterministic and the only component allowed to merge to main.
- Shell tool usage is restricted by an allowlist in `src/autocoder/agent/security.py`; treat changes there as security-sensitive.
