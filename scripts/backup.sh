#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required"
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/scheduler_${TS}.sql"

echo "Creating backup: $OUT"
pg_dump "$DATABASE_URL" > "$OUT"
gzip -f "$OUT"

echo "Backup created: ${OUT}.gz"
