# API Reference

**Base URL:** `http://localhost:8000`
**API Prefix:** `/v1` (all endpoints except health probes)
**Interactive Docs:** [`/docs`](http://localhost:8000/docs) (Swagger UI) · [`/redoc`](http://localhost:8000/redoc) (ReDoc)
**OpenAPI Schema:** [`/openapi.json`](http://localhost:8000/openapi.json)

## Authentication

Most endpoints require a JWT Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Obtain tokens via `POST /v1/auth/login`. Access tokens expire after 30 minutes (configurable). Use `POST /v1/auth/refresh` with a valid refresh token to obtain a new pair.

## Endpoint Summary

**38 endpoints** across 9 groups:

| Group | Endpoints | Auth Required |
|-------|-----------|---------------|
| [Health](#health-probes) | 4 | No |
| [Auth](#authentication-endpoints) | 6 | Varies |
| [Users](#user-management) | 5 | Yes (role-based) |
| [Retention](#retention-engine) | 2 | Yes |
| [Priority](#priority-engine) | 2 | Yes |
| [Schedule](#scheduling-engine) | 2 | Yes |
| [Recalibration](#recalibration-engine) | 2 | Yes |
| [Memory](#memory-state-management) | 10 | Yes |
| [Analytics](#analytics-engine) | 6 | Yes |

---

## Health Probes

No authentication required. Not prefixed with `/v1`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | General API status and version |
| GET | `/health/live` | Liveness probe (Docker HEALTHCHECK) |
| GET | `/health/ready` | Readiness probe (verifies DB connectivity) |
| GET | `/health/detailed` | Extended diagnostics (requires `super_admin` role) |

**Response** — `GET /health`:

```json
{
  "status": "ok",
  "engine": "KnowDecay Engine",
  "version": "0.1.0",
  "environment": "development"
}
```

---

## Authentication Endpoints

Prefix: `/v1/auth`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/auth/register` | None | Register a new user (always creates `student` role) |
| POST | `/v1/auth/login` | None | Login with email/password → access + refresh tokens |
| POST | `/v1/auth/refresh` | None (token in body) | Rotate refresh token → new token pair |
| POST | `/v1/auth/logout` | Authenticated | Revoke the refresh token |
| GET | `/v1/auth/me` | Authenticated | Get current user profile |
| POST | `/v1/auth/change-password` | Authenticated | Change own password (revokes all refresh tokens) |

### POST `/v1/auth/register`

**Request:**
```json
{
  "name": "Jane Doe",
  "email": "student@example.com",
  "password": "SecureP@ss123"
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Jane Doe",
  "email": "student@example.com",
  "role": "student",
  "institution_id": null,
  "is_active": true,
  "created_at": "2026-01-15T10:30:00Z",
  "updated_at": null
}
```

### POST `/v1/auth/login`

**Request:**
```json
{
  "email": "student@example.com",
  "password": "SecureP@ss123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### POST `/v1/auth/refresh`

**Request:**
```json
{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2..."
}
```

**Response (200):** Same as login — new access + refresh token pair. Previous refresh token is revoked.

### POST `/v1/auth/change-password`

**Request:**
```json
{
  "current_password": "SecureP@ss123",
  "new_password": "NewSecureP@ss456"
}
```

**Response (200):**
```json
{
  "message": "Password changed successfully"
}
```

All existing refresh tokens are revoked on password change.

---

## User Management

Prefix: `/v1/users`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/users` | `teacher`+ | List users (paginated) |
| GET | `/v1/users/{user_id}` | `teacher`+ | Get user by ID |
| PATCH | `/v1/users/{user_id}` | `teacher`+ | Update user profile |
| POST | `/v1/users/{user_id}/activate` | `institution_admin`+ | Activate a user account |
| POST | `/v1/users/{user_id}/deactivate` | `institution_admin`+ | Deactivate a user account |

### GET `/v1/users`

**Query Parameters:**
- `skip` (int, default: 0) — pagination offset
- `limit` (int, default: 100, max: 1000) — page size

**Response (200):**
```json
{
  "users": [
    {
      "id": "550e8400-...",
      "name": "Jane Doe",
      "email": "student@example.com",
      "role": "student",
      "institution_id": null,
      "is_active": true,
      "created_at": "2026-01-15T10:30:00Z",
      "updated_at": null
    }
  ],
  "total": 42,
  "page": 0,
  "page_size": 100
}
```

---

## Retention Engine

Prefix: `/v1/retention`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/retention/predict` | Authenticated | Predict retention for a single user×topic |
| POST | `/v1/retention/predict/batch` | Authenticated | Predict retention for multiple topics |

### POST `/v1/retention/predict`

Calculates the current retention probability using the Adaptive Forgetting Engine.

**Request:**
```json
{
  "user_id": "550e8400-...",
  "topic_id": "660e8400-..."
}
```

**Response (200):** Retention prediction with current probability, time elapsed since last revision, and decay parameters.

---

## Priority Engine

Prefix: `/v1/priority`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/priority/rank` | Authenticated | Rank topics by revision urgency |
| POST | `/v1/priority/rank/batch` | Authenticated | Batch priority ranking |

### POST `/v1/priority/rank`

Returns a priority-ordered list of topics for a user, considering retention probability, difficulty, importance weight, and optional exam proximity.

---

## Scheduling Engine

Prefix: `/v1/schedule`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/schedule/next` | Authenticated | Get next optimal revision time for a topic |
| POST | `/v1/schedule/generate` | Authenticated | Generate a full adaptive revision schedule |

### POST `/v1/schedule/generate`

Generates an optimal revision schedule for a user across multiple topics, considering retention states, priorities, and configurable daily study time.

---

## Recalibration Engine

Prefix: `/v1/recalibrate`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/recalibrate` | Authenticated | Process a learning event and recalibrate memory state |
| POST | `/v1/recalibrate/batch` | Authenticated | Batch recalibration for multiple events |

### POST `/v1/recalibrate`

Processes a learning event (quiz, revision, study session, or inactivity decay) and recalibrates the corresponding memory state. This is the primary write endpoint for the Adaptive Forgetting Engine.

**Request — event_type must be one of:** `quiz_submitted`, `revision_completed`, `study_session`, `inactivity_decay`

---

## Memory State Management

Prefix: `/v1/memory`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/memory/init` | Authenticated | Initialize a memory state for a user×topic |
| POST | `/v1/memory/batch` | Authenticated | Batch query memory states |
| GET | `/v1/memory/{user_id}` | Authenticated | List all memory states for a user |
| GET | `/v1/memory/{user_id}/{topic_id}` | Authenticated | Get specific memory state |
| GET | `/v1/memory/{user_id}/overdue` | Authenticated | Topics overdue for revision |
| GET | `/v1/memory/{user_id}/at-risk` | Authenticated | Topics at risk of forgetting |
| GET | `/v1/memory/{user_id}/overview` | Authenticated | Summary overview of all states |
| GET | `/v1/memory/{user_id}/aggregate/chapter/{chapter_id}` | Authenticated | Aggregate retention at chapter level |
| GET | `/v1/memory/{user_id}/aggregate/module/{module_id}` | Authenticated | Aggregate retention at module level |
| GET | `/v1/memory/{user_id}/aggregate/subject/{subject_id}` | Authenticated | Aggregate retention at subject level |

---

## Analytics Engine

Prefix: `/v1/analytics`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/analytics/{user_id}/summary` | Authenticated | Overall retention summary |
| GET | `/v1/analytics/{user_id}/weak-topics` | Authenticated | Topics with lowest retention |
| GET | `/v1/analytics/{user_id}/heatmap` | Authenticated | Retention heatmap data |
| GET | `/v1/analytics/{user_id}/distribution` | Authenticated | Retention score distribution |
| GET | `/v1/analytics/{user_id}/report` | Authenticated | Comprehensive analytics report |
| GET | `/v1/analytics/{user_id}/advanced` | Authenticated | Advanced analytics with trends |

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad Request — invalid input or business rule violation |
| 401 | Unauthorized — missing, expired, or invalid token |
| 403 | Forbidden — insufficient role permissions |
| 404 | Not Found — resource does not exist |
| 422 | Validation Error — request body fails Pydantic validation |
| 500 | Internal Server Error — unexpected failure |

### Validation Error (422) Detail Format

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Pagination

List endpoints accept the following query parameters:

| Parameter | Type | Default | Max | Description |
|-----------|------|---------|-----|-------------|
| `skip` | int | 0 | — | Offset for pagination |
| `limit` | int | 100 | 1000 | Number of results per page |

---

## Versioning

All API endpoints (except health probes) are prefixed with `/v1`. Future breaking changes will be introduced under `/v2` while maintaining backward compatibility on `/v1`.
