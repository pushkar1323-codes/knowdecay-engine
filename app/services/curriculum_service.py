"""
app/services/curriculum_service.py
───────────────────────────────────
Service layer for curriculum hierarchy provisioning.

Each create function validates that the parent entity exists before
inserting the child. Raises NotFoundError on invalid parent IDs.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.hierarchy import Chapter, Module, Subject, Topic
from app.models.institution import Institution
from app.models.course import Course
from app.schemas.curriculum import (
    ChapterCreate,
    ModuleCreate,
    SubjectCreate,
    TopicCreate,
)

logger = logging.getLogger(__name__)


# ── Subject ───────────────────────────────────────────────────────────────────

def create_subject(db: Session, payload: SubjectCreate) -> Subject:
    """
    Create a new subject.

    Validates institution_id and course_id if provided.
    """
    if payload.institution_id is not None:
        inst = db.query(Institution).filter(Institution.id == payload.institution_id).first()
        if inst is None:
            raise NotFoundError("Institution", str(payload.institution_id))

    if payload.course_id is not None:
        course = db.query(Course).filter(Course.id == payload.course_id).first()
        if course is None:
            raise NotFoundError("Course", str(payload.course_id))

    subject = Subject(
        name=payload.name,
        institution_id=payload.institution_id,
        course_id=payload.course_id,
    )
    db.add(subject)
    db.flush()
    logger.info("Created subject | id=%s name=%s", subject.id, subject.name)
    return subject


# ── Module ────────────────────────────────────────────────────────────────────

def create_module(db: Session, payload: ModuleCreate) -> Module:
    """
    Create a new module under a subject.

    Raises NotFoundError if subject_id does not exist.
    """
    parent = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if parent is None:
        raise NotFoundError("Subject", str(payload.subject_id))

    module = Module(
        name=payload.name,
        subject_id=payload.subject_id,
    )
    db.add(module)
    db.flush()
    logger.info("Created module | id=%s name=%s subject=%s", module.id, module.name, payload.subject_id)
    return module


# ── Chapter ───────────────────────────────────────────────────────────────────

def create_chapter(db: Session, payload: ChapterCreate) -> Chapter:
    """
    Create a new chapter under a module.

    Raises NotFoundError if module_id does not exist.
    """
    parent = db.query(Module).filter(Module.id == payload.module_id).first()
    if parent is None:
        raise NotFoundError("Module", str(payload.module_id))

    chapter = Chapter(
        name=payload.name,
        module_id=payload.module_id,
    )
    db.add(chapter)
    db.flush()
    logger.info("Created chapter | id=%s name=%s module=%s", chapter.id, chapter.name, payload.module_id)
    return chapter


# ── Topic ─────────────────────────────────────────────────────────────────────

def create_topic(db: Session, payload: TopicCreate) -> Topic:
    """
    Create a new topic under a chapter.

    Raises NotFoundError if chapter_id does not exist.
    Preserves engine-critical fields: difficulty, importance_weight.
    """
    parent = db.query(Chapter).filter(Chapter.id == payload.chapter_id).first()
    if parent is None:
        raise NotFoundError("Chapter", str(payload.chapter_id))

    topic = Topic(
        name=payload.name,
        chapter_id=payload.chapter_id,
        difficulty=payload.difficulty,
        importance_weight=payload.importance_weight,
    )
    db.add(topic)
    db.flush()
    logger.info(
        "Created topic | id=%s name=%s chapter=%s difficulty=%.2f weight=%.2f",
        topic.id, topic.name, payload.chapter_id, topic.difficulty, topic.importance_weight,
    )
    return topic
