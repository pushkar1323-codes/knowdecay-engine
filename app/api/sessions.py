"""
app/api/sessions.py
─────────────────────
Learning session recording and querying endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import get_current_user
from app.models.user import User
from app.schemas.session import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionListResponse,
    SessionStatsResponse,
)
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["Learning Sessions"])


@router.post("/", response_model=SessionResponse, status_code=201, summary="Create session")
def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new learning session for the current user."""
    session_obj = session_service.create_session(
        db,
        user_id=user.id,
        topic_id=payload.topic_id,
        duration_minutes=payload.duration_minutes,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        active_minutes=payload.active_minutes,
        idle_minutes=payload.idle_minutes,
        completion_status=payload.completion_status,
        device_type=payload.device_type,
        platform=payload.platform,
        session_metadata=payload.session_metadata,
    )
    return SessionResponse.model_validate(session_obj)


@router.get("/", response_model=SessionListResponse, summary="List sessions")
def list_sessions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=1000),
    topic_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List learning sessions for the current user."""
    sessions, total = session_service.list_user_sessions(
        db, user_id=user.id, skip=skip, limit=limit, topic_id=topic_id
    )
    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
        page=skip // limit if limit else 0,
        page_size=limit,
    )


@router.get("/stats", response_model=SessionStatsResponse, summary="Get session stats")
def get_session_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get learning session statistics for the current user."""
    stats = session_service.get_session_stats(db, user_id=user.id)
    return SessionStatsResponse(**stats)


@router.get("/{session_id}", response_model=SessionResponse, summary="Get session")
def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific learning session."""
    session_obj = session_service.get_session_by_id(db, session_id)
    return SessionResponse.model_validate(session_obj)


@router.patch("/{session_id}", response_model=SessionResponse, summary="Update session")
def update_session(
    session_id: uuid.UUID,
    payload: SessionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a learning session (mark completed, add active_minutes)."""
    update_data = payload.model_dump(exclude_unset=True)
    session_obj = session_service.update_session(db, session_id, **update_data)
    return SessionResponse.model_validate(session_obj)
