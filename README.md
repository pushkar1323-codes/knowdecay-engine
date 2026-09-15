# KnowDecay

### Retention Intelligence as a Service (RIaaS)

> KnowDecay is an API-first retention intelligence engine that transforms learning activity into evolving learner–topic memory states, predicts retention and forgetting risk, prioritizes revision, and generates adaptive revision schedules.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

---

## Overview

Students study hard but forget fast. Institutions lack visibility into knowledge decay. Cramming works short-term but fails long-term. Existing revision tools use fixed schedules rather than adapting to each learner.

KnowDecay answers one question:

> **What should a learner revise right now, and when should it be revised again?**

The engine analyzes learning activity and memory state to provide:

- **Retention prediction** — estimate recall probability for any learner–topic pair
- **Forgetting prediction** — identify concepts at risk of being forgotten
- **Revision prioritization** — rank topics by urgency, weakness, delay, and exam proximity
- **Adaptive scheduling** — compute optimal revision intervals personalized to each learner
- **Retention analytics** — aggregate retention visibility across the knowledge hierarchy

KnowDecay is designed as an **API-first backend engine** that can be integrated into:

- LMS platforms (Moodle, Canvas, Blackboard)
- EdTech applications
- Coaching and tutoring platforms
- School and university systems
- Enterprise learning platforms
- Standalone learning applications

### Two Integration Models

| | **Standalone Backend** | **Retention Intelligence as a Service (RIaaS)** |
|---|---|---|
| **For** | Teams building a KnowDecay-powered learning platform | EdTech companies and institutions adding retention intelligence to existing products |
| **How** | Complete backend with authentication, user management, and intelligence APIs | REST API that plugs into any LMS, application, or learning platform |
| **What** | Full-stack backend ready for a frontend to consume | Retention scoring, scheduling, and analytics endpoints |

---

## Key Features

### Implemented

- **Adaptive retention modeling** — every learner × topic pair has its own memory state (retention score, stability, decay rate, confidence) evolving with each interaction
- **Forgetting analysis** — real-time decay modeling using the Ebbinghaus exponential forgetting curve with configurable thresholds
- **Urgency-based revision prioritization** — multiplicative priority scoring using urgency, weakness, delay, and exam importance with explainable reason strings
- **Adaptive scheduling** — per-topic revision intervals adapting to learner behavior, with exam-aware compression modes (cram, intensive, balanced, long-term)
- **Event-driven recalibration** — quiz results, study sessions, and revision events continuously recalibrate memory states
- **Hierarchical analytics** — retention aggregated across Subject → Module → Chapter → Topic → Subtopic
- **Learning data collection** — extensible event tracking for study sessions, quiz attempts, revision history, and learning resources
- **Daily activity aggregation** — pre-aggregated daily summaries and retention time-series snapshots
- **Institution-aware multi-tenancy** — institution isolation, course management, enrollment workflows, and role-scoped access
- **JWT authentication** — access and refresh token authentication with token rotation
- **Role-based access control** — five-tier RBAC (Super Admin, Institution Admin, Teacher, Student, API Client)
- **Knowledge hierarchy** — Subject → Module → Chapter → Topic → Subtopic with optional Institution and Course scoping
- **Structured logging** — JSON/text logging with request IDs and correlation tracing
- **Health probes** — liveness and readiness endpoints for orchestration
- **Production infrastructure** — Docker multi-stage builds, Gunicorn + Uvicorn ASGI, GitHub Actions CI
- **Centralized error handling** — consistent error responses with request IDs and field-level validation detail
- **Pydantic validation** — strict request/response validation with Pydantic v2

---

## How It Works

```
Learning Activity (study session, quiz, revision)
        ↓
Validation & Event Recording
        ↓
Memory State Update
        ↓
Retention Calculation  ──→  R(t) = e^(−t / S_adaptive)
        ↓
Forgetting / Decay Analysis
        ↓
Revision Priority Ranking
        ↓
Adaptive Schedule Generation
        ↓
Updated Memory State (persisted)
```

The engine continuously updates the learner's memory state rather than recalculating the full learning history for every request. Each new learning event triggers a targeted recalibration of the affected memory state.

### Feedback Loop

```
Prediction (retention score, forgetting risk)
    ↓
Learning Activity (study, quiz, revision)
    ↓
Outcome (quiz score, confidence, study duration)
    ↓
Recalibration (adaptive stability evolution)
    ↓
New Prediction (updated retention, scheduling)
```

---

## Knowledge Hierarchy

```
Institution (optional)
    ↓
Course (optional)
    ↓
Subject
    ↓
Module / Unit
    ↓
Chapter
    ↓
Topic
    ↓
Subtopic / Concept
```

Retention is modeled at the **Topic** level and aggregated upward, giving visibility at every layer — from individual concepts to entire subjects.

---

## Retention Intelligence

KnowDecay currently uses a **deterministic retention model** based on the Ebbinghaus forgetting curve with adaptive memory stability.

### Input Signals

| Signal | Source |
|--------|--------|
| Study duration | Study sessions |
| Quiz score | Quiz attempts |
| Self-reported confidence | Quiz attempts |
| Revision count | Revision history |
| Elapsed time since last revision | Timestamps |
| Topic difficulty | Topic metadata |
| Exam proximity | User configuration |

### Memory State

Each learner × topic pair maintains a persistent memory state with:

| Field | Description |
|-------|-------------|
| `retention_score` | Current recall probability (0.0–1.0) |
| `stability_score` | Days until retention drops to threshold |
| `decay_rate` | Forgetting rate λ (higher = faster forgetting) |
| `confidence_score` | Blended confidence from quiz and self-report |
| `revision_strength` | Accumulated reinforcement from revisions |
| `revision_count` | Total revision events for this topic |
| `forgetting_probability` | Probability of substantial forgetting (0.0–1.0) |
| `urgency_score` | Composite urgency driving priority ranking |
| `adaptive_stability` | Dynamic S used in R(t) = e^(−t/S) |
| `base_stability` | Base stability evolving with each learning event |
| `performance_trend` | Recent performance trajectory (−1.0 to +1.0) |
| `half_life_days` | Days until retention drops to 50% |
| `effective_decay_rate` | Composite decay rate after all modifiers |
| `last_revision_at` | Timestamp of most recent revision |
| `next_revision_at` | Computed optimal next revision timestamp |

Memory state is persisted and updated incrementally — not recalculated from scratch.

---

## Forgetting and Decay

The engine uses an **Ebbinghaus-inspired exponential decay model**:

```
R(t) = e^(−t / S_adaptive)
```

Where:
- `R(t)` = retention estimate at elapsed time `t`
- `t` = days since last meaningful revision
- `S_adaptive` = adaptive memory stability (computed dynamically)

Memory stability `S_adaptive` is not fixed — it evolves based on:

- Revision history (more successful revisions → higher stability)
- Quiz performance (higher scores → slower decay)
- Difficulty (harder topics → lower stability)
- Learner-specific performance trends
- Confidence alignment (penalizes overconfidence)

This is an **engineering adaptation inspired by the Ebbinghaus forgetting curve**, not a claim that KnowDecay has scientifically validated or replaced the original model.

### Retention Computation

The composite retention score combines:

```
retention = base_strength + revision_reinforcement + quiz_boost − time_decay − difficulty_penalty
```

| Component | Formula | Behavior |
|-----------|---------|----------|
| Base strength | `weight × (duration / (duration + saturation))` | Sigmoid saturation — cramming has diminishing returns |
| Revision reinforcement | `factor × log(1 + revision_count)` | Logarithmic — first revisions help most |
| Quiz boost | `weight × quiz_score` | Linear — better quiz scores raise retention |
| Time decay | `1 − e^(−λt)` | Ebbinghaus forgetting curve |
| Difficulty penalty | `factor × difficulty` | Harder topics are forgotten faster |

---

## Revision Prioritization

KnowDecay determines which topics deserve attention using a multiplicative priority model:

```
Priority = Urgency × Weakness × Delay Factor × Exam Importance
```

| Component | Formula | Meaning |
|-----------|---------|---------|
| **Urgency** | `(1 − retention) × (1 + difficulty × weight)` | How badly has this topic decayed? |
| **Weakness** | `forgetting_prob × (1 + weakness_trend + quiz_penalty)` | Is the learner struggling with this topic? |
| **Delay Factor** | `1 + log(1 + overdue_days)` | How overdue is this revision? |
| **Exam Importance** | `importance × (1 + proximity × exam_weight)` | How close is an exam? |

Multiplicative composition ensures:
- A topic with zero urgency has zero priority regardless of delay
- A topic with no weakness has reduced priority even if overdue
- Exam proximity scales everything proportionally

Each priority result includes a **human-readable tier** (Critical, High, Medium, Low, Minimal) and **explainable reason strings** for every component.

---

## Adaptive Scheduling

The scheduling engine computes optimal revision intervals based on current memory state and exam context.

### Schedule Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| `EXAM_TOMORROW` | Exam < 1 day | Cram mode — compress intervals into hours |
| `EXAM_WEEK` | Exam 1–7 days | Intensive — daily revision of weak topics |
| `EXAM_MONTH` | Exam 7–30 days | Balanced — spaced intervals with exam ramp-up |
| `LONG_TERM` | No exam or > 30 days | Maintenance — pure spaced repetition |

### Core Algorithm

```
base_interval = stability_score × retention_factor
adjusted      = base_interval × difficulty_modifier / exam_compression
next_revision = now + adjusted
```

Spaced repetition intervals grow with each successful revision (capped to prevent unbounded growth):

```
Revision 1: base × 1.0
Revision 2: base × 1.5
Revision 3: base × 2.0
Revision n: base × min(n^0.6, 5.0)
```

---

## Architecture

```
┌──────────────────────────────────────────────┐
│          External Consumers                  │
│   (LMS · EdTech App · Third-Party Client)    │
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
│  ┌────────────┐ ┌───────────┐ ┌───────────┐ │
│  │ Recalib-   │ │ Analytics │ │ Adaptive  │ │
│  │ ration     │ │  Engine   │ │ Forgetting│ │
│  └────────────┘ └───────────┘ └───────────┘ │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│              PostgreSQL 16                   │
│   Users · Memory States · Learning Data      │
│   Institutions · Courses · Analytics         │
└──────────────────────────────────────────────┘
```

### Engine Separation

The intelligence layer is composed of **pure functions** with no database access and no side effects. All state is passed in, all results are returned. This makes every engine function independently testable.

| Engine | Responsibility |
|--------|---------------|
| **Retention Engine** | Composite retention scoring from study, quiz, revision, decay, and difficulty signals |
| **Adaptive Forgetting** | Ebbinghaus forgetting curve: R(t) = e^(−t/S_adaptive) |
| **Stability Engine** | Dynamic S_adaptive computation from learner behavior |
| **Priority Engine** | Urgency-based ranking with explainable reasons |
| **Scheduling Engine** | Adaptive revision intervals with exam-aware modes |
| **Recalibration Engine** | Event-driven memory state evolution |
| **Analytics Engine** | Hierarchical retention aggregation |
| **Decay Engine** | Decay rate computation and thresholds |

---

## Technology Stack

### Backend

| Technology | Purpose |
|-----------|---------|
| Python 3.11+ | Runtime |
| FastAPI | ASGI web framework |
| Pydantic v2 | Request/response validation and settings |
| SQLAlchemy 2.0 | ORM and database access |
| Alembic | Database migrations |
| NumPy | Numerical computation |
| pandas | Data processing |

### Database

| Technology | Purpose |
|-----------|---------|
| PostgreSQL 16 | Primary data store |
| psycopg2 | PostgreSQL driver |
| UUID primary keys | All entities use UUID identifiers |

### Authentication

| Technology | Purpose |
|-----------|---------|
| python-jose | JWT encoding/decoding (HS256) |
| bcrypt | Password hashing |
| python-multipart | Form data parsing for OAuth2 |

### Infrastructure

| Technology | Purpose |
|-----------|---------|
| Docker | Multi-stage production builds (non-root) |
| Docker Compose | Development and production profiles |
| Gunicorn + Uvicorn | Production ASGI server |
| GitHub Actions | CI pipeline |
| Ruff | Linting and formatting |
| pytest + httpx | Testing |

---

## API

KnowDecay is an **API-first system**. All functionality is exposed through a versioned RESTful API (`/v1/`).

Interactive documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when the server is running.

All endpoints except health probes and registration require JWT authentication via the `Authorization: Bearer <token>` header.

### Endpoint Groups

| Group | Purpose |
|-------|---------|
| `/v1/auth/*` | Registration, login, token refresh, logout |
| `/v1/users/*` | User management (admin) |
| `/v1/institutions/*` | Institution and tenant management |
| `/v1/courses/*` | Course management and enrollment |
| `/v1/retention/*` | Retention predictions |
| `/v1/priority/*` | Revision urgency ranking |
| `/v1/schedule/*` | Optimal revision scheduling |
| `/v1/memory/*` | Memory state management and recalibration |
| `/v1/recalibration/*` | Event-driven memory state recalibration |
| `/v1/analytics/*` | Retention analytics and reports |
| `/v1/sessions/*` | Learning session tracking |
| `/v1/quizzes/*` | Quiz attempt recording |
| `/v1/events/*` | Learning event collection |
| `/v1/resources/*` | Learning resource management |
| `/health` | Liveness and readiness probes |

For complete endpoint documentation, see [docs/API_REFERENCE.md](docs/API_REFERENCE.md) or the live Swagger UI at `/docs`.

---

## Authentication and Authorization

### Authentication

KnowDecay uses JWT-based authentication:

- **Access tokens** — short-lived tokens for API access (configurable TTL, default 30 minutes)
- **Refresh tokens** — longer-lived tokens for obtaining new access tokens (configurable TTL, default 7 days)
- **Token rotation** — refresh tokens are rotated on use
- **Password hashing** — bcrypt with configurable cost factor
- **Logout** — server-side refresh token revocation

### Authorization

```
Authentication → Who are you?
Authorization  → What are you allowed to access?
```

Server-side authorization enforces:
- Role-based access control on every protected endpoint
- Resource ownership checks (users can only access their own data)
- Institution isolation (users cannot access resources from other institutions)

### Roles

| Role | Permissions |
|------|-------------|
| **Super Admin** | Full system access, user management, institution management |
| **Institution Admin** | Manage users and resources within their institution |
| **Teacher** | Manage learning content and view student analytics within their scope |
| **Student** | Access own learning data, memory states, and revision schedules |
| **API Client** | Programmatic access for third-party integrations |

Public registration always creates a **Student** account. Privileged roles can only be assigned by administrators.

---

## Multi-Tenancy

Institutions operate as logical tenants. Server-side authorization prevents users from accessing resources belonging to another institution.

Individual learners without an institution belong to their own personal workspace and are not associated with any institution unless explicitly linked.

---

## Database

KnowDecay uses PostgreSQL 16 as its primary data store.

### Core Entities

| Entity | Purpose |
|--------|---------|
| `users` | Learner and administrator accounts |
| `institutions` | Organizational tenants |
| `courses` | Courses within institutions |
| `course_enrollments` | User-course relationships |
| `subjects` | Top-level knowledge domains |
| `modules` | Units within subjects |
| `chapters` | Chapters within modules |
| `topics` | Primary learning units (retention modeled here) |
| `subtopics` | Granular concepts within topics |
| `memory_states` | Per-user per-topic retention intelligence state |
| `revision_logs` | Individual revision events |
| `study_sessions` | Learning session records |
| `quiz_attempts` | Quiz attempt records |
| `quiz_question_responses` | Individual question responses |
| `learning_events` | Extensible learning activity events |
| `learning_resources` | Learning materials and content references |
| `refresh_tokens` | JWT refresh token records |
| `retention_time_series` | Historical retention snapshots |
| `daily_user_activity` | Pre-aggregated daily activity summaries |
| `feature_snapshots` | ML-ready feature snapshots |
| `analytics_snapshots` | Aggregated analytics records |

All entities use UUID primary keys, created/updated timestamps, and enforce referential integrity through foreign keys and constraints.

Database migrations are managed with Alembic.

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://docker.com/products/docker-desktop) (Docker Engine + Docker Compose)
- Git
- Python 3.11+ *(only for local development without Docker)*

### Using Docker (Recommended)

```bash
git clone <repo-url>
cd knowdecay-engine

# Configure environment
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY (minimum 32 characters):
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Start development stack (PostgreSQL + API with hot-reload)
docker compose up

# Or with Makefile:
make up

# Verify
curl http://localhost:8000/health
# Interactive API docs: http://localhost:8000/docs
```

### Run Database Migrations

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

### Local Development (Without Docker)

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

# Create admin account
python -m app.cli create-superadmin

# Start development server
uvicorn app.main:app --reload

# Interactive API docs
open http://localhost:8000/docs
```

---

## Environment Variables

Configuration is managed through environment variables. Copy `.env.example` to `.env` and update for your environment.

**Important:** Never commit `.env` to version control. It contains secrets.

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development, testing, production) | `development` |
| `DATABASE_URL` | PostgreSQL connection string | *(required)* |
| `JWT_SECRET_KEY` | Secret for JWT signing (minimum 32 characters) | *(required)* |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `7` |
| `BCRYPT_ROUNDS` | bcrypt cost factor | `12` |
| `REGISTRATION_ENABLED` | Allow public user registration | `true` |
| `LOG_LEVEL` | Log severity (DEBUG, INFO, WARNING, ERROR) | `DEBUG` |
| `LOG_FORMAT` | Log format (text, json) | `text` |
| `CORS_ORIGINS` | Comma-separated allowed CORS origins | *(disabled)* |
| `WORKERS` | Gunicorn worker count | `1` |

Generate a secure JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## Testing

```bash
# Run the full test suite
make test

# Or directly:
APP_ENV=testing JWT_SECRET_KEY=test-secret-key-minimum-32-characters-long \
    pytest tests/ -v --tb=short

# Run specific test areas
pytest tests/test_auth/           # Authentication and RBAC
pytest tests/test_engine/         # Engine algorithms (no database required)
pytest tests/test_api/            # API schema validation
pytest tests/test_simulation/     # Simulation and validation
pytest tests/test_infrastructure/ # Configuration, middleware, health

# Lint
make lint
```

Engine tests run without a database. Integration tests use a transactional test session that rolls back after each test. CI runs the complete suite with a PostgreSQL service container.

---

## Project Structure

```
knowdecay-engine/
├── app/
│   ├── api/              # REST endpoint handlers
│   ├── core/             # Security, logging, exceptions, constants
│   ├── database/         # Connection management and sessions
│   ├── engine/           # Retention intelligence algorithms (pure functions)
│   ├── middleware/        # Request pipeline (logging, errors, request ID)
│   ├── models/           # Database models (SQLAlchemy ORM)
│   ├── schemas/          # Request/response validation (Pydantic)
│   ├── services/         # Business logic layer
│   └── utils/            # Shared utilities
├── alembic/              # Database migration scripts
├── simulation/           # Offline simulation and validation framework
├── tests/                # Test suite
├── docs/                 # Documentation
├── .github/workflows/    # CI pipeline
├── Dockerfile            # Multi-stage production build
├── docker-compose.yml    # Development and production profiles
└── Makefile              # Developer workflow commands
```

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

## Security Considerations

### Implemented

- JWT authentication with configurable token lifetimes
- bcrypt password hashing with configurable cost factor
- Server-side role-based access control on all protected endpoints
- Resource ownership enforcement
- Institution/tenant isolation
- Pydantic request validation (rejects malformed input before processing)
- Database constraints and referential integrity
- Environment-based secret management (secrets never hardcoded)
- CORS configuration (disabled by default)
- Structured error handling with request IDs (no stack traces in production responses)
- Refresh token rotation and server-side revocation

### Important

- Learning and retention data may contain sensitive educational and behavioral information and should be handled appropriately
- Always use strong JWT secrets in production (minimum 32 characters, cryptographically random)
- Never commit `.env` files or credentials to version control
- Review CORS configuration before enabling cross-origin access

---

## Known Limitations

- **Deterministic intelligence only** — retention prediction currently uses a rule-based deterministic model, not machine learning
- **Limited real-world learner data** — the engine is designed for real-world use but has not been validated against large-scale production datasets
- **No ML model training** — ML infrastructure (XGBoost, Random Forest) is planned but not yet implemented
- **No LMS/ERP integration** — no direct connectors for Moodle, Canvas, Blackboard, or enterprise ERP systems
- **No SSO/SCIM** — no OAuth, OpenID Connect, SAML, or SCIM provisioning
- **No Redis caching** — all requests query PostgreSQL directly
- **No background job infrastructure** — no task queue or asynchronous worker processing
- **No file/object storage** — learning resources store metadata only, not binary content
- **No production observability** — no APM, distributed tracing, or metrics export beyond structured logging
- **No webhooks or real-time notifications** — API is request-response only
- **No API key authentication** — third-party integrations must use JWT

---

## Future Enhancements

The following are planned for future development and are **not currently implemented**:

- **ML-based retention prediction** — XGBoost and Random Forest models trained on real-world learning data
- **Feature engineering pipelines** — automated feature extraction from learning activity
- **Experiment tracking and model registry** — versioned model management with promotion workflows
- **Model monitoring and drift detection** — production model health monitoring
- **Redis caching** — cache frequently accessed memory states and analytics
- **Background workers** — asynchronous task processing for aggregation and model training
- **LMS integration** — connectors for Moodle, Canvas, Blackboard
- **SSO and OAuth/OIDC** — single sign-on for institutional deployments
- **SCIM provisioning** — automated user lifecycle management
- **API key authentication** — alternative authentication for third-party integrations
- **SDKs** — client libraries for common platforms
- **Webhooks** — event-driven notifications for external systems
- **Advanced institutional analytics** — cohort comparisons, trend analysis, exportable reports
- **Knowledge dependency graphs** — prerequisite relationships between topics
- **Advanced personalization** — learning path recommendations

---

## Documentation

- [API Reference](docs/API_REFERENCE.md) — Complete endpoint documentation
- [Architecture](docs/ARCHITECTURE.md) — System design and engine internals
- [Deployment](docs/DEPLOYMENT.md) — Deployment guides and production configuration

---

## License

This project is **proprietary software**. All rights reserved.

Public visibility of this repository does **not** constitute permission to copy, modify, redistribute, or commercially use any part of the software. See the [LICENSE](LICENSE) file for full terms.

---

## Acknowledgements

KnowDecay's retention modeling is grounded in established memory science:

- **Hermann Ebbinghaus** — Forgetting curve research (1885)
- **Piotr Woźniak** — Spaced repetition algorithms (SuperMemo)
- **Robert Bjork** — Desirable difficulties and retrieval practice
- **Leitner System** — Spaced repetition box method

---

<p align="center">
  <strong>Built for learners. Designed for institutions. Powered by memory science.</strong>
</p>
