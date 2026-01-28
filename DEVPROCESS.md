# DevProcess – phase tracker

Guidelines
- Update this file whenever you start or finish a task.
- Keep PRs small; one bullet per PR when possible.
- Link PRs beside the checkbox when merged.

## Phase 0 — Baseline
- [x] PR Check workflow exists (`pr-check.yml`)
- [ ] Branch protection requires “PR Check” (GitHub setting)
- [x] Pre-commit / git guard to block `.env` and secrets
- [x] `/health` endpoint
- [x] `/readiness` endpoint
- [x] UI smoke test in CI (landing page)

## Phase 1 — Reliability & Observability
- [x] JSON/structured logging with request IDs (FastAPI + uvicorn)
- [x] Error reporting (Sentry/OTEL) backend (env-gated)
- [x] `/metrics` Prometheus endpoint
- [x] OTEL tracing middleware + propagation (env-gated)

## Phase 2 — Platform & DevX
- [x] `docker-compose.dev.yml` with hot reload (API + UI)
- [x] Makefile/taskfile for common commands
- [ ] Pre-commit hooks: ruff/mypy, eslint/prettier
- [ ] mypy strict on `server/`

## Phase 3 — Product & Agent Quality
- [ ] UI model/provider picker (Claude/Gemini) with badge in chat
- [ ] Gemini “no tools” notice and Claude fallback for tooling tasks
- [ ] Assistant history search/export
- [ ] Feature/MCP dashboard in UI

## Phase 4 — Security & Compliance
- [ ] Optional Auth (JWT/OIDC) for UI/API with roles
- [ ] Rate limiting (Traefik + API)
- [ ] Audit trail for agent actions / feature state changes
- [ ] Security headers (HSTS, CSP)

## Phase 5 — Performance & Scale
- [ ] Static asset caching (Traefik/CDN)
- [ ] API response caching for model/status endpoints
- [ ] Separate worker/agent service + queue
- [ ] Background job retries/backoff

## Phase 6 — Testing & Quality Gates
- [ ] Backend tests for key routers (with mocked Claude/Gemini)
- [ ] Frontend Vitest/RTL smoke tests
- [ ] Playwright happy-path E2E
- [ ] Coverage gate in CI

## Phase 7 — Deployment & Ops
- [x] GHCR image build/push (CI)
- [x] Traefik + DuckDNS + Let’s Encrypt one-click deploy script
- [ ] Blue/green toggle via Traefik services
- [ ] Backups for `~/.autocoder` volume
- [x] RUNBOOK.md for common ops

## Phase 8 — Documentation & Onboarding
- [ ] “Run locally in 5 minutes” doc/script
- [x] Config matrix for all env vars (Claude, Gemini, DuckDNS, Traefik, TLS)
- [ ] Architecture overview diagram

## Phase 8 — Documentation & Onboarding
- [ ] “Run locally in 5 minutes” doc/script
- [ ] Config matrix for all env vars (Claude, Gemini, DuckDNS, Traefik, TLS)
- [ ] Architecture overview diagram
