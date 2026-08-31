"""
app/api/schedule.py
────────────────────
REST endpoints for revision scheduling.

Endpoint summary:
  POST /v1/schedule/next       — compute next revision time for one topic
  POST /v1/schedule/generate   — generate full schedule for multiple topics
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.schedule import (
    ScheduleGenerateRequest,
    ScheduleGenerateResponse,
    ScheduleSingleRequest,
    ScheduleSingleResponse,
)
from app.services import schedule_service

router = APIRouter(prefix="/schedule", tags=["Scheduling Engine"])


@router.post(
    "/next",
    response_model=ScheduleSingleResponse,
    summary="Compute next revision time for a single topic",
)
def schedule_next(
    payload: ScheduleSingleRequest,
    db: Session = Depends(get_db),
):
    """
    Compute when a topic should be revised next.

    The response includes:
    - **next_revision_days** — days from now to optimal revision
    - **next_revision_at** — absolute timestamp
    - **mode** — scheduling strategy (exam_tomorrow/exam_week/exam_month/long_term)
    - **breakdown** — how the interval was computed
    - **recommendation** — human-readable advice

    Optionally pass `days_until_exam` to activate exam-aware scheduling.
    """
    return schedule_service.schedule_single(
        db,
        payload.user_id,
        payload.topic_id,
        days_until_exam=payload.days_until_exam,
    )


@router.post(
    "/generate",
    response_model=ScheduleGenerateResponse,
    summary="Generate full revision schedule for multiple topics",
)
def generate_schedule(
    payload: ScheduleGenerateRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a unified revision schedule across multiple topics.

    Topics are distributed across days with per-day caps,
    ordered by schedule priority within each day.

    Use `max_per_day` to control workload (default: 10).
    """
    return schedule_service.schedule_batch(
        db,
        payload.user_id,
        payload.topic_ids,
        days_until_exam=payload.days_until_exam,
        max_per_day=payload.max_per_day,
    )
