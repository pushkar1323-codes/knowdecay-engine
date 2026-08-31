"""
app/api/resources.py
"""

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import get_current_user, require_teacher
from app.models.user import User
from app.schemas.resource import (
    ResourceCreate,
    ResourceUpdate,
    ResourceResponse,
    ResourceListResponse,
)
from app.services import resource_service

router = APIRouter(prefix="/resources", tags=["Learning Resources"])


@router.post("/", response_model=ResourceResponse, status_code=201, summary="Create resource")
def create_resource(
    payload: ResourceCreate,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """
    Create a new learning resource. Requires teacher or admin role.
    """
    resource = resource_service.create_resource(db, payload, user_id=user.id)
    return ResourceResponse.model_validate(resource)


@router.get("/", response_model=ResourceListResponse, summary="List resources")
def list_resources(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=1000),
    topic_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List learning resources.
    """
    resources, total = resource_service.list_resources(
        db, skip=skip, limit=limit, topic_id=topic_id, resource_type=resource_type
    )
    return ResourceListResponse(
        items=[ResourceResponse.model_validate(r) for r in resources],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{resource_id}", response_model=ResourceResponse, summary="Get resource")
def get_resource(
    resource_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific learning resource.
    """
    resource = resource_service.get_resource(db, resource_id)
    return ResourceResponse.model_validate(resource)


@router.patch("/{resource_id}", response_model=ResourceResponse, summary="Update resource")
def update_resource(
    resource_id: uuid.UUID,
    payload: ResourceUpdate,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """
    Update a learning resource. Requires teacher or admin role.
    """
    resource = resource_service.update_resource(db, resource_id, payload, user_id=user.id)
    return ResourceResponse.model_validate(resource)
