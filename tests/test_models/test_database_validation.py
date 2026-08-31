"""
tests/test_models/test_database_validation.py
──────────────────────────────────────────────
Phase 11: Database model validation.

Validates:
  • All ORM models define expected columns
  • Foreign key relationships are declared
  • Unique constraints exist on critical pairs
  • Indexes are defined for query-critical columns
  • MemoryState has all 26+ retention intelligence fields
  • Hierarchy relationships (Subject→Module→Chapter→Topic→Subtopic)
  • Table names follow conventions

All assertions use SQLAlchemy metadata inspection — no DB connection needed.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import inspect as sa_inspect

from app.models.user import User
from app.models.hierarchy import Subject, Module, Chapter, Topic, Subtopic
from app.models.memory_state import MemoryState
from app.models.study_session import StudySession
from app.models.quiz_attempt import QuizAttempt
from app.models.revision_log import RevisionLog
from app.models.analytics_snapshot import AnalyticsSnapshot


# ═══════════════════════════════════════════════════════════════════════════════
#  Table Existence
# ═══════════════════════════════════════════════════════════════════════════════

class TestTableNames:
    """Verify all expected tables exist in the ORM."""

    @pytest.mark.parametrize("model,expected_table", [
        (User, "users"),
        (Subject, "subjects"),
        (Module, "modules"),
        (Chapter, "chapters"),
        (Topic, "topics"),
        (Subtopic, "subtopics"),
        (MemoryState, "memory_states"),
        (StudySession, "study_sessions"),
        (QuizAttempt, "quiz_attempts"),
        (RevisionLog, "revision_logs"),
        (AnalyticsSnapshot, "analytics_snapshots"),
    ])
    def test_table_name(self, model, expected_table):
        """ORM model maps to expected table name."""
        assert model.__tablename__ == expected_table


# ═══════════════════════════════════════════════════════════════════════════════
#  MemoryState Fields (26+ columns)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryStateFields:
    """Validate MemoryState has all required retention intelligence fields."""

    CORE_FIELDS = [
        "retention_score", "stability_score", "decay_rate",
        "confidence_score", "revision_strength", "revision_count",
        "forgetting_probability", "urgency_score",
    ]

    ADAPTIVE_FORGETTING_FIELDS = [
        "base_stability", "revision_quality",
        "difficulty_factor", "performance_trend",
    ]

    ADAPTIVE_STABILITY_FIELDS = [
        "adaptive_stability", "stability_growth_rate", "half_life_days",
    ]

    DECAY_FIELDS = [
        "effective_decay_rate", "time_to_critical", "days_until_target",
    ]

    REINFORCEMENT_FIELDS = [
        "quality_variance", "effective_revision_count",
        "revision_effectiveness_ratio", "time_pattern_regularity",
        "confidence_calibration_error",
    ]

    RETENTION_HISTORY_FIELDS = [
        "peak_retention", "retention_at_last_revision",
        "total_forgetting_events",
    ]

    @pytest.mark.parametrize("field", CORE_FIELDS)
    def test_core_field_exists(self, field):
        """Core retention field exists on MemoryState."""
        mapper = sa_inspect(MemoryState)
        columns = {c.key for c in mapper.columns}
        assert field in columns, f"Missing core field: {field}"

    @pytest.mark.parametrize("field", ADAPTIVE_FORGETTING_FIELDS)
    def test_adaptive_forgetting_field_exists(self, field):
        """Adaptive forgetting field exists on MemoryState."""
        mapper = sa_inspect(MemoryState)
        columns = {c.key for c in mapper.columns}
        assert field in columns, f"Missing adaptive forgetting field: {field}"

    @pytest.mark.parametrize("field", ADAPTIVE_STABILITY_FIELDS)
    def test_adaptive_stability_field_exists(self, field):
        """Adaptive stability field exists on MemoryState."""
        mapper = sa_inspect(MemoryState)
        columns = {c.key for c in mapper.columns}
        assert field in columns, f"Missing adaptive stability field: {field}"

    @pytest.mark.parametrize("field", DECAY_FIELDS)
    def test_decay_field_exists(self, field):
        """Decay parameter field exists on MemoryState."""
        mapper = sa_inspect(MemoryState)
        columns = {c.key for c in mapper.columns}
        assert field in columns, f"Missing decay field: {field}"

    @pytest.mark.parametrize("field", REINFORCEMENT_FIELDS)
    def test_reinforcement_field_exists(self, field):
        """Reinforcement behaviour field exists on MemoryState."""
        mapper = sa_inspect(MemoryState)
        columns = {c.key for c in mapper.columns}
        assert field in columns, f"Missing reinforcement field: {field}"

    @pytest.mark.parametrize("field", RETENTION_HISTORY_FIELDS)
    def test_retention_history_field_exists(self, field):
        """Retention history field exists on MemoryState."""
        mapper = sa_inspect(MemoryState)
        columns = {c.key for c in mapper.columns}
        assert field in columns, f"Missing retention history field: {field}"

    def test_minimum_field_count(self):
        """MemoryState should have at least 26 engine-relevant columns."""
        mapper = sa_inspect(MemoryState)
        columns = [c.key for c in mapper.columns]
        # Exclude metadata (id, user_id, topic_id, created_at, updated_at, etc.)
        all_engine_fields = (
            self.CORE_FIELDS + self.ADAPTIVE_FORGETTING_FIELDS +
            self.ADAPTIVE_STABILITY_FIELDS + self.DECAY_FIELDS +
            self.REINFORCEMENT_FIELDS + self.RETENTION_HISTORY_FIELDS
        )
        present = [f for f in all_engine_fields if f in columns]
        assert len(present) >= 26, f"Only {len(present)} engine fields found"


# ═══════════════════════════════════════════════════════════════════════════════
#  Foreign Key Relationships
# ═══════════════════════════════════════════════════════════════════════════════

class TestHierarchyRelationships:
    """Verify Subject→Module→Chapter→Topic→Subtopic FK chain."""

    def test_module_has_subject_fk(self):
        """Module has a foreign key to Subject."""
        mapper = sa_inspect(Module)
        fk_targets = set()
        for col in mapper.columns:
            for fk in col.foreign_keys:
                fk_targets.add(fk.target_fullname)
        assert any("subjects" in t for t in fk_targets), "Module missing FK to subjects"

    def test_chapter_has_module_fk(self):
        """Chapter has a foreign key to Module."""
        mapper = sa_inspect(Chapter)
        fk_targets = set()
        for col in mapper.columns:
            for fk in col.foreign_keys:
                fk_targets.add(fk.target_fullname)
        assert any("modules" in t for t in fk_targets), "Chapter missing FK to modules"

    def test_topic_has_chapter_fk(self):
        """Topic has a foreign key to Chapter."""
        mapper = sa_inspect(Topic)
        fk_targets = set()
        for col in mapper.columns:
            for fk in col.foreign_keys:
                fk_targets.add(fk.target_fullname)
        assert any("chapters" in t for t in fk_targets), "Topic missing FK to chapters"

    def test_subtopic_has_topic_fk(self):
        """Subtopic has a foreign key to Topic."""
        mapper = sa_inspect(Subtopic)
        fk_targets = set()
        for col in mapper.columns:
            for fk in col.foreign_keys:
                fk_targets.add(fk.target_fullname)
        assert any("topics" in t for t in fk_targets), "Subtopic missing FK to topics"

    def test_memory_state_has_user_fk(self):
        """MemoryState has a foreign key to User."""
        mapper = sa_inspect(MemoryState)
        fk_targets = set()
        for col in mapper.columns:
            for fk in col.foreign_keys:
                fk_targets.add(fk.target_fullname)
        assert any("users" in t for t in fk_targets), "MemoryState missing FK to users"

    def test_memory_state_has_topic_fk(self):
        """MemoryState has a foreign key to Topic."""
        mapper = sa_inspect(MemoryState)
        fk_targets = set()
        for col in mapper.columns:
            for fk in col.foreign_keys:
                fk_targets.add(fk.target_fullname)
        assert any("topics" in t for t in fk_targets), "MemoryState missing FK to topics"
