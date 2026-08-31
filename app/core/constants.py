"""
app/core/constants.py
──────────────────────
Shared constants used across the KnowDecay Engine.
Centralises magic numbers and configuration defaults.
"""

# ── API ───────────────────────────────────────────────────────────────────────
API_V1_PREFIX = "/v1"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500
MIN_PAGE_SIZE = 1

# ── Engine Metric Bounds ──────────────────────────────────────────────────────
RETENTION_FLOOR = 0.05
RETENTION_CEILING = 1.0
STABILITY_MIN = 0.1
STABILITY_MAX = 365.0
DECAY_RATE_MIN = 0.0
DECAY_RATE_MAX = 10.0

# ── Request ───────────────────────────────────────────────────────────────────
REQUEST_ID_HEADER = "X-Request-ID"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30

# ── Health ────────────────────────────────────────────────────────────────────
HEALTH_STATUS_OK = "ok"
HEALTH_STATUS_DEGRADED = "degraded"
HEALTH_DB_CONNECTED = "connected"
HEALTH_DB_UNAVAILABLE = "unavailable"

# ── Authentication ────────────────────────────────────────────────────────────
AUTH_HEADER = "Authorization"
AUTH_SCHEME = "Bearer"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
