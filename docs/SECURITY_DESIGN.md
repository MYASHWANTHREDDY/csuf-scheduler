# Security Design

## Threat Model
Primary risks for this system include:
- Unauthorized access to admin/supervisor actions
- Session hijacking and CSRF abuse
- Injection attempts against API payloads
- Brute-force login attempts
- Sensitive action repudiation (lack of auditability)

## Implemented Controls
- Session security hardening (`HttpOnly`, `SameSite=Lax`, timeout)
- CSRF protection for authenticated mutating requests
- Rate limiting on login path
- Security headers (`CSP`, `X-Frame-Options`, `X-Content-Type-Options`, etc.)
- Role-based authorization checks on protected endpoints
- Structured audit trail for sensitive mutations
- Dependency/security scans integrated in CI (`pip-audit`, `bandit`)

## Operational Security Practices
- Keep secrets in environment variables only
- Rotate `SECRET_KEY` and DB credentials on incident suspicion
- Review audit logs for privileged operations
- Validate `/api/health` and deploy smoke checks after releases

## Known Tradeoffs
- Session-based auth is intentionally used for current web-first architecture
- Advanced controls (MFA, account lockout policies, WAF) are not yet in scope
