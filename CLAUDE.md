# AutoCoder (Claude Code / Claude Agent SDK)

This repository implements an autonomous coding agent using the **Claude Agent SDK**.

## High-level architecture

- **Workers**: `src/autocoder/agent/` (Claude Agent SDK loop + guardrails + MCP tools)
- **Orchestrator**: `src/autocoder/core/orchestrator.py` (parallel workers, port allocation, retries)
- **Gatekeeper**: `src/autocoder/core/gatekeeper.py` (deterministic verify + merge via temp worktree)
- **DB**: SQLite `agent_system.db` in each target project (features, attempts, artifacts, dependencies)
- **UI**: `src/autocoder/server/` + `ui/` (FastAPI + React)

## Key invariants

- Parallel runs must use **atomic feature claiming** (`claim_next_pending_feature`).
- Workers should **submit** work for verification (`review_status=READY_FOR_VERIFICATION`); Gatekeeper is the only component that marks merges as passing.
- Keep verification deterministic via `autocoder.yaml` in the target project.
- Runtime artifacts (`.autocoder/`, `worktrees/`, `agent_system.db`) should not block merges (Gatekeeper merges in a temp worktree).
- Initializer backlogs may be **staged** (disabled) to avoid huge active queues; staged features are re-enabled via enqueue.

## Alternate worker providers

Feature implementation can be switched from the Claude Agent SDK worker to a patch-based worker (Codex/Gemini CLIs) via `AUTOCODER_WORKER_PROVIDER` (`claude|codex_cli|gemini_cli|multi_cli`). Patch workers run `src/autocoder/qa_worker.py --mode implement` and still submit to Gatekeeper for deterministic verification.

## Initializer providers

Feature backlog generation can use:

- `claude` (default) via the Claude Agent SDK initializer prompt.
- `codex_cli` / `gemini_cli` / `multi_cli` to draft a JSON backlog (Codex/Gemini CLIs, optional Claude synthesis) and insert directly into the DB.

Configure via `autocoder.yaml` (`initializer:` block) or env (`AUTOCODER_INITIALIZER_*`).

## Local verification

- Python tests: `pytest -q`
- UI build: `npm -C ui run build`

## Diagnostics (recommended)

Use the UI: `#/settings/diagnostics` to run deterministic E2E fixtures and inspect run logs.
