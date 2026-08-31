"""
app/deps_auth.py
─────────────────
FastAPI authentication and authorization dependencies.

Provides:
  - OAuth2 scheme for Swagger UI integration
  - get_current_user: decode JWT, verify user exists and is active
  - require_roles: factory for role-based access control dependencies
  - Pre-built role dependencies for common patterns

Usage in API routers:
    from app.deps_auth import get_current_user, require_roles
    from app.core.enums import UserRole

    @router.get("/protected")
    def protected_endpoint(user: User = Depends(get_current_user)):
        ...

    @router.get("/admin-only")
    def admin_endpoint(user: User = Depends(require_admin)):
        ...
"""

import logging
import uuid
from typing import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.constants import TOKEN_TYPE_ACCESS
from app.core.enums import UserRole
from app.core.exceptions import (
    AccountDisabledError,
    AuthenticationError,
    AuthorizationError,
)
from app.core.security import decode_token
from app.deps import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# ── OAuth2 scheme ─────────────────────────────────────────────────────────────
# auto_error=False: we handle missing tokens ourselves for better error messages.
# tokenUrl points to the login endpoint for Swagger UI integration.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)


# ── Core auth dependency ──────────────────────────────────────────────────────

def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the JWT access token, load the user from the database,
    and verify the account is active.

    Raises:
      - AuthenticationError: missing/invalid/expired token, user not found
      - AccountDisabledError: user account is deactivated
    """
    if token is None:
        raise AuthenticationError("Authentication required")

    # Decode JWT
    try:
        payload = decode_token(token)
    except JWTError:
        logger.warning("Invalid token | reason=jwt_decode_failed")
        raise AuthenticationError("Invalid or expired access token")

    # Verify token type
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        logger.warning("Invalid token | reason=wrong_token_type")
        raise AuthenticationError("Invalid token type")

    # Extract user ID
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Invalid token payload")

    # Load user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning("Invalid token | reason=user_not_found | sub=%s", user_id_str)
        raise AuthenticationError("User not found")

    # Verify account is active
    if not user.is_active:
        logger.warning("Unauthorized access | user=%s | reason=account_disabled", user.id)
        raise AccountDisabledError()

    return user


# ── Role-based access control ────────────────────────────────────────────────

def require_roles(*allowed_roles: UserRole) -> Callable:
    """
    Factory that returns a FastAPI dependency checking that
    the authenticated user has one of the allowed roles.

    Usage:
        @router.get("/admin")
        def admin_only(user: User = Depends(require_roles(UserRole.SUPER_ADMIN))):
            ...
    """
    allowed_values = {r.value for r in allowed_roles}

    def _role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_values:
            logger.warning(
                "Permission denied | user=%s | role=%s | required=%s",
                user.id,
                user.role,
                ",".join(sorted(allowed_values)),
            )
            raise AuthorizationError(
                f"Role '{user.role}' does not have permission for this action"
            )
        return user

    return _role_checker


# ── Pre-built role dependencies ───────────────────────────────────────────────
# Convenience dependencies for common role patterns.

require_admin = require_roles(UserRole.SUPER_ADMIN)

require_institution_admin = require_roles(
    UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN
)

require_teacher = require_roles(
    UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.TEACHER
)

require_any_authenticated = require_roles(
    UserRole.SUPER_ADMIN,
    UserRole.INSTITUTION_ADMIN,
    UserRole.TEACHER,
    UserRole.STUDENT,
    UserRole.API_CLIENT,
)
