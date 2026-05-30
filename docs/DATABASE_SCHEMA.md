# Database Schema Overview

## Core Entities
- `users`: identity, role, auth attributes
- `shifts`: dated assignments and timing windows
- `availability`: recurring and one-time availability blocks
- `swap_requests`: employee swap request lifecycle
- `audit_logs`: cross-cutting change trail
- `time_adjustment_requests`: attendance correction workflow
- `timesheets` and related line/comment/audit tables
- scheduler tables: configs, generated schedules, overrides

## Relationship Summary
- One `user` to many `shifts` (as assigned employee)
- One `user` to many `availability` rows
- One `user` to many `swap_requests` (requester/target)
- One `user` to many `audit_logs` as actor
- One `timesheet` to many `timesheet_lines/comments/audit_logs`
- One `schedule_config` to many `generated_schedules`

## Migration Source of Truth
- Alembic revisions in `backend/alembic/versions/`
- Apply with:
  - `alembic -c alembic.ini upgrade head`

## Notes
- SQLite is supported for local quick-start paths
- PostgreSQL is recommended for staging/production parity
