<#
PowerShell helper for Windows developers.
Usage:
  .\scripts\dev.ps1 build
  .\scripts\dev.ps1 up
  .\scripts\dev.ps1 migrate
  .\scripts\dev.ps1 logs
  .\scripts\dev.ps1 smoke
  .\scripts\dev.ps1 down
#>
param(
    [string]$Action
)

function Build {
    Write-Host "Building backend and migrate images..."
    docker compose build --no-cache
}

function Up {
    Write-Host "Starting web, db and redis in background..."
    docker compose up -d web db redis
}

function Migrate {
    Write-Host "Running containerized migrations (alembic upgrade head)..."
    docker compose run --rm migrate
}

function Logs {
    Write-Host "Tailing web logs... (Ctrl-C to exit)"
    docker compose logs -f web
}

function Smoke {
    Write-Host "Running smoke test against http://127.0.0.1:5000"
    python .\backend\smoke_test.py
}

function Down {
    Write-Host "Stopping all compose services..."
    docker compose down -v
}

switch ($Action.ToLower()) {
    'build'   { Build; break }
    'up'      { Up; break }
    'migrate' { Migrate; break }
    'logs'    { Logs; break }
    'smoke'   { Smoke; break }
    'down'    { Down; break }
    default {
        Write-Host "Usage: .\scripts\dev.ps1 <build|up|migrate|logs|smoke|down>"
    }
}
