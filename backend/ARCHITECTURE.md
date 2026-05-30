# Architecture

## Overview
CSUF Scheduler is a Flask API with server-rendered templates and a progressively integrated Vue frontend. Core domain logic lives in `backend/app`, with SQLAlchemy models for persistence and Alembic for schema migrations.

## Folder Structure
- `backend/app/models` — SQLAlchemy domain entities (users, shifts, availability, audit, scheduling, timesheets)
- `backend/app/routes` — API blueprints grouped by feature (users, shifts, scheduler, reports, conflicts, audit)
- `backend/app/services` — business logic modules (`scheduler/engine.py` for AI schedule generation)
- `backend/app/utils` — shared helpers (auth, parsing, audit, availability checks)
- `backend/app/middleware` — request/response middleware hooks and reusable error-handling helpers
- `backend/alembic` — migration environment and revisions

## Request Flow
1. App factory `create_app()` configures extensions and security defaults.
2. Blueprints are registered under `/api/*` prefixes.
3. Route handlers validate/authenticate requests via shared utils.
4. Services and models perform data/constraint logic.
5. Responses are returned as JSON for APIs, HTML for template routes.

## API Conventions
- Success: JSON payloads using explicit keys (`ok`, `id`, `data`, or resource dictionaries)
- Error: JSON object with `error` message for API endpoints
- Common status codes:
  - `200` success
  - `201` resource created
  - `400` validation error
  - `401` unauthenticated
  - `403` forbidden
  - `404` resource not found
  - `409` conflict
  - `500` server error

## Data Layer
- SQLAlchemy ORM for all domain persistence
- Alembic for migrations (`alembic upgrade head` for schema sync)
- Environment-driven DB URL (`DATABASE_URL`)
- SQLite supported for local/dev workflows, PostgreSQL recommended for deployment

## Cross-Cutting Concerns
- Security headers and CSRF enforcement in app middleware hooks
- Session-based auth with role checks (`utils/auth.py`)
- Global auditing for mutating operations (`utils/audit.py`)
- Linting/formatting via Black, isort, Flake8, and pre-commit hooks
