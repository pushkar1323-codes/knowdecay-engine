"""
app/models/__init__.py
───────────────────────
Import every model here so that:
  1. Alembic's env.py can discover all tables via Base.metadata
  2. SQLAlchemy relationship resolution works across module boundaries
  3. A single import gives access to all models

DO NOT remove any import — Alembic autogenerate depends on all models
being visible when env.py runs.
"""

from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.course import Course
from app.models.course_enrollment import CourseEnrollment
from app.models.daily_user_activity import DailyUserActivity
from app.models.feature_snapshot import FeatureSnapshot
from app.models.hierarchy import Chapter, Module, Subject, Subtopic, Topic
from app.models.institution import Institution
from app.models.learning_event import LearningEvent
from app.models.learning_resource import LearningResource
from app.models.memory_state import MemoryState
from app.models.quiz_attempt import QuizAttempt
from app.models.quiz_question_response import QuizQuestionResponse
from app.models.refresh_token import RefreshToken
from app.models.retention_time_series import RetentionTimeSeries
from app.models.revision_log import RevisionLog
from app.models.study_session import StudySession
from app.models.user import User

__all__ = [
    "AnalyticsSnapshot",
    "Chapter",
    "Course",
    "CourseEnrollment",
    "DailyUserActivity",
    "FeatureSnapshot",
    "Institution",
    "LearningEvent",
    "LearningResource",
    "MemoryState",
    "Module",
    "QuizAttempt",
    "QuizQuestionResponse",
    "RefreshToken",
    "RetentionTimeSeries",
    "RevisionLog",
    "StudySession",
    "Subject",
    "Subtopic",
    "Topic",
    "User",
]
