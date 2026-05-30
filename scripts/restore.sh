#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required"
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: ./scripts/restore.sh <backup-file.sql|backup-file.sql.gz>"
  exit 1
fi

FILE="$1"
if [[ ! -f "$FILE" ]]; then
  echo "Backup file not found: $FILE"
  exit 1
fi

echo "Restoring from: $FILE"
if [[ "$FILE" == *.gz ]]; then
  gunzip -c "$FILE" | psql "$DATABASE_URL"
else
  psql "$DATABASE_URL" < "$FILE"
fi

echo "Restore completed"
