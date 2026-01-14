# Sub-Agents & Fix Modes (QA + Controller)

AutoCoder supports an optional **QA fix mode** today, and leaves hooks for future “sub-agent” style pipelines (separate Claude Agent SDK sessions for QA/controller).

## QA Fix Mode (implemented)

When enabled, parallel workers switch into a “fix the last failure” prompt after Gatekeeper rejects a feature. The agent is given `features.last_error` / `features.last_artifact_path` context and is instructed to focus only on making verification pass (no scope expansion).

Env vars:
- `AUTOCODER_WORKER_VERIFY=1` (required to trigger worker verification)
- `AUTOCODER_QA_FIX_ENABLED=1`
- `AUTOCODER_QA_MAX_SESSIONS=3`

## Controller

Planned: a post-verify “controller” pass to sanity-check completeness/quality and catch avoidable rejections early.

Env vars:
- `AUTOCODER_WORKER_VERIFY=1` (controller runs after this passes)
- `AUTOCODER_CONTROLLER_ENABLED=1`
- `AUTOCODER_CONTROLLER_MODEL=` (blank = reuse worker model)
- `AUTOCODER_CONTROLLER_MAX_SESSIONS=1`

## Multi-Provider Reviews

For a second “opinion” from another model/provider (Codex/Gemini/etc.), use the **Gatekeeper review step** via `review:` in the target project’s `autocoder.yaml` (or via UI Advanced settings). See `docs/multi_model_review.md`.
