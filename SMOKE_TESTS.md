# Post-Deployment Smoke Tests

Run after each deploy:

- [ ] `GET /api/health` returns `200`
- [ ] Login works with known admin account
- [ ] Create shift endpoint succeeds
- [ ] Assign shift endpoint succeeds
- [ ] Reports endpoint returns weekly payload
- [ ] Conflicts endpoint responds
- [ ] Audit endpoint responds
- [ ] UI dashboard loads
- [ ] No spike in 5xx logs for 10 minutes
