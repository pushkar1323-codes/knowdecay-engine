"""
tests/test_engine/test_recalibration_engine.py
─────────────────────────────────────────────────
Unit tests for the recalibration engine — pure functions, NO database required.

Test categories:
  1.  Quiz recalibration — strongest signal, full retention recompute
  2.  Revision recalibration — reinforcement, diminishing returns
  3.  Study session — modest retention boost, saturation
  4.  Inactivity — degradation, grace period, gradual loss
  5.  Apply delta — state evolution, clamping
  6.  Master recalibrate — end-to-end routing
  7.  Audit trail — change reasons, summary generation
  8.  Edge cases — zero state, extreme values
  9.  State preservation — never resets, only evolves
  10. Monotonicity — directional invariants
"""

import pytest

from app.engine.recalibration_engine import (
    ChangeReason,
    CurrentState,
    EventData,
    EventType,
    RecalibrationOutput,
    StateDelta,
    apply_delta,
    recalibrate,
    recalibrate_inactivity,
    recalibrate_quiz,
    recalibrate_revision,
    recalibrate_study,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper
# ═══════════════════════════════════════════════════════════════════════════════

def _default_state(**kwargs) -> CurrentState:
    defaults = dict(
        retention_score=0.5,
        stability_score=3.0,
        decay_rate=0.1,
        confidence_score=0.5,
        revision_strength=0.3,
        revision_count=3,
        forgetting_probability=0.5,
        urgency_score=0.3,
    )
    defaults.update(kwargs)
    return CurrentState(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Quiz Recalibration
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuizRecalibration:
    def test_good_quiz_improves_retention(self):
        state = _default_state(retention_score=0.5)
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9)
        delta, changes = recalibrate_quiz(state, event)
        assert delta.retention_delta > 0

    def test_poor_quiz_may_lower_retention(self):
        state = _default_state(retention_score=0.7)
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.1, elapsed_days=5.0)
        delta, changes = recalibrate_quiz(state, event)
        # Poor quiz with decay should reduce retention
        assert delta.retention_delta <= 0.05  # may be slightly positive from blending

    def test_quiz_increments_revision_count(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.7)
        delta, _ = recalibrate_quiz(state, event)
        assert delta.revision_count_delta == 1

    def test_quiz_updates_decay_rate(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8)
        delta, _ = recalibrate_quiz(state, event)
        assert delta.decay_rate_new is not None

    def test_good_quiz_lowers_urgency(self):
        state = _default_state(urgency_score=0.5)
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9)
        delta, _ = recalibrate_quiz(state, event)
        assert delta.urgency_delta < 0

    def test_poor_quiz_raises_urgency(self):
        state = _default_state(urgency_score=0.3)
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.1)
        delta, _ = recalibrate_quiz(state, event)
        assert delta.urgency_delta > 0

    def test_quiz_adds_revision_strength(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.7)
        delta, _ = recalibrate_quiz(state, event)
        assert delta.revision_strength_delta > 0

    def test_quiz_updates_forgetting_probability(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8)
        delta, _ = recalibrate_quiz(state, event)
        assert delta.forgetting_probability_new is not None

    def test_good_quiz_extends_stability(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9)
        delta, _ = recalibrate_quiz(state, event)
        assert delta.stability_delta > 0

    def test_poor_quiz_contracts_stability(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.1)
        delta, _ = recalibrate_quiz(state, event)
        assert delta.stability_delta < 0


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Revision Recalibration
# ═══════════════════════════════════════════════════════════════════════════════

class TestRevisionRecalibration:
    def test_revision_boosts_retention(self):
        state = _default_state(retention_score=0.5)
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        delta, _ = recalibrate_revision(state, event)
        assert delta.retention_delta > 0

    def test_revision_increments_count(self):
        state = _default_state()
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        delta, _ = recalibrate_revision(state, event)
        assert delta.revision_count_delta == 1

    def test_revision_extends_stability(self):
        state = _default_state()
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        delta, _ = recalibrate_revision(state, event)
        assert delta.stability_delta > 0

    def test_diminishing_returns(self):
        """More revisions → smaller retention boost."""
        state_few = _default_state(revision_count=1)
        state_many = _default_state(revision_count=20)
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        delta_few, _ = recalibrate_revision(state_few, event)
        delta_many, _ = recalibrate_revision(state_many, event)
        assert delta_few.retention_delta > delta_many.retention_delta

    def test_revision_lowers_decay(self):
        state = _default_state()
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        delta, _ = recalibrate_revision(state, event)
        assert delta.decay_rate_new is not None
        assert delta.decay_rate_new < state.decay_rate

    def test_revision_lowers_urgency(self):
        state = _default_state(urgency_score=0.5)
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        delta, _ = recalibrate_revision(state, event)
        assert delta.urgency_delta < 0


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Study Session
# ═══════════════════════════════════════════════════════════════════════════════

class TestStudyRecalibration:
    def test_study_boosts_retention(self):
        state = _default_state(retention_score=0.5)
        event = EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=30)
        delta, _ = recalibrate_study(state, event)
        assert delta.retention_delta > 0

    def test_study_does_not_increment_revision(self):
        state = _default_state()
        event = EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=30)
        delta, _ = recalibrate_study(state, event)
        assert delta.revision_count_delta == 0

    def test_study_saturation(self):
        """Studying 120 min should not give 2× the boost of 60 min."""
        state = _default_state()
        event_60 = EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=60)
        event_120 = EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=120)
        delta_60, _ = recalibrate_study(state, event_60)
        delta_120, _ = recalibrate_study(state, event_120)
        assert delta_60.retention_delta == delta_120.retention_delta  # saturates at 60 min

    def test_zero_duration_minimal_change(self):
        state = _default_state()
        event = EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=0)
        delta, _ = recalibrate_study(state, event)
        assert delta.retention_delta == 0.0

    def test_study_adds_strength(self):
        state = _default_state()
        event = EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=30)
        delta, _ = recalibrate_study(state, event)
        assert delta.revision_strength_delta > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Inactivity
# ═══════════════════════════════════════════════════════════════════════════════

class TestInactivityRecalibration:
    def test_within_grace_no_change(self):
        state = _default_state(retention_score=0.6)
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=5)
        delta, _ = recalibrate_inactivity(state, event)
        assert delta.retention_delta == 0.0
        assert delta.urgency_delta == 0.0

    def test_past_grace_degrades_retention(self):
        state = _default_state(retention_score=0.6)
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=20)
        delta, _ = recalibrate_inactivity(state, event)
        assert delta.retention_delta < 0

    def test_past_grace_increases_urgency(self):
        state = _default_state(urgency_score=0.3)
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=20)
        delta, _ = recalibrate_inactivity(state, event)
        assert delta.urgency_delta > 0

    def test_inactivity_worsens_decay_rate(self):
        state = _default_state()
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=30)
        delta, _ = recalibrate_inactivity(state, event)
        assert delta.decay_rate_new is not None
        assert delta.decay_rate_new > state.decay_rate

    def test_inactivity_contracts_stability(self):
        state = _default_state(stability_score=5.0)
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=25)
        delta, _ = recalibrate_inactivity(state, event)
        assert delta.stability_delta < 0

    def test_longer_inactivity_more_degradation(self):
        state = _default_state(retention_score=0.7)
        event_short = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=10)
        event_long = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=30)
        delta_short, _ = recalibrate_inactivity(state, event_short)
        delta_long, _ = recalibrate_inactivity(state, event_long)
        assert delta_long.retention_delta < delta_short.retention_delta

    def test_never_below_floor(self):
        state = _default_state(retention_score=0.1)
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=100)
        delta, _ = recalibrate_inactivity(state, event)
        new_ret = state.retention_score + delta.retention_delta
        assert new_ret >= 0.05  # RETENTION_FLOOR


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Apply Delta
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyDelta:
    def test_applies_retention_delta(self):
        state = _default_state(retention_score=0.5)
        delta = StateDelta(retention_delta=0.1)
        result = apply_delta(state, delta)
        assert result["retention_score"] == pytest.approx(0.6, abs=0.01)

    def test_clamps_retention_ceiling(self):
        state = _default_state(retention_score=0.95)
        delta = StateDelta(retention_delta=0.2)
        result = apply_delta(state, delta)
        assert result["retention_score"] <= 1.0

    def test_clamps_retention_floor(self):
        state = _default_state(retention_score=0.1)
        delta = StateDelta(retention_delta=-0.2)
        result = apply_delta(state, delta)
        assert result["retention_score"] >= 0.05

    def test_increments_revision_count(self):
        state = _default_state(revision_count=5)
        delta = StateDelta(revision_count_delta=1)
        result = apply_delta(state, delta)
        assert result["revision_count"] == 6

    def test_absolute_decay_rate_replacement(self):
        state = _default_state(decay_rate=0.1)
        delta = StateDelta(decay_rate_new=0.05)
        result = apply_delta(state, delta)
        assert result["decay_rate"] == pytest.approx(0.05, abs=0.001)

    def test_none_decay_keeps_original(self):
        state = _default_state(decay_rate=0.1)
        delta = StateDelta(decay_rate_new=None)
        result = apply_delta(state, delta)
        assert result["decay_rate"] == pytest.approx(0.1, abs=0.001)

    def test_urgency_clamped_to_01(self):
        state = _default_state(urgency_score=0.9)
        delta = StateDelta(urgency_delta=0.5)
        result = apply_delta(state, delta)
        assert result["urgency_score"] <= 1.0

    def test_all_fields_present(self):
        state = _default_state()
        delta = StateDelta()
        result = apply_delta(state, delta)
        expected_keys = {
            "retention_score", "stability_score", "decay_rate",
            "confidence_score", "revision_strength", "revision_count",
            "forgetting_probability", "urgency_score",
            # Adaptive forgetting curve fields (Phase 8.5)
            "base_stability", "revision_quality",
            "difficulty_factor", "performance_trend",
            # Retention evolution fields
            "adaptive_stability", "stability_growth_rate", "half_life_days",
            "effective_decay_rate", "time_to_critical", "days_until_target",
            "quality_variance", "effective_revision_count",
            "revision_effectiveness_ratio", "time_pattern_regularity",
            "confidence_calibration_error",
            "peak_retention", "retention_at_last_revision",
            "total_forgetting_events",
        }
        assert set(result.keys()) == expected_keys


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Master recalibrate — End-to-End
# ═══════════════════════════════════════════════════════════════════════════════

class TestMasterRecalibrate:
    def test_quiz_event(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8)
        out = recalibrate(state, event)
        assert isinstance(out, RecalibrationOutput)
        assert out.event_type == EventType.QUIZ_SUBMITTED
        assert out.new_revision_count == state.revision_count + 1

    def test_revision_event(self):
        state = _default_state()
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        out = recalibrate(state, event)
        assert out.event_type == EventType.REVISION_COMPLETED
        assert out.new_retention >= state.retention_score

    def test_study_event(self):
        state = _default_state()
        event = EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=30)
        out = recalibrate(state, event)
        assert out.event_type == EventType.STUDY_SESSION
        assert out.new_revision_count == state.revision_count  # study doesn't count

    def test_inactivity_event(self):
        state = _default_state()
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=20)
        out = recalibrate(state, event)
        assert out.event_type == EventType.INACTIVITY_DETECTED
        assert out.new_retention <= state.retention_score

    def test_output_has_delta(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.7)
        out = recalibrate(state, event)
        assert isinstance(out.delta, StateDelta)

    def test_output_has_changes(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.7)
        out = recalibrate(state, event)
        assert isinstance(out.changes, list)
        assert len(out.changes) > 0

    def test_output_has_summary(self):
        state = _default_state()
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        out = recalibrate(state, event)
        assert len(out.summary) > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Audit Trail
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditTrail:
    def test_quiz_generates_change_reasons(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8)
        _, changes = recalibrate_quiz(state, event)
        assert len(changes) >= 2  # at least decay_rate + revision_count
        assert all(isinstance(c, ChangeReason) for c in changes)

    def test_change_reason_has_fields(self):
        state = _default_state()
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        _, changes = recalibrate_revision(state, event)
        for c in changes:
            assert len(c.field) > 0
            assert len(c.reason) > 0

    def test_inactivity_grace_period_noted(self):
        state = _default_state()
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=3)
        _, changes = recalibrate_inactivity(state, event)
        assert any("grace" in c.reason.lower() for c in changes)

    def test_summary_contains_event_type(self):
        state = _default_state()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.7)
        out = recalibrate(state, event)
        assert "quiz" in out.summary.lower() or "Quiz" in out.summary


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_zero_state(self):
        state = CurrentState()
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.5)
        out = recalibrate(state, event)
        assert isinstance(out, RecalibrationOutput)
        assert out.new_retention >= 0.05

    def test_perfect_retention_quiz(self):
        state = _default_state(retention_score=1.0)
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=1.0)
        out = recalibrate(state, event)
        assert out.new_retention <= 1.0

    def test_floor_retention_revision(self):
        state = _default_state(retention_score=0.05)
        event = EventData(event_type=EventType.REVISION_COMPLETED)
        out = recalibrate(state, event)
        assert out.new_retention >= 0.05

    def test_extreme_inactivity(self):
        state = _default_state(retention_score=0.8)
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=365)
        out = recalibrate(state, event)
        assert out.new_retention >= 0.05
        assert out.new_urgency <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  9. State Preservation
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatePreservation:
    """Verify that recalibration EVOLVES state, never RESETS it."""

    def test_revision_count_never_decreases(self):
        state = _default_state(revision_count=10)
        for event_type in [EventType.QUIZ_SUBMITTED, EventType.REVISION_COMPLETED,
                           EventType.STUDY_SESSION, EventType.INACTIVITY_DETECTED]:
            event = EventData(event_type=event_type, quiz_score=0.5, study_duration_minutes=30, days_inactive=5)
            out = recalibrate(state, event)
            assert out.new_revision_count >= state.revision_count

    def test_revision_strength_never_decreases(self):
        state = _default_state(revision_strength=1.0)
        for event_type in [EventType.QUIZ_SUBMITTED, EventType.REVISION_COMPLETED,
                           EventType.STUDY_SESSION, EventType.INACTIVITY_DETECTED]:
            event = EventData(event_type=event_type, quiz_score=0.5, study_duration_minutes=30, days_inactive=5)
            out = recalibrate(state, event)
            assert out.new_revision_strength >= state.revision_strength

    def test_retention_never_exceeds_ceiling(self):
        state = _default_state(retention_score=0.99)
        event = EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=1.0)
        out = recalibrate(state, event)
        assert out.new_retention <= 1.0

    def test_retention_never_below_floor(self):
        state = _default_state(retention_score=0.1)
        event = EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=100)
        out = recalibrate(state, event)
        assert out.new_retention >= 0.05


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Monotonicity Properties
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    """Verify directional invariants of the recalibration engine."""

    def test_higher_quiz_score_higher_retention(self):
        state = _default_state()
        out_low = recalibrate(state, EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.2))
        out_high = recalibrate(state, EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9))
        assert out_high.new_retention > out_low.new_retention

    def test_revision_always_improves_or_maintains(self):
        state = _default_state()
        out = recalibrate(state, EventData(event_type=EventType.REVISION_COMPLETED))
        assert out.new_retention >= state.retention_score

    def test_more_study_more_retention(self):
        state = _default_state()
        out_short = recalibrate(state, EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=5))
        out_long = recalibrate(state, EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=45))
        assert out_long.new_retention >= out_short.new_retention

    def test_more_inactivity_less_retention(self):
        state = _default_state(retention_score=0.7)
        out_short = recalibrate(state, EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=10))
        out_long = recalibrate(state, EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=30))
        assert out_long.new_retention <= out_short.new_retention

    def test_good_quiz_lowers_urgency_vs_bad(self):
        state = _default_state(urgency_score=0.5)
        out_good = recalibrate(state, EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9))
        out_bad = recalibrate(state, EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.1))
        assert out_good.new_urgency < out_bad.new_urgency
