"""
app/main.py
────────────
FastAPI application factory for KnowDecay Engine.

Router registration and middleware configuration.
DO NOT import engine modules here — keep main.py thin.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.exceptions import ConfigurationError, register_exception_handlers
from app.core.logging import configure_logging

# ── Bootstrap ─────────────────────────────────────────────────────────────────
configure_logging()
settings = get_settings()

# ── Lifespan ──────────────────────────────────────────────────────────────────
import logging as _logging  # noqa: E402
_startup_logger = _logging.getLogger("knowdecay.startup")

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan: startup and shutdown events."""
    if (
        (not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32)
        and settings.app_env != "testing"
    ):
        raise ConfigurationError(
            "JWT_SECRET_KEY must be set and at least 32 characters long"
        )
    _startup_logger.info(
        "KnowDecay Engine starting | version=%s | env=%s | log_level=%s | ml_enabled=%s",
        settings.app_version,
        settings.app_env,
        settings.log_level,
        settings.ml_enabled,
    )
    yield
    _startup_logger.info("KnowDecay Engine shutting down")

# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "**KnowDecay Engine** — Retention Intelligence as a Service (RIaaS).\n\n"
        "API-first adaptive revision intelligence infrastructure for educational ecosystems.\n\n"
        "Provides: retention prediction · forgetting analysis · revision prioritization · "
        "adaptive scheduling · hierarchical learning analytics."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "KnowDecay Engine",
    },
    license_info={
        "name": "Proprietary",
    },
    lifespan=lifespan,
)

# ── Exception handlers ────────────────────────────────────────────────────────
register_exception_handlers(app)

# ── Middleware Pipeline ───────────────────────────────────────────────────────
# Order matters: last added = first executed
# Execution order: RequestID → Logging → Error → [FastAPI handlers]
from app.middleware.error_middleware import ErrorMiddleware  # noqa: E402
from app.middleware.logging_middleware import LoggingMiddleware  # noqa: E402
from app.middleware.request_id import RequestIdMiddleware  # noqa: E402

app.add_middleware(ErrorMiddleware)       # 3rd: last-resort error catching
app.add_middleware(LoggingMiddleware)     # 2nd: request/response logging
app.add_middleware(RequestIdMiddleware)   # 1st: assign correlation ID

# ── CORS (disabled by default) ────────────────────────────────────────────────
if settings.cors_origins_list:
    from starlette.middleware.cors import CORSMiddleware  # noqa: E402
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ── Health Probes ─────────────────────────────────────────────────────────────
from app.api.health import router as health_router  # noqa: E402
app.include_router(health_router)

# ── Authentication & Users ────────────────────────────────────────────────────
from app.api.auth import router as auth_router  # noqa: E402
from app.api.users import router as users_router  # noqa: E402
app.include_router(auth_router, prefix="/v1")
app.include_router(users_router, prefix="/v1")

# ── Institution & Course Management (Phase 16) ───────────────────────────────
from app.api.institutions import router as institutions_router  # noqa: E402
from app.api.courses import router as courses_router  # noqa: E402
app.include_router(institutions_router, prefix="/v1")
app.include_router(courses_router, prefix="/v1")

# ── Learning Data Collection (Phase 16) ──────────────────────────────────────
from app.api.sessions import router as sessions_router  # noqa: E402
from app.api.quizzes import router as quizzes_router  # noqa: E402
from app.api.events import router as events_router  # noqa: E402
from app.api.resources import router as resources_router  # noqa: E402
app.include_router(sessions_router, prefix="/v1")
app.include_router(quizzes_router, prefix="/v1")
app.include_router(events_router, prefix="/v1")
app.include_router(resources_router, prefix="/v1")

# ── Retention Engine ──────────────────────────────────────────────────────────
from app.api.retention import router as retention_router  # noqa: E402
app.include_router(retention_router, prefix="/v1")

# ── Priority Engine ───────────────────────────────────────────────────────────
from app.api.priority import router as priority_router  # noqa: E402
app.include_router(priority_router, prefix="/v1")

# ── Scheduling Engine ─────────────────────────────────────────────────────────
from app.api.schedule import router as schedule_router  # noqa: E402
app.include_router(schedule_router, prefix="/v1")

# ── Recalibration Engine ──────────────────────────────────────────────────────
from app.api.recalibration import router as recalibration_router  # noqa: E402
app.include_router(recalibration_router, prefix="/v1")

# ── Memory State Management ───────────────────────────────────────────────────
from app.api.memory import router as memory_router  # noqa: E402
app.include_router(memory_router, prefix="/v1")

# ── Analytics Engine ──────────────────────────────────────────────────────────
from app.api.analytics import router as analytics_router  # noqa: E402
app.include_router(analytics_router, prefix="/v1")
