# Copilot Instructions for Contributors (Autocoder)

Purpose: give AI coding agents (and humans) the immediate context and concrete commands needed to be productive in this repo.

Quick-start workflow
- Python setup: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- Run the CLI agent: `python autonomous_agent_demo.py --project-dir <path|registered_name>`.
- YOLO (fast prototyping): add `--yolo` (skips Playwright-based browser tests and marks features as passing after lint/type-check).
- Web UI: in `ui/` run `npm ci` then `npm run dev` (dev) or `npm run build` (production). `start_ui.sh`/`start_ui.bat` serve `ui/dist/`.

Key verification & CI commands
- Lint: `ruff check .`
- Security checks: `python test_security.py` (covers bash command allowlist and scripts like `init.sh`).
- Full local check (as used in project templates): `ruff check . && python test_security.py && cd ui && npm run lint && npm run build`.
- GitHub CI uses Python 3.11 and Node 20 (.github/workflows/ci.yml).

Big-picture architecture & data flow (short)
- Agent runtime: `autonomous_agent_demo.py` (entry) -> `agent.py` (session loop) -> `client.py` (Opencode client adapter config, MCP servers, allowed tool lists).
- MCP servers: `mcp_server/feature_mcp.py` exposes feature management tools; Playwright MCP available for browser automation in non-YOLO mode.
- Features & tests: stored in project `features.db` (SQLAlchemy models in `api/database.py`). Agents operate via MCP tools like `mcp__features__feature_get_next` and `mcp__features__feature_mark_passing`.
- UI: FastAPI backend `start_ui.py` + `server/routers/*`; `ui/src/*` consumes REST + WebSocket (`/ws/projects/{project_name}`) for logs and progress.

Project-specific conventions & important patterns
- Prompt fallback chain: project-specific `prompts/{name}.md` -> `.opencode/templates/{name}.template.md` (See `prompts.py`).
- YOLO mode: `--yolo` flag in `autonomous_agent_demo.py` and toggle in UI. In YOLO:
  - Playwright MCP server is skipped
  - Regression testing is skipped
  - Features are marked passing on lint/type-check success
- Security: all bash commands are validated in `security.py` and tested in `test_security.py`. Example rules:
  - `chmod +x init.sh` is allowed; numeric modes (`chmod 777`) and recursive `-R` are blocked.
  - `./init.sh` is allowed; `bash init.sh` or other script names may be blocked.
  - When changing the allowlist, update `test_security.py` accordingly.
- Tool allowlists and Playwright tooling are configured in `client.py`. Note: `mcp__playwright__browser_run_code` was removed due to crashes—avoid reintroducing without tests.

Where to look first (most impact)
- `OPENCODE.md` — project overview & workflows (already maintained and authoritative).
- `client.py` — how agents are configured, allowed tools, and Playwright headless flag (`PLAYWRIGHT_HEADLESS`).
- `security.py` & `test_security.py` — bash security rules and tests.
- `mcp_server/feature_mcp.py` — available MCP tools and their behavior.
- `autonomous_agent_demo.py` / `agent.py` — agent lifecycle and prompts used.
- `ui/` — run and build steps; `ui/src/hooks/useWebSocket.ts` and `ui/src/hooks/useProjects.ts` for real-time behavior.

Examples agents should follow
- To run the same checks CI uses: `ruff check . && python test_security.py && cd ui && npm run lint && npm run build`.
- To run agent locally with Playwright (standard mode): `python autonomous_agent_demo.py --project-dir <project>` (ensure Playwright is available or use default environment from `start.sh`).
- When adding an MCP tool, add a corresponding test and document it in `mcp_server/feature_mcp.py` and `client.py`.

Editing guidelines
- Keep prompt changes additive and preserve existing prompt templates in `.opencode/templates`. (rename `.claude/templates` → `.opencode/templates`)
- If you change security rules or allowed commands, add/adjust tests in `test_security.py`.
- When updating the UI, remember the `start_ui.*` scripts serve the pre-built `ui/dist/`; a `npm run build` is required before using those scripts.

If anything here is unclear or you'd like a different level of detail (examples or links to specific functions), tell me which sections to expand and I'll iterate. ✅
