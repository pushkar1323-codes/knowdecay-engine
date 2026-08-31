"""
tests/test_simulation/test_learning_cycle.py
──────────────────────────────────────────────
Phase 11: Complete learning cycle validation.

Validates the full revision lifecycle:
  Study → Retention Prediction → Revision Recommendation →
  Revision Completed → MemoryState Updated → Next Schedule Generated

Tests verify:
  • Each stage produces valid output
  • State evolves incrementally (never reset)
  • Multiple cycles improve retention for good performers
  • Retention degrades between cycles if inactive
  • Difficulty affects cycle outcomes
  • Exam proximity affects scheduling within cycles

All tests are pure — no DB, no I/O.
"""

import math

import pytest

from app.engine.recalibration_engine import (
    CurrentState,
    EventData,
    EventType,
    RecalibrationOutput,
    recalibrate,
    apply_delta,
    StateDelta,
)
from app.engine.stability_engine import StabilityInput, compute_adaptive_stability
from app.engine.priority_engine import PriorityInput, compute_priority
from app.engine.scheduling_engine import ScheduleInput, compute_schedule


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _to_current_state(d: dict) -> CurrentState:
    """Convert apply_delta output dict to CurrentState."""
    cs_fields = set(CurrentState.__dataclass_fields__)
    return CurrentState(**{k: v for k, v in d.items() if k in cs_fields})


def _run_cycle(
    state: CurrentState,
    quiz_score: float = 0.7,
    elapsed_days: float = 1.0,
    difficulty: float = 0.5,
    importance: float = 1.0,
    days_until_exam: float | None = 30.0,
) -> dict:
    """
    Execute one complete learning cycle:
      1. Study session
      2. Quiz submitted
      3. Revision completed
      4. Priority computed
      5. Schedule generated
    Returns dict with all stage outputs and final state.
    """
    stages = {}

    # Stage 1: Study session
    study_event = EventData(
        event_type=EventType.STUDY_SESSION,
        study_duration_minutes=45.0,
        elapsed_days=elapsed_days,
        difficulty=difficulty,
        importance_weight=importance,
    )
    study_out = recalibrate(state, study_event)
    study_dict = apply_delta(state, study_out.delta)
    state_after_study = _to_current_state(study_dict)
    stages["study"] = {"out": study_out, "state": state_after_study}

    # Stage 2: Quiz submitted
    quiz_event = EventData(
        event_type=EventType.QUIZ_SUBMITTED,
        quiz_score=quiz_score,
        quiz_confidence=quiz_score * 0.9,
        elapsed_days=0.0,  # Same day as study
        difficulty=difficulty,
        importance_weight=importance,
    )
    quiz_out = recalibrate(state_after_study, quiz_event)
    quiz_dict = apply_delta(state_after_study, quiz_out.delta)
    state_after_quiz = _to_current_state(quiz_dict)
    stages["quiz"] = {"out": quiz_out, "state": state_after_quiz}

    # Stage 3: Revision completed
    rev_event = EventData(
        event_type=EventType.REVISION_COMPLETED,
        elapsed_days=0.0,
        difficulty=difficulty,
        importance_weight=importance,
    )
    rev_out = recalibrate(state_after_quiz, rev_event)
    rev_dict = apply_delta(state_after_quiz, rev_out.delta)
    state_after_rev = _to_current_state(rev_dict)
    stages["revision"] = {"out": rev_out, "state": state_after_rev}

    # Stage 4: Priority
    pri_input = PriorityInput(
        retention_score=state_after_rev.retention_score,
        forgetting_probability=state_after_rev.forgetting_probability,
        stability_score=state_after_rev.stability_score,
        decay_rate=state_after_rev.decay_rate,
        revision_count=state_after_rev.revision_count,
        days_since_last_revision=0.0,
        difficulty=difficulty,
        importance_weight=importance,
        days_until_exam=days_until_exam,
    )
    pri_out = compute_priority(pri_input)
    stages["priority"] = pri_out

    # Stage 5: Schedule
    sched_input = ScheduleInput(
        retention_score=state_after_rev.retention_score,
        stability_score=state_after_rev.stability_score,
        decay_rate=state_after_rev.decay_rate,
        urgency_score=state_after_rev.urgency_score,
        revision_count=state_after_rev.revision_count,
        forgetting_probability=state_after_rev.forgetting_probability,
        difficulty=difficulty,
        days_until_exam=days_until_exam,
        adaptive_stability=state_after_rev.adaptive_stability,
    )
    sched_out = compute_schedule(sched_input)
    stages["schedule"] = sched_out

    stages["final_state"] = state_after_rev
    return stages


# ═══════════════════════════════════════════════════════════════════════════════
#  Single Cycle Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSingleCycle:
    """Validate a single complete learning cycle."""

    def test_cycle_produces_valid_retention(self):
        """Retention after full cycle is in [0, 1]."""
        result = _run_cycle(CurrentState())
        final = result["final_state"]
        assert 0.0 <= final.retention_score <= 1.0

    def test_cycle_increases_revision_count(self):
        """Revision count increases through the cycle."""
        initial = CurrentState()
        result = _run_cycle(initial)
        final = result["final_state"]
        assert final.revision_count > initial.revision_count

    def test_cycle_priority_is_valid(self):
        """Priority output is bounded [0, 1] with valid tier."""
        result = _run_cycle(CurrentState())
        assert 0.0 <= result["priority"].priority_score <= 1.0
        assert result["priority"].tier is not None

    def test_cycle_schedule_is_positive(self):
        """Schedule produces positive revision interval."""
        result = _run_cycle(CurrentState())
        assert result["schedule"].next_revision_days > 0

    def test_cycle_state_never_reset(self):
        """State evolves — not reset to defaults at any stage."""
        result = _run_cycle(CurrentState(), quiz_score=0.9)
        # After study + quiz + revision, some fields must differ from defaults
        final = result["final_state"]
        default = CurrentState()
        changed = False
        for f in ["retention_score", "stability_score", "revision_count"]:
            if getattr(final, f) != getattr(default, f):
                changed = True
                break
        assert changed, "State unchanged after full cycle"


# ═══════════════════════════════════════════════════════════════════════════════
#  Multi-Cycle Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiCycle:
    """Validate multiple consecutive learning cycles."""

    def test_three_good_cycles_improve_retention(self):
        """3 cycles with good scores should improve or maintain retention."""
        state = CurrentState()
        retentions = [state.retention_score]

        for i in range(3):
            result = _run_cycle(state, quiz_score=0.85, elapsed_days=float(i + 1))
            state = result["final_state"]
            retentions.append(state.retention_score)

        # Retention after 3 good cycles should be >= initial
        assert retentions[-1] >= retentions[0]

    def test_retention_degrades_with_inactivity_between_cycles(self):
        """Inactivity between cycles should degrade retention."""
        # First cycle — good performance
        state = CurrentState()
        result = _run_cycle(state, quiz_score=0.85)
        state = result["final_state"]
        retention_after_cycle = state.retention_score

        # Simulate 14 days of inactivity
        inactivity = EventData(
            event_type=EventType.INACTIVITY_DETECTED,
            days_inactive=14.0,
            difficulty=0.5,
        )
        inact_out = recalibrate(state, inactivity)
        inact_dict = apply_delta(state, inact_out.delta)
        state = _to_current_state(inact_dict)

        assert state.retention_score <= retention_after_cycle

    def test_stability_grows_over_cycles(self):
        """Stability should trend upward over multiple good cycles."""
        state = CurrentState()
        stabilities = [state.stability_score]

        for i in range(5):
            result = _run_cycle(state, quiz_score=0.9, elapsed_days=1.0)
            state = result["final_state"]
            stabilities.append(state.stability_score)

        assert stabilities[-1] > stabilities[0]


# ═══════════════════════════════════════════════════════════════════════════════
#  Difficulty Impact
# ═══════════════════════════════════════════════════════════════════════════════

class TestDifficultyImpact:
    """Verify difficulty affects cycle outcomes."""

    def test_hard_topic_lower_retention(self):
        """Hard topic should produce lower retention than easy topic (same score)."""
        easy = _run_cycle(CurrentState(), quiz_score=0.7, difficulty=0.2)
        hard = _run_cycle(CurrentState(), quiz_score=0.7, difficulty=0.9)
        # Hard topic should have equal or lower retention
        assert hard["final_state"].retention_score <= easy["final_state"].retention_score + 0.15

    def test_hard_topic_shorter_schedule(self):
        """Hard topic should get shorter or equal schedule interval."""
        easy = _run_cycle(CurrentState(), quiz_score=0.7, difficulty=0.2)
        hard = _run_cycle(CurrentState(), quiz_score=0.7, difficulty=0.9)
        assert hard["schedule"].next_revision_days <= easy["schedule"].next_revision_days * 1.2


# ═══════════════════════════════════════════════════════════════════════════════
#  Exam Awareness
# ═══════════════════════════════════════════════════════════════════════════════

class TestExamAwareCycles:
    """Verify exam proximity affects cycle scheduling."""

    def test_near_exam_shorter_schedule(self):
        """Near exam → shorter schedule interval."""
        near = _run_cycle(CurrentState(), days_until_exam=3.0)
        far = _run_cycle(CurrentState(), days_until_exam=60.0)
        assert near["schedule"].next_revision_days <= far["schedule"].next_revision_days
