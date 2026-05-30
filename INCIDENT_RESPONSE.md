# Incident Response Playbook

## Severity
- SEV1: Full outage or data loss risk
- SEV2: Major degradation (core actions failing)
- SEV3: Minor degradation / localized issues

## Immediate Response
1. Acknowledge incident and assign an owner
2. Capture current impact and start timestamp
3. Stabilize service (rollback or restart)
4. Communicate status updates every 15 minutes for SEV1/SEV2

## Security Incidents
1. Revoke/rotate secrets (`SECRET_KEY`, DB creds, API keys)
2. Invalidate active sessions if needed
3. Preserve logs and evidence
4. Patch vulnerability and verify with tests/scans

## Recovery
- Validate `/api/health`
- Run smoke test checklist
- Confirm user-facing flows are operational

## Postmortem
- Root cause
- Detection gaps
- Corrective actions with owners and due dates
