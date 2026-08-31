# Production Readiness Checklist

Before deploying the KnowDecay Engine to production, ensure all of the following checks pass.

### Security
- [ ] `JWT_SECRET_KEY` set to cryptographically random value (≥32 chars)
- [ ] `JWT_SECRET_KEY` not committed to version control
- [ ] `.env` file gitignored
- [ ] `BCRYPT_ROUNDS` appropriate (default 12)
- [ ] `CORS_ORIGINS` configured for production domains only
- [ ] `APP_ENV` set to "production"

### Database
- [ ] `DATABASE_URL` points to production PostgreSQL
- [ ] Database credentials are strong and unique
- [ ] Migrations run via dedicated service (not auto-migrate)
- [ ] Database backup strategy implemented
- [ ] Connection pooling configured

### Infrastructure
- [ ] Docker image builds successfully
- [ ] Non-root user in container (knowdecay, UID 1001)
- [ ] HEALTHCHECK configured (`/health/live`)
- [ ] Worker count configured (`WORKERS` env var, `(2×CPU)+1`)
- [ ] Graceful shutdown configured
- [ ] `LOG_FORMAT` set to "json" for production
- [ ] `LOG_LEVEL` set to "INFO" or "WARNING"

### Deployment
- [ ] Health endpoints responding: `/health`, `/health/live`, `/health/ready`
- [ ] Database connectivity verified via `/health/ready`
- [ ] API documentation accessible at `/docs`
- [ ] OpenAPI schema available at `/openapi.json`
- [ ] All existing 1219 tests pass
- [ ] CI pipeline passes

### Monitoring
- [ ] Application logs collected (stdout/stderr)
- [ ] Health check monitoring configured
- [ ] Error alerting configured
- [ ] 📌 **Future**: APM/OpenTelemetry integration
- [ ] 📌 **Future**: Metrics collection (Prometheus)

### Backup & Recovery
- [ ] Database backup schedule documented
- [ ] Backup restoration procedure tested
- [ ] Disaster recovery plan documented
- [ ] 📌 **Future**: Automated backup verification
