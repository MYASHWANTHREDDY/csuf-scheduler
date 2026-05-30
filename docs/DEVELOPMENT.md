# Development Guide

## Prerequisites
- Python 3.11
- PostgreSQL (recommended for local parity)
- Git

## Local Setup (Windows PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements-dev.txt
```

## Environment
1. Copy `backend/.env.example` to `backend/.env`
2. Set at minimum:
   - `DATABASE_URL`
   - `SECRET_KEY`

## Run App
```powershell
$env:PYTHONPATH='.'
python scripts/run_dev.py
```

## Migrations
```powershell
$env:DATABASE_URL='postgresql://csuf:csufpass@localhost:5432/scheduler'
alembic -c alembic.ini upgrade head
```

## Quality Checks
```powershell
black --check backend
isort --check-only backend
flake8 backend/app
pytest -q
```

## API Docs
- Swagger UI: `http://127.0.0.1:5000/apidocs/`
- Reference summary: `API_REFERENCE.md`

## Contribution Workflow
1. Create a feature branch
2. Make focused changes
3. Run lint/tests/security checks
4. Open PR with a short validation summary
