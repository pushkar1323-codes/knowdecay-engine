"""
app/api/users.py
─────────────────
User management REST endpoints (admin-only).

Endpoint summary:
  GET    /v1/users              — list users (admin)
  GET    /v1/users/{user_id}    — get user (admin)
  PATCH  /v1/users/{user_id}    — update user (admin)
  POST   /v1/users/{user_id}/activate   — activate user (super_admin)
  POST   /v1/users/{user_id}/deactivate — deactivate user (super_admin)
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import require_admin, require_institution_admin
from app.models.user import User
from app.schemas.user import (
    UserAdminUpdate,
    UserListResponse,
    UserResponse,
)
from app.services import user_service

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
)
def list_users(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=500, description="Items per page"),
    _admin: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """
    List all users with pagination.

    Requires **super_admin** or **institution_admin** role.
    """
    skip = (page - 1) * page_size
    users, total = user_service.list_users(db, skip=skip, limit=page_size)
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
def get_user(
    user_id: uuid.UUID,
    _admin: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """
    Retrieve a user profile by ID.

    Requires **super_admin** or **institution_admin** role.
    """
    user = user_service.get_user_by_id(db, user_id)
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
)
def update_user(
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    _admin: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """
    Update a user's profile, role, or active status.

    Requires **super_admin** or **institution_admin** role.
    """
    user = user_service.admin_update_user(
        db=db,
        user_id=user_id,
        name=payload.name,
        email=payload.email,
        role=payload.role,
        institution_id=payload.institution_id,
        is_active=payload.is_active,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Activate user",
)
def activate_user(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Activate a deactivated user account.

    Requires **super_admin** role.
    """
    user = user_service.activate_user(db, user_id)
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate user",
)
def deactivate_user(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Deactivate a user account. Deactivated users cannot log in.

    Requires **super_admin** role.
    """
    user = user_service.deactivate_user(db, user_id)
    return UserResponse.model_validate(user)
