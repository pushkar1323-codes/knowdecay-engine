"""
app/services/user_service.py
─────────────────────────────
User management business logic.

Handles:
  - User registration (public — always creates STUDENT role)
  - User CRUD operations
  - Password management
  - Account activation/deactivation
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.core.exceptions import (
    ConflictError,
    InputValidationError,
    NotFoundError,
)
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services import auth_service

logger = logging.getLogger(__name__)


def register_user(
    db: Session,
    name: str,
    email: str,
    password: str,
) -> User:
    """
    Register a new user with STUDENT role.

    Public registration ALWAYS creates a STUDENT account regardless of
    any role supplied by the client. Privileged roles can only be
    assigned by administrators via admin_create_user or update endpoints.

    Raises ConflictError if email already exists.
    """
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ConflictError(f"User with email '{email}' already exists")

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("User registered | user=%s | email=%s | role=student", user.id, user.email)
    return user


def admin_create_user(
    db: Session,
    name: str,
    email: str,
    password: str,
    role: str = UserRole.STUDENT.value,
    institution_id: str | None = None,
) -> User:
    """
    Admin-only user creation with explicit role assignment.

    Validates that the role is a valid UserRole.
    Raises ConflictError if email already exists.
    """
    # Validate role
    valid_roles = {r.value for r in UserRole}
    if role not in valid_roles:
        raise InputValidationError(
            f"Invalid role '{role}'. Must be one of: {', '.join(sorted(valid_roles))}"
        )

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ConflictError(f"User with email '{email}' already exists")

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        institution_id=institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("User created by admin | user=%s | email=%s | role=%s", user.id, user.email, role)
    return user


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User:
    """Fetch a user by ID. Raises NotFoundError if not found."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User", str(user_id))
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email. Returns None if not found."""
    return db.query(User).filter(User.email == email).first()


def update_user_profile(
    db: Session,
    user_id: uuid.UUID,
    name: str | None = None,
    email: str | None = None,
    institution_id: str | None = None,
) -> User:
    """Update user profile fields. Raises NotFoundError if user doesn't exist."""
    user = get_user_by_id(db, user_id)

    if email and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ConflictError(f"Email '{email}' is already in use")
        user.email = email

    if name is not None:
        user.name = name
    if institution_id is not None:
        user.institution_id = institution_id

    db.commit()
    db.refresh(user)
    logger.info("User updated | user=%s", user.id)
    return user


def admin_update_user(
    db: Session,
    user_id: uuid.UUID,
    name: str | None = None,
    email: str | None = None,
    role: str | None = None,
    institution_id: str | None = None,
    is_active: bool | None = None,
) -> User:
    """Admin-only user update — can change role and active status."""
    user = get_user_by_id(db, user_id)

    if email and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ConflictError(f"Email '{email}' is already in use")
        user.email = email

    if name is not None:
        user.name = name
    if role is not None:
        valid_roles = {r.value for r in UserRole}
        if role not in valid_roles:
            raise InputValidationError(
                f"Invalid role '{role}'. Must be one of: {', '.join(sorted(valid_roles))}"
            )
        user.role = role
    if institution_id is not None:
        user.institution_id = institution_id
    if is_active is not None:
        user.is_active = is_active

    db.commit()
    db.refresh(user)
    logger.info("User admin-updated | user=%s | role=%s | active=%s", user.id, user.role, user.is_active)
    return user


def change_password(
    db: Session,
    user_id: uuid.UUID,
    current_password: str,
    new_password: str,
) -> None:
    """
    Change a user's password.
    Verifies current password before updating.
    """
    user = get_user_by_id(db, user_id)

    if not user.password_hash or not verify_password(current_password, user.password_hash):
        raise InputValidationError("Current password is incorrect")

    user.password_hash = hash_password(new_password)
    db.commit()

    # Security: revoke all refresh tokens after password change
    auth_service.revoke_all_user_tokens(db, user_id)

    logger.info("Password changed | user=%s", user.id)


def activate_user(db: Session, user_id: uuid.UUID) -> User:
    """Activate a deactivated user account."""
    user = get_user_by_id(db, user_id)
    user.is_active = True
    db.commit()
    db.refresh(user)
    logger.info("User activated | user=%s", user.id)
    return user


def deactivate_user(db: Session, user_id: uuid.UUID) -> User:
    """Deactivate a user account."""
    user = get_user_by_id(db, user_id)
    user.is_active = False
    db.commit()
    db.refresh(user)
    logger.info("User deactivated | user=%s", user.id)
    return user


def list_users(
    db: Session,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[User], int]:
    """List users with pagination. Returns (users, total_count)."""
    total = db.query(User).count()
    users = db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return users, total
