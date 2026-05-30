# Monitoring & Alerting

## Key Metrics
- API availability (`/api/health` success rate)
- P95 response latency
- Error rate (4xx/5xx)
- Database connectivity failures
- Background migration failures

## Alert Thresholds
- Health check failure for 3 consecutive intervals
- Error rate > 2% over 5 minutes
- P95 latency > 1.5s for 10 minutes
- DB connection failures > 5/min

## Log Strategy
- Request logs from middleware include request id, method, path, status, duration
- Centralize logs in production platform (e.g., CloudWatch / Datadog / ELK)
- Retain logs for at least 30 days

## Dashboards
- API overview: traffic, latency, error rate
- Database: connections, CPU, storage
- Deployments: build status and release events
