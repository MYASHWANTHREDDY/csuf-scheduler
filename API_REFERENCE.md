# API Reference

## Documentation UI
- Swagger UI: `/apidocs/`

## Authentication
- `POST /api/users/login`
  - Request: `{ "email": "user@example.com", "password": "..." }`
  - Response: user object plus `csrf_token`
- `POST /api/users/logout`
- `GET /api/users/me`
- `GET /api/users/csrf`

## Users
- `GET /api/users`
- `POST /api/users`
  - Request: `{ first_name?, last_name?, name?, email, password, role? }`
  - Auth: `admin` or `supervisor`

## Shifts
- `GET /api/shifts`
  - Query: `scope`, `date_from`, `date_to`, `status`, `assigned_user_id`, `q`
  - Optional pagination: `page`, `per_page` (returns `{ items, page, per_page, total, pages }`)
- `POST /api/shifts`
  - Request: `{ date, start_time, end_time }`
  - Auth: `admin` or `supervisor`
- `POST /api/shifts/assign`
  - Request: `{ shift_id, user_id }`
  - Auth: `admin` or `supervisor`
- `POST /api/shifts/auto-assign`
- `GET /api/shifts/by-user/<user_id>`
- `POST /api/shifts/swap`
- `DELETE /api/shifts/<shift_id>`

## Health
- `GET /api/health`
  - Response: `{ status, database, timestamp }`

## Reports
- `GET /api/reports/hours?week=YYYY-Www`
- `GET /api/reports/hours.csv?week=YYYY-Www`

## Conflicts
- `GET /api/conflicts?week=YYYY-Www`

## Audit
- `GET /api/audit`
  - Query: `action`, `entity_type`, `entity_id`, `limit`

## Scheduler
- `GET /api/scheduler/status`
- `POST /api/scheduler/quick-generate`
- `POST /api/scheduler/generate`
- `GET /api/scheduler/schedules`
- `GET /api/scheduler/schedules/<schedule_id>`
- `POST /api/scheduler/schedules/<schedule_id>/apply`
- `POST /api/scheduler/schedules/<schedule_id>/cancel`

## Extras
- Availability: `/api/availability`
- Swap requests: `/api/swap_requests`
- Announcements: `/api/announcements`
- Notifications: `/api/notifications`
- Call-off: `/api/call_off`
- Time adjustments: `/api/time_adjustments`
- Timesheets: `/api/timesheets`
