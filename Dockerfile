# ── Stage 1: Builder ──────────────────────────────────────────────────────────
# Install dependencies into an isolated virtual environment.
# Build tools (gcc, libpq-dev) stay in this stage only.
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
# Minimal image with only runtime dependencies. Runs as non-root user.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Runtime-only system dependencies (no compiler toolchain)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r knowdecay --gid=1001 \
    && useradd -r -g knowdecay --uid=1001 --home-dir=/app --shell=/bin/bash knowdecay

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY --chown=knowdecay:knowdecay alembic/ alembic/
COPY --chown=knowdecay:knowdecay alembic.ini .
COPY --chown=knowdecay:knowdecay app/ app/
COPY --chown=knowdecay:knowdecay scripts/ scripts/
COPY --chown=knowdecay:knowdecay gunicorn.conf.py .

# Make entrypoint executable
RUN chmod +x scripts/entrypoint.sh

USER knowdecay

EXPOSE 8000

# Docker-native liveness monitoring
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Production default: Gunicorn with Uvicorn ASGI workers
CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
