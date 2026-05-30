# Development Guide — CSUF Scheduler

## Core paths

- App factory: `backend/app/__init__.py`
- WSGI entrypoint: `backend/wsgi.py`
- API routes: `backend/app/routes/`
- Models: `backend/app/models/`
- Scheduler engine: `backend/app/services/scheduler/engine.py`
- Migrations: `backend/alembic/` + root `alembic.ini`
- Tests: `tests/`

## Run locally

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH='.'
python scripts/run_dev.py
```

## Install dependencies

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
```

- `backend/requirements.txt` is the production/runtime dependency set.
- `backend/requirements-dev.txt` adds test and audit tooling.

## Run tests

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH='.'
python -m pytest tests -q
```

## Apply migrations

```powershell
$env:DATABASE_URL='postgresql://csuf:csufpass@localhost:5432/scheduler'
alembic -c alembic.ini upgrade head
```

## Operational scripts

- Seed: `python scripts/seed.py`
- Smoke: `python scripts/smoke_test.py`
- Validate schedule: `python validate_schedule.py`
- Backup: `python scripts/backup_database.py`
- Restore: `python scripts/restore_database.py <backup-file>`

## Cleanup policy

- Ad-hoc/debug scripts are moved into `.cleanup_unwanted/` and ignored.
- Keep only production-relevant scripts in repo root and `scripts/`.
