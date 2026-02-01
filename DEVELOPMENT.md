# AutoCoder Development Roadmap

This roadmap breaks work into clear phases so you can pick the next most valuable items quickly.

## Phase 0 — Baseline (ship ASAP)
- **PR discipline:** Enforce branch protection requiring “PR Check” (already configured in workflows; ensure GitHub rule is on).
- **Secrets hygiene:** Move all deploy secrets into repo/environment secrets; prohibit `.env` commits via pre-commit hook.
- **Smoke tests:** Keep `/health` and `/readiness` endpoints green; add UI smoke (landing page loads) to CI.

## Phase 1 — Reliability & Observability
- **Structured logging:** Add JSON logging for FastAPI (uvicorn access + app logs) with request IDs; forward to stdout for Docker/Traefik.
- **Error reporting:** Wire Sentry (or OpenTelemetry + OTLP) for backend exceptions and front-end errors.
- **Metrics:** Expose `/metrics` (Prometheus) for FastAPI; Traefik already exposes metrics option—enable when scraping is available.
- **Tracing:** Add OTEL middleware to FastAPI; propagate trace IDs through to Claude/Gemini calls when possible.

## Phase 2 — Platform & DevX
- **Local dev parity:** Add `docker-compose.dev.yml` with hot-reload for FastAPI + Vite UI; document one-command setup.
- **Makefile/taskfile:** Common commands (`make dev`, `make test`, `make lint`, `make format`, `make seed`).
- **Pre-commit:** Ruff, mypy, black (if adopted), eslint/prettier for `ui/`.
- **Typed APIs:** Add mypy strict mode to `server/` and type `schemas.py` fully (Pydantic v2 ConfigDict).

## Phase 3 — Product & Agent Quality
- **Model selection UI:** Let users choose assistant provider (Claude/Gemini) in settings; display active provider badge in chat.
- **Tooling guardrails:** For Gemini (chat-only), show “no tools” notice in UI and fallback logic to Claude when tools needed.
- **Conversation persistence:** Add pagination/search over assistant history; export conversation to file.
- **Feature board:** Surface feature stats/graph from MCP in the UI (read-only dashboard).

## Phase 4 — Security & Compliance
- **AuthN/AuthZ:** Add optional login (JWT/OIDC) gate for UI/API; role for “admin” vs “viewer” at least.
- **Rate limiting:** Enable per-IP rate limits at Traefik and per-token limits in FastAPI.
- **Audit trails:** Log agent actions and feature state changes with user identity.
- **Headers/HTTPS:** HSTS via Traefik, content-security-policy header from FastAPI.

## Phase 5 — Performance & Scale
- **Caching:** CDN/Traefik static cache for UI assets; server-side cache for model list/status endpoints.
- **Worker separation:** Optionally split agent runner from API via separate services and queues (e.g., Redis/RQ or Celery).
- **Background jobs:** Move long-running tasks to scheduler/worker with backoff and retries.

## Phase 6 — Testing & Quality Gates
- **Backend tests:** Add pytest suite for key routers (`/api/setup/status`, assistant chat happy-path with mock Claude/Gemini).
- **Frontend tests:** Add Vitest + React Testing Library smoke tests for core pages (dashboard loads, settings save).
- **E2E:** Playwright happy-path (login optional, start agent, view logs).
- **Coverage:** Fail CI if coverage drops below threshold (start at 60–70%). 

## Phase 7 — Deployment & Ops
- **Blue/green deploy:** Add image tagging `:sha` + `:latest` (already for CI) with Traefik service labels to toggle.
- **Backups:** Snapshot `~/.autocoder` data volume; document restore.
- **Runbooks:** Add `RUNBOOK.md` for common ops (restart, rotate keys, renew certs, roll back).

## Phase 8 — Documentation & Onboarding
- **Getting started:** Short path for “run locally in 5 minutes” (scripted).
- **Config matrix:** Document required/optional env vars (Claude, Gemini, DuckDNS, Traefik, TLS).
- **Architecture:** One-page diagram: UI ↔ FastAPI ↔ Agent subprocess ↔ Claude/Gemini; MCP servers; Traefik front.

## Stretch Ideas
- **Telemetry-driven tuning:** Auto-select model/provider based on latency/cost SLA.
- **Cost controls:** Show per-run token/cost estimates; configurable budgets.
- **Offline/edge mode:** Ollama provider toggle with cached models.

## How to use this roadmap
- Pick the next phase that unblocks your current goal (reliability → platform → product).
- Keep PRs small and scoped to one bullet.
- Update this document when a bullet ships or is reprioritized.
