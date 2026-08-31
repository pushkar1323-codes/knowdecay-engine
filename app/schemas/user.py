"""
app/schemas/user.py
────────────────────
Pydantic schemas for user management endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Request body for user registration."""
    name: str = Field(..., min_length=1, max_length=255, description="Full name")
    email: str = Field(..., max_length=255, description="Email address", examples=["student@example.com"])
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")


class UserResponse(BaseModel):
    """Public user profile response."""
    id: uuid.UUID
    name: str
    email: str
    role: str
    institution_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Request body for updating user profile."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    institution_id: uuid.UUID | None = Field(default=None)


class UserAdminUpdate(BaseModel):
    """Admin-only user update — can change role and active status."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, description="New role (super_admin|institution_admin|teacher|student|api_client)")
    institution_id: uuid.UUID | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class UserListResponse(BaseModel):
    """Paginated list of users."""
    users: list[UserResponse]
    total: int
    page: int
    page_size: int
