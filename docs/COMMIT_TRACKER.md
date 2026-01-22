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
| `9039108` | Split UI bundle into smaller chunks | **Ported (adapted)** | Added `manualChunks` split in `ui/vite.config.ts` (Windows-safe path normalization). |
| `28e8bd6` | Conversation history perf + delete UX + memoized chat messages | **Ported (adapted)** | Ported N+1 fix + cached SQLAlchemy engine/session for assistant DB; added delete error feedback + memoized `ChatMessage` (our component set differs). |
| `85f6940` | Parallel orchestration + dependency graph UI + agent mission control | **Partially ported** | We’re not adopting upstream’s dependency-graph orchestrator, but we *did* port the Playwright MCP `--isolated` behavior to reduce cross-agent browser conflicts. |
| `bf3a6b0` | Per‑agent log viewer + stuck agent fixes + scheduling score | **Ported (adapted)** | Added per‑agent log jump + activity mini‑list, copy-to-clipboard for tails, and guarded the SDK client context manager to prevent “stuck” crash states. Scheduling score not applicable (we already prioritize blockers). |
| `76e6521` | Dependency graph blank fix | **N/A** | We don’t ship dependency graph UI in this fork. |
| `5f78607` | SQLAlchemy session cache fix in parallel orchestrator | **N/A** | We don’t use SQLAlchemy; our DB layer is raw SQLite with explicit retry/backoff. |
| `1312836` | Dedicated testing agents + testing ratio + MCP mark‑failing | **Ported (adapted)** | We did **not** adopt upstream’s SQLAlchemy/DAG orchestrator or dependency graph UI. We *did* port the “dedicated tester” idea as an **optional regression pool** (Claude+Playwright) that reports failures as new `REGRESSION` features via `feature_report_regression`. |
| `126151d` | “Production readiness”: locks + PID reuse + WAL safety + Windows cleanup | **Ported (selectively)** | Ported atomic `<project>/.agent.lock` (`PID:CREATE_TIME`) + PID reuse protection + process‑tree stop; added SQLite journal mode fallback for network drives (`AUTOCODER_SQLITE_JOURNAL_MODE` override). |
| `6c8b463` | Completion detection: don’t treat initializer as “done” | **Ported (adapted)** | Our single-agent completion check now skips the first initializer session (prevents exiting on an empty DB before the initializer creates features). |
| `fbe4c39` | UI build reliability: config inputs + FAT32 tolerance + trigger logging | **Ported (adapted)** | We already track config files; added `AUTOCODER_UI_MTIME_TOLERANCE_S` + best-effort trigger logging when auto-rebuilding `ui/dist`. |

## Full upstream audit (master..upstream/master) — 2026-01-19

This is the **full list** of upstream commits we don’t have (as of 2026-01-19), ordered newest → oldest.
Status is relative to this fork’s behavior (we often re-implement upstream ideas differently).

Legend:
- **Ported**: explicitly ported/adapted into this fork
- **Already have**: behavior exists here (different implementation is fine)
- **Skipped**: not applicable / conflicts with our architecture / no value

| Commit | Upstream summary | Status | Notes |
| --- | --- | --- | --- |
| `29c6b25` | correct SDK import and clear stale agent UI on stop | **Already have** | We use `claude_agent_sdk` and reset WS state on project switch; activity/agent panels are DB-backed. |
| `9039108` | split bundle into smaller chunks for better caching | **Ported** | Implemented Vite `manualChunks` split (react/query/xterm/ui) to reduce initial load + improve caching. |
| `28e8bd6` | conversation history perf + code quality fixes | **Ported (selectively)** | Assistant DB: cached engine/session + SQL count; UI: delete errors stay visible + memoized chat message rendering. |
| `fbe4c39` | improve build_frontend reliability and cross-platform compatibility | **Ported** | Added UI rebuild trigger logging + optional mtime tolerance (`AUTOCODER_UI_MTIME_TOLERANCE_S`). |
| `3c80611` | Merge PR #76 (ui-build-detection) | **Skipped** | Merge commit only. |
| `6c8b463` | use is_initializer instead of undefined is_first_run variable | **Ported** | Fixed first-run completion check edge case for initializer runs. |
| `0391df8` | Merge PR #77 (agent-completion-detection) | **Skipped** | Merge commit only. |
| `1312836` | dedicated testing agents + enhanced parallel orchestration | **Partially ported** | We added an optional regression pool (Claude+Playwright testers) + `feature_report_regression` issue creation. We did **not** adopt upstream’s SQLAlchemy/DAG orchestrator or dependency graph UI. |
| `ffdd97a` | completion detection to prevent infinite loop when all features done | **Already have** | We exit when queue is empty (or wait if `AUTOCODER_STOP_WHEN_DONE=0`). |
| `32fb4dc` | UI build detection to check source file timestamps | **Already have** | We already compare `ui/src` + config inputs against `ui/dist`. |
| `5f78607` | prevent orchestrator early exit due to stale session cache | **Skipped** | Upstream SQLAlchemy session issue; we use raw SQLite. |
| `64b6531` | clean up unused imports and sort import blocks | **Skipped** | Style-only. |
| `126151d` | production readiness fixes for dependency trees and parallel agents | **Ported** | Atomic project lock + PID reuse protection + process-tree stop; WAL safety fallback on network filesystems. |
| `92450a0` | graph refresh issue | **Skipped** | Dependency graph UI not shipped in this fork. |
| `76e6521` | prevent dependency graph from going blank during agent activity | **Skipped** | Dependency graph UI not shipped in this fork. |
| `bf3a6b0` | per-agent logging UI + stuck agent fixes + scheduling score | **Ported** | Added per-agent log jump + activity mini-list + copy tail; guard SDK client context errors to avoid stuck/crash UI states. |
| `85f6940` | concurrent agents with dependency system + “mission control” UI | **Skipped** | Architecture mismatch (upstream parallel orchestrator + dependency graph). We still ported one high-signal idea: Playwright MCP `--isolated` by default (toggle via `AUTOCODER_PLAYWRIGHT_ISOLATED=0`). |
| `91cc00a` | add explicit in_progress=False to all feature creation paths | **Skipped** | Our DB uses `status` + `review_status` (not `in_progress` boolean). |
| `ab51bb6` | Merge PR #53 (null booleans resilience) | **Skipped** | Merge commit only. |
| `2757ca3` | Merge PR #57 (GSD integration) | **Skipped** | Merge commit only. |
| `2216657` | Merge PR #58 (env model override) | **Skipped** | Merge commit only. |
| `53f0b36` | Merge PR #59 (shell script permissions) | **Skipped** | Merge commit only. |
| `5068790` | use MCP tool for feature persistence in expand-project | **Already have** | Our expand flow persists via `feature_create_bulk()` / unified DB. |
| `bc2f12b` | Merge PR #67 (ui-design-system-improvements) | **Skipped** | Merge commit only. |
| `02d0ef9` | address UI code review feedback | **Already have** | Our UI diverged, but the same UX concerns are handled. |
| `501719f` | comprehensive design system improvements | **Already have** | We ported + extended the design system in our UI. |
| `d1b8eb5` | feature editing for pending/in-progress features | **Already have** | Feature edit/delete exists in this fork. |
| `c2f9848` | add execute permission to shell scripts | **Already have** | Our `start*.sh` scripts are executable in git. |
| `bc7970f` | use ANTHROPIC_DEFAULT_OPUS_MODEL env var for model selection | **Already have** | We support `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`. |
| `29715f2` | add GSD integration skill for existing projects | **Already have** | GSD → `prompts/app_spec.txt` generation exists here. |
| `3c97051` | boolean fields resilient to NULL values | **Already have** | We treat NULL-ish values defensively in DB + schemas. |
| `07c2010` | write system prompts to file to avoid Windows command line limit | **Already have** | We write prompts to `CLAUDE.md` for long system prompts. |
| `9816621` | resolve command too long message | **Already have** | We guard Windows CLI length issues (assistant/spec/expand). |
| `f31ea40` | GLM/alternative API support via env vars | **Already have** | Supported via `.env` + provider badge in header. |
| `a7f8c3a` | multiple terminal tabs with rename capability | **Already have** | Terminal tab creation + rename exists in `TerminalTabsPanel`. |
| `c1985eb` | interactive terminal + dev server management | **Already have** | UI terminal + dev server controls exist in this fork. |
| `b1473cd` | reset WebSocket state when switching projects | **Already have** | We reset state on project switch + guard StrictMode reconnect. |
| `aede8f7` | decouple project name from folder path | **Already have** | Duplicate-path registration blocked; name can differ from folder. |
| `b18ca80` | hide AssistantFAB during spec creation mode | **Already have** | Assistant FAB is hidden while spec chat runs. |
| `334b655` | move feature action buttons to pending column header | **Skipped** | Our header/settings layout is different (actions moved to Settings hub). |
| `117ca89` | configurable CLI command + UI improvements | **Already have** | `AUTOCODER_CLI_COMMAND` + UI wiring exists. |
| `a0f7e72` | consolidate auth error handling and fix start.bat credential check | **Already have** | Auth error detection + fix hints in UI/server output. |
| `cd82a4c` | Merge PR #12 (start.sh credential check) | **Skipped** | Merge commit only. |
| `7007e2b` | Merge PR #28 (assistant feature management) | **Skipped** | Merge commit only. |
| `f7da9d6` | ignore strange nul files on Windows | **Already have** | We ignore stray Windows `nul` artifacts. |
| `d5d8191` | rename test_hook to check_hook (pytest fixture) | **Skipped** | Not applicable (we don’t have the old fixture). |
| `b633e6d` | Merge PR #35 | **Skipped** | Merge commit only. |
| `1998de7` | resolve merge conflicts and clean up expand project feature | **Already have** | Our expand-project implementation is different but covers the same fixes. |
| `0e7f8c6` | Merge PR #36 (expand-project-with-ai) | **Skipped** | Merge commit only. |
| `56202fa` | merge branch master into expand-project-with-ai | **Skipped** | Merge commit only. |
| `cbe3ecd` | resolve CI linting errors (Python + ESLint) | **Skipped** | We don’t enforce ruff/eslint in CI yet (ruff currently fails on legacy/dev files). |
| `dff28c5` | cross-platform venv compatibility in WSL | **Skipped** | Our preferred flow is `pip install -e '.[dev]'` + entrypoints; scripts still activate `.venv` when present. |
| `cdcbd11` | second-round code review fixes (expand session locks + ws reconnection) | **Already have** | Our expand session uses `asyncio.Lock`, temp settings files, safer ws reconnect handling. |
| `9c07dd7` | coderabbit fixes: more flexible limit parsing + clamp delays | **Ported** | Match `limit reached` anywhere in the response, accept `resets at …`, clamp delay to 24h. |
| `2b2e28a` | improve “limit reached” UI message context | **Ported** | Clearer log line: “Claude Code Limit Reached…” for easier debugging + UI log scanning. |
| `75f2bf2` | code review fixes for expand-project (security + idempotent start) | **Already have** | Our expand flow avoids leaking exception details and is idempotent/reconnect-safe. |
| `5f06dcf` | Expand Project for bulk AI-powered feature creation | **Already have** | Expand modal/chat + feature bulk creation exists here. |
| `7f436a4` | reset time parsing for auto-continue | **Already have** | Auto-continue waits until reset time (plus we added timezone handling). |
| `118f393` | validation constraints to feature_create tool | **Ported** | `feature_create_bulk` now validates input via Pydantic constraints before writing to DB. |
| `398c9d4` | assistant chat to create/manage features | **Already have** | Assistant can create/update/delete features via MCP tools. |
| `a195d6d` | YOLO mode effects | **Already have** | YOLO toggle + styling exists; exact visual treatment differs (intent preserved). |
| `b2c19b0` | auth error handling to UI flow | **Already have** | Auth errors detected + hint printed into logs. |
| `780cfd3` | auth error handling to start.py | **Already have** | Startup banner/checklist + auth hinting exists. |
| `81dbc4b` | start.sh Claude CLI auth detection | **Already have** | Shell launchers load `.env` and check CLIs; auth hints are handled in-process. |
| `45ba266` | global settings modal + simplify agent controls | **Already have** | Advanced settings stored in DB; Settings hub + modal exist. |
| `122f03d` | GitHub Actions CI for PR protection | **Already have** | We have CI (pytest + UI build). Lint parity is optional future work. |
| `17b7354` | activate venv in UI launcher scripts | **Already have** | `start_ui.sh` activates `.venv` when present. |
| `63731c1` | rebrand | **Skipped** | This fork has its own branding/UX. |

## Rules of thumb
- If an upstream change depends on `parallel_orchestrator.py` + dependency graph, treat as a **separate track** unless we decide to migrate architectures.
- If it improves reliability/observability and doesn’t conflict with our design, **port it**.
- If it conflicts with our gatekeeper + worktree model, **document the mismatch and skip**.
