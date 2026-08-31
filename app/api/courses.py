"""
app/api/courses.py
────────────────────
Course management endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import get_current_user, require_teacher
from app.models.user import User
from app.schemas.course import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseListResponse,
    EnrollRequest,
    EnrollmentResponse,
)
from app.services import course_service

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("/", response_model=CourseResponse, status_code=201, summary="Create course")
def create_course(
    payload: CourseCreate,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Create a new course. Requires teacher or admin role."""
    course = course_service.create_course(
        db,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        institution_id=payload.institution_id,
        created_by=user.id,
    )
    return CourseResponse.model_validate(course)


@router.get("/", response_model=CourseListResponse, summary="List courses")
def list_courses(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=1000),
    institution_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List courses. Non-admin users with an institution only see their
    institution's courses unless a specific institution_id is provided.
    Super admins can list all courses.
    """
    # Scope by institution for non-admin users
    effective_institution_id = institution_id
    if user.role not in ("super_admin",) and user.institution_id and not institution_id:
        effective_institution_id = user.institution_id

    courses, total = course_service.list_courses(
        db, skip=skip, limit=limit, institution_id=effective_institution_id
    )
    return CourseListResponse(
        courses=[CourseResponse.model_validate(c) for c in courses],
        total=total,
        page=skip // limit if limit else 0,
        page_size=limit,
    )


@router.get("/{course_id}", response_model=CourseResponse, summary="Get course")
def get_course(
    course_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a course by ID."""
    course = course_service.get_course_by_id(db, course_id)
    return CourseResponse.model_validate(course)


@router.patch("/{course_id}", response_model=CourseResponse, summary="Update course")
def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Update a course. Requires teacher or admin role."""
    update_data = payload.model_dump(exclude_unset=True)
    course = course_service.update_course(db, course_id, **update_data)
    return CourseResponse.model_validate(course)


@router.post("/{course_id}/enroll", response_model=EnrollmentResponse, summary="Enroll current user")
def enroll_course(
    course_id: uuid.UUID,
    payload: EnrollRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enroll the current user in a course."""
    role = payload.role if payload else "student"
    enrollment = course_service.enroll_user(db, course_id, user.id, role=role)
    return EnrollmentResponse.model_validate(enrollment)


@router.delete("/{course_id}/enroll", summary="Unenroll current user")
def unenroll_course(
    course_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unenroll the current user from a course."""
    course_service.unenroll_user(db, course_id, user.id)
    return {"message": "Unenrolled"}


@router.get("/{course_id}/students", response_model=list[EnrollmentResponse], summary="List enrolled students")
def list_enrolled_students(
    course_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=1000),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """List enrolled students for a course. Requires teacher or admin role."""
    enrollments, _total = course_service.list_enrolled_users(
        db, course_id, skip=skip, limit=limit
    )
    return [EnrollmentResponse.model_validate(e) for e in enrollments]
