"""
app/schemas/curriculum.py
──────────────────────────
Pydantic v2 schemas for curriculum hierarchy provisioning.

Supports creation and response serialization for:
  Subject → Module → Chapter → Topic
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Create Schemas ────────────────────────────────────────────────────────────

class SubjectCreate(BaseModel):
    """Create a new subject."""

    name: str = Field(min_length=1, max_length=255)
    institution_id: uuid.UUID | None = Field(
        default=None, description="Optional institution FK"
    )
    course_id: uuid.UUID | None = Field(
        default=None, description="Optional course FK"
    )


class ModuleCreate(BaseModel):
    """Create a new module under a subject."""

    name: str = Field(min_length=1, max_length=255)
    subject_id: uuid.UUID


class ChapterCreate(BaseModel):
    """Create a new chapter under a module."""

    name: str = Field(min_length=1, max_length=255)
    module_id: uuid.UUID


class TopicCreate(BaseModel):
    """Create a new topic under a chapter."""

    name: str = Field(min_length=1, max_length=255)
    chapter_id: uuid.UUID
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    importance_weight: float = Field(default=1.0, ge=0.0)


# ── Response Schemas ──────────────────────────────────────────────────────────

class SubjectResponse(BaseModel):
    """Serialized subject."""

    id: uuid.UUID
    name: str
    institution_id: uuid.UUID | None
    course_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModuleResponse(BaseModel):
    """Serialized module."""

    id: uuid.UUID
    name: str
    subject_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ChapterResponse(BaseModel):
    """Serialized chapter."""

    id: uuid.UUID
    name: str
    module_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class TopicResponse(BaseModel):
    """Serialized topic."""

    id: uuid.UUID
    name: str
    chapter_id: uuid.UUID
    difficulty: float
    importance_weight: float
    created_at: datetime

    model_config = {"from_attributes": True}
