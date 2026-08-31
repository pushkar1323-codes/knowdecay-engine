"""
app/api/auth.py
────────────────
Authentication REST endpoints.

Endpoint summary:
  POST /v1/auth/register       — register new user (student role)
  POST /v1/auth/login          — login → access + refresh tokens
  POST /v1/auth/refresh        — refresh access token (token rotation)
  POST /v1/auth/logout         — revoke refresh token
  GET  /v1/auth/me             — get current authenticated user
  POST /v1/auth/change-password — change own password
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AuthenticationError, InputValidationError
from app.deps import get_db
from app.deps_auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.user import UserCreate, UserResponse
from app.services import auth_service, user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register a new user",
)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.

    - Public registration always creates a **STUDENT** role.
    - Any role supplied in the request body is ignored.
    - Returns the created user profile.
    - Returns 409 if email already exists.

    Registration can be disabled via `REGISTRATION_ENABLED=false`.
    """
    settings = get_settings()
    if not settings.registration_enabled:
        raise InputValidationError("Public registration is currently disabled")

    user = user_service.register_user(
        db=db,
        name=payload.name,
        email=payload.email,
        password=payload.password,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate with email/password and receive JWT tokens.

    Returns:
    - **access_token** — short-lived JWT for API access
    - **refresh_token** — long-lived token for refreshing access tokens
    - **expires_in** — access token TTL in seconds

    Use the access_token in the Authorization header:
    `Authorization: Bearer <access_token>`
    """
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    return auth_service.create_tokens(db, user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
def refresh_token(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new token pair.

    Implements **token rotation**: the old refresh token is revoked
    and a new pair is issued. This limits the damage if a refresh
    token is compromised.
    """
    return auth_service.refresh_access_token(db, payload.refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (revoke refresh token)",
)
def logout(
    payload: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revoke the provided refresh token (logout from one device).

    Requires a valid access token in the Authorization header.
    """
    auth_service.revoke_refresh_token(db, payload.refresh_token)
    logger.info("Logout | user=%s", current_user.id)
    return MessageResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Return the profile of the currently authenticated user.

    Requires a valid access token in the Authorization header.
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change own password",
)
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change the authenticated user's password.

    Requires the current password for verification.
    """
    user_service.change_password(
        db=db,
        user_id=current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(message="Password changed successfully")
