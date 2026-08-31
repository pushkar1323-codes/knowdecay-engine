"""
app/schemas/resource.py
────────────────────
Pydantic schemas for learning resources endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ResourceCreate(BaseModel):
    topic_id: uuid.UUID = Field(..., description="Topic ID")
    subtopic_id: uuid.UUID | None = Field(default=None, description="Subtopic ID")
    title: str = Field(..., description="Resource title")
    resource_type: str = Field(..., description="Type of resource")
    url: str | None = Field(default=None, description="URL to the resource")
    resource_metadata: dict = Field(default_factory=dict, description="Additional resource metadata")


class ResourceUpdate(BaseModel):
    title: str | None = Field(default=None, description="Resource title")
    resource_type: str | None = Field(default=None, description="Type of resource")
    url: str | None = Field(default=None, description="URL to the resource")
    resource_metadata: dict | None = Field(default=None, description="Additional resource metadata")


class ResourceResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Resource ID")
    topic_id: uuid.UUID = Field(..., description="Topic ID")
    subtopic_id: uuid.UUID | None = Field(default=None, description="Subtopic ID")
    title: str = Field(..., description="Resource title")
    resource_type: str = Field(..., description="Type of resource")
    url: str | None = Field(default=None, description="URL to the resource")
    resource_metadata: dict = Field(..., description="Additional resource metadata")
    created_by: uuid.UUID = Field(..., description="ID of creator")
    created_at: datetime = Field(..., description="Creation time")

    model_config = {"from_attributes": True}


class ResourceListResponse(BaseModel):
    resources: list[ResourceResponse] = Field(..., description="List of resources")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
