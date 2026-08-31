"""
app/api/events.py
───────────────────
Learning event recording and querying endpoints.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import get_current_user
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventResponse,
    EventListResponse,
    EventTimelineResponse,
)
from app.services import event_service

router = APIRouter(prefix="/events", tags=["Learning Events"])


@router.post("/", response_model=EventResponse, status_code=201, summary="Record event")
def record_event(
    payload: EventCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a new learning event for the current user."""
    event = event_service.emit_event(
        db,
        user_id=user.id,
        event_type=payload.event_type,
        topic_id=payload.topic_id,
        ref_id=payload.ref_id,
        ref_type=payload.ref_type,
        payload=payload.payload,
        occurred_at=payload.occurred_at,
    )
    return EventResponse.model_validate(event)


@router.get("/", response_model=EventListResponse, summary="List events")
def list_events(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=1000),
    event_type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List learning events for the current user."""
    events, total = event_service.list_user_events(
        db, user_id=user.id, skip=skip, limit=limit, event_type=event_type
    )
    return EventListResponse(
        events=[EventResponse.model_validate(e) for e in events],
        total=total,
        page=skip // limit if limit else 0,
        page_size=limit,
    )


@router.get("/timeline", response_model=EventTimelineResponse, summary="Get event timeline")
def get_timeline(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a timeline of learning events for the current user."""
    events = event_service.get_event_timeline(
        db, user_id=user.id, start_date=start_date, end_date=end_date, limit=limit
    )
    now = datetime.utcnow()
    return EventTimelineResponse(
        events=[EventResponse.model_validate(e) for e in events],
        date_range_start=start_date or (events[-1].occurred_at if events else now),
        date_range_end=end_date or (events[0].occurred_at if events else now),
        total=len(events),
    )
