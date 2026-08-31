"""
app/api/quizzes.py
────────────────────
Quiz attempt management endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import get_current_user
from app.models.user import User
from app.schemas.quiz import (
    QuizAttemptCreate,
    QuizAttemptResponse,
    QuizAttemptListResponse,
    QuizStatsResponse,
    QuestionResponseCreate,
    QuestionResponseItem,
)
from app.services import quiz_service

router = APIRouter(prefix="/quizzes", tags=["Quiz Engine"])


@router.post("/attempts", response_model=QuizAttemptResponse, status_code=201, summary="Submit quiz attempt")
def submit_quiz_attempt(
    payload: QuizAttemptCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a new quiz attempt for the current user."""
    # Convert question_responses from Pydantic models to dicts for the service
    qr_dicts = None
    if payload.question_responses:
        qr_dicts = [qr.model_dump() for qr in payload.question_responses]

    attempt = quiz_service.create_quiz_attempt(
        db,
        user_id=user.id,
        topic_id=payload.topic_id,
        score=payload.score,
        confidence=payload.confidence,
        attempt_number=payload.attempt_number,
        time_taken_seconds=payload.time_taken_seconds,
        total_marks=payload.total_marks,
        earned_marks=payload.earned_marks,
        bloom_level=payload.bloom_level,
        question_count=payload.question_count,
        quiz_metadata=payload.quiz_metadata,
        question_responses=qr_dicts,
    )
    return QuizAttemptResponse.model_validate(attempt)


@router.get("/attempts", response_model=QuizAttemptListResponse, summary="List quiz attempts")
def list_quiz_attempts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=1000),
    topic_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List quiz attempts for the current user."""
    attempts, total = quiz_service.list_user_attempts(
        db, user_id=user.id, skip=skip, limit=limit, topic_id=topic_id
    )
    return QuizAttemptListResponse(
        attempts=[QuizAttemptResponse.model_validate(a) for a in attempts],
        total=total,
        page=skip // limit if limit else 0,
        page_size=limit,
    )


@router.get("/stats", response_model=QuizStatsResponse, summary="Get quiz stats")
def get_quiz_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get quiz statistics for the current user."""
    stats = quiz_service.get_quiz_stats(db, user_id=user.id)
    return QuizStatsResponse(**stats)


@router.get("/attempts/{attempt_id}", response_model=QuizAttemptResponse, summary="Get quiz attempt")
def get_quiz_attempt(
    attempt_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific quiz attempt with its responses."""
    attempt = quiz_service.get_quiz_attempt(db, attempt_id)
    return QuizAttemptResponse.model_validate(attempt)


@router.post("/attempts/{attempt_id}/responses", response_model=list[QuestionResponseItem], summary="Add question responses")
def add_question_responses(
    attempt_id: uuid.UUID,
    payload: list[QuestionResponseCreate],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add multiple question responses to a quiz attempt."""
    response_dicts = [r.model_dump() for r in payload]
    responses = quiz_service.add_question_responses(db, attempt_id, response_dicts)
    return [QuestionResponseItem.model_validate(r) for r in responses]
