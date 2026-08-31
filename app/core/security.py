"""
app/core/security.py
─────────────────────
Core security utilities for authentication.

Provides:
  - Password hashing and verification (bcrypt — direct)
  - JWT access/refresh token creation and decoding (python-jose)
  - Refresh token hashing (SHA-256 for DB storage)

All functions are stateless and side-effect free.
Never log passwords, tokens, or secrets.
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt  # noqa: F401 — JWTError re-exported

from app.config import get_settings
from app.core.constants import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH

logger = logging.getLogger(__name__)

# ── Password hashing ─────────────────────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    pwd_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ── JWT tokens ────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    role: str = "student",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a JWT access token.

    Claims:
      - sub: user ID (UUID string)
      - role: user role
      - type: "access"
      - exp: expiration timestamp
      - iat: issued at timestamp
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": TOKEN_TYPE_ACCESS,
        "exp": expire,
        "iat": now,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """
    Create a JWT refresh token.

    Claims:
      - sub: user ID (UUID string)
      - type: "refresh"
      - exp: expiration timestamp
      - iat: issued at timestamp
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": subject,
        "type": TOKEN_TYPE_REFRESH,
        "exp": expire,
        "iat": now,
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Returns the decoded payload dict.
    Raises jose.JWTError on invalid/expired tokens.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


# ── Refresh token hashing ────────────────────────────────────────────────────

def get_token_hash(token: str) -> str:
    """
    Compute SHA-256 hash of a token for secure DB storage.
    Never store plaintext refresh tokens.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
