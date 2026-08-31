"""
app/api/recalibration.py
──────────────────────────
REST endpoints for event-driven recalibration.

Endpoint summary:
  POST /v1/recalibrate         — process a single learning event
  POST /v1/recalibrate/batch   — process multiple events sequentially
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.recalibration import (
    BatchRecalibrationRequest,
    BatchRecalibrationResponse,
    RecalibrationEventRequest,
    RecalibrationResponse,
)
from app.services import recalibration_service

router = APIRouter(prefix="/recalibrate", tags=["Recalibration Engine"])


@router.post(
    "",
    response_model=RecalibrationResponse,
    summary="Process a single learning event",
)
def recalibrate_event(
    payload: RecalibrationEventRequest,
    db: Session = Depends(get_db),
):
    """
    Submit a learning event to trigger memory state recalibration.

    Supported event types:
    - **quiz_submitted** — strongest signal. Provide `quiz_score` (0–1) and optional `quiz_confidence`
    - **revision_completed** — reinforcement signal. Increments revision count
    - **study_session** — modest boost. Provide `study_duration_minutes`
    - **inactivity_detected** — degradation. Provide `days_inactive`

    The response includes:
    - **new_*** fields — updated memory state values
    - **delta** — what changed and by how much
    - **changes** — audit trail with human-readable reasons
    - **next_revision_at** — rescheduled revision time
    """
    return recalibration_service.process_event(db, payload)


@router.post(
    "/batch",
    response_model=BatchRecalibrationResponse,
    summary="Process multiple learning events",
)
def recalibrate_batch(
    payload: BatchRecalibrationRequest,
    db: Session = Depends(get_db),
):
    """
    Submit multiple learning events for sequential processing.

    Events are processed in order — later events for the same
    user×topic will see the results of earlier events in the batch.
    """
    return recalibration_service.process_batch(db, payload.events)
