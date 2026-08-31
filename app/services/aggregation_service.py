"""
app/services/aggregation_service.py
───────────────────────────────────
Data aggregation and snapshotting business logic.
"""

import logging
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.daily_user_activity import DailyUserActivity
from app.models.retention_time_series import RetentionTimeSeries
from app.models.feature_snapshot import FeatureSnapshot
from app.models.memory_state import MemoryState
from app.models.study_session import StudySession
from app.models.quiz_attempt import QuizAttempt
from app.models.revision_log import RevisionLog
from app.models.user import User

logger = logging.getLogger(__name__)


def aggregate_daily_activity(
    db: Session, user_id: uuid.UUID, activity_date: date
) -> DailyUserActivity:
    """Aggregate daily activity for a user. Idempotent — upserts on (user_id, activity_date)."""
    # Compute from study_sessions
    study_stats = db.query(
        func.count(StudySession.id).label("sessions_count"),
        func.coalesce(func.sum(StudySession.duration_minutes), 0).label("study_minutes"),
    ).filter(
        StudySession.user_id == user_id,
        func.date(StudySession.created_at) == activity_date,
    ).first()

    # Compute from quiz_attempts
    quiz_stats = db.query(
        func.count(QuizAttempt.id).label("quizzes_taken"),
        func.avg(QuizAttempt.score).label("quiz_avg_score"),
    ).filter(
        QuizAttempt.user_id == user_id,
        func.date(QuizAttempt.attempted_at) == activity_date,
    ).first()

    # Compute from revision_logs
    revision_stats = db.query(
        func.count(RevisionLog.id).label("revisions_count"),
    ).filter(
        RevisionLog.user_id == user_id,
        func.date(RevisionLog.revised_at) == activity_date,
    ).first()

    # Upsert: find existing or create new
    activity = db.query(DailyUserActivity).filter(
        DailyUserActivity.user_id == user_id,
        DailyUserActivity.activity_date == activity_date,
    ).first()

    if not activity:
        activity = DailyUserActivity(
            user_id=user_id,
            activity_date=activity_date,
        )
        db.add(activity)

    # Set values using correct model field names
    activity.study_minutes = int(study_stats.study_minutes or 0)
    activity.sessions_count = study_stats.sessions_count or 0
    activity.quizzes_taken = quiz_stats.quizzes_taken or 0
    activity.quiz_avg_score = float(quiz_stats.quiz_avg_score) if quiz_stats.quiz_avg_score else None
    activity.revisions_count = revision_stats.revisions_count or 0

    db.commit()
    db.refresh(activity)
    logger.info(
        "Daily activity aggregated | user_id=%s | date=%s", user_id, activity_date
    )
    return activity


def snapshot_retention(
    db: Session, user_id: uuid.UUID, topic_id: uuid.UUID, snapshot_date: date
) -> RetentionTimeSeries | None:
    """Snapshot retention state for a user×topic. Idempotent — upserts on (user_id, topic_id, snapshot_date)."""
    memory_state = db.query(MemoryState).filter(
        MemoryState.user_id == user_id,
        MemoryState.topic_id == topic_id,
    ).first()

    if not memory_state:
        return None

    snapshot = db.query(RetentionTimeSeries).filter(
        RetentionTimeSeries.user_id == user_id,
        RetentionTimeSeries.topic_id == topic_id,
        RetentionTimeSeries.snapshot_date == snapshot_date,
    ).first()

    if not snapshot:
        snapshot = RetentionTimeSeries(
            user_id=user_id,
            topic_id=topic_id,
            snapshot_date=snapshot_date,
        )
        db.add(snapshot)

    # Use correct MemoryState field names → correct RetentionTimeSeries field names
    snapshot.retention_score = memory_state.retention_score
    snapshot.stability_score = memory_state.stability_score
    snapshot.decay_rate = memory_state.decay_rate
    snapshot.revision_count = memory_state.revision_count
    snapshot.days_since_last_revision = (
        (datetime.utcnow() - memory_state.last_revision_at).total_seconds() / 86400.0
        if memory_state.last_revision_at
        else None
    )

    db.commit()
    db.refresh(snapshot)
    logger.info(
        "Retention snapshot created | user_id=%s | topic_id=%s | date=%s",
        user_id,
        topic_id,
        snapshot_date,
    )
    return snapshot


def run_daily_aggregation(db: Session) -> dict:
    """Run daily aggregation for all active users. Per-user errors are caught and logged."""
    today = datetime.utcnow().date()
    active_users = db.query(User).filter(User.is_active == True).all()

    users_processed = 0
    users_failed = 0
    snapshots_created = 0

    for user in active_users:
        try:
            aggregate_daily_activity(db, user.id, today)
            users_processed += 1

            # Snapshot retention for all user's active memory states
            memory_states = db.query(MemoryState).filter(
                MemoryState.user_id == user.id
            ).all()
            for state in memory_states:
                result = snapshot_retention(db, user.id, state.topic_id, today)
                if result:
                    snapshots_created += 1
        except Exception:
            users_failed += 1
            logger.exception(
                "Failed to aggregate for user_id=%s — skipping", user.id
            )
            db.rollback()
            continue

    logger.info(
        "Daily aggregation complete | users=%d | failed=%d | snapshots=%d",
        users_processed,
        users_failed,
        snapshots_created,
    )
    return {
        "status": "success",
        "users_processed": users_processed,
        "users_failed": users_failed,
        "snapshots_created": snapshots_created,
        "date": today.isoformat(),
    }


def generate_feature_snapshot(
    db: Session, user_id: uuid.UUID, topic_id: uuid.UUID
) -> FeatureSnapshot:
    """Generate ML feature snapshot. Idempotent — upserts on (user_id, topic_id, feature_version)."""
    memory_state = db.query(MemoryState).filter(
        MemoryState.user_id == user_id,
        MemoryState.topic_id == topic_id,
    ).first()

    study_count = db.query(func.count(StudySession.id)).filter(
        StudySession.user_id == user_id,
        StudySession.topic_id == topic_id,
    ).scalar() or 0

    quiz_count = db.query(func.count(QuizAttempt.id)).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.topic_id == topic_id,
    ).scalar() or 0

    revision_count = db.query(func.count(RevisionLog.id)).filter(
        RevisionLog.user_id == user_id,
        RevisionLog.topic_id == topic_id,
    ).scalar() or 0

    features = {
        "ms_retention_score": float(memory_state.retention_score) if memory_state else None,
        "ms_stability_score": float(memory_state.stability_score) if memory_state else None,
        "ms_decay_rate": float(memory_state.decay_rate) if memory_state else None,
        "ms_revision_count": int(memory_state.revision_count) if memory_state else 0,
        "study_sessions_count": study_count,
        "quiz_attempts_count": quiz_count,
        "revision_logs_count": revision_count,
    }

    feature_version = "v1"

    # Upsert: find existing or create new (idempotent)
    snapshot = db.query(FeatureSnapshot).filter(
        FeatureSnapshot.user_id == user_id,
        FeatureSnapshot.topic_id == topic_id,
        FeatureSnapshot.feature_version == feature_version,
    ).first()

    if not snapshot:
        snapshot = FeatureSnapshot(
            user_id=user_id,
            topic_id=topic_id,
            feature_version=feature_version,
        )
        db.add(snapshot)

    snapshot.features = features
    snapshot.computed_at = datetime.utcnow()

    db.commit()
    db.refresh(snapshot)

    logger.info(
        "Feature snapshot generated | user_id=%s | topic_id=%s | version=%s",
        user_id,
        topic_id,
        feature_version,
    )
    return snapshot
