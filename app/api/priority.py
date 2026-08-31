"""
app/api/priority.py
────────────────────
REST endpoints for priority ranking.

Endpoint summary:
  POST /v1/priority/rank        — single topic priority computation
  POST /v1/priority/rank/batch  — multi-topic batch ranking (sorted)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.priority import (
    PriorityBatchRequest,
    PriorityBatchResponse,
    PriorityRankRequest,
    PriorityRankResponse,
)
from app.services import priority_service

router = APIRouter(prefix="/priority", tags=["Priority Engine"])


@router.post(
    "/rank",
    response_model=PriorityRankResponse,
    summary="Compute priority for a single user × topic",
)
def rank_topic(
    payload: PriorityRankRequest,
    db: Session = Depends(get_db),
):
    """
    Compute the current revision priority for a single topic.

    The response includes:
    - **priority_score** — raw composite score (higher = more urgent)
    - **normalised_score** — 0.0–1.0 normalised for comparison
    - **tier** — human-readable bucket (critical/high/medium/low/minimal)
    - **breakdown** — how each component contributed
    - **reason** — human-readable explanation of WHY this topic is prioritised

    Optionally pass `days_until_exam` and `importance_weight` to override
    values from the topic metadata.
    """
    return priority_service.rank_single(
        db,
        payload.user_id,
        payload.topic_id,
        days_until_exam=payload.days_until_exam,
        importance_override=payload.importance_weight,
    )


@router.post(
    "/rank/batch",
    response_model=PriorityBatchResponse,
    summary="Rank multiple topics by revision priority",
)
def rank_topics_batch(
    payload: PriorityBatchRequest,
    db: Session = Depends(get_db),
):
    """
    Rank multiple topics by revision urgency, sorted from highest to lowest.

    Each topic in the response includes its rank position (1 = most urgent),
    full component breakdown, and explainable reasons.

    Use `limit` to return only the top-N most urgent topics.
    """
    return priority_service.rank_batch(
        db,
        payload.user_id,
        payload.topic_ids,
        days_until_exam=payload.days_until_exam,
        limit=payload.limit,
    )
