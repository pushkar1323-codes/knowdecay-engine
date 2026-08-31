"""
app/api/health.py
──────────────────
Health check endpoint.
Used by Docker health checks, load balancers, and monitoring systems
to confirm the engine process is alive and configured correctly.

Returns engine metadata, DB connectivity status, and supported capabilities.
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])
settings = get_settings()

_STARTUP_TIME = time.monotonic()


# ── Response Schema ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response with engine metadata and connectivity status."""

    status: str = Field(description="ok | degraded")
    engine: str
    version: str
    environment: str
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    uptime_seconds: float = Field(description="Seconds since engine process started")

    # Connectivity
    database: str = Field(description="connected | unavailable")

    # Capabilities
    capabilities: list[str] = Field(
        description="List of active engine modules",
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Engine health check",
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Engine liveness + readiness endpoint.

    Returns:
    - **status** — `ok` if all checks pass, `degraded` if DB unreachable
    - **database** — `connected` or `unavailable`
    - **uptime_seconds** — seconds since engine process start
    - **capabilities** — active engine modules

    A 200 response confirms the process is running. Check the `status`
    field to distinguish between full health and degraded mode.
    """
    # ── DB connectivity ───────────────────────────────────────────────────
    db_status = "connected"
    overall_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.warning("Health check: database unreachable")
        db_status = "unavailable"
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        engine=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=round(time.monotonic() - _STARTUP_TIME, 2),
        database=db_status,
        capabilities=[
            "retention_prediction",
            "priority_ranking",
            "adaptive_scheduling",
            "event_recalibration",
            "memory_state_management",
            "retention_analytics",
            "advanced_analytics",
            "ml_augmentation",
            "retention_evolution",
        ],
    )


# ── Infrastructure Health Endpoints ────────────────────────────────────────────


class LivenessResponse(BaseModel):
    """Simple liveness probe response."""
    status: str = Field(default="alive", description="Always 'alive' if process is running")


class ReadinessResponse(BaseModel):
    """Readiness probe response with dependency checks."""
    status: str = Field(description="ready | not_ready")
    database: str = Field(description="connected | unavailable")
    checks: dict[str, str] = Field(description="Individual check results")


class DetailedHealthResponse(BaseModel):
    """Comprehensive health response for monitoring systems."""
    status: str
    engine: str
    version: str
    environment: str
    timestamp: str
    uptime_seconds: float
    database: str
    capabilities: list[str]
    infrastructure: dict[str, str] = Field(description="Infrastructure component status")
    configuration: dict[str, str] = Field(description="Non-sensitive configuration summary")


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
)
def liveness_probe() -> LivenessResponse:
    """
    Kubernetes/Docker liveness probe.
    Always returns 200 if the process is running.
    Does NOT check dependencies — that's what readiness is for.
    """
    return LivenessResponse(status="alive")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
)
def readiness_probe(db: Session = Depends(get_db)) -> ReadinessResponse:
    """
    Kubernetes/Docker readiness probe.
    Returns 200 with status='ready' only if all dependencies are healthy.
    Returns 503 if any critical dependency is unavailable.
    """
    from fastapi.responses import JSONResponse

    checks: dict[str, str] = {}

    # Database check
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception:
        db_status = "unavailable"
        checks["database"] = "unavailable"
        logger.warning("Readiness probe: database unreachable")

    overall = "ready" if db_status == "connected" else "not_ready"

    response = ReadinessResponse(
        status=overall,
        database=db_status,
        checks=checks,
    )

    # Return 503 if not ready
    if overall == "not_ready":
        return JSONResponse(
            status_code=503,
            content=response.model_dump(),
        )

    return response


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed health status",
)
def detailed_health(db: Session = Depends(get_db)) -> DetailedHealthResponse:
    """
    Comprehensive health endpoint for monitoring and observability systems.

    Returns:
    - All fields from the standard /health endpoint
    - Infrastructure component status (middleware, logging, config)
    - Non-sensitive configuration summary
    """
    # Database check
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    return DetailedHealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        engine=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=round(time.monotonic() - _STARTUP_TIME, 2),
        database=db_status,
        capabilities=[
            "retention_prediction",
            "priority_ranking",
            "adaptive_scheduling",
            "event_recalibration",
            "memory_state_management",
            "retention_analytics",
            "advanced_analytics",
            "ml_augmentation",
            "retention_evolution",
        ],
        infrastructure={
            "request_id_middleware": "active",
            "logging_middleware": "active",
            "error_middleware": "active",
            "structured_logging": "active",
            "exception_handlers": "active",
        },
        configuration={
            "log_level": settings.log_level,
            "log_format": getattr(settings, 'log_format', 'text'),
            "ml_enabled": str(settings.ml_enabled),
            "retention_threshold": str(settings.default_retention_threshold),
        },
    )
