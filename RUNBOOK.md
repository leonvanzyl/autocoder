# Runbook — AutoCoder Ops

## Daily
- `docker compose -f docker-compose.yml -f docker-compose.traefik.yml ps` — check services.
- `docker compose ... logs -f` — tail API/Trafik if issues.
- Verify `/health` and `/readiness` on the API; check `/metrics` scrape.

## Deploy
1) SSH to VPS.
2) `sudo bash scripts/deploy.sh` (prompts for domain/token/email/repo/branch/path/port).
3) Wait for Traefik to fetch certs; browse `https://<domain>`.

## Rollback
- Re-run deploy pointing to previous branch/sha: set branch prompt to the earlier ref.
- Or `git -C /home/autocoder checkout <sha>` then `docker compose ... up -d --build`.

## Logs
- App/Traefik: `docker compose -f docker-compose.yml -f docker-compose.traefik.yml logs -f`.
- Systemd Docker: `journalctl -u docker`.

## Certificates
- Stored at `/home/autocoder/letsencrypt/acme.json` (0600). Traefik auto-renews via HTTP-01.

## DNS (DuckDNS)
- Cron at `/etc/cron.d/duckdns`. Logs: `/var/log/duckdns.log`.

## Backups
- App data volume: `autocoder-data` (mapped to `~/.autocoder` in the container).
- Snapshot strategy: `docker run --rm -v autocoder-data:/data -v $PWD:/backup alpine tar czf /backup/autocoder-data-$(date +%F).tgz /data`.

## Observability
- Sentry (backend): set `SENTRY_DSN` (optional `SENTRY_ENV`, `SENTRY_TRACES_SAMPLE_RATE`).
- OTEL tracing: set `OTEL_EXPORTER_OTLP_ENDPOINT`, optional `OTEL_SERVICE_NAME`, `OTEL_ENVIRONMENT`.
- Metrics: scrape `https://<domain>/metrics` (behind Traefik; adjust scrape config).
- Frontend Sentry: `VITE_SENTRY_DSN`, optional `VITE_SENTRY_ENV`, `VITE_SENTRY_TRACES_SAMPLE_RATE`, `VITE_SENTRY_PROMPT_USER=1`.

## Common Issues
- **Cert not issued**: ensure ports 80/443 reachable; DuckDNS points to VPS; rerun deploy.
- **App not reachable**: `docker compose ... ps`, check logs; verify `.env.deploy` port matches internal service port (default 8888).
- **DNS not updating**: check `/etc/cron.d/duckdns` and `/var/log/duckdns.log`.
