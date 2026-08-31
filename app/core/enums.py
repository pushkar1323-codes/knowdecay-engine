"""
app/core/enums.py
──────────────────
Shared enumerations used across the KnowDecay Engine.
"""

from enum import Enum


class Environment(str, Enum):
    """Application environment."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ApiVersion(str, Enum):
    """Supported API versions."""
    V1 = "v1"


class UserRole(str, Enum):
    """User roles for Role-Based Access Control (Phase 13)."""
    SUPER_ADMIN = "super_admin"
    INSTITUTION_ADMIN = "institution_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    API_CLIENT = "api_client"
