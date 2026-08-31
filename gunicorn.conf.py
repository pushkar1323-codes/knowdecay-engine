"""
gunicorn.conf.py
─────────────────
Gunicorn configuration for KnowDecay Engine production deployment.

Architecture: Gunicorn (process manager) → Uvicorn (ASGI workers) → FastAPI

Gunicorn manages worker processes (restarts on crash, graceful shutdown)
while Uvicorn handles the async ASGI protocol that FastAPI requires.

Worker count defaults to 1 for safe initial deployment.
Recommended scaling formula: (2 × CPU cores) + 1
Set via WORKERS environment variable.
"""

import os

# ── Binding ───────────────────────────────────────────────────────────────────
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8000')}"

# ── Workers ───────────────────────────────────────────────────────────────────
# Default: 1 worker (safe for initial deployment, works on Render/Railway free tier)
# Recommended formula for scaling: (2 × CPU cores) + 1
# Override: set WORKERS=N in environment
workers = int(os.getenv("WORKERS", "1"))

# ── Worker Class ──────────────────────────────────────────────────────────────
# UvicornWorker is required for FastAPI's async/ASGI support.
# Do NOT change to sync workers — FastAPI endpoints are async-compatible.
worker_class = "uvicorn.workers.UvicornWorker"

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout = int(os.getenv("WORKER_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("KEEPALIVE", "5"))

# ── Server Mechanics ──────────────────────────────────────────────────────────
preload_app = False              # Each worker loads its own app instance
max_requests = int(os.getenv("MAX_REQUESTS", "0"))        # 0 = disabled
max_requests_jitter = int(os.getenv("MAX_REQUESTS_JITTER", "0"))

# ── Logging ───────────────────────────────────────────────────────────────────
# Gunicorn access/error logs go to stdout/stderr for container log collection
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# ── Process Naming ────────────────────────────────────────────────────────────
proc_name = "knowdecay-engine"
