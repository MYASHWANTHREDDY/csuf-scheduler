# Deployment Runbook

## Pre-Deployment Checklist
- Tests pass (`pytest -q`)
- Lint passes (`black`, `isort`, `flake8`)
- Security scans pass (`pip-audit`, `bandit`)
- Database backup completed
- Staging environment validated

## Deploy (Docker Compose Production)
1. Copy env template:
   - `cp backend/.env.prod.example backend/.env.prod`
2. Set secrets in `backend/.env.prod`:
   - `SECRET_KEY`, `DATABASE_URL`, `POSTGRES_PASSWORD`
   - Optional but recommended: `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`
3. Build and migrate:
   - `docker compose -f docker-compose.prod.yml build`
   - `docker compose -f docker-compose.prod.yml run --rm migrate`
4. Start services:
   - `docker compose -f docker-compose.prod.yml up -d web db redis`
5. Validate health:
   - `GET /api/health` should return `200`

## Rollback
1. Stop current deployment:
   - `docker compose -f docker-compose.prod.yml down`
2. Re-deploy previous image tag.
3. Re-run health checks and smoke tests.

## Post-Deploy Validation
- API health is green
- Login works
- Shift create/assign works
- Reports endpoint returns data
- No new high-severity errors in logs
- If `SENTRY_DSN` is set, new errors appear in Sentry with request IDs
