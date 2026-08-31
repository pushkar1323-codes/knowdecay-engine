"""
app/schemas/course.py
────────────────────
Pydantic schemas for course management endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    name: str = Field(..., description="Course name")
    code: str | None = Field(default=None, description="Course code")
    description: str | None = Field(default=None, description="Course description")
    institution_id: uuid.UUID | None = Field(default=None, description="Institution ID")


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, description="Course name")
    code: str | None = Field(default=None, description="Course code")
    description: str | None = Field(default=None, description="Course description")
    is_active: bool | None = Field(default=None, description="Is course active")


class CourseResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Course ID")
    institution_id: uuid.UUID | None = Field(default=None, description="Institution ID")
    name: str = Field(..., description="Course name")
    code: str | None = Field(default=None, description="Course code")
    description: str | None = Field(default=None, description="Course description")
    is_active: bool = Field(..., description="Is course active")
    created_by: uuid.UUID | None = Field(default=None, description="ID of creator")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime | None = Field(default=None, description="Last update time")

    model_config = {"from_attributes": True}


class CourseListResponse(BaseModel):
    courses: list[CourseResponse] = Field(..., description="List of courses")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class EnrollRequest(BaseModel):
    role: str = Field(default="student", description="Role in course")


class EnrollmentResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Enrollment ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    course_id: uuid.UUID = Field(..., description="Course ID")
    role: str = Field(..., description="Role in course")
    enrolled_at: datetime = Field(..., description="Enrollment time")
    is_active: bool = Field(..., description="Is enrollment active")

    model_config = {"from_attributes": True}
