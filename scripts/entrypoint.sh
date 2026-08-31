#!/bin/bash
set -e

# ──────────────────────────────────────────────────────────────────────────────
# KnowDecay Engine — Container Entrypoint
# ──────────────────────────────────────────────────────────────────────────────
#
# 1. Wait for PostgreSQL to accept connections
# 2. Optionally run Alembic migrations (development/testing only)
# 3. Start the application server (via CMD)
#
# Migration safety:
#   AUTO_MIGRATE is disabled by default and must NOT be enabled in production
#   with multiple replicas. Use the dedicated migration service instead:
#     docker compose --profile tools run --rm migrate
# ──────────────────────────────────────────────────────────────────────────────

echo "══════════════════════════════════════════════"
echo "  KnowDecay Engine — Container Entrypoint"
echo "══════════════════════════════════════════════"

# ── Wait for PostgreSQL ──────────────────────────────────────────────────────
if [ -n "$DATABASE_URL" ]; then
    # Extract host:port from postgresql://user:pass@HOST:PORT/dbname
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*@[^:]+:([0-9]+).*|\1|')
    DB_PORT=${DB_PORT:-5432}

    echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

    MAX_RETRIES=${DB_WAIT_RETRIES:-30}
    RETRY=0
    while [ $RETRY -lt $MAX_RETRIES ]; do
        if python -c "
import socket
try:
    s = socket.create_connection(('${DB_HOST}', ${DB_PORT}), timeout=2)
    s.close()
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; then
            echo "✓ PostgreSQL is accepting connections"
            break
        fi
        RETRY=$((RETRY + 1))
        echo "  Waiting... ($RETRY/$MAX_RETRIES)"
        sleep 2
    done

    if [ $RETRY -eq $MAX_RETRIES ]; then
        echo "✗ PostgreSQL not available after $MAX_RETRIES attempts — aborting"
        exit 1
    fi
fi

# ── Auto-migrate (development/testing ONLY) ──────────────────────────────────
# WARNING: Do NOT enable in production with multiple replicas.
# Concurrent migrations from multiple instances can corrupt the database.
# Use the dedicated migration service: docker compose --profile tools run --rm migrate
if [ "${AUTO_MIGRATE:-false}" = "true" ]; then
    echo "Running database migrations (AUTO_MIGRATE=true)..."
    alembic upgrade head
    echo "✓ Migrations complete"
fi

# ── Start application server ─────────────────────────────────────────────────
echo "Starting KnowDecay Engine..."
exec "$@"
