# KnowDecay Engine

**The adaptive learning engine that remembers what your students forget.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

---

## Overview

**KnowDecay Engine** is the backend intelligence system that predicts when learners will forget what they've studied — and tells them exactly what to revise, when.

Most learning platforms treat every topic the same. KnowDecay doesn't. It models each learner's memory individually using adaptive forgetting curves, continuously recalibrating as new study events arrive. The result: **smarter revision schedules that maximize long-term retention with less study time.**

### Two integration models

| | **Standalone Backend** | **Retention Intelligence as a Service (RIaaS)** |
|---|---|---|
| **For** | Teams building a KnowDecay-powered learning platform | EdTech companies & institutions adding retention intelligence to existing products |
| **How** | Complete backend with auth, user management, and intelligence APIs | REST API that plugs into any LMS, app, or learning platform |
| **What** | Full-stack backend ready for a frontend to consume | Retention scoring, scheduling, and analytics endpoints |

### The problem

> Students study hard but forget fast. Institutions lack visibility into knowledge decay. Cramming works short-term but fails long-term. Existing revision tools use fixed schedules rather than adapting to each learner.

### The solution

KnowDecay Engine uses **evidence-based memory science** (Ebbinghaus forgetting curves + adaptive stability modeling) to:

- **Predict** exactly when a concept will fall below a learner's retention threshold
- **Prioritize** which topics need revision most urgently
- **Schedule** the optimal moment for each review session
- **Track** retention strength across entire knowledge hierarchies

---

## Key Capabilities

### Adaptive Retention Modeling
Every learner × topic pair has its own memory state — retention score, stability, decay rate, and confidence — evolving with each interaction.

### Intelligent Forgetting Analysis
Real-time decay modeling with configurable thresholds. Know which concepts are at risk before the learner forgets.

### Urgency-Based Revision Prioritization
Not all forgotten topics are equal. KnowDecay ranks revisions by exam proximity, difficulty, topic importance, and current retention.

### Adaptive Scheduling
Optimal revision intervals computed per-topic, adapting to learner behavior patterns. No fixed schedules — every recommendation is personalized.

### Event-Driven Recalibration
Quiz results, study sessions, and revision events continuously recalibrate memory states. The engine gets smarter with every interaction.

### Hierarchical Analytics
Retention heatmaps aggregated across Subject → Module → Chapter → Topic → Subtopic. Spot weak areas at any level of the knowledge tree.

### Learning Data Collection
Extensible event tracking for study sessions, quiz attempts, revision history, and learning resources. Pre-aggregated daily activity summaries and retention time-series snapshots support downstream analytics.

### Institution-Aware Architecture
Multi-tenant support with institution isolation, course management, enrollment workflows, and role-scoped access. Designed to operate both as a standalone platform for individual learners and as an institutional deployment.

### Authentication & Role-Based Access Control
JWT-based authentication with refresh token rotation. Five-tier RBAC system supporting individual learners, teachers, and institutional administrators.

### Production-Ready Infrastructure
Structured logging, request tracing, global error handling, health probes, Docker-based deployment, CI pipeline, and configurable middleware.

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://docker.com/products/docker-desktop) (Docker Engine + Docker Compose)
- Git
- Python 3.11+ *(only for local development without Docker)*

### Using Docker (recommended)

```bash
git clone <repo-url>
cd knowdecay-engine

# Configure environment
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY (minimum 32 characters):
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Start development stack (DB + API with hot-reload)
docker compose up

# Or with Makefile:
make up

# Verify
curl http://localhost:8000/health
# Swagger UI: http://localhost:8000/docs
```

### Run Migrations

```bash
# Via dedicated migration service (safe for all environments)
docker compose --profile tools run --rm migrate

# Or with Makefile:
make migrate
```

### Create Admin Account

```bash
docker compose exec api python -m app.cli create-superadmin
```

### Local Development (without Docker)

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY and DATABASE_URL

# Run database migrations
alembic upgrade head

# Create your admin account
python -m app.cli create-superadmin

# Start the development server
uvicorn app.main:app --reload

# Browse interactive API docs
open http://localhost:8000/docs
```

---

## API

KnowDecay Engine exposes a versioned RESTful API (`/v1/`) organized by domain. Full interactive documentation is available at `/docs` (Swagger UI) when the server is running.

All endpoints except health checks and registration require JWT authentication via the `Authorization: Bearer <token>` header.

**Core endpoint groups:**

| Group | Purpose |
|-------|---------|
| `/v1/auth/*` | Registration, login, token management |
| `/v1/users/*` | User management (admin) |
| `/v1/retention/*` | Retention predictions |
| `/v1/priority/*` | Revision urgency ranking |
| `/v1/schedule/*` | Optimal revision scheduling |
| `/v1/memory/*` | Memory state management and recalibration |
| `/v1/analytics/*` | Retention analytics and reports |
| `/v1/institutions/*` | Institution and tenant management |
| `/v1/courses/*` | Course management and enrollment |
| `/v1/sessions/*` | Learning session tracking |
| `/v1/quizzes/*` | Quiz attempt recording |
| `/v1/events/*` | Learning event collection |
| `/v1/resources/*` | Learning resource management |
| `/health*` | Health and readiness probes |

For complete endpoint documentation, see [docs/API_REFERENCE.md](docs/API_REFERENCE.md) or the live Swagger UI.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│          External Consumers                  │
│   (Your LMS · Your App · Third-Party API)    │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│            KnowDecay API Gateway             │
│   Request Pipeline · Auth · RBAC · Logging   │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│        Retention Intelligence Engine         │
│                                              │
│  ┌────────────┐ ┌───────────┐ ┌───────────┐ │
│  │  Retention  │ │  Priority │ │ Scheduler │ │
│  │  & Decay    │ │  Engine   │ │  Engine   │ │
│  └────────────┘ └───────────┘ └───────────┘ │
│  ┌────────────┐ ┌───────────┐               │
│  │ Recalib-   │ │ Analytics │               │
│  │ ration     │ │  Engine   │               │
│  └────────────┘ └───────────┘               │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│              PostgreSQL 16                   │
│   Users · Memory States · Learning Data      │
│   Institutions · Courses · Analytics         │
└──────────────────────────────────────────────┘
```

### Knowledge Hierarchy

```
Institution (optional) → Course (optional) → Subject → Module → Chapter → Topic → Subtopic
```

Retention is modeled at the **Topic** level and aggregated upward, giving visibility at every layer — from individual concepts to entire subjects.

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| API | FastAPI, Pydantic v2, pydantic-settings |
| ORM & Migrations | SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL 16, psycopg2 |
| Authentication | JWT (python-jose), bcrypt, 5-tier RBAC |
| Numerics | NumPy, pandas |
| Infrastructure | Docker (multi-stage, non-root), Gunicorn + Uvicorn ASGI, GitHub Actions CI |
| Testing | pytest, httpx |
| Code Quality | Ruff |

---

## Project Structure

```
knowdecay-engine/
├── app/
│   ├── api/              # REST endpoint handlers
│   ├── core/             # Security, logging, exceptions, constants
│   ├── database/         # Connection management and sessions
│   ├── engine/           # Retention intelligence algorithms
│   ├── middleware/        # Request pipeline (logging, errors, request ID)
│   ├── models/           # Database models (SQLAlchemy ORM)
│   ├── schemas/          # Request/response validation (Pydantic)
│   ├── services/         # Business logic layer
│   └── utils/            # Shared utilities
├── alembic/              # Database migration scripts
├── simulation/           # Offline simulation and validation framework
├── tests/                # Comprehensive test suite
├── docs/                 # Documentation
├── .github/workflows/    # CI pipeline
├── Dockerfile            # Multi-stage production build
├── docker-compose.yml    # Development + production profiles
└── Makefile              # Developer workflow commands
```

---

## Testing

```bash
# Run the full suite
make test

# Or directly:
APP_ENV=testing JWT_SECRET_KEY=test-secret-key-minimum-32-characters-long \
    pytest tests/ -v --tb=short

# Run specific areas
pytest tests/test_auth/           # Authentication & RBAC
pytest tests/test_engine/         # Engine algorithms (no DB required)
pytest tests/test_simulation/     # Simulation & validation

# Lint
make lint
```

Engine-only tests run without a database. Integration tests use a transactional test session that rolls back after each test. CI runs the complete suite with a PostgreSQL service container.

---

## Deployment

### Development

```bash
docker compose up       # or: make up
```

### Production

```bash
# Via Docker Compose
docker compose --profile production up

# Direct
gunicorn app.main:app -c gunicorn.conf.py
```

The production server uses **Gunicorn as a process manager** with **Uvicorn ASGI workers**. The application is stateless and designed for horizontal scaling behind a load balancer.

For detailed deployment instructions, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Documentation

- [API Reference](docs/API_REFERENCE.md) — Complete endpoint documentation
- [Architecture](docs/ARCHITECTURE.md) — System design and engine internals
- [Deployment](docs/DEPLOYMENT.md) — Deployment guides and production configuration

---

## Roadmap

### Planned

- **Machine Learning Augmentation** — Neural network corrections blended over the deterministic engine, feature store, experiment tracking
- **Advanced Analytics** — Exportable reports, trend analysis, cohort comparisons
- **Enterprise Integrations** — SSO (OAuth, OpenID Connect), LMS connectors, API key management
- **Scalability Infrastructure** — Redis caching, background workers, real-time WebSocket notifications, observability

### KnowDecay Ecosystem *(separate projects)*

| Project | Description |
|---------|-------------|
| KnowDecay Platform | Student-facing web application |
| KnowDecay Admin | Institution management dashboard |
| KnowDecay Mobile | iOS and Android applications |
| LMS Plugins | Connectors for Moodle, Canvas, Blackboard |

---

## License

This project is **proprietary software**. All rights reserved.

Public visibility of this repository does **not** constitute permission to copy, modify, redistribute, or commercially use any part of the software. See the [LICENSE](LICENSE) file for full terms.

---

## Acknowledgements

KnowDecay Engine's retention modeling is grounded in established memory science:

- **Hermann Ebbinghaus** — Forgetting curve research (1885)
- **Piotr Woźniak** — Spaced repetition algorithms (SuperMemo)
- **Robert Bjork** — Desirable difficulties and retrieval practice
- **Leitner System** — Spaced repetition box method

---

<p align="center">
  <strong>Built for learners. Designed for institutions. Powered by memory science.</strong>
</p>
