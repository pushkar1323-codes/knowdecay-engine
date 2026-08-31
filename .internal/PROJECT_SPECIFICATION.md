# KnowDecay Engine — Project Specification

> **Document Status:** Living document — updated after each development phase.
> **Last Updated:** 2026-07-31
> **Current Version:** 0.1.0
> **Test Suite:** 1218/1218 passing

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Intelligence Backbone](#3-intelligence-backbone)
4. [Technology Stack](#4-technology-stack)
5. [Database Requirements](#5-database-requirements)
6. [Engine Requirements](#6-engine-requirements)
7. [API Requirements](#7-api-requirements)
8. [Simulation & Validation Requirements](#8-simulation--validation-requirements)
9. [Testing Requirements](#9-testing-requirements)
10. [Deployment Requirements](#10-deployment-requirements)
11. [Documentation Requirements](#11-documentation-requirements)
12. [Development Rules](#12-development-rules)
13. [Project Roadmap & Implementation Status](#13-project-roadmap--implementation-status)

---

## 1. Project Overview

**KnowDecay Engine** is an API-first retention intelligence backend (RIaaS — Retention Intelligence as a Service) that integrates into LMS systems, coaching platforms, EdTech applications, and institutional learning portals.

### Core Capabilities

| Capability | Description | Status |
|-----------|-------------|--------|
| Retention Prediction | Probability of correct recall for a user × topic | ✅ Completed |
| Forgetting Analysis | Decay rate modeling, half-life, time-to-critical | ✅ Completed |
| Revision Prioritization | Urgency scoring and rank ordering | ✅ Completed |
| Adaptive Scheduling | Optimal revision interval computation | ✅ Completed |
| Memory Recalibration | Event-driven state evolution | ✅ Completed |
| Hierarchical Analytics | Aggregation across Subject → Module → Chapter → Topic | ✅ Completed |
| Adaptive Forgetting Curve | R = e^(-t / S_adaptive) with dynamic stability | ✅ Completed |
| ML Augmentation Layer | Blendable ML corrections over deterministic engine | ✅ Completed |
| Simulation Framework | DB-free synthetic learner testing | ✅ Completed |
| Deep Validation Suite | 4-axis engine invariant validation | ✅ Completed |
| Phase 11 QA Framework | Comprehensive validation & quality assurance | ✅ Completed |
| Backend Infrastructure | Request pipeline, structured logging, exception handling | ✅ Completed |
| Authentication & Security | JWT auth, RBAC, refresh tokens, password management | ✅ Completed |

### What KnowDecay Engine Is NOT

- Not a study platform, flashcard app, or LMS
- Not a frontend application
- It is the **retention intelligence layer** that powers those systems

---

## 2. Architecture

### Layered Architecture

```
Institution LMS / App
        ↓
KnowDecay API Gateway  (FastAPI)
        ↓
Service Layer (orchestration)
        ↓
┌───────────────────────────────────────────┐
│  stability_engine  │  decay_engine        │
│  retention_engine  │  recalibration_engine │
│  priority_engine   │  scheduling_engine    │
│  analytics_engine  │  ml_augmentor         │
│  adaptive_forgetting                      │
└───────────────────────────────────────────┘
        ↓
PostgreSQL (memory_states — continuously evolved)
```

### Directory Structure

```
knowdecay-engine/
├── app/
│   ├── main.py                     # FastAPI app factory
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── deps.py                     # Dependency injection
│   ├── api/                        # Route handlers (7 routers)
│   │   ├── health.py               # GET /health
│   │   ├── retention.py            # POST /v1/retention/predict, /predict/batch
│   │   ├── priority.py             # POST /v1/priority/rank, /rank/batch
│   │   ├── schedule.py             # POST /v1/schedule/generate, /generate/batch
│   │   ├── recalibration.py        # POST /v1/recalibration/process, /process/batch
│   │   ├── memory.py               # Memory state CRUD (10 endpoints)
│   │   └── analytics.py            # Analytics (6 endpoints)
│   ├── core/                       # Logging + exception handling
│   │   ├── exceptions.py           # Custom exceptions + handlers
│   │   └── logging.py              # Structured logging config
│   ├── database/                   # SQLAlchemy engine + session
│   │   ├── base.py                 # Declarative base
│   │   ├── session.py              # Session factory
│   │   └── init_db.py              # DB initialization
│   ├── engine/                     # Pure engine layer (9 modules)
│   │   ├── retention_engine.py     # Point-in-time retention scoring
│   │   ├── decay_engine.py         # Forgetting progression analysis
│   │   ├── stability_engine.py     # Adaptive stability computation
│   │   ├── priority_engine.py      # Urgency scoring + ranking
│   │   ├── scheduling_engine.py    # Adaptive interval calculation
│   │   ├── recalibration_engine.py # Event-driven state evolution
│   │   ├── analytics_engine.py     # Hierarchical aggregation
│   │   ├── adaptive_forgetting.py  # Forgetting curve utilities
│   │   └── ml_augmentor.py         # ML augmentation layer
│   ├── models/                     # SQLAlchemy ORM (7 models)
│   │   ├── user.py                 # User
│   │   ├── hierarchy.py            # Subject, Module, Chapter, Topic, Subtopic
│   │   ├── memory_state.py         # MemoryState (26+ fields)
│   │   ├── study_session.py        # StudySession
│   │   ├── quiz_attempt.py         # QuizAttempt
│   │   ├── revision_log.py         # RevisionLog
│   │   └── analytics_snapshot.py   # AnalyticsSnapshot
│   ├── schemas/                    # Pydantic request/response (6 schema files)
│   ├── services/                   # Business logic (7 service files)
│   └── utils/                      # Shared utilities
│       └── time_utils.py           # UTC time helpers
│   ├── core/                       # Infrastructure (Phase 12)
│   │   ├── constants.py            # Application-wide constants
│   │   ├── enums.py                # Shared enumerations
│   │   ├── exceptions.py           # Centralised exception hierarchy
│   │   ├── logging.py              # Structured logging (JSON/text)
│   │   └── responses.py            # Standard response envelope
│   ├── middleware/                  # Request pipeline (Phase 12)
│   │   ├── request_id.py           # X-Request-ID generation
│   │   ├── logging_middleware.py   # Access logging
│   │   └── error_middleware.py     # Last-resort error catching
├── simulation/                     # DB-free simulation framework
│   ├── learner_profiles.py         # 10 learner archetypes
│   ├── event_generator.py          # Synthetic event generation
│   ├── timeline_simulator.py       # Day-by-day orchestrator
│   ├── validators.py               # 7 engine invariant validators
│   ├── analytics_reporter.py       # Post-simulation reporting
│   ├── deep_validation.py          # 4-axis deep validation suite
│   ├── qa_report.py                # Phase 11 QA report generator
│   └── run_simulation.py           # CLI entry point
├── tests/                          # 1110 tests across 30 files
├── alembic/                        # 3 migration versions
├── docs/
│   ├── API_REFERENCE.md
│   └── PROJECT_SPECIFICATION.md    # This document
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pyproject.toml
```

### Knowledge Hierarchy

```
Subject → Module → Chapter → Topic → Subtopic
```

Retention is calculated at **Topic** level and aggregated upward through the hierarchy.

---

## 3. Intelligence Backbone

**PERMANENT ARCHITECTURAL RULE:** All intelligence systems MUST follow this pipeline:

```
MemoryState → Adaptive Stability → Decay Engine → Retention Estimate → Priority Engine → Scheduling Engine → Analytics
```

| Stage | Engine Module | Purpose |
|-------|--------------|---------|
| 1. MemoryState | `memory_state.py` (ORM) | Single source of truth — load from DB or in-memory dict |
| 2. Adaptive Stability | `stability_engine.py` | Compute S_adaptive BEFORE decay/retention |
| 3. Decay Engine | `decay_engine.py` | Compute forgetting progression using S_adaptive |
| 4. Retention Estimate | `retention_engine.py` / `recalibration_engine.py` | R = e^(-t / S_adaptive) |
| 5. Priority Engine | `priority_engine.py` | Consumes pre-computed R — never estimates retention |
| 6. Scheduling Engine | `scheduling_engine.py` | Uses R + S_adaptive + priority for interval |
| 7. Analytics | `analytics_engine.py` | Downstream consumer of all prior stages |

### Backbone Rules

- Stability BEFORE Decay — S_adaptive feeds into decay computation
- No Skipping — every module must pass through all stages
- Separation of Concerns — Priority never estimates retention, Scheduling never estimates priority
- Pure Engine Layer — all engine functions are stateless (no DB, no I/O)
- MemoryState Persistence — all 26+ fields flow through MemoryState ORM
- Simulation Parity — simulation pipeline mirrors service layer exactly

---

## 4. Technology Stack

| Layer | Technology | Version | Status |
|-------|-----------|---------|--------|
| Language | Python | 3.11+ | ✅ Completed |
| API Framework | FastAPI | ≥0.111.0 | ✅ Completed |
| Database | PostgreSQL | 16 | ✅ Completed |
| ORM | SQLAlchemy | ≥2.0.30 | ✅ Completed |
| Validation | Pydantic v2 | ≥2.7.0 | ✅ Completed |
| Settings | pydantic-settings | ≥2.2.1 | ✅ Completed |
| Migrations | Alembic | ≥1.13.1 | ✅ Completed |
| Analytics | NumPy, pandas | ≥1.26, ≥2.2 | ✅ Completed |
| Containerisation | Docker + Docker Compose | v3.9 | ✅ Completed |
| Testing | pytest + httpx | ≥8.2, ≥0.27 | ✅ Completed |
| ASGI Server | Uvicorn | ≥0.29.0 | ✅ Completed |

---

## 5. Database Requirements

### 5.1 ORM Models

| Model | Table | Fields | Status |
|-------|-------|--------|--------|
| `User` | `users` | id, name, email, created_at | ✅ Completed |
| `Subject` | `subjects` | id, name, description, user_id | ✅ Completed |
| `Module` | `modules` | id, name, description, subject_id | ✅ Completed |
| `Chapter` | `chapters` | id, name, description, module_id | ✅ Completed |
| `Topic` | `topics` | id, name, description, difficulty, importance_weight, chapter_id | ✅ Completed |
| `Subtopic` | `subtopics` | id, name, description, topic_id | ✅ Completed |
| `MemoryState` | `memory_states` | 26+ fields (see §5.2) | ✅ Completed |
| `StudySession` | `study_sessions` | id, user_id, topic_id, duration, timestamps | ✅ Completed |
| `QuizAttempt` | `quiz_attempts` | id, user_id, topic_id, score, confidence, timestamps | ✅ Completed |
| `RevisionLog` | `revision_logs` | id, user_id, topic_id, retention metrics, timestamps | ✅ Completed |
| `AnalyticsSnapshot` | `analytics_snapshots` | id, user_id, scope, metrics, timestamps | ✅ Completed |

### 5.2 MemoryState Fields (26+ columns)

| Category | Fields |
|----------|--------|
| Core Retention | retention_score, stability_score, decay_rate, confidence_score, revision_strength, revision_count, forgetting_probability, urgency_score |
| Adaptive Forgetting Curve | base_stability, revision_quality, difficulty_factor, performance_trend |
| Adaptive Stability | adaptive_stability, stability_growth_rate, half_life_days |
| Decay Parameters | effective_decay_rate, time_to_critical, days_until_target |
| Reinforcement Behaviour | quality_variance, effective_revision_count, revision_effectiveness_ratio, time_pattern_regularity, confidence_calibration_error |
| Retention History | peak_retention, retention_at_last_revision, total_forgetting_events, last_forgetting_event_at |
| Scheduling | last_revision_at, next_revision_at, updated_at |

### 5.3 Database Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `uq_memory_state_user_topic` | user_id, topic_id | Unique constraint |
| `ix_memory_state_user_urgency` | user_id, urgency_score | Priority ranking |
| `ix_memory_state_user_schedule` | user_id, next_revision_at | Schedule lookups |
| `ix_memory_state_user_retention` | user_id, retention_score | Analytics aggregation |
| `ix_memory_state_user_adaptive_stability` | user_id, adaptive_stability | Stability lookups |

### 5.4 Migrations

| Migration | Description | Status |
|-----------|-------------|--------|
| `0001_initial_schema` | All tables + indexes | ✅ Applied |
| `0002_add_adaptive_forgetting_fields` | Phase 8.5 fields | ✅ Applied |
| `0003_add_retention_evolution_fields` | Stability, decay, reinforcement, history fields | ✅ Applied |

---

## 6. Engine Requirements

### 6.1 Retention Engine (`retention_engine.py`) — ✅ Completed

- **Formula:** retention = clamp(base_strength + revision_reinforcement + quiz_boost − time_decay − difficulty_penalty, floor, 1.0)
- Pure functions: `compute_retention()`, `compute_stability()`, `compute_confidence()`
- Explainability: full component breakdown in output
- Tests: 51 tests passing

### 6.2 Decay Engine (`decay_engine.py`) — ✅ Completed

- **Formula:** R(t) = R₀ × e^(-λt) (Ebbinghaus)
- Difficulty-adjusted λ, reinforcement damping, inactivity acceleration
- Forgetting probability, half-life computation, retention floor
- Horizon-based projection, multi-horizon analysis
- Tests: 58 tests passing

### 6.3 Stability Engine (`stability_engine.py`) — ✅ Completed

- **Formula:** S_adaptive = base_stability × reinforcement_factor × quiz_factor × confidence_factor − difficulty_penalty
- Base stability evolution on successful events
- Bounded output: [0.1, 365.0] days
- Component breakdown for explainability
- Tests: 48 tests passing

### 6.4 Priority Engine (`priority_engine.py`) — ✅ Completed

- Multi-factor urgency scoring (retention, decay, exam pressure, difficulty, importance)
- Tier classification: critical / high / medium / low / minimal
- Normalised scoring (0.0–1.0) for cross-topic comparison
- Human-readable urgency reasons
- Tests: 57 tests passing

### 6.5 Scheduling Engine (`scheduling_engine.py`) — ✅ Completed

- Adaptive interval computation based on retention + stability + decay
- Exam-aware compression (shorter intervals near exams)
- Multi-strategy: fixed, adaptive, exam-aware
- Bounded intervals with configurable min/max
- Tests: 54 tests passing

### 6.6 Recalibration Engine (`recalibration_engine.py`) — ✅ Completed

- Event-driven state evolution via `recalibrate(CurrentState, EventData) → RecalibrationOutput`
- 4 event types: quiz_submitted, revision_completed, study_session, inactivity_detected
- StateDelta-based incremental updates via `apply_delta()`
- Full audit trail (ChangeReason list + summary)
- 26+ field evolution per event
- Tests: 60 tests passing

### 6.7 Analytics Engine (`analytics_engine.py`) — ✅ Completed

- Hierarchical aggregation (topic → chapter → module → subject)
- Retention heatmaps, risk scoring, trend analysis
- Forgetting risk identification
- Topic-level detailed breakdowns
- Session and quiz analytics
- Tests: 75 + 61 = 136 tests passing

### 6.8 Adaptive Forgetting (`adaptive_forgetting.py`) — ✅ Completed

- Forgetting curve utilities and parameter fitting
- Curve shape analysis and prediction
- Tests: 45 tests passing

### 6.9 ML Augmentor (`ml_augmentor.py`) — ✅ Completed

- Blendable ML corrections over deterministic engine
- Master kill switch (`ml_enabled`)
- Stability correction: ±30% max
- Decay modifier: 0.7–1.3 range
- Blend weight: 0.0 (pure deterministic) to 1.0 (full ML)
- Tests: 51 tests passing

---

## 7. API Requirements

### 7.1 Registered Endpoints

| Router | Method | Path | Description | Status |
|--------|--------|------|-------------|--------|
| Health | GET | `/health` | Liveness + version check | ✅ Completed |
| Retention | POST | `/v1/retention/predict` | Single topic retention | ✅ Completed |
| Retention | POST | `/v1/retention/predict/batch` | Multi-topic batch | ✅ Completed |
| Priority | POST | `/v1/priority/rank` | Single topic priority | ✅ Completed |
| Priority | POST | `/v1/priority/rank/batch` | Multi-topic batch ranking | ✅ Completed |
| Schedule | POST | `/v1/schedule/generate` | Single topic schedule | ✅ Completed |
| Schedule | POST | `/v1/schedule/generate/batch` | Multi-topic batch | ✅ Completed |
| Recalibration | POST | `/v1/recalibration/process` | Single event processing | ✅ Completed |
| Recalibration | POST | `/v1/recalibration/process/batch` | Batch event processing | ✅ Completed |
| Memory | GET | `/v1/memory/{user_id}/{topic_id}` | Get memory state | ✅ Completed |
| Memory | POST | `/v1/memory/` | Create memory state | ✅ Completed |
| Memory | GET | `/v1/memory/{user_id}` | All states for user | ✅ Completed |
| Memory | GET | `/v1/memory/{user_id}/weak-topics` | Weak topics | ✅ Completed |
| Memory | GET | `/v1/memory/{user_id}/strong-topics` | Strong topics | ✅ Completed |
| Memory | POST | `/v1/memory/{user_id}/{topic_id}/reset` | Reset memory state | ✅ Completed |
| Memory | GET | `/v1/memory/{user_id}/stats` | Summary statistics | ✅ Completed |
| Memory | GET | `/v1/memory/{user_id}/forgetting-risk` | At-risk topics | ✅ Completed |
| Memory | GET | `/v1/memory/{user_id}/overdue` | Overdue revisions | ✅ Completed |
| Memory | GET | `/v1/memory/{user_id}/stability-report` | Stability analysis | ✅ Completed |
| Analytics | GET | `/v1/analytics/{user_id}/overview` | Retention overview | ✅ Completed |
| Analytics | GET | `/v1/analytics/{user_id}/topics` | Per-topic breakdown | ✅ Completed |
| Analytics | GET | `/v1/analytics/{user_id}/forgetting-risk` | High-risk topics | ✅ Completed |
| Analytics | GET | `/v1/analytics/{user_id}/heatmap` | Retention heatmap | ✅ Completed |
| Analytics | GET | `/v1/analytics/{user_id}/study-efficiency` | Study metrics | ✅ Completed |
| Analytics | GET | `/v1/analytics/{user_id}/revision-history` | Revision timeline | ✅ Completed |

### 7.2 API Features

| Feature | Status |
|---------|--------|
| Request validation (Pydantic v2) | ✅ Completed |
| Response schemas | ✅ Completed |
| Error handling (custom exceptions) | ✅ Completed |
| Health endpoint with version info | ✅ Completed |
| OpenAPI/Swagger documentation | ✅ Completed |
| ReDoc documentation | ✅ Completed |
| Versioned API prefix (`/v1/`) | ✅ Completed |
| Schema validation tests | ✅ Completed (31 tests) |

### 7.3 Planned API Endpoints (Not Yet Implemented)

| Phase | Method | Path | Description | Status |
|-------|--------|------|-------------|--------|
| 2 | POST | `/v1/users` | Create user | 🔲 Planned |
| 2 | POST | `/v1/subjects` | Create subject | 🔲 Planned |
| 2 | POST | `/v1/subjects/{id}/modules` | Create module | 🔲 Planned |
| 2 | POST | `/v1/modules/{id}/chapters` | Create chapter | 🔲 Planned |
| 2 | POST | `/v1/chapters/{id}/topics` | Create topic | 🔲 Planned |
| 2 | POST | `/v1/topics/{id}/subtopics` | Create subtopic | 🔲 Planned |
| 3 | POST | `/v1/study-sessions` | Log study session | 🔲 Planned |
| 3 | POST | `/v1/quiz-attempts` | Submit quiz attempt | 🔲 Planned |

> **Note:** The engine-first architecture means Phases 4–10 (engine + API + simulation) were built before Phases 2–3 (CRUD endpoints). User/hierarchy CRUD routers are defined in `main.py` but commented out pending implementation.

---

## 8. Simulation & Validation Requirements

### 8.1 Simulation Framework — ✅ Completed

| Component | Module | Purpose | Status |
|-----------|--------|---------|--------|
| Learner Profiles | `learner_profiles.py` | 10 archetypes with configurable behaviour | ✅ Completed |
| Event Generator | `event_generator.py` | Synthetic quiz/revision/study/inactivity events | ✅ Completed |
| Timeline Simulator | `timeline_simulator.py` | Day-by-day orchestrator (backbone-aligned) | ✅ Completed |
| Validators | `validators.py` | 7 engine invariant assertions (with floor-convergence guard) | ✅ Completed |
| Analytics Reporter | `analytics_reporter.py` | Post-simulation JSON + stdout reporting | ✅ Completed |
| Deep Validation | `deep_validation.py` | 4-axis validation suite | ✅ Completed |
| QA Report Generator | `qa_report.py` | Machine-readable JSON QA report + CLI (`python -m simulation.qa_report`) | ✅ Completed (Phase 11) |
| CLI Entry Point | `run_simulation.py` | `python -m simulation.run_simulation` | ✅ Completed |

### 8.2 Learner Archetypes (10 total)

| Archetype | Quiz Range | Revision Prob | Study Duration | Inactivity Risk | Phase |
|-----------|------------|---------------|----------------|-----------------|-------|
| Diligent | 0.75–0.95 | 85% | 30–60 min | 5% | Original |
| Cramming | 0.50–0.85 | 30% | 60–120 min | 25% | Original |
| Struggling | 0.30–0.60 | 40% | 15–30 min | 20% | Original |
| Coasting | 0.60–0.80 | 50% | 20–40 min | 15% | Original |
| Absent | 0.20–0.40 | 10% | 10–20 min | 40% | Original |
| Beginner | 0.35–0.55 | 45% | 20–40 min | 15% | Phase 11 |
| Average | 0.55–0.75 | 55% | 25–45 min | 12% | Phase 11 |
| Advanced | 0.80–0.98 | 75% | 25–50 min | 5% | Phase 11 |
| Inconsistent | 0.25–0.90 | 40% | 10–90 min | 30% | Phase 11 |
| High-Frequency | 0.55–0.85 | 90% | 10–25 min | 3% | Phase 11 |

### 8.3 Engine Invariant Validators (7/7 passing)

| # | Invariant | Assertion |
|---|-----------|-----------|
| 1 | retention_bounds | 0 ≤ R ≤ 1 |
| 2 | stability_positive | S ≥ 0 |
| 3 | decay_bounded | 0 < λ < 10 |
| 4 | priority_ordering | Low R → high priority (≤30% tolerance) |
| 5 | schedule_retention_adaptation | Low R → short interval (≤30% tolerance) |
| 6 | diligent_vs_struggling | Mean R_diligent > R_struggling |
| 7 | forgetting_events_tracked | Decay detection (informational) |

### 8.4 Deep Validation Suite (4/4 passing)

| Validation | Description | Key Result |
|-----------|-------------|------------|
| Adaptive Decay Consistency | R = e^(-t/S_adaptive) correctness | 0 violations / 3,590 transitions |
| Retention Evolution | Non-flat trajectories across archetypes | 5/5 archetypes show evolution |
| Reinforcement Behavior | Positive events increase R and S | 76–100% increase rate |
| Stability Transitions | Stability grows with revision, not inactivity | 95% growth after revision |

---

## 9. Testing Requirements

### 9.1 Test Suite Summary

| Test File | Tests | Target | Phase |
|-----------|-------|--------|-------|
| `test_analytics_engine.py` | 75 | Analytics engine | 8 |
| `test_advanced_analytics.py` | 61 | Advanced analytics | 8 |
| `test_recalibration_engine.py` | 60 | Recalibration engine | 7 |
| `test_decay_engine.py` | 58 | Decay engine | 4 |
| `test_priority_engine.py` | 57 | Priority engine | 5 |
| `test_scheduling_engine.py` | 54 | Scheduling engine | 6 |
| `test_memory_state_fields.py` | 52 | ORM field coverage | 8.6 |
| `test_retention_engine.py` | 51 | Retention engine | 4 |
| `test_ml_augmentor.py` | 51 | ML augmentor | 8.6 |
| `test_stability_engine.py` | 48 | Stability engine | 8.5 |
| `test_adaptive_forgetting.py` | 45 | Adaptive forgetting | 8.5 |
| `test_simulation.py` | 33 | Simulation framework | 10 |
| `test_api_schemas.py` | 31 | API schema validation | 9 |
| `test_learner_simulations.py` | 30 | Learner simulation integration | 10 |
| `test_memory_service.py` | 13 | Memory service | 8 |
| **Pre-Phase 11 Subtotal** | **719** | | |
| `test_forgetting_curve_validation.py` | ~32 | Forgetting curve time-point validation | 11 |
| `test_priority_scenarios.py` | ~30 | Priority engine scenario matrix | 11 |
| `test_learning_cycle.py` | ~12 | Complete learning cycle validation | 11 |
| `test_scheduler_validation.py` | ~12 | Scheduler edge cases & exam-awareness | 11 |
| `test_analytics_validation.py` | ~10 | Analytics accuracy & trend detection | 11 |
| `test_data_flow.py` | ~9 | End-to-end backbone pipeline validation | 11 |
| `test_edge_cases.py` | ~15 | Edge cases (never revises, large sets, boundaries) | 11 |
| `test_performance.py` | ~8 | Engine operation timing benchmarks | 11 |
| `test_ml_readiness.py` | ~38 | ML training data field coverage | 11 |
| `test_database_validation.py` | ~38 | FK chain, MemoryState fields, table names | 11 |
| **Phase 11 Subtotal** | **~304** | | |
| **TOTAL** | **1023** | | |

### 9.2 Test Characteristics

| Requirement | Status |
|-------------|--------|
| All engine tests run without DB (pure functions) | ✅ Completed |
| Simulation tests run without DB | ✅ Completed |
| API schema tests run without DB | ✅ Completed |
| Database validation tests use SQLAlchemy inspection (no DB connection) | ✅ Completed |
| Deterministic seeded tests for reproducibility | ✅ Completed |
| Zero test warnings (except pytest config) | ✅ Completed |
| Performance benchmarks with wall-clock timing | ✅ Completed (Phase 11) |

---

## 10. Deployment Requirements

### 10.1 Docker Configuration

| Component | Status |
|-----------|--------|
| `Dockerfile` (Python 3.11-slim, multi-stage) | ✅ Completed |
| `docker-compose.yml` (PostgreSQL 16 + API) | ✅ Completed |
| Health check for PostgreSQL | ✅ Completed |
| Volume persistence for DB data | ✅ Completed |
| Hot-reload in development | ✅ Completed |
| `.env.example` with all config variables | ✅ Completed |

### 10.2 Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `APP_NAME` | KnowDecay Engine | Application name |
| `APP_VERSION` | 0.1.0 | Version |
| `APP_ENV` | development | Environment |
| `DATABASE_URL` | postgresql://... | PostgreSQL connection |
| `LOG_LEVEL` | INFO | Logging level |
| `DEFAULT_RETENTION_THRESHOLD` | 0.85 | Target recall probability |
| `BASE_DECAY_RATE` | 0.1 | Base λ for forgetting curve |
| `MIN_RETENTION_FLOOR` | 0.05 | Minimum retention floor |
| `ML_ENABLED` | false | ML augmentation kill switch |
| `ML_BLEND_WEIGHT` | 0.0 | ML blend (0=deterministic) |
| `LOG_FORMAT` | text | Logging format (text/json) |
| `CORS_ORIGINS` | *(empty)* | Comma-separated CORS origins |
| `TRUSTED_HOSTS` | * | Comma-separated trusted hosts |
| `REQUEST_TIMEOUT` | 30 | Request timeout (seconds) |
| `MAX_BATCH_SIZE` | 100 | Max batch endpoint items |

---

## 11. Documentation Requirements

| Document | Location | Status |
|----------|----------|--------|
| README.md | `/README.md` | ✅ Completed |
| API Reference | `/docs/API_REFERENCE.md` | ⚠️ Outdated (only Phase 1 documented) |
| Project Specification | `/docs/PROJECT_SPECIFICATION.md` | ✅ This document |
| AGENTS.md (Backbone Rules) | `/.agents/AGENTS.md` | ✅ Completed |
| OpenAPI/Swagger (auto-generated) | `/docs` endpoint | ✅ Completed |
| ReDoc (auto-generated) | `/redoc` endpoint | ✅ Completed |

### Documentation Gaps

- `docs/API_REFERENCE.md` needs updating — currently only documents Phase 1 health endpoint. All 25+ endpoints implemented but not documented in this file.

---

## 12. Development Rules

1. **Phase-by-phase only** — never skip the build order
2. **Never regenerate completed modules** — extend, don't rewrite
3. **Memory states evolve incrementally** — never recalculate from scratch
4. **Engine first, UI never** — this is backend infrastructure
5. **Deterministic before ML** — ML augments, never replaces
6. **Intelligence Backbone is permanent** — all modules follow the 7-stage pipeline
7. **Pure engine layer** — no DB, no I/O, no side effects in engine functions
8. **Simulation parity** — simulation pipeline must mirror service layer

---

## 13. Project Roadmap & Implementation Status

### Completed Phases

| Phase | Scope | Status | Tests |
|-------|-------|--------|-------|
| 1 | Foundation: scaffold, ORM models, Docker, health endpoint | ✅ Complete | — |
| 4 | Retention Engine + Decay Engine | ✅ Complete | 109 |
| 5 | Priority Engine | ✅ Complete | 57 |
| 6 | Scheduling Engine | ✅ Complete | 54 |
| 7 | Recalibration Engine | ✅ Complete | 60 |
| 8 | Analytics Engine + Hierarchical Aggregation | ✅ Complete | 136 |
| 8.5 | Adaptive Forgetting Curve + Stability Engine | ✅ Complete | 93 |
| 8.6 | ML Augmentor + MemoryState Field Expansion | ✅ Complete | 103 |
| 9 | API Layer (FastAPI endpoints for all engines) | ✅ Complete | 31 |
| 10 | Simulation & Testing Framework | ✅ Complete | 33 |
| 11 | Simulation, Validation & Quality Assurance | ✅ Complete | 304 |
| — | Intelligence Backbone Alignment | ✅ Complete | — |
| — | Deep Validation Suite (4-axis) | ✅ Complete | — |

### Phase 11 Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| 5 new learner archetypes | Beginner, Average, Advanced, Inconsistent, High-Frequency | ✅ Completed |
| Forgetting curve time-point validation | Decay at 0,1,3,7,15,30,60,90 days | ✅ Completed |
| Complete learning cycle validation | Study→Quiz→Revise→Priority→Schedule | ✅ Completed |
| Priority scenario matrix | 6 realistic urgency scenarios | ✅ Completed |
| Scheduler edge cases | Exam-aware, spacing, impossible schedules | ✅ Completed |
| Analytics validation | Trends, weak topics, forgetting risk | ✅ Completed |
| End-to-end backbone pipeline | 7-stage flow validation | ✅ Completed |
| Edge case testing | Never-revises, daily, large sets, boundaries | ✅ Completed |
| Database model validation | FK chains, 26+ MemoryState fields, indexes | ✅ Completed |
| Performance benchmarks | Timing validation for all engines | ✅ Completed |
| ML readiness validation | Training field coverage + explainability | ✅ Completed |
| QA report generator | `python -m simulation.qa_report` → JSON + CLI | ✅ Completed |

| 12 | Backend Infrastructure & Engineering Standards | ✅ Complete | 87 |

### Phase 12 Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Request ID middleware | X-Request-ID generation/pass-through | ✅ Completed |
| Structured logging | JSON (production) / text (dev) with secret redaction | ✅ Completed |
| Error middleware | Last-resort unhandled exception catching | ✅ Completed |
| Exception hierarchy | KnowDecayError → ServiceError, DatabaseError, etc. | ✅ Completed |
| Standard response envelope | success_response / error_response / paginated_response | ✅ Completed |
| Health probes | /health/live, /health/ready, /health/detailed | ✅ Completed |
| Configuration management | Environment detection, CORS parsing, new settings | ✅ Completed |
| Lifespan management | Modern asynccontextmanager lifespan event | ✅ Completed |
| Infrastructure tests | 87 tests across 5 test files | ✅ Completed |

| 13 | Authentication & Security | ✅ Complete | 109 |

### Phase 13 Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| JWT access tokens | HS256 tokens with sub, role, type, exp, iat | ✅ Completed |
| Refresh token rotation | SHA-256 hashed DB storage, automatic rotation | ✅ Completed |
| Password hashing | Direct bcrypt (no passlib) with configurable rounds | ✅ Completed |
| RBAC system | 5 roles: super_admin, institution_admin, teacher, student, api_client | ✅ Completed |
| Role hierarchy | require_admin, require_institution_admin, require_teacher, require_any | ✅ Completed |
| Auth API | POST register, login, refresh, logout, change-password; GET me | ✅ Completed |
| User management API | GET/PATCH users, activate/deactivate (admin-only) | ✅ Completed |
| Auth dependencies | get_current_user, require_roles factory, OAuth2 scheme | ✅ Completed |
| CLI bootstrap | `python -m app.cli create-superadmin` interactive command | ✅ Completed |
| Auth migration | 0004_add_auth_fields: users auth columns + refresh_tokens table | ✅ Completed |
| Auth tests | 109 tests across 5 test files (security, RBAC, service, API) | ✅ Completed |

### Planned Phases (Not Yet Implemented)

| Phase | Scope | Status |
|-------|-------|--------|
| 2 | Users + Knowledge Hierarchy CRUD APIs | 🔲 Planned |
| 3 | Study Session + Quiz Attempt ingestion APIs | 🔲 Planned |

### Future Phases (Scope TBD)

| Phase | Scope | Status |
|-------|-------|--------|
| 14 | Docker production configuration (multi-stage, gunicorn) | 🔲 Future |
| — | Real ML model training (when sufficient data) | 🔲 Future |
| — | WebSocket push for real-time retention updates | 🔲 Future |
| — | Multi-tenant support | 🔲 Future |
| — | Rate limiting + API key authentication | 🔲 Future |

---

> **Note:** The engine-first build order (Phases 4–10 before 2–3) is intentional. The core intelligence stack was built and verified with simulations before adding CRUD endpoints, ensuring the retention engine is correct independent of any UI or data ingestion pathway.
