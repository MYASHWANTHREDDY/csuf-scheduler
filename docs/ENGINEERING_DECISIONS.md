# Engineering Decisions

## Backend Framework
**Choice:** Flask + SQLAlchemy

**Why:**
- Fast iteration for API-centric backend
- Mature extension ecosystem (limiting, migrations, docs)
- Clear separation between routes, models, services, and utils

## API Style
**Choice:** Session-based auth + JSON REST endpoints

**Why:**
- Matches current web client architecture
- Simpler state management for same-origin app
- Explicit role checks at route boundaries

## Data Layer
**Choice:** SQLAlchemy ORM + Alembic migrations

**Why:**
- ORM safety and maintainability
- Repeatable schema evolution
- Database portability for local vs. production

## Scheduler Engine
**Choice:** OR-Tools integration in service layer

**Why:**
- Handles constrained optimization for staffing rules
- Keeps complex scheduling logic isolated from route handlers

## Quality & Security Tooling
**Choice:** pre-commit + Black/isort/Flake8 + Bandit + pip-audit

**Why:**
- Consistent code quality gates
- Early security feedback in CI and local workflows

## Tradeoffs
- UI modernization remains incremental within template-first app
- Session auth chosen over JWT to reduce moving parts for current scope
- Some enterprise controls (MFA, full SIEM integration) deferred to future phases
