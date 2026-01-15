# External Reference Patterns (to_check/)

This repo includes `to_check/` as a scratchpad of external projects that use the Claude Agent SDK and/or multi-agent orchestration. We **do not copy code** from these repos unless their license allows it; we use them for **ideas, architecture patterns, and UX inspiration**.

## High-value patterns to port into AutoCoder

### Orchestration & reliability
- **Fresh-context, atomic tasks** (`mala`): keep issues/features small; restart agents per feature to avoid context drift.
- **Two-layer coordination** (`mala`): combine *issue claiming* (DB/queue) with *file locks* (prevent parallel edits to same files).
- **DAG scheduling + smart waits** (`claude-code-orchestrator`): model features as a dependency graph and run ready tasks in parallel.
- **Circuit breakers / retries** (`claude-code-orchestrator`, `mala`): bounded retries with exponential backoff; persist failure reasons.

### Quality gates & multi-model checks
- **Multi-model review consensus** (`cerberus`): run Codex/Gemini/Claude reviews in parallel; require majority/all before merge.
- **Specialized “expert” reviewers** (`scagent`): different perspectives (security, architecture, UX) produce more actionable feedback.
- **Evidence-based verification** (`mala`): require deterministic commands (setup/test/lint/typecheck) as merge evidence.

### Testing & UX automation
- **Docs-as-tests acceptance testing** (`AutoQA-Agent`): Markdown specs → Playwright runs → export stable test code + artifacts.
- **Artifacts-first debugging** (`AutoQA-Agent`, `cerberus`): store run outputs, diffs, and excerpts as files and surface them in UI.

### Sub-agent architecture
- **Orchestrator + subagents** (`claude-agent-sdk-mastery`, `multi-agent-builder`): coordinator spawns specialists (planner/implementer/tester/reviewer) with isolated context and budgets.

## Recommended integration approach

1. **Standardize stages** (plan → implement → verify → review → merge) with a single “pipeline” interface.
2. **Persist artifacts** for every stage under `.autocoder/` and store concise excerpts in DB (`features.last_error`).
3. **Keep provider-agnostic hooks**: Claude Agent SDK for workers; optional external CLI reviewers (Codex/Gemini) for review/QA.

## Licensing note

Some references are **AGPL** (e.g. `to_check/autoclaude`) or have **no license**; treat them as *inspiration only*. Prefer implementing concepts from scratch and keep changes reviewed.

## Status in this repository

Implemented (core behavior + tests + UI where applicable):
- Retry/backoff + bounded retry scheduling (`features.next_attempt_at`)
- No-progress loop breaker (same error streak + same diff fingerprint -> `BLOCKED`)
- Gatekeeper artifacts + DB pointers (`features.last_error`, `features.last_artifact_path`)
- Framework-agnostic verification via `autocoder.yaml` + UI editor
- Worktree cleanup queue (Windows file-lock resilience)
- Optional multi-model review (Codex/Gemini CLIs) in Gatekeeper
- Optional QA fix mode (worker switches to “fix last failure” prompt)

Still planned / partially implemented:
- “No-progress” detection based on *code not changing* is implemented, but can be improved by using commit hashes and/or per-file fingerprints
- True QA sub-agent process (separate short-lived session/process) + optional multi-provider QA
