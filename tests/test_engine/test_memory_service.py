"""
tests/test_engine/test_memory_service.py
─────────────────────────────────────────
Unit tests for the memory_service aggregation and helper functions.
These tests exercise the PURE functions (no database required).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# We test the pure helper functions that don't need a real DB session.
# The service module is imported after we set up any needed mocks.


def _make_mock_state(
    retention: float = 0.5,
    stability: float = 2.0,
    urgency: float = 0.3,
    decay_rate: float = 0.1,
    confidence: float = 0.5,
    revision_strength: float = 0.0,
    revision_count: int = 0,
    forgetting_probability: float = 0.5,
    topic_id: uuid.UUID | None = None,
    last_revision_at: datetime | None = None,
    next_revision_at: datetime | None = None,
) -> MagicMock:
    """Create a mock MemoryState object for testing aggregation."""
    state = MagicMock()
    state.topic_id = topic_id or uuid.uuid4()
    state.retention_score = retention
    state.stability_score = stability
    state.urgency_score = urgency
    state.decay_rate = decay_rate
    state.confidence_score = confidence
    state.revision_strength = revision_strength
    state.revision_count = revision_count
    state.forgetting_probability = forgetting_probability
    state.last_revision_at = last_revision_at
    state.next_revision_at = next_revision_at
    return state


class TestAggregateStates:
    """Test the _aggregate_states pure function."""

    def test_empty_list(self):
        from app.services.memory_service import _aggregate_states

        result = _aggregate_states([])
        assert result["retention_avg"] == 0.0
        assert result["stability_avg"] == 0.0
        assert result["urgency_avg"] == 0.0
        assert result["topics_total"] == 0
        assert result["topics_at_risk"] == 0

    def test_single_state(self):
        from app.services.memory_service import _aggregate_states

        states = [_make_mock_state(retention=0.8, stability=3.0, urgency=0.2)]
        result = _aggregate_states(states)
        assert result["retention_avg"] == 0.8
        assert result["stability_avg"] == 3.0
        assert result["urgency_avg"] == 0.2
        assert result["topics_total"] == 1
        assert result["topics_at_risk"] == 0

    def test_multiple_states_averaging(self):
        from app.services.memory_service import _aggregate_states

        states = [
            _make_mock_state(retention=0.9, stability=4.0, urgency=0.1),
            _make_mock_state(retention=0.3, stability=2.0, urgency=0.7),
            _make_mock_state(retention=0.6, stability=3.0, urgency=0.4),
        ]
        result = _aggregate_states(states)
        assert result["retention_avg"] == pytest.approx(0.6, abs=0.001)
        assert result["stability_avg"] == pytest.approx(3.0, abs=0.001)
        assert result["urgency_avg"] == pytest.approx(0.4, abs=0.001)
        assert result["topics_total"] == 3

    def test_at_risk_counting(self):
        from app.services.memory_service import _aggregate_states

        states = [
            _make_mock_state(retention=0.1),  # at risk (< 0.4)
            _make_mock_state(retention=0.2),  # at risk
            _make_mock_state(retention=0.5),  # safe
            _make_mock_state(retention=0.9),  # safe
            _make_mock_state(retention=0.39), # at risk (boundary)
        ]
        result = _aggregate_states(states)
        assert result["topics_at_risk"] == 3
        assert result["topics_total"] == 5

    def test_all_at_risk(self):
        from app.services.memory_service import _aggregate_states

        states = [
            _make_mock_state(retention=0.0),
            _make_mock_state(retention=0.1),
            _make_mock_state(retention=0.3),
        ]
        result = _aggregate_states(states)
        assert result["topics_at_risk"] == 3

    def test_none_at_risk(self):
        from app.services.memory_service import _aggregate_states

        states = [
            _make_mock_state(retention=0.4),  # boundary — NOT at risk (< 0.4)
            _make_mock_state(retention=0.8),
        ]
        result = _aggregate_states(states)
        assert result["topics_at_risk"] == 0


class TestStateToSummary:
    """Test the _state_to_summary converter."""

    def test_converts_fields(self):
        from app.services.memory_service import _state_to_summary

        tid = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)
        state = _make_mock_state(
            topic_id=tid,
            retention=0.75,
            stability=2.5,
            forgetting_probability=0.25,
            urgency=0.6,
            revision_count=3,
            last_revision_at=now,
        )
        summary = _state_to_summary(state, "Calculus Limits")
        assert summary.topic_id == tid
        assert summary.topic_name == "Calculus Limits"
        assert summary.retention_score == 0.75
        assert summary.stability_score == 2.5
        assert summary.forgetting_probability == 0.25
        assert summary.urgency_score == 0.6
        assert summary.revision_count == 3
        assert summary.last_revision_at == now

    def test_empty_topic_name(self):
        from app.services.memory_service import _state_to_summary

        state = _make_mock_state()
        summary = _state_to_summary(state)
        assert summary.topic_name == ""


class TestMemoryStateUpdate:
    """Test the Pydantic update schema."""

    def test_partial_update_excludes_none(self):
        from app.schemas.memory import MemoryStateUpdate

        update = MemoryStateUpdate(retention_score=0.9, urgency_score=0.5)
        data = update.model_dump(exclude_none=True)
        assert data == {"retention_score": 0.9, "urgency_score": 0.5}
        assert "stability_score" not in data
        assert "decay_rate" not in data

    def test_empty_update(self):
        from app.schemas.memory import MemoryStateUpdate

        update = MemoryStateUpdate()
        data = update.model_dump(exclude_none=True)
        assert data == {}

    def test_full_update(self):
        from app.schemas.memory import MemoryStateUpdate

        update = MemoryStateUpdate(
            retention_score=0.8,
            stability_score=3.0,
            decay_rate=0.05,
            confidence_score=0.9,
            revision_strength=1.5,
            revision_count=5,
            forgetting_probability=0.2,
            urgency_score=0.3,
        )
        data = update.model_dump(exclude_none=True)
        assert len(data) == 8


class TestMemoryStateInit:
    """Test the init schema defaults."""

    def test_defaults(self):
        from app.schemas.memory import MemoryStateInit

        uid = uuid.uuid4()
        tid = uuid.uuid4()
        init = MemoryStateInit(user_id=uid, topic_id=tid)
        assert init.retention_score == 0.0
        assert init.stability_score == 1.0
        assert init.decay_rate == 0.1
        assert init.confidence_score == 0.5

    def test_custom_values(self):
        from app.schemas.memory import MemoryStateInit

        uid = uuid.uuid4()
        tid = uuid.uuid4()
        init = MemoryStateInit(
            user_id=uid, topic_id=tid,
            retention_score=0.7, stability_score=5.0,
        )
        assert init.retention_score == 0.7
        assert init.stability_score == 5.0
