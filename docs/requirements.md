# CSUF Scheduler — Requirements (MVP)

This document captures Phase 1 (MVP) requirements for the CSUF Scheduler pilot. Use this as the single source of truth for scoping, dev, and acceptance.

---

## 1) Project Scope

In scope (MVP):

- Admin portal to create/manage shifts
- Student portal to submit availability + view assigned shifts
- Basic shift assignment (manual now; AI later)
- Conflict detection (double-book, outside availability, hour-cap)
- Swap request workflow (request → approve/deny)
- Notifications (in-app or email OK; start with in-app)
- Audit log for changes (who/what/when)

Out of scope (MVP):

- Payroll integration (export CSV only, integration later)
- Mobile apps (later)
- Biometric/geolocation time logging
- Multi-department federation (single pilot dept first)

---

## 2) Stakeholders & Roles (RASCI-lite)

- Admin (Department Admin)
  - Responsibilities: Create/edit shifts, approve swaps, override, reports
  - Access: Admin UI, reports

- Student Worker
  - Responsibilities: Submit availability, request swaps, view schedule
  - Access: Student UI

- Scheduler Engine (service)
  - Responsibilities: Run assignment checks, flag conflicts
  - Access: Internal

- IT / Advisor
  - Responsibilities: Review logs, deployment
  - Access: Read-only (optional)

---

## 3) Key Policies to Encode (University Context)

- Hour cap: Max 20 hrs/week during semester; 40 hrs/week during breaks.
- Availability honoring: Assign only inside submitted availability.
- Rest window (optional): Minimum N hours between shifts (e.g., 8 hrs).
- Qualification/role match (optional): Some shifts require specific training.
- Swap rules: Swaps require admin approval; both students must meet policies.
- Overtime or conflicts: Must be flagged and blocked unless admin override.

---

## 4) User Stories (MVP)

### Admin

- Create shifts
  - As an Admin, I want to create shifts with date/start/end and location so students can be assigned.
  - Acceptance: Shift appears in schedule list; validates time window; stored in DB.

- Assign/override
  - As an Admin, I want to assign or reassign a shift to a student, even if conflicts exist, with an explicit override reason.
  - Acceptance: Assignment persists, conflicts logged; override requires reason.

- Approve swaps
  - As an Admin, I want to approve/deny swap requests with one click and leave a note.
  - Acceptance: Status changes and notifications sent.

- See conflicts
  - As an Admin, I want a list of conflicts (double-booking, hour-cap) to resolve quickly.
  - Acceptance: Conflicts page shows items with links to affected shifts/users.

- Export
  - As an Admin, I want to export weekly schedule and hours by student to CSV.
  - Acceptance: Downloadable CSV with correct totals.

### Student

- Submit availability
  - As a Student, I want to submit weekly availability blocks so I’m only scheduled when I’m free.
  - Acceptance: Saved blocks visible; prevents out-of-window assignment.

- View schedule
  - As a Student, I want to view my assigned shifts on a calendar/list.
  - Acceptance: Accurate, up-to-date view.

- Request swap
  - As a Student, I want to request a swap of a shift to another student.
  - Acceptance: Request recorded, target notified, admin approval gating.

- Notifications
  - As a Student, I want notifications when a shift is assigned, changed, or swap is approved.
  - Acceptance: Notification appears and is logged.

---

## 5) Functional Requirements (FR)

- FR-1 Shifts: Create/read/update/delete shifts (Admin).
- FR-2 Availability: CRUD weekly availability (Student; Admin read).
- FR-3 Assignment: Assign/reassign shifts; validate constraints; allow override with reason.
- FR-4 Swap Workflow: Initiate → accept/decline by target → admin approves/denies.
- FR-5 Conflict Engine: Detect hour-cap violations, overlaps, out-of-availability.
- FR-6 Notifications: Send in-app (MVP) and/or email (optional).
- FR-7 Audit Log: Record all changes with actor, timestamp, diff.
- FR-8 Reporting: Hours per student per week; export CSV.
- FR-9 Auth/RBAC: Login, roles (Admin/Student), session handling.
- FR-10 Calendar Views: List + weekly view for Admin/Student.

---

## 6) Non-Functional Requirements (NFR)

- NFR-1 Performance: <500ms typical API response; list endpoints paginate.
- NFR-2 Availability: Target 99.5% in pilot phase (single instance OK).
- NFR-3 Security: HTTPS, RBAC, server-side validation; protect PII.
- NFR-4 Auditability: Immutable audit log entries; time-stamped (UTC).
- NFR-5 Usability: Mobile-responsive web; keyboard accessible forms.
- NFR-6 Scalability (near-term): Single department ~50 users, ~500 shifts/week.
- NFR-7 Observability: Basic request logging + error logs; health endpoint.

---

## 7) Constraints & Assumptions

### Constraints

- Respect 20/40 hr caps; no shift outside availability unless override.
- Use CSUF email domain for accounts (optional policy).
- Data retention: keep logs for ≥ 1 semester.

### Assumptions

- Users have stable internet; use web portal.
- One pilot department initially (e.g., CS Front Desk).
- Admins will review conflicts daily.

---

## 8) Data Model (ERD – textual)

### User
- id (PK), name, email (unique), role ∈ {admin, student}, created_at

### Availability
- id (PK), user_id (FK User.id), weekday (0–6), start_time, end_time

### Shift
- id (PK), date, start_time, end_time, location?, required_role?, assigned_user_id (FK User.id, nullable), created_at

### SwapRequest
- id (PK), shift_id (FK Shift.id), requestor_user_id (FK User.id), target_user_id (FK User.id), status ∈ {pending, accepted, declined, approved, rejected}, created_at, decision_note?

### AuditLog
- id (PK), actor_user_id (FK User.id), action (create_shift/assign/override/etc.), entity_type, entity_id, before_json, after_json, timestamp

---

## 9) API Sketch (MVP)

> Use RESTful JSON APIs. Authentication via session (MVP) or JWT later. Admin endpoints require role check.

### Auth (stub for now)
- POST /api/login
  - Request: { email, password }
  - Response: 200 + session cookie or JWT

### Users
- GET /api/users (admin)
- POST /api/users (admin) — create user

### Availability
- GET /api/users/{id}/availability
- POST /api/users/{id}/availability
  - Request: [{ weekday:0-6, start_time:"HH:MM", end_time:"HH:MM" }, ...]
- DELETE /api/availability/{id}

### Shifts
- GET /api/shifts?from=YYYY-MM-DD&to=YYYY-MM-DD
- POST /api/shifts (admin)
  - Request: { date: "YYYY-MM-DD", start_time: "HH:MM", end_time: "HH:MM", location?: string, required_role?: string }
- PATCH /api/shifts/{id} (admin)
- POST /api/shifts/{id}/assign (admin)
  - Request: { user_id, override?: { reason } }
- GET /api/my/shifts (student)

### Swaps
- POST /api/swaps
  - Request: { shift_id, target_user_id }
- POST /api/swaps/{id}/respond
  - Request: { action: "accept" | "decline" }
- POST /api/swaps/{id}/approve (admin)
  - Request: { action: "approve" | "reject", note?: string }

### Reports
- GET /api/reports/hours?week=YYYY-Www → totals per student
- GET /api/reports/hours.csv?week=… → CSV export

### Conflicts
- GET /api/conflicts?week=… → list violations

### Audit
- GET /api/audit?entity=Shift&id=123 (admin)

---

## 10) Validation & Business Rules (examples)

- Hour cap: Sum of assigned shift durations per student per week ≤ 20 (semester) / ≤ 40 (break).
- Overlap: new_shift must not overlap existing assignments for that student unless override.
- Availability: Assignment must be within student’s availability unless override.
- Swap: Target must meet availability and hour-cap; if not, block or require override.

---

## 11) Acceptance Criteria (Gherkin-style)

### Create shift
```gherkin
Given I am an Admin
When I POST a valid shift (2025-11-01, 09:00–13:00)
Then the API returns 201 with shift id
And GET /api/shifts includes the new shift
```

### Assign within availability
```gherkin
Given Student A has availability Monday 09:00–17:00
And there is an unassigned shift Monday 10:00–12:00
When I assign Student A to the shift
Then the assignment succeeds without conflicts
```

### Block hour-cap
```gherkin
Given Student B already has 18 hours in week 45
When I try to assign a 4-hour shift in week 45
Then the system flags hour-cap violation
And blocks unless admin override is provided
```

### Swap workflow
```gherkin
Given Student A is assigned a shift
When A requests a swap to Student B
And B accepts
And Admin approves
Then the shift is reassigned to B
And all actions appear in the audit log
```

---

## 12) Risks & Mitigations

- Ambiguous policies (hour cap exceptions)
  - Impact: Wrong enforcement
  - Mitigation: Confirm with supervisor; make caps configurable per term

- Dirty availability data
  - Impact: Bad assignments
  - Mitigation: Validate input; expire old availability; reminders

- Scope creep
  - Impact: Delays
  - Mitigation: Lock MVP; backlog future features

- Notifications delivery
  - Impact: Missed alerts
  - Mitigation: Start with in-app notifications; add email later

- Single admin dependency
  - Impact: Bottleneck
  - Mitigation: Add second admin role or delegate approvals

---

## 13) Supervisor Discovery Questions (use in 1:1)

- What exact hour-cap rules apply during semester vs breaks?
- Any blackout dates (exams, holidays) we should auto-block?
- Do shifts require training/qualification tags?
- How are swaps handled today? Any approval SLAs?
- What reports do you need weekly/monthly (format: CSV/Excel)?
- Who should receive notifications (admins only, or students too)?
- Any data retention or FERPA/PII constraints we should note?

---

## 14) Tiny Wireframe Notes

- Admin Dashboard: cards for “New Shift”, “Conflicts”, “Pending Swaps”, table of upcoming week.
- Student Home: next 7 days list + “Submit/Update Availability” button.
- Availability Editor: weekly grid (Mon–Sun) with time sliders.
- Conflicts View: filter by type; quick “Go to shift” action.

---

## Artifacts created
- `docs/requirements.md` — this file (MVP requirements)
- `docs/backlog.csv` — backlog CSV (user stories) created alongside this doc for import into Jira/Trello/Notion


---

If you'd like, I can also:
- Export a Postman collection that matches the API sketch (JSON) and add it to `docs/postman_collection.json`.
- Convert the backlog into GitHub Issues or a Notion CSV schema.

Which of those would you like next?