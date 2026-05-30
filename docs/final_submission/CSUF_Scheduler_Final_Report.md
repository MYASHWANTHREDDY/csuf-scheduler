# CSUF Scheduler
## Master's Project Report (Development Project)

### Approval Cover Page (Template)

Project Title: CSUF Scheduler: Production-Focused Staff Scheduling Platform  
Candidate: [Your Name]  
Program: M.S. Computer Science, California State University, Fullerton  
Semester/Year: Spring 2026  
Advisor: [Advisor Name]  
Reviewer: [Reviewer Name]

Signatures:
- Advisor: __________________________ Date: __________
- Reviewer: _________________________ Date: __________
- Candidate: ________________________ Date: __________

---

## Abstract (100 words max)

CSUF Scheduler is a production-focused scheduling platform designed to support university student-staff operations. The system implements role-based access control, shift lifecycle management, availability handling, swap workflows, audit logging, and AI-assisted schedule generation using OR-Tools. The project evolved from a web-first architecture into a full-stack solution with a React Native mobile MVP. Security and quality gates were added through session hardening, CSRF, rate limiting, structured logging, linting, and security scanning. Validation included API smoke tests, full automated tests, Expo diagnostics, and runtime health checks. Results show the platform is stable, secure for current scope, and deployment-ready.

## Keywords

Scheduling system, Flask, SQLAlchemy, OR-Tools, React Native, Expo, role-based access control, CSRF, audit logging, CI/CD

---

## Table of Contents

1. Introduction  
2. Requirements Description  
3. Design Description  
4. Implementation  
5. Test and Integration  
6. Installation Instructions  
7. Operating Instructions  
8. Recommendations for Enhancement  
9. Bibliography

---

## 1. Introduction

### 1.1 Problem Description

Student-staff scheduling in academic environments is error-prone when handled manually. Common issues include shift conflicts, uneven allocation, delayed communication, and weak traceability for administrative changes.

### 1.2 Project Objectives

The project objective was to design and implement a production-oriented scheduler that:
- Supports role-based operation across administrators, supervisors, and student workers.
- Automates key scheduling decisions while allowing manual oversight.
- Improves transparency through audit trails and reporting.
- Provides both web and mobile access to core workflows.
- Meets baseline operational expectations for security, testing, and deployment readiness.

### 1.3 Development and Runtime Environments

- OS: Windows (development), Linux-compatible deployment through Docker
- Backend: Flask, SQLAlchemy, Alembic
- Mobile: React Native (Expo SDK 51)
- Database: SQLite (development), PostgreSQL (recommended production)
- Tooling: Black, isort, Flake8, Bandit, pip-audit, pytest, pre-commit

---

## 2. Requirements Description

### 2.1 Functional Requirements

The implemented system covers:
- User authentication and role-based authorization (`admin`, `supervisor`, `student`, `FTO`).
- Shift management: create, assign, auto-assign, swap, and delete.
- Availability submission and retrieval.
- Scheduler workflows including quick generation and schedule apply/cancel actions.
- Weekly reporting (JSON/CSV), conflict detection, and audit viewing.
- Notification and timesheet/time-adjustment support.
- Mobile MVP flows: login, assigned shifts, availability, swaps, notifications, settings.

### 2.2 Non-Functional Requirements

- Security: session hardening, CSRF protection, security headers, login rate limiting.
- Reliability: health endpoint and post-deployment smoke tests.
- Maintainability: documented architecture, coding conventions, migration discipline.
- Performance readiness: indexing and query optimization enhancements included in transformation phases.
- Deployability: Docker, environment templates, and CI workflow.

---

## 3. Design Description

### 3.1 System Architecture

CSUF Scheduler uses a modular Flask architecture with clear separation of concerns:
- `models` for persistence and domain entities
- `routes` for API surface
- `services` for business logic (including OR-Tools scheduler engine)
- `utils` and `middleware` for cross-cutting capabilities (auth, audit, error/logging)

The frontend strategy is progressive:
- Existing server-rendered templates retained for compatibility.
- Vue integration introduced for modern reusable components.
- React Native mobile app added as Phase 7 MVP.

### 3.2 Data Design

- ORM: SQLAlchemy models for users, shifts, availability, audit, communication, scheduling, timesheets.
- Migration framework: Alembic with versioned schema revisions.
- Database portability: SQLite for local development and PostgreSQL for production.

### 3.3 API Design

- REST-style endpoints under `/api/*`.
- Session-based authentication with CSRF token propagation on mutating requests.
- Documented endpoints for users, shifts, scheduler, reports, conflicts, audit, availability, notifications, and health.

---

## 4. Implementation

### 4.1 Backend Features Implemented

- Core APIs for user and shift lifecycle.
- AI-assisted scheduler endpoints with OR-Tools integration.
- Reporting endpoints (`/api/reports/hours`, `/api/reports/hours.csv`).
- Conflict and audit endpoints.
- Health endpoint (`/api/health`) for platform monitoring.
- Security controls and middleware hardening.

### 4.2 Frontend and UX Improvements

- Design system and reusable Vue component base.
- Accessibility checklist and responsive behavior guidance.
- Documentation for UI and development workflows.

### 4.3 Mobile MVP (Phase 7)

React Native/Expo application implemented with the following screens:
- Login
- Schedule
- Swap
- Availability
- Notifications
- Settings

The mobile client integrates with the existing session/CSRF backend contract and uses environment-aware base URLs for emulator/simulator workflows.

---

## 5. Test and Integration

### 5.1 Automated Validation

- `pytest -q`: full backend test suite passed (64 tests).
- Pre-commit quality/security gates: Black, isort, Flake8, Bandit passed on final commit.
- Dependency audit process documented in `SECURITY_AUDIT.md`.

### 5.2 Smoke and Runtime Validation

- Health check endpoint returned healthy status with database OK.
- End-to-end smoke test verified:
  - login
  - users fetch
  - shifts fetch
  - shift creation
  - created shift verification
- Expo diagnostics: 16/16 checks passed.
- Metro bundler startup validated for mobile runtime.

### 5.3 Integration Outcome

Backend APIs, web workflows, and mobile MVP flows are functionally integrated and operational in the validated local environment.

---

## 6. Installation Instructions

### 6.1 Backend

1. Create and activate Python virtual environment:
   - `py -3.11 -m venv .venv`
   - `.\.venv\Scripts\Activate.ps1`
2. Install dependencies:
   - `python -m pip install --upgrade pip`
   - `python -m pip install -r backend\requirements-dev.txt`
3. Configure environment:
   - Copy `backend/.env.example` to `backend/.env`
   - Set `DATABASE_URL` and `SECRET_KEY`
4. Run application:
   - `python scripts/run_dev.py`

### 6.2 Mobile

1. `cd mobile`
2. `npm install`
3. `npm run start`
4. Launch iOS/Android simulator or Expo Go

---

## 7. Operating Instructions

### 7.1 Core Operations

- Start backend and verify `http://127.0.0.1:5000/api/health`.
- Access API docs at `http://127.0.0.1:5000/apidocs/`.
- Authenticate using valid user credentials.
- Execute scheduling operations through shift/scheduler/report routes.

### 7.2 Post-Deployment Smoke Tests

Run checks listed in `SMOKE_TESTS.md`, including:
- health endpoint
- login
- create/assign shift
- reports/conflicts/audit endpoint verification
- dashboard load and 5xx monitoring

---

## 8. Recommendations for Enhancement

1. Add push notification infrastructure for mobile devices.
2. Expand accessibility testing with automated WCAG scanning and manual audits.
3. Introduce deeper observability (tracing, dashboards, alert thresholds).
4. Implement MFA and enterprise identity integration.
5. Add stronger load/performance benchmarking for concurrent usage.
6. Continue dependency risk monitoring and remediation automation in CI.

---

## 9. Bibliography

1. Flask Documentation. https://flask.palletsprojects.com/  
2. SQLAlchemy Documentation. https://docs.sqlalchemy.org/  
3. Alembic Documentation. https://alembic.sqlalchemy.org/  
4. Google OR-Tools Documentation. https://developers.google.com/optimization  
5. Expo Documentation. https://docs.expo.dev/  
6. React Native Documentation. https://reactnative.dev/docs/getting-started  
7. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/  
8. Bandit Documentation. https://bandit.readthedocs.io/  
9. pip-audit Documentation. https://pypi.org/project/pip-audit/

---

## Submission Notes

- Replace all bracketed placeholders (name, advisor, reviewer) before final submission.
- If your department requires DOCX/PDF, export this markdown to the required format.
- Attach supporting artifacts as appendices if requested (screenshots, logs, API samples).
