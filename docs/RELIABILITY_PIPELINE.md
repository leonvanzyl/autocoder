# Reliability Pipeline (Parallel Mode)

This document explains the reliability mechanisms that keep AutoCoder’s parallel mode from getting stuck in infinite retry loops or leaking worktrees/logs over time.

## Feature lifecycle (high level)

1. **Orchestrator** claims a pending feature (atomic DB claim).
2. It creates an isolated **git worktree** and spawns a worker process for that feature.
3. The worker implements code and submits the feature for **Gatekeeper** verification.
4. **Gatekeeper** verifies in a fresh temp worktree and merges to the main branch only if verification passes.
5. On success: feature becomes `DONE`/passing. On failure: feature is scheduled for retry with backoff.

Implementation note: parallel workers **exit automatically** once the feature is submitted for verification
(`review_status=READY_FOR_VERIFICATION`) so the orchestrator can recycle ports and move on.

## Retry/backoff (prevents tight failure loops)

When a feature fails verification, AutoCoder records:

- `features.attempts`: how many times the feature has been attempted
- `features.next_attempt_at`: when it is eligible to retry (exponential backoff)
- `features.last_error`: short excerpt shown in UI and fed to retry prompts

Backoff knobs:

- `AUTOCODER_FEATURE_RETRY_INITIAL_DELAY_S` (default `10`)
- `AUTOCODER_FEATURE_RETRY_MAX_DELAY_S` (default `600`)
- `AUTOCODER_FEATURE_RETRY_EXPONENTIAL_BASE` (default `2`)
- `AUTOCODER_FEATURE_RETRY_JITTER` (default `true`)

## No-progress loop breaker (blocks repeated identical failures)

Backoff slows retries; it does not stop “no progress” situations where the same error repeats forever. AutoCoder also tracks:

- `features.last_error_key`: normalized failure fingerprint
- `features.same_error_streak`: how many consecutive attempts hit the same error

When `same_error_streak` reaches `AUTOCODER_FEATURE_MAX_SAME_ERROR_STREAK` (default `3`), the feature becomes `BLOCKED` with a clear reason. This prevents churn and frees agents to work on other features.

### Diff fingerprint (code didn’t change)

Gatekeeper also computes a `diff_fingerprint` for the merged change-set (the staged diff in the verification worktree). AutoCoder tracks:

- `features.last_diff_fingerprint`
- `features.same_diff_streak`

If the **same diff** keeps getting produced and verification still fails, AutoCoder treats that as “no progress” and blocks the feature after `AUTOCODER_FEATURE_MAX_SAME_DIFF_STREAK` (default `3`).

## Evidence-first artifacts (debuggable retries)

Gatekeeper writes a JSON artifact for every verification attempt. AutoCoder stores the pointer in:

- `features.last_artifact_path`: path to the most recent Gatekeeper artifact

Default locations:

- `.autocoder/features/<feature_id>/gatekeeper/<timestamp>.json` (preferred)
- `.autocoder/gatekeeper/<timestamp>.json` (fallback if feature id is unknown)

These artifacts include the exact command(s), exit code, and stderr/stdout excerpt that caused rejection.

## Optional QA sub-agent (automatic fix pass)

When enabled, AutoCoder can spawn a short-lived QA worker immediately after Gatekeeper rejects a feature. The QA worker:

- Reuses the same `branch_name` (no branch churn).
- Sees `last_error` + `last_artifact_path` and is instructed to only fix verification failures.
- Is capped by `AUTOCODER_QA_MAX_SESSIONS` (per feature) and `AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS` (per QA run).

Env vars:

- `AUTOCODER_QA_FIX_ENABLED=1` (prompt mode)
- `AUTOCODER_QA_MAX_SESSIONS=3`
- `AUTOCODER_QA_SUBAGENT_ENABLED=1`
- `AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS=2`

Web UI:

- Settings -> Advanced -> Automation -> QA sub-agent
- Settings -> Engines -> QA Fix (engine chain)

## Engine chains (feature workers, QA, review, spec, initializer)

Feature implementation normally runs through the Claude Agent SDK loop. For some environments, you can switch feature implementation to a patch worker chain that emits a unified diff via external CLIs (Codex/Gemini) and submits to Gatekeeper for deterministic verification.

Engine chains are configured per project in the Web UI:

- Settings -> Engines (project scoped)
- API: `GET/PUT /api/engine-settings?project=...`

## Worktree cleanup queue (Windows-safe)

On Windows, `node_modules` can be locked (WinError 5) and prevent deleting worktrees. AutoCoder uses a deferred cleanup queue:

- `.autocoder/cleanup_queue.json`

Failed deletions are queued and retried later so `worktrees/` doesn’t grow unbounded.

## Project run lock (Web UI start/stop)

When starting an agent from the Web UI, AutoCoder enforces a **single run per project directory** using a lock file:

- Lock file: `<project>/.agent.lock`
- Format: `PID:CREATE_TIME` (or legacy `PID`)
- Created **atomically** (`O_CREAT|O_EXCL`) to avoid race conditions
- Includes **PID reuse protection** via `psutil.Process(pid).create_time()`

If a second UI session tries to start the same project, it fails fast instead of spawning a “ghost” process.
Stopping a run kills the **full process tree** (parent + children) to avoid orphaned `node`/`npm` processes on Windows.

## SQLite journal mode safety (WAL vs network drives)

AutoCoder uses `journal_mode=WAL` by default because the orchestrator is multi-process and needs decent concurrency.

On network filesystems (SMB/NFS/etc), WAL can be unsafe. AutoCoder detects that case and falls back to:

- `journal_mode=DELETE`

You can override explicitly:

- `AUTOCODER_SQLITE_JOURNAL_MODE=WAL|DELETE|TRUNCATE|PERSIST|MEMORY|OFF`

## Log & artifact retention (storage hygiene)

Worker logs live at:

- `.autocoder/logs/*.log`

Gatekeeper artifacts live at:

- `.autocoder/**/gatekeeper/*.json`

Manual pruning:

- CLI: `autocoder logs --project-dir <path> --prune --include-artifacts`
- UI: Logs panel → Prune → “Include Gatekeeper artifacts”

Automatic pruning during runs:

- `AUTOCODER_LOGS_KEEP_DAYS`, `AUTOCODER_LOGS_KEEP_FILES`, `AUTOCODER_LOGS_MAX_TOTAL_MB`
- `AUTOCODER_LOGS_PRUNE_ARTIFACTS=1` (also prunes Gatekeeper artifacts)

Web UI:

- Settings -> Advanced -> Logs -> "Auto-prune Gatekeeper artifacts"

## Acceptance checks (docs-as-tests friendly)

Gatekeeper can run additional deterministic commands beyond `test`/`lint`/`typecheck`.

If your project defines `commands.acceptance` in `autocoder.yaml` (for example, Playwright smoke tests),
Gatekeeper will run it after build steps and block merges on failure (unless `allow_fail: true`).

## Controller preflight (optional)

If `AUTOCODER_CONTROLLER_ENABLED=1`, the orchestrator runs the same verification command pipeline in the
agent worktree **before** invoking Gatekeeper merge verification. Failures go through the same retry/QA
sub-agent workflow, but without burning a Gatekeeper merge attempt.

## Feature planning (optional)

If `AUTOCODER_PLANNER_ENABLED=1`, AutoCoder generates a short per-feature plan (optionally multi-model)
and prepends it to the worker prompt. This tends to reduce thrash in parallel mode by making the
implementation/verification checklist explicit.

Planner synthesis is timeboxed and safe to call from within the orchestrator’s asyncio event loop
(`claude` synthesis runs in a dedicated thread to avoid `asyncio.run()` conflicts).

## Diagnostics (Web UI)

The Web UI includes a **Diagnostics** page to validate the reliability pipeline without guessing:

- Configure a fixtures directory (defaults to `dev_archive/e2e-fixtures`).
- Run deterministic E2E fixtures (QA engine pipeline, parallel mini project).
- View recent run logs + tail output.

Implementation note: the "Parallel Mini" fixture uses a deterministic dummy worker (`AUTOCODER_E2E_DUMMY_WORKER=1`)
so it can validate orchestration + Gatekeeper merge quickly without requiring an LLM.
