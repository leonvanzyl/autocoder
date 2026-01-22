# Changelog

All notable changes to this fork will be listed here.

## Unreleased

- Home Dashboard: bento layout with projects grid, system status, and shortcuts; safe “back to Dashboard” navigation even while agents run (shows “running in background” card)
- Settings page now supports **Global** scope without selecting a project (Dashboard → Settings / `S`)
- Project setup required banner with 24h snooze (Expand stays locked until spec is real)
- Project reset endpoint (runtime reset + full reset) and UI Danger Zone controls
- Project delete: if Windows file locks block deletion, the project is still removed from the registry and deletion is queued for the cleanup worker
- Knowledge files (`/knowledge/*.md`) injected into prompts + UI editor modal
- Single-agent loop exits when no pending/staged/verification features remain
- Clarified prompt guidance: refactor/cleanup features are mandatory and override the original spec
- Regression selection now prioritizes least-tested features (tracks `regression_count`)
- UI auto-build now detects stale `ui/dist` and rebuilds when sources are newer
- UI auto-build shows which file triggered rebuild; optional mtime tolerance for FAT32/exFAT (`AUTOCODER_UI_MTIME_TOLERANCE_S`)
- UI static serving: disable caching for `index.html` to avoid stale bundles after rebuilds
- UI reliability: global error boundary shows a recovery screen instead of a blank page
- Diagnostics: show UI build id + backend git SHA; one-click “Copy debug info”
- WebSocket debug logs deduplicate consecutive identical lines (prevents StrictMode double-connect noise)
- Assistant chat: avoid history loss on conversation switch, disable input while loading, and reduce server log noise
- Scheduled runs (UI) with persisted schedule state
- New `AUTOCODER_STOP_WHEN_DONE` toggle to keep agents alive on empty queues
- LAN-ready UI host toggle (`AUTOCODER_UI_HOST`, `AUTOCODER_UI_ALLOW_REMOTE`)
- Windows CLI length guard for assistant chat via temporary `CLAUDE.md`
- Atomic per-project agent lock (`<project>/.agent.lock`) + PID-reuse protection + stop kills full process tree
- SQLite defaults to WAL, but falls back to DELETE on network filesystems (override via `AUTOCODER_SQLITE_JOURNAL_MODE`)
- Fix: fresh projects no longer exit early before initializer creates features
- Agent auto-continue: improved “limit reached” parsing (resets-at variants) + 24h clamp
- MCP `feature_create_bulk`: validate inputs before writing to DB
- Worker logs: copy tail to clipboard
- Playwright MCP now runs with `--isolated` by default (disable with `AUTOCODER_PLAYWRIGHT_ISOLATED=0`)
- Optional regression tester pool (Claude+Playwright): creates issue-like `REGRESSION` features linked via `regression_of_id`
- Mission Control activity feed: DB-backed timeline (Gatekeeper/QA/regressions) shown on the project dashboard + bottom drawer Activity tab (shortcut: `M`)
- Activity retention/pruning: `AUTOCODER_ACTIVITY_KEEP_DAYS`, `AUTOCODER_ACTIVITY_KEEP_ROWS` (also configurable in UI Advanced → Logs)
- UI polish: calmer hover states (no “everything jumps”), slightly softer rounding, Assistant button stays above the logs drawer
- Settings UX: Advanced settings now use friendly labels/tooltips, warn on unsafe toggles, and disable Codex/Gemini-only options when their CLIs aren’t detected
- Settings UX: replaced CSV “agent lists” with safe pickers + ordered selection; added in-UI Help modals for Review/Locks/Gatekeeper/QA/Planner/Initializer/Regression; file locks default to ON (with confirmation when disabling)
- Codex CLI defaults: auto-detect `model` + `model_reasoning_effort` from `~/.codex/config.toml` (Codex reasoning effort now supports `xlow|xmedium|xhigh`)
- Fix: Gatekeeper verify-branch sanitization is Python 3.10 compatible
- Fix: `test_mcp` includes missing `json` import

## 2026-01-17

- Web UI startup banner + boot checklist; auto-open browser toggle
- Windows terminal auto-install for pywinpty in UI
- Dynamic spec/expand skill resolution fixes
