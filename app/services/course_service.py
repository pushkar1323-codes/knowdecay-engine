"""
app/services/course_service.py
──────────────────────────────
Course management business logic.
"""

import logging
import uuid
from sqlalchemy.orm import Session
from app.core.exceptions import ConflictError, NotFoundError
from app.models.course import Course
from app.models.course_enrollment import CourseEnrollment

logger = logging.getLogger(__name__)


def create_course(db: Session, name: str, code: str | None = None, description: str | None = None, institution_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None) -> Course:
    course = Course(
        name=name,
        code=code,
        description=description,
        institution_id=institution_id,
        created_by=created_by,
        is_active=True
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    logger.info("Course created | id=%s | name=%s", course.id, course.name)
    return course


def get_course_by_id(db: Session, course_id: uuid.UUID) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise NotFoundError("Course", str(course_id))
    return course


def list_courses(db: Session, skip: int = 0, limit: int = 50, institution_id: uuid.UUID | None = None, is_active: bool | None = None) -> tuple[list[Course], int]:
    query = db.query(Course)
    if institution_id is not None:
        query = query.filter(Course.institution_id == institution_id)
    if is_active is not None:
        query = query.filter(Course.is_active == is_active)
    
    total = query.count()
    courses = query.order_by(Course.created_at.desc()).offset(skip).limit(limit).all()
    return courses, total


def update_course(db: Session, course_id: uuid.UUID, name: str | None = None, code: str | None = None, description: str | None = None, is_active: bool | None = None) -> Course:
    course = get_course_by_id(db, course_id)

    if name is not None:
        course.name = name
    if code is not None:
        course.code = code
    if description is not None:
        course.description = description
    if is_active is not None:
        course.is_active = is_active

    db.commit()
    db.refresh(course)
    logger.info("Course updated | id=%s", course.id)
    return course


def enroll_user(db: Session, course_id: uuid.UUID, user_id: uuid.UUID, role: str = 'student') -> CourseEnrollment:
    course = get_course_by_id(db, course_id)
    
    existing = db.query(CourseEnrollment).filter(CourseEnrollment.course_id == course_id, CourseEnrollment.user_id == user_id).first()
    if existing:
        raise ConflictError(f"User {user_id} is already enrolled in course {course_id}")

    enrollment = CourseEnrollment(
        course_id=course_id,
        user_id=user_id,
        role=role,
        is_active=True
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    logger.info("User enrolled in course | user_id=%s | course_id=%s", user_id, course_id)
    return enrollment


def unenroll_user(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> None:
    enrollment = db.query(CourseEnrollment).filter(CourseEnrollment.course_id == course_id, CourseEnrollment.user_id == user_id).first()
    if not enrollment:
        raise NotFoundError("CourseEnrollment", f"user={user_id}, course={course_id}")

    db.delete(enrollment)
    db.commit()
    logger.info("User unenrolled from course | user_id=%s | course_id=%s", user_id, course_id)


def list_enrolled_users(db: Session, course_id: uuid.UUID, skip: int = 0, limit: int = 50) -> tuple[list[CourseEnrollment], int]:
    query = db.query(CourseEnrollment).filter(CourseEnrollment.course_id == course_id)
    total = query.count()
    enrollments = query.order_by(CourseEnrollment.enrolled_at.desc()).offset(skip).limit(limit).all()
    return enrollments, total
