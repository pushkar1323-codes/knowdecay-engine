# Operations Guide

## Service Management
The engine is containerised and relies on Docker.
- **Start Services**: `docker compose up -d`
- **Stop Services**: `docker compose down`
- **Restart**: `docker compose restart`
- **Rebuild**: `docker compose up --build -d`

**Make Shortcuts**:
Utilize the provided `Makefile` for streamlined operations (e.g., `make run`, `make test`, `make build`).

## Log Inspection
- **Viewing Logs**: `docker compose logs -f`
- **Formats**: Development environments emit readable text, while production emits structured JSON suitable for log aggregators.

## Database Operations
- **Backup**: Use `pg_dump` to create point-in-time backups.
- **Restore**: Use `pg_restore` against the target database.
- **Migrations**: Always run via `alembic upgrade head`.

## Migration Safety
Migrations are executed by a **dedicated migration service**. The system is explicitly configured to *never* auto-migrate in a multi-replica production environment, preventing race conditions and schema locks.

## Version Upgrade Workflow
1. Pull new code.
2. Run database migrations via the dedicated migration service.
3. Rebuild and deploy containers.
4. Verify health endpoints.

## Release Workflow
1. **Lint**: Enforce code style and static analysis.
2. **Test**: Execute the test suite.
3. **Build**: Generate Docker images.
4. **Migrate**: Apply database schema changes.
5. **Deploy**: Roll out the new image.
6. **Verify**: Check health probes.

## Health Monitoring
The API provides several endpoints for monitoring:
- `/health`: General API availability.
- `/health/live`: Liveness probe (is the container running?).
- `/health/ready`: Readiness probe (is it ready to serve traffic and connect to DB?).
- `/health/detailed`: Deep diagnostic probe.

## Troubleshooting
- **DB Connection Refused**: Verify PostgreSQL container is running and that the `DATABASE_URL` is correctly configured in your `.env`.
- **JWT Errors**: Check that the token hasn't expired and that `JWT_SECRET_KEY` matches across services.
- **Port Conflicts**: Ensure port `8000` or `5432` are not occupied on the host machine.
- **Migration Errors**: If Alembic states it is out of sync, check for dangling migration revisions or resolve manual conflicts in the DB `alembic_version` table.

## Environment Management
- **Development**: Features hot-reloading, text logs, and relaxed CORS for local testing.
- **Testing**: Uses ephemeral databases and bypasses strict secret length constraints for CI speed.
- **Production**: Uses Gunicorn with ASGI workers, strict security settings, JSON logs, and relies on robust external database hosting.
