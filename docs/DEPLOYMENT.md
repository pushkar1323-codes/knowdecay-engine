# KnowDecay Engine - Deployment Guide

## Prerequisites
- Docker & Docker Compose
- PostgreSQL 16 (if external)
- Python 3.11+ (for local/bare-metal execution)

## Environment Variables
Copy `.env.example` to `.env` and fill in:
- **`JWT_SECRET_KEY`** (Required): 32+ char secure random string.
- **`DATABASE_URL`** (Required): `postgresql://user:password@host:port/db`.
- **`APP_ENV`**: Set to `production` for prod deployment.
- **`WORKERS`**: Number of worker processes (default 1).

## Docker Deployment

### Development
```bash
docker compose up
```

### Production
```bash
docker compose --profile production up -d
```

## Platform Deployment

### Render Deployment
1. Create a new **Web Service**.
2. Connect your GitHub repository.
3. Environment: **Docker**.
4. Add PostgreSQL database and link it.
5. Set environment variables (especially `JWT_SECRET_KEY` and `DATABASE_URL`).
6. Build command (handled by Dockerfile).
7. Start command: `gunicorn app.main:app -c gunicorn.conf.py` (Handled by Dockerfile CMD).
8. Health Check Path: `/health/live`

### Railway Deployment
1. Create a new Project, add a **Postgres** plugin.
2. Link your GitHub repo to create a web service.
3. Set environment variables. Railway will auto-inject `DATABASE_URL`.
4. Configure healthcheck for `/health/live`.

## Database Migration Strategy
**NEVER** auto-migrate in production with multiple replicas (`AUTO_MIGRATE=false`). 
Use the dedicated migration service BEFORE starting API replicas:
```bash
docker compose --profile tools run --rm migrate
```

## Worker Scaling
- **Default**: 1
- **Formula**: `(2 × CPU) + 1`
- Configure via `WORKERS` env var in production.

## Health Checks
- `/health/live`: Liveness (Is the process running?) - Use for Docker HEALTHCHECK.
- `/health/ready`: Readiness (Is DB connected?) - Use for load balancers.

## Future Deployment Targets 🔮
- AWS ECS/EKS
- Azure Container Apps
- Google Cloud Run

Please review the [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) before going live.
