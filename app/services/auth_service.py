"""
app/services/auth_service.py
─────────────────────────────
Authentication business logic.

Handles:
  - User credential verification
  - JWT access/refresh token creation
  - Refresh token rotation and revocation
  - Audit logging (never logs secrets)
"""

import logging
import uuid
from datetime import datetime, timezone

from jose import JWTError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.constants import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH
from app.core.exceptions import AuthenticationError, AccountDisabledError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_hash,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = logging.getLogger(__name__)


def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    Verify user credentials.

    Raises AuthenticationError on invalid email/password.
    Raises AccountDisabledError if user is deactivated.
    """
    user = db.query(User).filter(User.email == email).first()

    if not user or not user.password_hash:
        logger.warning("Login failed | email=%s | reason=user_not_found", email)
        raise AuthenticationError("Invalid email or password")

    if not verify_password(password, user.password_hash):
        logger.warning("Login failed | email=%s | reason=invalid_password", email)
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        logger.warning("Login failed | email=%s | reason=account_disabled", email)
        raise AccountDisabledError()

    logger.info("Login success | user=%s | email=%s", user.id, user.email)
    return user


def create_tokens(db: Session, user: User) -> dict:
    """
    Generate access + refresh token pair.
    Stores hashed refresh token in database.

    Returns dict with access_token, refresh_token, token_type, expires_in.
    """
    settings = get_settings()
    user_id_str = str(user.id)

    access_token = create_access_token(
        subject=user_id_str,
        role=user.role,
    )
    refresh_token = create_refresh_token(subject=user_id_str)

    # Decode refresh token to get expiry
    refresh_payload = decode_token(refresh_token)
    expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)

    # Store hashed refresh token
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=get_token_hash(refresh_token),
        expires_at=expires_at,
    )
    db.add(db_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


def refresh_access_token(db: Session, refresh_token_str: str) -> dict:
    """
    Validate a refresh token and issue a new token pair.

    Implements token rotation:
      1. Decode and verify the JWT
      2. Look up the hashed token in the DB
      3. Revoke the old refresh token
      4. Issue a new token pair

    Raises AuthenticationError on invalid/expired/revoked tokens.
    """
    # Decode JWT
    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        logger.warning("Token refresh failed | reason=invalid_jwt")
        raise AuthenticationError("Invalid or expired refresh token")

    if payload.get("type") != TOKEN_TYPE_REFRESH:
        logger.warning("Token refresh failed | reason=wrong_token_type")
        raise AuthenticationError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid refresh token")

    # Verify token exists in DB and is not revoked
    token_hash = get_token_hash(refresh_token_str)
    db_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,  # noqa: E712
        )
        .first()
    )

    if not db_token:
        logger.warning("Token refresh failed | reason=token_not_found_or_revoked")
        raise AuthenticationError("Refresh token is invalid or has been revoked")

    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        logger.warning("Token refresh failed | reason=token_expired")
        db_token.revoked = True
        db.commit()
        raise AuthenticationError("Refresh token has expired")

    # Revoke old token (rotation)
    db_token.revoked = True
    db.commit()

    # Load user
    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AccountDisabledError()

    logger.info("Token refreshed | user=%s", user.id)

    # Issue new pair
    return create_tokens(db, user)


def revoke_refresh_token(db: Session, refresh_token_str: str) -> None:
    """
    Revoke a single refresh token (logout from one device).
    """
    token_hash = get_token_hash(refresh_token_str)
    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )
    if db_token:
        db_token.revoked = True
        db.commit()
        logger.info("Token revoked | user_id=%s", db_token.user_id)


def revoke_all_user_tokens(db: Session, user_id: uuid.UUID) -> int:
    """
    Revoke ALL refresh tokens for a user (logout from all devices).
    Returns count of revoked tokens.
    """
    count = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,  # noqa: E712
        )
        .update({"revoked": True})
    )
    db.commit()
    logger.info("All tokens revoked | user=%s | count=%d", user_id, count)
    return count
