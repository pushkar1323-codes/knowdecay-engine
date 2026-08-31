"""
app/services/session_service.py
───────────────────────────────
Study session management business logic.
"""

import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.exceptions import NotFoundError
from app.models.study_session import StudySession

logger = logging.getLogger(__name__)


def create_session(db: Session, user_id: uuid.UUID, topic_id: uuid.UUID, duration_minutes: int, started_at: datetime | None = None, ended_at: datetime | None = None, active_minutes: int | None = None, idle_minutes: int | None = None, completion_status: str | None = None, device_type: str | None = None, platform: str | None = None, session_metadata: dict | None = None) -> StudySession:
    session = StudySession(
        user_id=user_id,
        topic_id=topic_id,
        duration_minutes=duration_minutes,
        started_at=started_at or func.now(),
        ended_at=ended_at,
        active_minutes=active_minutes,
        idle_minutes=idle_minutes,
        completion_status=completion_status,
        device_type=device_type,
        platform=platform,
        session_metadata=session_metadata
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Study session created | id=%s | user_id=%s", session.id, user_id)
    return session


def get_session_by_id(db: Session, session_id: uuid.UUID) -> StudySession:
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    if not session:
        raise NotFoundError("StudySession", str(session_id))
    return session


def list_user_sessions(db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 50, topic_id: uuid.UUID | None = None) -> tuple[list[StudySession], int]:
    query = db.query(StudySession).filter(StudySession.user_id == user_id)
    if topic_id is not None:
        query = query.filter(StudySession.topic_id == topic_id)
    
    total = query.count()
    sessions = query.order_by(StudySession.started_at.desc()).offset(skip).limit(limit).all()
    return sessions, total


def update_session(db: Session, session_id: uuid.UUID, **kwargs) -> StudySession:
    session = get_session_by_id(db, session_id)

    for key, value in kwargs.items():
        if hasattr(session, key):
            setattr(session, key, value)

    db.commit()
    db.refresh(session)
    logger.info("Study session updated | id=%s", session.id)
    return session


def get_session_stats(db: Session, user_id: uuid.UUID) -> dict:
    query = db.query(StudySession).filter(StudySession.user_id == user_id)
    
    total_sessions = query.count()
    
    # Calculate stats
    stats = db.query(
        func.sum(StudySession.duration_minutes).label('total_minutes'),
        func.avg(StudySession.duration_minutes).label('avg_minutes'),
        func.count().filter(StudySession.completion_status == 'completed').label('completed')
    ).filter(StudySession.user_id == user_id).first()
    
    # Active days
    active_days = db.query(func.date(StudySession.started_at)).filter(StudySession.user_id == user_id).distinct().count()
    
    return {
        "total_sessions": total_sessions,
        "total_study_minutes": int(stats.total_minutes or 0),
        "avg_session_minutes": float(stats.avg_minutes or 0.0),
        "completed_sessions": stats.completed or 0,
        "active_days": active_days
    }
