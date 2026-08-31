"""
app/services/quiz_service.py
────────────────────────────
Quiz attempt management business logic.
"""

import logging
import uuid
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.core.exceptions import NotFoundError
from app.models.quiz_attempt import QuizAttempt
from app.models.quiz_question_response import QuizQuestionResponse

logger = logging.getLogger(__name__)


def create_quiz_attempt(db: Session, user_id: uuid.UUID, topic_id: uuid.UUID, score: float, confidence: float = 0.5, attempt_number: int | None = None, time_taken_seconds: int | None = None, total_marks: float | None = None, earned_marks: float | None = None, bloom_level: str | None = None, question_count: int | None = None, quiz_metadata: dict | None = None, question_responses: list[dict] | None = None) -> QuizAttempt:
    attempt = QuizAttempt(
        user_id=user_id,
        topic_id=topic_id,
        score=score,
        confidence=confidence,
        attempt_number=attempt_number,
        time_taken_seconds=time_taken_seconds,
        total_marks=total_marks,
        earned_marks=earned_marks,
        bloom_level=bloom_level,
        question_count=question_count,
        quiz_metadata=quiz_metadata
    )
    db.add(attempt)
    db.flush() # flush to get attempt.id

    if question_responses:
        for resp in question_responses:
            qr = QuizQuestionResponse(
                quiz_attempt_id=attempt.id,
                **resp
            )
            db.add(qr)

    db.commit()
    db.refresh(attempt)
    logger.info("Quiz attempt created | id=%s | user_id=%s", attempt.id, user_id)
    return attempt


def get_quiz_attempt(db: Session, attempt_id: uuid.UUID) -> QuizAttempt:
    attempt = db.query(QuizAttempt).options(joinedload(QuizAttempt.question_responses)).filter(QuizAttempt.id == attempt_id).first()
    if not attempt:
        raise NotFoundError("QuizAttempt", str(attempt_id))
    return attempt


def list_user_attempts(db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 50, topic_id: uuid.UUID | None = None) -> tuple[list[QuizAttempt], int]:
    query = db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id)
    if topic_id is not None:
        query = query.filter(QuizAttempt.topic_id == topic_id)
    
    total = query.count()
    attempts = query.order_by(QuizAttempt.attempted_at.desc()).offset(skip).limit(limit).all()
    return attempts, total


def add_question_responses(db: Session, attempt_id: uuid.UUID, responses: list[dict]) -> list[QuizQuestionResponse]:
    attempt = get_quiz_attempt(db, attempt_id)
    
    new_responses = []
    for resp in responses:
        qr = QuizQuestionResponse(
            quiz_attempt_id=attempt.id,
            **resp
        )
        db.add(qr)
        new_responses.append(qr)
        
    db.commit()
    for qr in new_responses:
        db.refresh(qr)
    
    logger.info("Added %d question responses to attempt %s", len(new_responses), attempt.id)
    return new_responses


def get_quiz_stats(db: Session, user_id: uuid.UUID) -> dict:
    query = db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id)
    
    total_attempts = query.count()
    
    stats = db.query(
        func.avg(QuizAttempt.score).label('avg_score'),
        func.avg(QuizAttempt.confidence).label('avg_confidence')
    ).filter(QuizAttempt.user_id == user_id).first()

    # Count total questions and correct answers
    q_stats = db.query(
        func.count(QuizQuestionResponse.id).label('total_questions'),
        func.count().filter(QuizQuestionResponse.is_correct == True).label('correct_count')
    ).join(QuizAttempt, QuizQuestionResponse.quiz_attempt_id == QuizAttempt.id
    ).filter(QuizAttempt.user_id == user_id).first()

    total_questions = q_stats.total_questions if q_stats else 0
    correct_count = q_stats.correct_count if q_stats else 0
    
    return {
        "total_attempts": total_attempts,
        "avg_score": float(stats.avg_score or 0.0),
        "avg_confidence": float(stats.avg_confidence or 0.0),
        "total_questions": total_questions,
        "correct_rate": float(correct_count / total_questions) if total_questions > 0 else 0.0,
    }

