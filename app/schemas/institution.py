"""
app/schemas/institution.py
────────────────────
Pydantic schemas for institution management endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class InstitutionCreate(BaseModel):
    name: str = Field(..., description="Name of the institution")
    slug: str = Field(..., max_length=100, description="Unique slug for the institution")
    description: str | None = Field(default=None, description="Description of the institution")


class InstitutionUpdate(BaseModel):
    name: str | None = Field(default=None, description="Name of the institution")
    slug: str | None = Field(default=None, max_length=100, description="Unique slug for the institution")
    description: str | None = Field(default=None, description="Description of the institution")
    is_active: bool | None = Field(default=None, description="Is institution active")


class InstitutionResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Institution ID")
    name: str = Field(..., description="Name of the institution")
    slug: str = Field(..., description="Unique slug for the institution")
    description: str | None = Field(default=None, description="Description of the institution")
    settings: dict = Field(..., description="Institution settings")
    is_active: bool = Field(..., description="Is institution active")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime | None = Field(default=None, description="Last update time")

    model_config = {"from_attributes": True}


class InstitutionListResponse(BaseModel):
    institutions: list[InstitutionResponse] = Field(..., description="List of institutions")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID = Field(..., description="User ID to add")
    role: str | None = Field(default=None, description="Role for assigning on add")


class MemberListResponse(BaseModel):
    members: list[UserResponse] = Field(..., description="List of members")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
