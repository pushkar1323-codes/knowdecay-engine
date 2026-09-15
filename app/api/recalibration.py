"""
app/api/recalibration.py
──────────────────────────
REST endpoints for event-driven recalibration.

Endpoint summary:
  POST /v1/recalibrate         — process a single learning event
  POST /v1/recalibrate/batch   — process multiple events sequentially

All endpoints require authentication. Learners can only submit events
for their own data unless the caller is a privileged role (admin / API_CLIENT).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import enforce_learner_access, get_current_user
from app.models.user import User
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
    current_user: User = Depends(get_current_user),
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
    enforce_learner_access(payload.user_id, current_user)
    return recalibration_service.process_event(db, payload)


@router.post(
    "/batch",
    response_model=BatchRecalibrationResponse,
    summary="Process multiple learning events",
)
def recalibrate_batch(
    payload: BatchRecalibrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit multiple learning events for sequential processing.

    Events are processed in order — later events for the same
    user×topic will see the results of earlier events in the batch.

    All events in the batch must belong to the authenticated user
    (unless the caller is a privileged role).
    """
    # Enforce access for every distinct user_id in the batch
    seen_users = set()
    for event in payload.events:
        if event.user_id not in seen_users:
            enforce_learner_access(event.user_id, current_user)
            seen_users.add(event.user_id)
    return recalibration_service.process_batch(db, payload.events)
