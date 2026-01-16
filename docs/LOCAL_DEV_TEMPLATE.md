# Local Dev Notes (Template)

This file is intentionally a **template**.

For personal notes, copy it to the repo root as `LOCAL_DEV.md` (it’s ignored by git via `.gitignore`).

## My Setup

- OS:
- Python:
- Node:
- Claude CLI:
- Codex CLI:
- Gemini CLI:

## Useful Commands

- Start UI: `autocoder-ui`
- Run parallel: `autocoder parallel --project-dir <path> --parallel 3`
- Run tests: `pytest -q`
- Build UI: `cd ui && npm run build`

## Local Paths (don’t commit)

- Default fixtures dir:
- Custom fixtures dir:
- Notes about where you keep demo projects:

## Debug Checklist

- UI Settings saved? (Advanced Settings override env only after saving)
- `autocoder.yaml` present in project root?
- Gatekeeper artifact in `.autocoder/**/gatekeeper/*.json`?
- Feature has `last_error` / `last_artifact_path` in `agent_system.db`?

