# Sub-Agents & Fix Modes (QA + Controller)

AutoCoder is built on the **Claude Agent SDK** and supports short-lived “sub-agent” style passes to improve reliability after deterministic verification failures.

## QA Fix Mode (implemented)

When enabled, workers switch into a **“fix the last Gatekeeper failure”** prompt on retries. The agent is given `features.last_error` / `features.last_artifact_path` and is instructed to focus only on making verification pass (no new scope).

Env vars:
- `AUTOCODER_QA_FIX_ENABLED=1`
- `AUTOCODER_QA_MODEL=` (optional; blank = default)
- `AUTOCODER_QA_MAX_SESSIONS=3` (limits QA sessions per feature)

Web UI:
- Settings -> Advanced -> Automation -> QA auto-fix

## QA Sub-Agent (implemented)

When enabled, **immediately after a Gatekeeper rejection**, the orchestrator spawns a short-lived QA worker process that:
- Reuses the **same feature branch** (no branch churn).
- Runs with a smaller iteration budget (YOLO off).
- Uses QA Fix Mode prompts (so it only fixes the failure).

Env vars:
- `AUTOCODER_QA_SUBAGENT_ENABLED=1`
- `AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS=2`

Web UI:
- Settings -> Advanced -> Automation -> QA sub-agent (toggle)
- Settings -> Engines -> QA Fix (engine order)

## Engine Chains (implemented)

AutoCoder uses **engine chains** (per project) for feature implementation, QA fixers, review, spec drafts, and initializer drafts. Configure them in:

- Settings -> Engines (project scoped)
- `GET/PUT /api/engine-settings?project=...`

Patch worker entrypoint: `src/autocoder/qa_worker.py --mode implement --engines '["codex_cli","gemini_cli","claude_patch"]'`.

## Controller (preflight verification)

When enabled, the orchestrator runs a deterministic **preflight verification** pass in the agent worktree
before doing a full Gatekeeper merge verification. This catches common issues early (missing test scripts,
typecheck failures, etc.) and routes failures into the same QA retry pipeline.

Env vars:
- `AUTOCODER_CONTROLLER_ENABLED=1`
- `AUTOCODER_ALLOW_NO_TESTS=1` only applies in YOLO mode and only for clearly-detectable "no tests" cases.

## Multi-Model Reviews

For a second "opinion" from another model (Codex/Gemini/etc.), use the **Gatekeeper review step** via `review:` in the target project's `autocoder.yaml` and configure the engine chain in **Settings → Engines**. See `docs/multi_model_review.md`.

## Planner (feature plan)

When enabled, the orchestrator generates a short per-feature plan and prepends it to the worker prompt.
This uses the same multi-provider generation system as the Spec/Plan generator.

Env vars:
- `AUTOCODER_PLANNER_ENABLED=1`
- `AUTOCODER_PLANNER_SYNTHESIZER=claude` (`none|claude|codex|gemini`)
- `AUTOCODER_PLANNER_TIMEOUT_S=180`
- `AUTOCODER_PLANNER_MODEL=` (optional Claude model for synthesis)

Web UI:
- Settings -> Advanced -> Automation -> Planner (toggle + synthesizer)
- Settings -> Engines -> Spec Draft (engine order)
