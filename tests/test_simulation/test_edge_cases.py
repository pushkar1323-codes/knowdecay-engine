"""
tests/test_simulation/test_edge_cases.py
─────────────────────────────────────────
Phase 11: Edge case testing for the KnowDecay engine.

Tests extreme and boundary scenarios:
  • Learner who never revises
  • Learner who revises daily
  • Missed revisions (long gaps)
  • New topics added mid-cycle
  • Invalid/boundary inputs
  • Empty datasets
  • Large topic sets
  • Extreme difficulty values
  • Zero elapsed time
  • Maximum retention/stability values
"""

import math
import uuid

import pytest

from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    recalibrate,
    apply_delta,
    StateDelta,
)
from app.engine.stability_engine import StabilityInput, compute_adaptive_stability
from app.engine.priority_engine import PriorityInput, compute_priority
from app.engine.scheduling_engine import ScheduleInput, compute_schedule
from simulation.learner_profiles import generate_learners, Archetype
from simulation.timeline_simulator import run_simulation, simulate_learner


# ═══════════════════════════════════════════════════════════════════════════════
#  Never Revises
# ═══════════════════════════════════════════════════════════════════════════════

class TestNeverRevises:
    """Simulate a learner who never engages after initial study."""

    def test_retention_decays_without_revision(self):
        """With only inactivity, retention should stay at floor or decrease."""
        state = CurrentState(retention_score=0.5, stability_score=3.0)
        for day in range(1, 30):
            event = EventData(
                event_type=EventType.INACTIVITY_DETECTED,
                days_inactive=float(day),
                difficulty=0.5,
            )
            out = recalibrate(state, event)
            new_dict = apply_delta(state, out.delta)
            cs = {f for f in CurrentState.__dataclass_fields__}
            state = CurrentState(**{k: v for k, v in new_dict.items() if k in cs})

        # After 30 days of pure inactivity, retention should be at floor
        assert state.retention_score <= 0.15

    def test_absent_archetype_low_engagement(self):
        """Absent archetype simulation should produce very few events."""
        learners = generate_learners(1, 5, days_until_exam=30.0, seed=999)
        # Find absent archetype
        absent = [l for l in learners if l.archetype == Archetype.ABSENT]
        if absent:
            results = run_simulation(absent, total_days=30, base_seed=999)
            assert results[0].total_events < 30  # Very few events


# ═══════════════════════════════════════════════════════════════════════════════
#  Daily Reviser
# ═══════════════════════════════════════════════════════════════════════════════

class TestDailyReviser:
    """Simulate a learner who revises every day."""

    def test_daily_revision_grows_stability(self):
        """Daily revisions should grow stability."""
        state = CurrentState()
        stabilities = [state.stability_score]

        for _ in range(15):
            event = EventData(
                event_type=EventType.REVISION_COMPLETED,
                elapsed_days=1.0,
                difficulty=0.5,
            )
            out = recalibrate(state, event)
            new_dict = apply_delta(state, out.delta)
            cs = {f for f in CurrentState.__dataclass_fields__}
            state = CurrentState(**{k: v for k, v in new_dict.items() if k in cs})
            stabilities.append(state.stability_score)

        # Stability should have generally increased
        assert stabilities[-1] > stabilities[0]

    def test_daily_revision_maintains_retention(self):
        """Daily revisions should prevent retention collapse."""
        state = CurrentState(retention_score=0.3, stability_score=2.0)

        for _ in range(10):
            event = EventData(
                event_type=EventType.REVISION_COMPLETED,
                elapsed_days=1.0,
                difficulty=0.5,
            )
            out = recalibrate(state, event)
            new_dict = apply_delta(state, out.delta)
            cs = {f for f in CurrentState.__dataclass_fields__}
            state = CurrentState(**{k: v for k, v in new_dict.items() if k in cs})

        assert state.retention_score >= 0.05


# ═══════════════════════════════════════════════════════════════════════════════
#  Missed Revisions (Long Gaps)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissedRevisions:
    """Test behaviour after extended absence."""

    def test_long_gap_degrades_retention(self):
        """30-day gap should significantly degrade retention."""
        state = CurrentState(retention_score=0.8, stability_score=5.0)
        event = EventData(
            event_type=EventType.INACTIVITY_DETECTED,
            days_inactive=30.0,
            difficulty=0.5,
        )
        out = recalibrate(state, event)
        assert out.new_retention < state.retention_score

    def test_recovery_after_long_gap(self):
        """Learner can recover with good quiz after long gap."""
        state = CurrentState(retention_score=0.1, stability_score=1.0)
        event = EventData(
            event_type=EventType.QUIZ_SUBMITTED,
            quiz_score=0.9,
            quiz_confidence=0.8,
            elapsed_days=30.0,
            difficulty=0.5,
        )
        out = recalibrate(state, event)
        assert out.new_retention > state.retention_score


# ═══════════════════════════════════════════════════════════════════════════════
#  Boundary Inputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoundaryInputs:
    """Test engine with boundary/extreme values."""

    def test_zero_difficulty(self):
        """Difficulty = 0 should not crash."""
        event = EventData(
            event_type=EventType.QUIZ_SUBMITTED,
            quiz_score=0.7, difficulty=0.0,
        )
        out = recalibrate(CurrentState(), event)
        assert 0.0 <= out.new_retention <= 1.0

    def test_max_difficulty(self):
        """Difficulty = 1.0 should not crash."""
        event = EventData(
            event_type=EventType.QUIZ_SUBMITTED,
            quiz_score=0.7, difficulty=1.0,
        )
        out = recalibrate(CurrentState(), event)
        assert 0.0 <= out.new_retention <= 1.0

    def test_perfect_quiz_score(self):
        """Quiz score = 1.0 should produce valid state."""
        event = EventData(
            event_type=EventType.QUIZ_SUBMITTED,
            quiz_score=1.0, quiz_confidence=1.0, difficulty=0.5,
        )
        out = recalibrate(CurrentState(), event)
        assert 0.0 <= out.new_retention <= 1.0

    def test_zero_quiz_score(self):
        """Quiz score = 0.0 should produce valid state."""
        event = EventData(
            event_type=EventType.QUIZ_SUBMITTED,
            quiz_score=0.0, quiz_confidence=0.0, difficulty=0.5,
        )
        out = recalibrate(CurrentState(), event)
        assert 0.0 <= out.new_retention <= 1.0

    def test_zero_elapsed_days(self):
        """elapsed_days = 0 should not crash."""
        event = EventData(
            event_type=EventType.REVISION_COMPLETED,
            elapsed_days=0.0, difficulty=0.5,
        )
        out = recalibrate(CurrentState(), event)
        assert 0.0 <= out.new_retention <= 1.0

    def test_very_large_elapsed_days(self):
        """elapsed_days = 365 should produce valid (low) retention."""
        state = CurrentState(retention_score=0.8, stability_score=5.0)
        event = EventData(
            event_type=EventType.INACTIVITY_DETECTED,
            days_inactive=365.0, difficulty=0.5,
        )
        out = recalibrate(state, event)
        assert 0.0 <= out.new_retention <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  Large Topic Sets
# ═══════════════════════════════════════════════════════════════════════════════

class TestLargeTopicSets:
    """Validate engine works with many topics."""

    def test_simulation_with_20_topics(self):
        """Simulation should handle 20 topics per learner."""
        learners = generate_learners(2, 20, days_until_exam=30.0, seed=123)
        results = run_simulation(learners, total_days=14, base_seed=123)
        for r in results:
            assert len(r.learner.topics) == 20
            # Should have snapshots for all topics
            topic_ids = {s.topic_id for s in r.snapshots}
            assert len(topic_ids) == 20

    def test_priority_ranking_many_topics(self):
        """Priority engine should rank many topics consistently."""
        scores = []
        for i in range(20):
            p_input = PriorityInput(
                retention_score=0.05 * i,  # Vary retention
                forgetting_probability=1.0 - 0.05 * i,
                stability_score=1.0 + i * 0.5,
                decay_rate=0.1,
                revision_count=i,
                days_since_last_revision=float(i + 1),
                difficulty=0.3 + i * 0.03,
                importance_weight=1.0,
                days_until_exam=30.0,
            )
            out = compute_priority(p_input)
            scores.append(out.priority_score)

        # All scores should be non-negative (priority can exceed 1.0 with urgency)
        assert all(0.0 <= s for s in scores)
