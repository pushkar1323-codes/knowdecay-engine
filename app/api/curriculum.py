"""
app/api/curriculum.py
──────────────────────
REST endpoints for curriculum hierarchy provisioning.

These endpoints allow the KnowDecay Platform (or other trusted services)
to create the knowledge hierarchy records required by memory/retention
operations.

Endpoint summary:
  POST /v1/curriculum/subjects   — create a subject
  POST /v1/curriculum/modules    — create a module under a subject
  POST /v1/curriculum/chapters   — create a chapter under a module
  POST /v1/curriculum/topics     — create a topic under a chapter

Authorization:
  Requires SUPER_ADMIN, INSTITUTION_ADMIN, or API_CLIENT role.
  API_CLIENT is the trusted server-to-server integration role used by the
  Platform backend. API_CLIENT credentials must never be exposed to browsers
  or end users.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import require_provisioner
from app.models.user import User
from app.schemas.curriculum import (
    ChapterCreate,
    ChapterResponse,
    ModuleCreate,
    ModuleResponse,
    SubjectCreate,
    SubjectResponse,
    TopicCreate,
    TopicResponse,
)
from app.services import curriculum_service

router = APIRouter(prefix="/curriculum", tags=["Curriculum Provisioning"])


@router.post(
    "/subjects",
    response_model=SubjectResponse,
    status_code=201,
    summary="Create a subject",
)
def create_subject(
    payload: SubjectCreate,
    _user: User = Depends(require_provisioner),
    db: Session = Depends(get_db),
):
    """
    Create a new subject in the knowledge hierarchy.

    Optionally associate with an institution and/or course.
    Returns 404 if institution_id or course_id is provided but does not exist.
    """
    subject = curriculum_service.create_subject(db, payload)
    db.commit()
    db.refresh(subject)
    return SubjectResponse.model_validate(subject)


@router.post(
    "/modules",
    response_model=ModuleResponse,
    status_code=201,
    summary="Create a module under a subject",
)
def create_module(
    payload: ModuleCreate,
    _user: User = Depends(require_provisioner),
    db: Session = Depends(get_db),
):
    """
    Create a new module under an existing subject.

    Returns 404 if subject_id does not exist.
    """
    module = curriculum_service.create_module(db, payload)
    db.commit()
    db.refresh(module)
    return ModuleResponse.model_validate(module)


@router.post(
    "/chapters",
    response_model=ChapterResponse,
    status_code=201,
    summary="Create a chapter under a module",
)
def create_chapter(
    payload: ChapterCreate,
    _user: User = Depends(require_provisioner),
    db: Session = Depends(get_db),
):
    """
    Create a new chapter under an existing module.

    Returns 404 if module_id does not exist.
    """
    chapter = curriculum_service.create_chapter(db, payload)
    db.commit()
    db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)


@router.post(
    "/topics",
    response_model=TopicResponse,
    status_code=201,
    summary="Create a topic under a chapter",
)
def create_topic(
    payload: TopicCreate,
    _user: User = Depends(require_provisioner),
    db: Session = Depends(get_db),
):
    """
    Create a new topic under an existing chapter.

    Topic carries the engine-critical fields:
    - **difficulty** (0.0–1.0, default 0.5) — affects decay rate and priority
    - **importance_weight** (≥0.0, default 1.0) — scales urgency under exam pressure

    Returns 404 if chapter_id does not exist.
    """
    topic = curriculum_service.create_topic(db, payload)
    db.commit()
    db.refresh(topic)
    return TopicResponse.model_validate(topic)
