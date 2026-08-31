"""
app/core/logging.py
────────────────────
Structured logging configuration for the entire application.

Supports two output formats:
  - "text" (development): human-readable with timestamps
  - "json" (production): machine-parseable structured JSON

Call configure_logging() once at startup in main.py.
Use get_logger(__name__) in every module that needs logging.

Never logs secrets. The SecretFilter strips sensitive data from all
log records. Checks for value-adjacent patterns (e.g., ``password=``,
``bearer ``) rather than bare keywords to avoid over-redacting
legitimate log messages.
"""

import json
import logging
import sys
from datetime import datetime, timezone

from app.config import get_settings


# ── Secret Filter ─────────────────────────────────────────────────────────────

# Patterns that indicate actual secret VALUES being logged (not just the word)
_SECRET_VALUE_PATTERNS = (
    "password=",
    "password:",
    "secret_key=",
    "secret_key:",
    "api_key=",
    "api_key:",
    "authorization:",
    "authorization=",
    "database_url=",
    "database_url:",
    "token_hash=",
    "token_hash:",
    "access_token=",
    "access_token:",
    "refresh_token=",
    "refresh_token:",
    "bearer ",
)


class SecretFilter(logging.Filter):
    """
    Logging filter that redacts messages containing secret-like patterns.
    Applied automatically to all handlers.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage()).lower()
        for pattern in _SECRET_VALUE_PATTERNS:
            if pattern in msg:
                record.msg = self._redact(str(record.msg))
                record.args = None
                break
        return True

    @staticmethod
    def _redact(msg: str) -> str:
        """Replace the message with a redacted version."""
        return "[REDACTED — log message contained sensitive data]"


# ── JSON Formatter ────────────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """
    Outputs log records as single-line JSON objects.
    Includes request_id from contextvars when available.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Import here to avoid circular dependency at module load time
        from app.middleware.request_id import get_request_id

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request_id if in a request context
        rid = get_request_id()
        if rid:
            log_entry["request_id"] = rid

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ── Text Formatter ────────────────────────────────────────────────────────────

class TextFormatter(logging.Formatter):
    """
    Human-readable formatter for development.
    Includes request_id when available.
    """

    def format(self, record: logging.LogRecord) -> str:
        from app.middleware.request_id import get_request_id

        rid = get_request_id()
        rid_part = f" [rid={rid}]" if rid else ""

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        base = (
            f"{timestamp} | {record.levelname:<8s} | "
            f"{record.name:<40s} | {record.getMessage()}{rid_part}"
        )

        if record.exc_info and record.exc_info[0] is not None:
            base += "\n" + self.formatException(record.exc_info)

        return base


# ── Configuration ─────────────────────────────────────────────────────────────

def configure_logging() -> None:
    """
    Configure root logger with structured format.

    Format selection:
      - LOG_FORMAT=json  → JSONFormatter (production)
      - LOG_FORMAT=text  → TextFormatter (development, default)

    Suppresses noisy third-party loggers in non-development environments.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    log_format = getattr(settings, "log_format", "text").lower()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Select formatter
    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    # Apply secret filter
    handler.addFilter(SecretFilter())

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy loggers in non-development
    if settings.app_env != "development":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    logging.getLogger(__name__).info(
        "Logging configured | level=%s | format=%s | env=%s",
        settings.log_level.upper(),
        log_format,
        settings.app_env,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger for a module.

    Usage:
        logger = get_logger(__name__)
        logger.info("Memory state updated: retention=%.3f", retention)
    """
    return logging.getLogger(name)
