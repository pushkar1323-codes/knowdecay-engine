"""
app/services/institution_service.py
───────────────────────────────────
Institution management business logic.
"""

import logging
import uuid
from sqlalchemy.orm import Session
from app.core.exceptions import ConflictError, NotFoundError
from app.models.institution import Institution
from app.models.user import User

logger = logging.getLogger(__name__)


def create_institution(db: Session, name: str, slug: str, description: str | None = None) -> Institution:
    existing = db.query(Institution).filter(Institution.slug == slug).first()
    if existing:
        raise ConflictError(f"Institution with slug '{slug}' already exists")

    institution = Institution(
        name=name,
        slug=slug,
        description=description,
        is_active=True
    )
    db.add(institution)
    db.commit()
    db.refresh(institution)
    logger.info("Institution created | id=%s | slug=%s", institution.id, institution.slug)
    return institution


def get_institution_by_id(db: Session, institution_id: uuid.UUID) -> Institution:
    institution = db.query(Institution).filter(Institution.id == institution_id).first()
    if not institution:
        raise NotFoundError("Institution", str(institution_id))
    return institution


def get_institution_by_slug(db: Session, slug: str) -> Institution | None:
    return db.query(Institution).filter(Institution.slug == slug).first()


def list_institutions(db: Session, skip: int = 0, limit: int = 50, is_active: bool | None = None) -> tuple[list[Institution], int]:
    query = db.query(Institution)
    if is_active is not None:
        query = query.filter(Institution.is_active == is_active)
    
    total = query.count()
    institutions = query.order_by(Institution.created_at.desc()).offset(skip).limit(limit).all()
    return institutions, total


def update_institution(db: Session, institution_id: uuid.UUID, name: str | None = None, slug: str | None = None, description: str | None = None, is_active: bool | None = None) -> Institution:
    institution = get_institution_by_id(db, institution_id)

    if slug and slug != institution.slug:
        existing = db.query(Institution).filter(Institution.slug == slug).first()
        if existing:
            raise ConflictError(f"Institution with slug '{slug}' already exists")
        institution.slug = slug

    if name is not None:
        institution.name = name
    if description is not None:
        institution.description = description
    if is_active is not None:
        institution.is_active = is_active

    db.commit()
    db.refresh(institution)
    logger.info("Institution updated | id=%s", institution.id)
    return institution


def activate_institution(db: Session, institution_id: uuid.UUID) -> Institution:
    institution = get_institution_by_id(db, institution_id)
    institution.is_active = True
    db.commit()
    db.refresh(institution)
    logger.info("Institution activated | id=%s", institution.id)
    return institution


def deactivate_institution(db: Session, institution_id: uuid.UUID) -> Institution:
    institution = get_institution_by_id(db, institution_id)
    institution.is_active = False
    db.commit()
    db.refresh(institution)
    logger.info("Institution deactivated | id=%s", institution.id)
    return institution


def add_member(db: Session, institution_id: uuid.UUID, user_id: uuid.UUID, role: str | None = None) -> User:
    institution = get_institution_by_id(db, institution_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User", str(user_id))

    user.institution_id = institution.id
    if role is not None:
        user.role = role
    
    db.commit()
    db.refresh(user)
    logger.info("Member added to institution | user_id=%s | institution_id=%s", user.id, institution.id)
    return user


def remove_member(db: Session, institution_id: uuid.UUID, user_id: uuid.UUID) -> User:
    institution = get_institution_by_id(db, institution_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User", str(user_id))

    if user.institution_id != institution.id:
        raise ConflictError("User is not a member of this institution")

    user.institution_id = None
    db.commit()
    db.refresh(user)
    logger.info("Member removed from institution | user_id=%s | institution_id=%s", user.id, institution.id)
    return user


def list_members(db: Session, institution_id: uuid.UUID, skip: int = 0, limit: int = 50) -> tuple[list[User], int]:
    institution = get_institution_by_id(db, institution_id)
    query = db.query(User).filter(User.institution_id == institution.id)
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return users, total
