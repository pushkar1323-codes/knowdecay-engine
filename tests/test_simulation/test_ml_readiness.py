"""
tests/test_simulation/test_ml_readiness.py
────────────────────────────────────────────
Phase 11: ML readiness validation.

Validates that MemoryState and engine outputs collect all data fields
required for future ML training pipelines:
  • Learning history fields
  • Revision history fields
  • Retention trajectory fields
  • Quiz performance fields
  • MemoryState evolution fields

Does NOT implement ML. Validates that the data substrate exists
and is populated during simulation.

All tests are pure — no DB, no I/O.
"""

import pytest

from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    RecalibrationOutput,
    StateDelta,
    ChangeReason,
    recalibrate,
    apply_delta,
)
from simulation.learner_profiles import generate_learners
from simulation.timeline_simulator import run_simulation


# ═══════════════════════════════════════════════════════════════════════════════
#  ML Feature Fields on CurrentState
# ═══════════════════════════════════════════════════════════════════════════════

class TestMLFeatureFields:
    """Verify CurrentState carries all fields needed for future ML features."""

    # Fields required for an ML training row
    ML_TRAINING_FIELDS = [
        # Target variables
        "retention_score",
        "forgetting_probability",
        # Temporal features
        "decay_rate",
        "effective_decay_rate",
        "half_life_days",
        "time_to_critical",
        "days_until_target",
        # Stability features
        "stability_score",
        "base_stability",
        "adaptive_stability",
        "stability_growth_rate",
        # Learner behaviour features
        "revision_count",
        "effective_revision_count",
        "revision_strength",
        "revision_quality",
        "revision_effectiveness_ratio",
        # Performance features
        "confidence_score",
        "confidence_calibration_error",
        "quality_variance",
        "performance_trend",
        # Pattern features
        "time_pattern_regularity",
        # History features
        "peak_retention",
        "retention_at_last_revision",
        "total_forgetting_events",
        # Context features
        "difficulty_factor",
        "urgency_score",
    ]

    @pytest.mark.parametrize("field", ML_TRAINING_FIELDS)
    def test_field_exists_on_current_state(self, field):
        """ML training field exists as a CurrentState attribute."""
        assert field in CurrentState.__dataclass_fields__, (
            f"Missing ML field: {field}"
        )

    def test_all_ml_fields_populated_after_quiz(self):
        """After a quiz event, all ML fields are accessible (not None)."""
        state = CurrentState()
        event = EventData(
            event_type=EventType.QUIZ_SUBMITTED,
            quiz_score=0.75,
            quiz_confidence=0.7,
            elapsed_days=3.0,
            difficulty=0.5,
        )
        out = recalibrate(state, event)
        new_dict = apply_delta(state, out.delta)

        for field in self.ML_TRAINING_FIELDS:
            assert field in new_dict, f"Field {field} missing from apply_delta output"
            assert new_dict[field] is not None, f"Field {field} is None"


# ═══════════════════════════════════════════════════════════════════════════════
#  RecalibrationOutput Audit Trail (ML Explainability)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMLExplainability:
    """Verify recalibration outputs include data for ML explainability."""

    def test_change_reasons_populated(self):
        """ChangeReason list is non-empty after meaningful event."""
        out = recalibrate(
            CurrentState(retention_score=0.5),
            EventData(event_type=EventType.QUIZ_SUBMITTED, quiz_score=0.9, difficulty=0.5),
        )
        assert len(out.changes) > 0

    def test_change_reason_has_required_fields(self):
        """Each ChangeReason has field, old_value, new_value, reason."""
        out = recalibrate(
            CurrentState(),
            EventData(event_type=EventType.REVISION_COMPLETED, difficulty=0.5),
        )
        for cr in out.changes:
            assert isinstance(cr.field, str) and len(cr.field) > 0
            assert isinstance(cr.old_value, (int, float))
            assert isinstance(cr.new_value, (int, float))
            assert isinstance(cr.reason, str) and len(cr.reason) > 0

    def test_summary_is_non_empty(self):
        """Recalibration summary string is populated."""
        out = recalibrate(
            CurrentState(),
            EventData(event_type=EventType.STUDY_SESSION, study_duration_minutes=30.0),
        )
        assert isinstance(out.summary, str) and len(out.summary) > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  Simulation Data Collection for ML
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimulationMLDataCollection:
    """Verify simulation produces data usable for ML training."""

    @pytest.fixture(scope="class")
    def sim_results(self):
        learners = generate_learners(3, 4, days_until_exam=30.0, seed=321)
        return run_simulation(learners, total_days=20, base_seed=321)

    def test_snapshots_contain_retention_trajectory(self, sim_results):
        """Each learner has daily retention snapshots (trajectory data)."""
        for r in sim_results:
            assert len(r.snapshots) > 0
            # Verify snapshots span multiple days
            days = {s.day for s in r.snapshots}
            assert len(days) >= 10  # At least 10 distinct days

    def test_final_states_contain_all_fields(self, sim_results):
        """Final states contain all ML-relevant fields."""
        key_fields = [
            "retention_score", "stability_score", "decay_rate",
            "revision_count", "adaptive_stability", "peak_retention",
        ]
        for r in sim_results:
            for tid, state_dict in r.final_states.items():
                for f in key_fields:
                    assert f in state_dict, (
                        f"Field {f} missing from final state of {r.learner.name}"
                    )

    def test_event_counts_tracked(self, sim_results):
        """Event type counts are tracked for ML feature engineering."""
        for r in sim_results:
            # event_counts is a dict mapping event_type -> count
            assert isinstance(r.event_counts, dict)
            # At least some events should have occurred
            if r.total_events > 0:
                assert len(r.event_counts) > 0
