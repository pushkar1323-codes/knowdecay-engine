"""
app/api/retention.py
─────────────────────
REST endpoints for retention prediction.

Endpoint summary:
  POST /v1/retention/predict        — single topic retention prediction
  POST /v1/retention/predict/batch  — multi-topic batch prediction
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.retention import (
    RetentionBatchRequest,
    RetentionBatchResponse,
    RetentionPredictRequest,
    RetentionPredictResponse,
)
from app.services import retention_service

router = APIRouter(prefix="/retention", tags=["Retention Engine"])


@router.post(
    "/predict",
    response_model=RetentionPredictResponse,
    summary="Predict retention for a single user × topic",
)
def predict_retention(
    payload: RetentionPredictRequest,
    db: Session = Depends(get_db),
):
    """
    Compute the current retention score for a user × topic pair.

    The response includes:
    - **retention_score** — probability of correct recall right now
    - **stability_score** — estimated days until retention drops to threshold
    - **confidence_score** — blended confidence (quiz + self-reported)
    - **breakdown** — explainability: how each component contributed

    Optionally pass `quiz_score`, `quiz_confidence`, `study_duration_minutes`,
    or `elapsed_days` to override values from the stored memory state.
    Scores are persisted to the memory state by default.
    """
    return retention_service.predict_retention(
        db,
        payload.user_id,
        payload.topic_id,
        study_duration_override=payload.study_duration_minutes,
        quiz_score_override=payload.quiz_score,
        quiz_confidence_override=payload.quiz_confidence,
        elapsed_days_override=payload.elapsed_days,
    )


@router.post(
    "/predict/batch",
    response_model=RetentionBatchResponse,
    summary="Predict retention for multiple topics",
)
def predict_retention_batch(
    payload: RetentionBatchRequest,
    db: Session = Depends(get_db),
):
    """
    Compute retention for multiple topics in a single request.
    Each topic is computed independently.
    """
    predictions = retention_service.predict_retention_batch(
        db, payload.user_id, payload.topic_ids,
    )
    return RetentionBatchResponse(
        user_id=payload.user_id,
        predictions=predictions,
        total=len(predictions),
    )
