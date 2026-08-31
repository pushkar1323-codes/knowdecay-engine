"""
tests/test_simulation/test_scheduler_validation.py
────────────────────────────────────────────────────
Phase 11: Scheduler engine validation under realistic scenarios.

Validates:
  • Revision intervals adapt to retention
  • Exam-aware scheduling compresses intervals
  • No duplicate or impossible schedules
  • Intelligent spacing between revisions
  • High-stability topics get longer intervals
  • Low-retention topics get shorter intervals
"""

import math

import pytest

from app.engine.scheduling_engine import ScheduleInput, compute_schedule
from app.engine.recalibration_engine import (
    CurrentState, EventData, EventType, recalibrate, apply_delta, StateDelta,
)
from app.engine.stability_engine import StabilityInput, compute_adaptive_stability


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _schedule(
    retention: float = 0.5,
    stability: float = 2.0,
    decay: float = 0.1,
    urgency: float = 0.3,
    rev_count: int = 1,
    forg_prob: float = 0.5,
    difficulty: float = 0.5,
    days_until_exam: float | None = None,
    days_since_last: float = 1.0,
    adaptive_stability: float | None = None,
) -> float:
    """Shortcut to compute next_revision_days."""
    si = ScheduleInput(
        retention_score=retention,
        stability_score=stability,
        decay_rate=decay,
        urgency_score=urgency,
        revision_count=rev_count,
        forgetting_probability=forg_prob,
        difficulty=difficulty,
        days_until_exam=days_until_exam,
        days_since_last_revision=days_since_last,
        adaptive_stability=adaptive_stability,
    )
    return compute_schedule(si).next_revision_days


# ═══════════════════════════════════════════════════════════════════════════════
#  Revision Interval Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRevisionIntervals:
    """Verify interval computation is sane."""

    def test_interval_always_positive(self):
        """Next revision interval must always be > 0."""
        for r in [0.0, 0.05, 0.2, 0.5, 0.8, 1.0]:
            for s in [0.5, 1.0, 5.0, 20.0]:
                interval = _schedule(retention=r, stability=s)
                assert interval > 0, f"Negative interval for R={r}, S={s}"

    def test_interval_bounded(self):
        """Intervals should not exceed reasonable bounds."""
        # Even best-case, interval shouldn't be infinite
        interval = _schedule(retention=0.99, stability=30.0, rev_count=50)
        assert interval < 365, "Interval exceeds 1 year"

    def test_low_retention_shorter_interval(self):
        """Low retention → shorter interval than high retention."""
        low = _schedule(retention=0.2, stability=2.0)
        high = _schedule(retention=0.8, stability=2.0)
        assert low < high, f"Low R interval {low} >= high R interval {high}"

    def test_high_stability_longer_interval(self):
        """High stability → longer intervals."""
        low_s = _schedule(retention=0.5, stability=1.0)
        high_s = _schedule(retention=0.5, stability=10.0)
        assert high_s > low_s, f"High S interval {high_s} <= low S interval {low_s}"

    def test_more_revisions_longer_interval(self):
        """More successful revisions → tends toward longer intervals."""
        few = _schedule(retention=0.6, stability=3.0, rev_count=1)
        many = _schedule(retention=0.6, stability=3.0, rev_count=20)
        # Many revisions with same retention suggests stability, so interval >= few
        assert many >= few * 0.8, "Many revisions produced much shorter interval"


# ═══════════════════════════════════════════════════════════════════════════════
#  Exam-Aware Scheduling
# ═══════════════════════════════════════════════════════════════════════════════

class TestExamAwareScheduling:
    """Verify exam proximity compresses intervals."""

    def test_near_exam_shorter_interval(self):
        """Near exam → shorter interval than distant exam."""
        near = _schedule(retention=0.5, days_until_exam=3.0)
        far = _schedule(retention=0.5, days_until_exam=60.0)
        assert near < far, f"Near exam {near} >= far exam {far}"

    def test_no_exam_reasonable_interval(self):
        """Without exam, interval should still be reasonable."""
        interval = _schedule(retention=0.5, days_until_exam=None)
        assert 0 < interval < 90

    def test_exam_tomorrow_urgent(self):
        """Exam tomorrow → very short interval."""
        interval = _schedule(retention=0.5, days_until_exam=1.0)
        assert interval < 2.0, f"Day-before-exam interval {interval} too long"

    def test_exam_doesnt_produce_impossible_schedule(self):
        """Exam scheduling should never produce interval > days_until_exam."""
        for days in [1.0, 3.0, 7.0, 14.0]:
            interval = _schedule(retention=0.3, days_until_exam=days)
            # Interval should be at most the exam window
            assert interval <= days + 1.0, (
                f"Interval {interval} exceeds exam window {days}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
#  Scheduling Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchedulingEdgeCases:
    """Edge cases for the scheduler."""

    def test_zero_retention_floor_schedule(self):
        """Even at retention floor (0.05), schedule returns valid interval."""
        interval = _schedule(retention=0.05, stability=0.5)
        assert interval > 0

    def test_perfect_retention_long_interval(self):
        """Perfect retention → longer interval (not immediate)."""
        interval = _schedule(retention=1.0, stability=10.0, rev_count=10)
        assert interval >= 1.0

    def test_deterministic_output(self):
        """Same inputs → same outputs (pure function)."""
        a = _schedule(retention=0.5, stability=3.0, days_until_exam=14.0)
        b = _schedule(retention=0.5, stability=3.0, days_until_exam=14.0)
        assert a == b

    def test_high_difficulty_shorter_interval(self):
        """Harder topics should trend toward shorter intervals."""
        easy = _schedule(retention=0.5, difficulty=0.2)
        hard = _schedule(retention=0.5, difficulty=0.9)
        assert hard <= easy * 1.1, "Hard topic got much longer interval"
