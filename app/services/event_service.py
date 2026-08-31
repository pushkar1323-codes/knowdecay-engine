"""
app/services/event_service.py
─────────────────────────────
Learning event management business logic.
"""

import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.learning_event import LearningEvent

logger = logging.getLogger(__name__)


def emit_event(db: Session, user_id: uuid.UUID, event_type: str, topic_id: uuid.UUID | None = None, ref_id: uuid.UUID | None = None, ref_type: str | None = None, payload: dict | None = None, occurred_at: datetime | None = None) -> LearningEvent:
    event = LearningEvent(
        user_id=user_id,
        event_type=event_type,
        topic_id=topic_id,
        ref_id=ref_id,
        ref_type=ref_type,
        payload=payload,
        occurred_at=occurred_at or func.now()
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    logger.info("Event emitted | id=%s | event_type=%s", event.id, event.event_type)
    return event


def list_user_events(db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 50, event_type: str | None = None) -> tuple[list[LearningEvent], int]:
    query = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
    if event_type is not None:
        query = query.filter(LearningEvent.event_type == event_type)
    
    total = query.count()
    events = query.order_by(LearningEvent.occurred_at.desc()).offset(skip).limit(limit).all()
    return events, total


def get_event_timeline(db: Session, user_id: uuid.UUID, start_date: datetime | None = None, end_date: datetime | None = None, limit: int = 100) -> list[LearningEvent]:
    query = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
    if start_date:
        query = query.filter(LearningEvent.occurred_at >= start_date)
    if end_date:
        query = query.filter(LearningEvent.occurred_at <= end_date)
        
    events = query.order_by(LearningEvent.occurred_at.desc()).limit(limit).all()
    return events
