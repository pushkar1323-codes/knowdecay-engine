# Infrastructure Guide

Comprehensive guide for building, running, and operating the KnowDecay Engine infrastructure.

**See also:** [Deployment Guide](DEPLOYMENT.md) · [Operations Guide](OPERATIONS.md) · [Security](SECURITY.md) · [Production Checklist](PRODUCTION_CHECKLIST.md)

---

## Docker Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                        │
│                                                                 │
│  ┌─────────────────┐     ┌──────────────────────────────────┐  │
│  │  PostgreSQL 16   │◄────│  KnowDecay API                   │  │
│  │  (knowdecay_db)  │     │  (knowdecay_api)                 │  │
│  │                  │     │                                  │  │
│  │  Port: 5432      │     │  Port: 8000                      │  │
│  │  Volume: pgdata  │     │  Dev:  Uvicorn (hot-reload)      │  │
│  └─────────────────┘     │  Prod: Gunicorn → Uvicorn ASGI   │  │
│                           └──────────────────────────────────┘  │
│  ┌─────────────────┐     ┌──────────────────────────────────┐  │
│  │  Test Database   │     │  Migration Runner                │  │
│  │  (profile: test) │     │  (profile: tools)                │  │
│  │  Port: 5433      │     │  alembic upgrade head            │  │
│  │  tmpfs (no disk) │     │  Runs once, then exits           │  │
│  └─────────────────┘     └──────────────────────────────────┘  │
│                                                                 │
│  Network: knowdecay_network                                     │
│  Volume:  knowdecay_pgdata                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Container Overview

| Container | Image | Purpose | Profile |
|-----------|-------|---------|---------|
| `knowdecay_db` | postgres:16-alpine | Primary database | *(default)* |
| `knowdecay_api` | knowdecay-engine | API server (development) | *(default)* |
| `knowdecay_api_prod` | knowdecay-engine | API server (production) | `production` |
| `knowdecay_migrate` | knowdecay-engine | Database migrations | `tools` |
| `knowdecay_db_test` | postgres:16-alpine | Isolated test database | `test` |

### Production Image

The production Docker image uses a **multi-stage build**:

- **Builder stage** — Installs dependencies into an isolated virtual environment (includes gcc, libpq-dev)
- **Runtime stage** — Copies only the venv and application source (no build tools)
- **Non-root user** — Runs as `knowdecay` (UID 1001) for security
- **Health check** — Docker-native `HEALTHCHECK` on `/health/live`
- **Server** — Gunicorn (process manager) → Uvicorn (ASGI workers) → FastAPI

---

## Local Development Workflow

### Prerequisites

- [Docker Desktop](https://docker.com/products/docker-desktop) (Docker Engine + Docker Compose)
- Git

### Quick Start

```bash
# Clone and enter the project
git clone <repo-url>
cd knowdecay-engine

# Configure environment
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY to a secure random value

# Start everything (database + API with hot-reload)
docker compose up

# Verify
curl http://localhost:8000/health
# Open Swagger UI: http://localhost:8000/docs
```

### Common Commands

| Command | Description |
|---------|-------------|
| `docker compose up` | Start DB + API (foreground, hot-reload) |
| `docker compose up -d` | Start in background |
| `docker compose up db` | Start database only |
| `docker compose down` | Stop all containers |
| `docker compose down -v` | Stop + delete database volume |
| `docker compose build` | Rebuild Docker image |
| `docker compose logs -f api` | Follow API logs |
| `docker compose exec api /bin/bash` | Shell into API container |

### Using the Makefile

If you have `make` installed:

```bash
make help          # List all available commands
make up            # Start development stack
make down          # Stop all containers
make restart       # Restart stack
make rebuild       # Rebuild and restart
make logs          # Follow API logs
make shell         # Shell into API container
```

---

## Database Operations

### Run Migrations

Migrations are managed via a **dedicated migration service** to ensure safety in multi-replica deployments:

```bash
# Via Docker Compose (recommended)
docker compose --profile tools run --rm migrate

# Via Makefile
make migrate

# Directly (when running API outside Docker)
alembic upgrade head
```

> **⚠ Production Warning**: Do NOT enable `AUTO_MIGRATE=true` in production with multiple replicas. Concurrent migrations can corrupt the database. Always run migrations as a dedicated step before starting API instances.

### Generate a New Migration

```bash
# After modifying ORM models
alembic revision --autogenerate -m "add_new_table"

# Or via Makefile
make migration MSG="add_new_table"
```

### Access PostgreSQL

```bash
# Via Docker
docker compose exec db psql -U knowdecay -d knowdecay

# Via Makefile
make db-shell
```

### Reset Database

```bash
# Delete all data and re-migrate
make db-reset

# Or manually
docker compose down -v
docker compose up -d db
sleep 5
docker compose --profile tools run --rm migrate
```

---

## CI Pipeline

### Overview

The GitHub Actions CI pipeline runs on every push and pull request to `main` and `develop`:

```
lint (formatting + linting)
  └─► test (full suite with PostgreSQL)
       └─► docker (build + verify health endpoints)
```

### Jobs

| Job | What it checks |
|-----|---------------|
| **lint** | Code formatting (ruff format) and linting (ruff check) |
| **test** | Dependencies install, config validation, Alembic migrations, full test suite (1219+ tests), OpenAPI schema generation |
| **docker** | Docker image builds, services start, health endpoints respond, DB connectivity works, Swagger UI accessible |

### Running CI Checks Locally

```bash
# Lint
ruff check .
ruff format --check .

# Tests (requires PostgreSQL)
APP_ENV=testing JWT_SECRET_KEY=test-secret-key-minimum-32-characters-long \
    pytest tests/ -v --tb=short

# Docker build
docker compose build
```

---

## Environment Configuration

### Profiles

| Environment | APP_ENV | Auto-Migrate | Server | Log Level |
|-------------|---------|-------------|--------|-----------|
| Development | `development` | Yes (single instance) | Uvicorn --reload | DEBUG |
| Testing | `testing` | No (tests manage schema) | pytest | DEBUG |
| Production | `production` | **No** (use migration service) | Gunicorn + Uvicorn | INFO |

### Environment Variables

All configuration is loaded from environment variables or `.env` file. See [.env.example](../.env.example) for the complete reference.

**Required in production:**
- `JWT_SECRET_KEY` — must be at least 32 characters
- `DATABASE_URL` — PostgreSQL connection string

**Never hardcode or commit:**
- Passwords
- API keys
- JWT secrets
- Database credentials
- Cloud credentials

### Secrets Management Readiness

The application reads all secrets from environment variables, making it compatible with:

- Docker Secrets
- AWS Secrets Manager
- Azure Key Vault
- HashiCorp Vault
- Kubernetes Secrets
- Platform-injected environment variables (Render, Railway, Heroku)

---

## Production Deployment

### Server Architecture

```
Gunicorn (process manager)
  └─► Uvicorn Worker 1 (ASGI)  ─► FastAPI
  └─► Uvicorn Worker 2 (ASGI)  ─► FastAPI
  └─► Uvicorn Worker N (ASGI)  ─► FastAPI
```

Gunicorn manages worker processes (auto-restart on crash, graceful shutdown) while Uvicorn handles the async ASGI protocol that FastAPI requires.

### Worker Scaling

| Setting | Default | Recommendation |
|---------|---------|---------------|
| `WORKERS` | 1 | `(2 × CPU cores) + 1` |
| `WORKER_TIMEOUT` | 120s | Adjust based on longest expected request |
| `GRACEFUL_TIMEOUT` | 30s | Time allowed for in-flight requests during shutdown |

### Health Endpoints

| Endpoint | Purpose | Use For |
|----------|---------|---------|
| `/health/live` | Process is running | Docker HEALTHCHECK, Kubernetes liveness probe |
| `/health/ready` | Process + DB connected | Load balancer readiness, Kubernetes readiness probe |
| `/health` | Full status with capabilities | Monitoring dashboards |
| `/health/detailed` | Extended diagnostics | Operations debugging |

### Deployment Checklist

1. Set `JWT_SECRET_KEY` to a cryptographically strong random value
2. Set `APP_ENV=production`
3. Set `DATABASE_URL` to production database
4. Set `WORKERS` based on available CPU
5. Run migrations: `alembic upgrade head`
6. Start server: `gunicorn app.main:app -c gunicorn.conf.py`
7. Verify: `curl <host>/health/ready`

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs api

# Common causes:
# - Database not ready → entrypoint waits 30 retries (60s)
# - JWT_SECRET_KEY missing or too short → startup validation failure
# - Port 8000 already in use → change API_PORT in .env
```

### Database connection refused

```bash
# Verify database is running and healthy
docker compose ps db
docker compose logs db

# Test connectivity
docker compose exec db pg_isready -U knowdecay
```

### Alembic migration errors

```bash
# Check current migration state
alembic current

# Show migration history
alembic history

# If migrations are corrupt, reset (DESTROYS DATA):
make db-reset
```

### Port conflicts

```bash
# Change ports via environment variables
DB_PORT=5434 API_PORT=8001 docker compose up
```

---

## Future Scalability

The infrastructure is designed for incremental expansion. Future services plug into the existing Docker Compose and network architecture:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Future Architecture                           │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ KnowDecay│  │  Redis   │  │ Worker   │  │  ML Service      │    │
│  │   API    │  │  Cache   │  │ (Celery) │  │  (Inference)     │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘    │
│       │              │             │               │                 │
│  ─────┴──────────────┴─────────────┴───────────────┴──── network    │
│       │                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │PostgreSQL│  │ Object Store │  │  Monitoring (Prometheus/     │  │
│  │  (RW+RO) │  │  (S3/R2)     │  │  Grafana/OpenTelemetry)     │  │
│  └──────────┘  └──────────────┘  └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Adding a New Service

1. Add the service definition to `docker-compose.yml` (under a profile if optional)
2. Add configuration variables to `app/config.py` and `.env.example`
3. Connect to the `knowdecay` network
4. Add health check
5. Update this documentation

No existing services or APIs need to change.
