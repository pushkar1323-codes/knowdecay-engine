"""
app/services/resource_service.py
────────────────────────────────
Learning resource management business logic.
"""

import logging
import uuid
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundError
from app.models.learning_resource import LearningResource

logger = logging.getLogger(__name__)


def create_resource(db: Session, topic_id: uuid.UUID, title: str, resource_type: str, subtopic_id: uuid.UUID | None = None, url: str | None = None, resource_metadata: dict | None = None, created_by: uuid.UUID | None = None) -> LearningResource:
    resource = LearningResource(
        topic_id=topic_id,
        subtopic_id=subtopic_id,
        title=title,
        resource_type=resource_type,
        url=url,
        resource_metadata=resource_metadata,
        created_by=created_by,
        is_active=True
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    logger.info("Learning resource created | id=%s | title=%s", resource.id, resource.title)
    return resource


def get_resource_by_id(db: Session, resource_id: uuid.UUID) -> LearningResource:
    resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
    if not resource:
        raise NotFoundError("LearningResource", str(resource_id))
    return resource


def list_resources(db: Session, skip: int = 0, limit: int = 50, topic_id: uuid.UUID | None = None, resource_type: str | None = None) -> tuple[list[LearningResource], int]:
    query = db.query(LearningResource)
    if topic_id is not None:
        query = query.filter(LearningResource.topic_id == topic_id)
    if resource_type is not None:
        query = query.filter(LearningResource.resource_type == resource_type)
    
    total = query.count()
    resources = query.order_by(LearningResource.created_at.desc()).offset(skip).limit(limit).all()
    return resources, total


def update_resource(db: Session, resource_id: uuid.UUID, title: str | None = None, resource_type: str | None = None, url: str | None = None, resource_metadata: dict | None = None) -> LearningResource:
    resource = get_resource_by_id(db, resource_id)

    if title is not None:
        resource.title = title
    if resource_type is not None:
        resource.resource_type = resource_type
    if url is not None:
        resource.url = url
    if resource_metadata is not None:
        resource.resource_metadata = resource_metadata

    db.commit()
    db.refresh(resource)
    logger.info("Learning resource updated | id=%s", resource.id)
    return resource
