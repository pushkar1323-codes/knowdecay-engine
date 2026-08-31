"""
app/schemas/session.py
────────────────────
Pydantic schemas for session endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    topic_id: uuid.UUID = Field(..., description="Topic ID")
    duration_minutes: int = Field(..., description="Session duration in minutes")
    started_at: datetime | None = Field(default=None, description="Start time")
    ended_at: datetime | None = Field(default=None, description="End time")
    active_minutes: int | None = Field(default=None, description="Active time in minutes")
    idle_minutes: int | None = Field(default=None, description="Idle time in minutes")
    completion_status: str | None = Field(default=None, description="Status of completion")
    device_type: str | None = Field(default=None, description="Type of device used")
    platform: str | None = Field(default=None, description="Platform used")
    session_metadata: dict | None = Field(default=None, description="Additional session metadata")


class SessionUpdate(BaseModel):
    ended_at: datetime | None = Field(default=None, description="End time")
    duration_minutes: int | None = Field(default=None, description="Session duration in minutes")
    active_minutes: int | None = Field(default=None, description="Active time in minutes")
    idle_minutes: int | None = Field(default=None, description="Idle time in minutes")
    completion_status: str | None = Field(default=None, description="Status of completion")
    session_metadata: dict | None = Field(default=None, description="Additional session metadata")


class SessionResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Session ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    topic_id: uuid.UUID = Field(..., description="Topic ID")
    duration_minutes: int = Field(..., description="Session duration in minutes")
    started_at: datetime | None = Field(default=None, description="Start time")
    ended_at: datetime | None = Field(default=None, description="End time")
    active_minutes: int | None = Field(default=None, description="Active time in minutes")
    idle_minutes: int | None = Field(default=None, description="Idle time in minutes")
    completion_status: str | None = Field(default=None, description="Status of completion")
    device_type: str | None = Field(default=None, description="Type of device used")
    platform: str | None = Field(default=None, description="Platform used")
    session_metadata: dict | None = Field(default=None, description="Additional session metadata")
    created_at: datetime = Field(..., description="Creation time")

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse] = Field(..., description="List of sessions")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class SessionStatsResponse(BaseModel):
    total_sessions: int = Field(..., description="Total number of sessions")
    total_study_minutes: int = Field(..., description="Total study time in minutes")
    avg_session_minutes: float = Field(..., description="Average session length")
    completed_sessions: int = Field(..., description="Number of completed sessions")
    active_days: int = Field(..., description="Number of active days")
