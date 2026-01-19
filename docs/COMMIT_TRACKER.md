# Commit Tracker

Purpose: keep a lightweight record of upstream changes and whether we’ve ported, adapted, or intentionally skipped them.

## How to update

```bash
git fetch upstream --prune
git log --oneline upstream/master..master   # what we have that upstream doesn't
git log --oneline master..upstream/master   # what upstream has that we don't
```

## Upstream watchlist (leonvanzyl/autocoder)

| Commit | Summary | Status in this fork | Notes / Action |
| --- | --- | --- | --- |
| `85f6940` | Parallel orchestration + dependency graph UI + agent mission control | **Not ported** | Different architecture (worktree-based orchestrator). We already have dynamic ports, QA sub-agent, gatekeeper artifacts. Dependency graph UI is nice but requires upstream feature graph + parallel orchestrator. |
| `bf3a6b0` | Per‑agent log viewer + stuck agent fixes + scheduling score | **Partially ported** | Added per‑agent log jump (Agent Status → logs drawer), friendlier labels, and recent activity mini‑list + configurable colors. We already have WorkerLogsPanel + gatekeeper artifacts + retry/backoff. Scheduling score not applicable. |
| `76e6521` | Dependency graph blank fix | **N/A** | We don’t ship dependency graph UI in this fork. |
| `5f78607` | SQLAlchemy session cache fix in parallel orchestrator | **N/A** | We don’t use SQLAlchemy; our DB layer is raw SQLite with explicit retry/backoff. |
| `1312836` | Dedicated testing agents + testing ratio + MCP mark‑failing | **Partial overlap** | We already run tests in Gatekeeper + spawn QA fixers on failure (configurable provider). Consider optional **parallel QA ratio** later if we want proactive test agents. |

## Rules of thumb
- If an upstream change depends on `parallel_orchestrator.py` + dependency graph, treat as a **separate track** unless we decide to migrate architectures.
- If it improves reliability/observability and doesn’t conflict with our design, **port it**.
- If it conflicts with our gatekeeper + worktree model, **document the mismatch and skip**.
