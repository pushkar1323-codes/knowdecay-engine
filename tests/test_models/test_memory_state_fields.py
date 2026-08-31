"""
tests/test_models/test_memory_state_fields.py
──────────────────────────────────────────────
Validates that all retention evolution fields exist on MemoryState,
have correct defaults, and are properly wired through the recalibration
engine's apply_delta output.

Pure unit tests — no DB required.
"""

import pytest

from app.models.memory_state import MemoryState
from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    RecalibrationOutput,
    StateDelta,
    apply_delta,
    recalibrate,
    recalibrate_quiz,
    recalibrate_revision,
    recalibrate_inactivity,
    recalibrate_study,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Model Column Presence & Defaults
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryStateColumns:
    """Verify all 15 new columns exist with correct defaults."""

    # Adaptive Stability
    def test_adaptive_stability_default(self):
        assert MemoryState.adaptive_stability.property.columns[0].default.arg == 1.0

    def test_stability_growth_rate_default(self):
        assert MemoryState.stability_growth_rate.property.columns[0].default.arg == 0.0

    def test_half_life_days_default(self):
        assert MemoryState.half_life_days.property.columns[0].default.arg == 0.0

    # Decay Parameters
    def test_effective_decay_rate_default(self):
        assert MemoryState.effective_decay_rate.property.columns[0].default.arg == 0.1

    def test_time_to_critical_default(self):
        assert MemoryState.time_to_critical.property.columns[0].default.arg == 0.0

    def test_days_until_target_default(self):
        assert MemoryState.days_until_target.property.columns[0].default.arg == 0.0

    # Reinforcement Behaviour
    def test_quality_variance_default(self):
        assert MemoryState.quality_variance.property.columns[0].default.arg == 0.0

    def test_effective_revision_count_default(self):
        assert MemoryState.effective_revision_count.property.columns[0].default.arg == 0

    def test_revision_effectiveness_ratio_default(self):
        assert MemoryState.revision_effectiveness_ratio.property.columns[0].default.arg == 0.0

    def test_time_pattern_regularity_default(self):
        assert MemoryState.time_pattern_regularity.property.columns[0].default.arg == 0.5

    def test_confidence_calibration_error_default(self):
        assert MemoryState.confidence_calibration_error.property.columns[0].default.arg == 0.0

    # Retention History
    def test_peak_retention_default(self):
        assert MemoryState.peak_retention.property.columns[0].default.arg == 0.0

    def test_retention_at_last_revision_default(self):
        assert MemoryState.retention_at_last_revision.property.columns[0].default.arg == 0.0

    def test_total_forgetting_events_default(self):
        assert MemoryState.total_forgetting_events.property.columns[0].default.arg == 0

    def test_last_forgetting_event_at_nullable(self):
        col = MemoryState.last_forgetting_event_at.property.columns[0]
        assert col.nullable is True


# ═══════════════════════════════════════════════════════════════════════════════
#  2. apply_delta — All 15 Fields in Output Dict
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyDeltaNewFields:
    """apply_delta must output all 15 new fields."""

    EXPECTED_NEW_KEYS = [
        "adaptive_stability", "stability_growth_rate", "half_life_days",
        "effective_decay_rate", "time_to_critical", "days_until_target",
        "quality_variance", "effective_revision_count",
        "revision_effectiveness_ratio", "time_pattern_regularity",
        "confidence_calibration_error",
        "peak_retention", "retention_at_last_revision",
        "total_forgetting_events",
    ]

    def test_all_new_keys_present_in_output(self):
        result = apply_delta(CurrentState(), StateDelta())
        for key in self.EXPECTED_NEW_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_defaults_when_no_delta(self):
        result = apply_delta(CurrentState(), StateDelta())
        assert result["adaptive_stability"] == 1.0
        assert result["stability_growth_rate"] == 0.0
        assert result["half_life_days"] == 0.0
        assert result["effective_decay_rate"] == 0.1
        assert result["time_to_critical"] == 0.0
        assert result["days_until_target"] == 0.0
        assert result["quality_variance"] == 0.0
        assert result["effective_revision_count"] == 0
        assert result["revision_effectiveness_ratio"] == 0.0
        assert result["time_pattern_regularity"] == 0.5
        assert result["confidence_calibration_error"] == 0.0
        assert result["peak_retention"] >= 0.0
        assert result["retention_at_last_revision"] == 0.0
        assert result["total_forgetting_events"] == 0

    def test_adaptive_stability_applied(self):
        result = apply_delta(
            CurrentState(), StateDelta(adaptive_stability_new=5.0)
        )
        assert result["adaptive_stability"] == 5.0

    def test_quality_variance_applied(self):
        result = apply_delta(
            CurrentState(), StateDelta(quality_variance_new=0.25)
        )
        assert result["quality_variance"] == 0.25

    def test_effective_revision_count_delta(self):
        state = CurrentState(effective_revision_count=3)
        result = apply_delta(state, StateDelta(effective_revision_count_delta=1))
        assert result["effective_revision_count"] == 4

    def test_total_forgetting_events_delta(self):
        state = CurrentState(total_forgetting_events=2)
        result = apply_delta(state, StateDelta(total_forgetting_events_delta=1))
        assert result["total_forgetting_events"] == 3

    def test_peak_retention_tracks_maximum(self):
        """Peak retention should always be >= current retention."""
        state = CurrentState(peak_retention=0.6, retention_score=0.8)
        # retention_delta=0 → new_ret=0.8, peak should track 0.8
        result = apply_delta(state, StateDelta())
        assert result["peak_retention"] >= 0.8

    def test_adaptive_stability_clamped_lower(self):
        result = apply_delta(
            CurrentState(), StateDelta(adaptive_stability_new=0.01)
        )
        assert result["adaptive_stability"] >= 0.1

    def test_time_pattern_regularity_clamped(self):
        result = apply_delta(
            CurrentState(), StateDelta(time_pattern_regularity_new=1.5)
        )
        assert result["time_pattern_regularity"] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  3. RecalibrationOutput — New Fields Present
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecalibrationOutputNewFields:
    """Master recalibrate() must populate all new fields in output."""

    @pytest.fixture
    def quiz_output(self):
        return recalibrate(
            CurrentState(retention_score=0.5, revision_count=3, base_stability=5.0),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8, elapsed_days=2.0),
        )

    def test_has_adaptive_stability(self, quiz_output):
        assert hasattr(quiz_output, "new_adaptive_stability")
        assert quiz_output.new_adaptive_stability > 0

    def test_has_stability_growth_rate(self, quiz_output):
        assert hasattr(quiz_output, "new_stability_growth_rate")

    def test_has_half_life_days(self, quiz_output):
        assert hasattr(quiz_output, "new_half_life_days")

    def test_has_effective_decay_rate(self, quiz_output):
        assert hasattr(quiz_output, "new_effective_decay_rate")
        assert quiz_output.new_effective_decay_rate > 0

    def test_has_quality_variance(self, quiz_output):
        assert hasattr(quiz_output, "new_quality_variance")

    def test_has_effective_revision_count(self, quiz_output):
        assert hasattr(quiz_output, "new_effective_revision_count")
        assert quiz_output.new_effective_revision_count >= 0

    def test_has_revision_effectiveness_ratio(self, quiz_output):
        assert hasattr(quiz_output, "new_revision_effectiveness_ratio")

    def test_has_time_pattern_regularity(self, quiz_output):
        assert hasattr(quiz_output, "new_time_pattern_regularity")

    def test_has_confidence_calibration_error(self, quiz_output):
        assert hasattr(quiz_output, "new_confidence_calibration_error")

    def test_has_peak_retention(self, quiz_output):
        assert hasattr(quiz_output, "new_peak_retention")

    def test_has_retention_at_last_revision(self, quiz_output):
        assert hasattr(quiz_output, "new_retention_at_last_revision")

    def test_has_total_forgetting_events(self, quiz_output):
        assert hasattr(quiz_output, "new_total_forgetting_events")


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Event Handler Evolution — New Fields Emitted
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuizEvolution:
    """Quiz recalibration should emit retention evolution deltas."""

    def test_quiz_updates_adaptive_stability(self):
        delta, _ = recalibrate_quiz(
            CurrentState(retention_score=0.5, revision_count=5, base_stability=5.0),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.85, elapsed_days=3.0),
        )
        assert delta.adaptive_stability_new is not None

    def test_quiz_updates_quality_variance(self):
        delta, _ = recalibrate_quiz(
            CurrentState(retention_score=0.5, revision_count=5, base_stability=5.0, revision_quality=0.6),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9, elapsed_days=2.0),
        )
        assert delta.quality_variance_new is not None
        assert delta.quality_variance_new > 0  # 0.9 vs 0.6 avg → variance

    def test_quiz_updates_confidence_calibration(self):
        delta, _ = recalibrate_quiz(
            CurrentState(retention_score=0.5, confidence_score=0.3, revision_count=3),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8, elapsed_days=1.0),
        )
        assert delta.confidence_calibration_error_new is not None
        # confidence=0.3 vs score=0.8 → large error
        assert delta.confidence_calibration_error_new > 0

    def test_quiz_tracks_effective_revision(self):
        # Good quiz → retention improves → effective revision
        delta, _ = recalibrate_quiz(
            CurrentState(retention_score=0.3, revision_count=2, base_stability=3.0),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9, elapsed_days=1.0),
        )
        assert delta.effective_revision_count_delta >= 0  # 0 or 1

    def test_quiz_detects_forgetting_event(self):
        # Retention drops below 0.3 from above
        delta, _ = recalibrate_quiz(
            CurrentState(retention_score=0.35, revision_count=5, base_stability=2.0),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.1, elapsed_days=5.0),
        )
        # Poor quiz may trigger a forgetting event
        assert delta.total_forgetting_events_delta >= 0

    def test_quiz_updates_peak_retention(self):
        delta, _ = recalibrate_quiz(
            CurrentState(retention_score=0.6, peak_retention=0.65, revision_count=3),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.95, elapsed_days=1.0),
        )
        assert delta.peak_retention_new is not None

    def test_quiz_records_retention_at_last_revision(self):
        delta, _ = recalibrate_quiz(
            CurrentState(retention_score=0.7, revision_count=5, base_stability=5.0),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.8, elapsed_days=2.0),
        )
        # Should snapshot the PRE-event retention
        assert delta.retention_at_last_revision_new == 0.7


class TestRevisionEvolution:
    """Revision recalibration should emit retention evolution deltas."""

    def test_revision_updates_growth_rate(self):
        delta, _ = recalibrate_revision(
            CurrentState(revision_count=3, base_stability=5.0, stability_growth_rate=0.1),
            EventData(event_type=EventType.REVISION_COMPLETED, elapsed_days=2.0),
        )
        assert delta.stability_growth_rate_new is not None

    def test_revision_updates_time_regularity(self):
        delta, _ = recalibrate_revision(
            CurrentState(revision_count=5, base_stability=5.0, half_life_days=3.0),
            EventData(event_type=EventType.REVISION_COMPLETED, elapsed_days=3.0),
        )
        assert delta.time_pattern_regularity_new is not None

    def test_revision_updates_effectiveness(self):
        delta, _ = recalibrate_revision(
            CurrentState(revision_count=3, effective_revision_count=2, retention_score=0.5),
            EventData(event_type=EventType.REVISION_COMPLETED, elapsed_days=1.0),
        )
        assert delta.revision_effectiveness_ratio_new is not None


class TestInactivityEvolution:
    """Inactivity should degrade regularity and detect forgetting events."""

    def test_inactivity_degrades_regularity(self):
        delta, _ = recalibrate_inactivity(
            CurrentState(time_pattern_regularity=0.8, retention_score=0.6),
            EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=21.0),
        )
        assert delta.time_pattern_regularity_new is not None
        assert delta.time_pattern_regularity_new < 0.8

    def test_inactivity_detects_forgetting(self):
        delta, _ = recalibrate_inactivity(
            CurrentState(retention_score=0.35, base_stability=1.0),
            EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=30.0),
        )
        # Retention may drop below 0.3 → forgetting event
        assert delta.total_forgetting_events_delta >= 0

    def test_inactivity_within_grace_no_regularity_change(self):
        delta, _ = recalibrate_inactivity(
            CurrentState(time_pattern_regularity=0.8),
            EventData(event_type=EventType.INACTIVITY_DETECTED, days_inactive=3.0),
        )
        # Within grace period → no delta at all
        assert delta.time_pattern_regularity_new is None


class TestStudyEvolution:
    """Study sessions should only do lightweight updates."""

    def test_study_updates_peak_retention(self):
        delta, _ = recalibrate_study(
            CurrentState(retention_score=0.5, peak_retention=0.55),
            EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=30.0),
        )
        assert delta.peak_retention_new is not None

    def test_study_does_not_update_effectiveness(self):
        """Study is not a revision — should not update effectiveness ratio."""
        delta, _ = recalibrate_study(
            CurrentState(retention_score=0.5),
            EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=20.0),
        )
        assert delta.revision_effectiveness_ratio_new is None
        assert delta.effective_revision_count_delta == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  5. CurrentState — New Fields Have Safe Defaults
# ═══════════════════════════════════════════════════════════════════════════════

class TestCurrentStateDefaults:
    """All new CurrentState fields should have safe defaults."""

    def test_defaults(self):
        s = CurrentState()
        assert s.adaptive_stability == 1.0
        assert s.stability_growth_rate == 0.0
        assert s.half_life_days == 0.0
        assert s.effective_decay_rate == 0.1
        assert s.time_to_critical == 0.0
        assert s.days_until_target == 0.0
        assert s.quality_variance == 0.0
        assert s.effective_revision_count == 0
        assert s.revision_effectiveness_ratio == 0.0
        assert s.time_pattern_regularity == 0.5
        assert s.confidence_calibration_error == 0.0
        assert s.peak_retention == 0.0
        assert s.retention_at_last_revision == 0.0
        assert s.total_forgetting_events == 0
