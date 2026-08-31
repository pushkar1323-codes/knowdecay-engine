"""
tests/test_engine/test_scheduling_engine.py
─────────────────────────────────────────────
Unit tests for the scheduling engine — pure functions, NO database required.

Test categories:
  1.  Mode selection — exam proximity → scheduling mode
  2.  Base interval — stability × retention × revision mult
  3.  Difficulty modifier — harder topics → shorter intervals
  4.  Exam compression — mode-based interval compression
  5.  Schedule priority — urgency + retention gap + forgetting
  6.  Master compute_schedule — end-to-end scenarios
  7.  Multi-topic generate_schedule — sorting, per-day cap
  8.  Recommendations — human-readable advice strings
  9.  Edge cases — zero, extreme, boundary values
  10. Monotonicity — directional invariants
"""

import pytest

from app.engine.scheduling_engine import (
    ScheduleInput,
    ScheduleMode,
    ScheduleOutput,
    ScheduleSlot,
    compute_base_interval,
    compute_difficulty_modifier,
    compute_exam_compression,
    compute_schedule,
    compute_schedule_priority,
    generate_schedule,
    select_mode,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Mode Selection
# ═══════════════════════════════════════════════════════════════════════════════

class TestModeSelection:
    def test_no_exam(self):
        assert select_mode(None) == ScheduleMode.LONG_TERM

    def test_exam_far_away(self):
        assert select_mode(60.0) == ScheduleMode.LONG_TERM

    def test_exam_month(self):
        assert select_mode(20.0) == ScheduleMode.EXAM_MONTH

    def test_exam_week_boundary(self):
        assert select_mode(7.0) == ScheduleMode.EXAM_WEEK  # exactly 7 days = week mode

    def test_exam_week(self):
        assert select_mode(5.0) == ScheduleMode.EXAM_WEEK

    def test_exam_tomorrow(self):
        assert select_mode(0.5) == ScheduleMode.EXAM_TOMORROW

    def test_exam_today(self):
        assert select_mode(0.0) == ScheduleMode.EXAM_TOMORROW

    def test_boundary_30(self):
        assert select_mode(30.0) == ScheduleMode.EXAM_MONTH

    def test_boundary_31(self):
        assert select_mode(31.0) == ScheduleMode.LONG_TERM


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Base Interval
# ═══════════════════════════════════════════════════════════════════════════════

class TestBaseInterval:
    def test_basic_computation(self):
        interval, ret_factor = compute_base_interval(1.0, 0.5, 0)
        assert interval > 0

    def test_higher_stability_longer_interval(self):
        i_low, _ = compute_base_interval(1.0, 0.5, 3)
        i_high, _ = compute_base_interval(5.0, 0.5, 3)
        assert i_high > i_low

    def test_higher_retention_longer_interval(self):
        i_low, _ = compute_base_interval(2.0, 0.2, 3)
        i_high, _ = compute_base_interval(2.0, 0.9, 3)
        assert i_high > i_low

    def test_more_revisions_longer_interval(self):
        i_few, _ = compute_base_interval(2.0, 0.5, 1)
        i_many, _ = compute_base_interval(2.0, 0.5, 10)
        assert i_many > i_few

    def test_zero_revision_count(self):
        interval, _ = compute_base_interval(2.0, 0.5, 0)
        assert interval > 0

    def test_retention_factor_range(self):
        _, ret_factor = compute_base_interval(1.0, 0.0, 0)
        assert ret_factor >= 0.3  # minimum floor
        _, ret_factor = compute_base_interval(1.0, 1.0, 0)
        assert ret_factor <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Difficulty Modifier
# ═══════════════════════════════════════════════════════════════════════════════

class TestDifficultyModifier:
    def test_easy_topic(self):
        mod = compute_difficulty_modifier(0.0)
        assert mod == pytest.approx(1.0, abs=0.01)

    def test_hard_topic(self):
        mod = compute_difficulty_modifier(1.0)
        assert mod < 1.0

    def test_harder_shorter_interval(self):
        easy = compute_difficulty_modifier(0.2)
        hard = compute_difficulty_modifier(0.8)
        assert hard < easy

    def test_range(self):
        for d in [0.0, 0.3, 0.5, 0.7, 1.0]:
            mod = compute_difficulty_modifier(d)
            assert 0.5 < mod <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Exam Compression
# ═══════════════════════════════════════════════════════════════════════════════

class TestExamCompression:
    def test_long_term_no_compression(self):
        assert compute_exam_compression(ScheduleMode.LONG_TERM, None) == 1.0

    def test_exam_tomorrow_max_compression(self):
        comp = compute_exam_compression(ScheduleMode.EXAM_TOMORROW, 0.5)
        assert comp == 10.0

    def test_exam_week_moderate(self):
        comp = compute_exam_compression(ScheduleMode.EXAM_WEEK, 3.0)
        assert 3.0 <= comp <= 5.0

    def test_exam_month_light(self):
        comp = compute_exam_compression(ScheduleMode.EXAM_MONTH, 20.0)
        assert 1.5 <= comp <= 2.5

    def test_closer_exam_more_compression(self):
        c_far = compute_exam_compression(ScheduleMode.EXAM_WEEK, 6.0)
        c_close = compute_exam_compression(ScheduleMode.EXAM_WEEK, 2.0)
        assert c_close > c_far


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Schedule Priority
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchedulePriority:
    def test_high_urgency_high_priority(self):
        p = compute_schedule_priority(0.9, 0.2, 0.8)
        assert p > 0.5

    def test_low_urgency_low_priority(self):
        p = compute_schedule_priority(0.0, 0.9, 0.1)
        assert p < 0.2

    def test_range(self):
        for u in [0.0, 0.5, 1.0]:
            for r in [0.0, 0.5, 1.0]:
                p = compute_schedule_priority(u, r, 0.5)
                assert 0.0 <= p <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Master compute_schedule — End-to-End
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeSchedule:
    def test_long_term_basic(self):
        """No exam — pure spaced repetition."""
        inp = ScheduleInput(
            retention_score=0.7,
            stability_score=3.0,
            revision_count=3,
            difficulty=0.4,
        )
        out = compute_schedule(inp)
        assert isinstance(out, ScheduleOutput)
        assert out.mode == ScheduleMode.LONG_TERM
        assert out.exam_compression == 1.0
        assert out.next_revision_days > 0

    def test_exam_tomorrow_cram(self):
        """Exam in hours — cram mode."""
        inp = ScheduleInput(
            retention_score=0.4,
            stability_score=2.0,
            revision_count=2,
            days_until_exam=0.5,
        )
        out = compute_schedule(inp)
        assert out.mode == ScheduleMode.EXAM_TOMORROW
        assert out.exam_compression == 10.0
        assert out.next_revision_days < 1.0

    def test_exam_week_intensive(self):
        inp = ScheduleInput(
            retention_score=0.5,
            stability_score=3.0,
            revision_count=2,
            days_until_exam=4.0,
        )
        out = compute_schedule(inp)
        assert out.mode == ScheduleMode.EXAM_WEEK
        assert out.next_revision_days <= 4.0 * 0.9  # never past exam

    def test_never_past_exam(self):
        """Revision should never be scheduled after the exam."""
        inp = ScheduleInput(
            retention_score=0.9,
            stability_score=30.0,
            revision_count=10,
            days_until_exam=5.0,
        )
        out = compute_schedule(inp)
        assert out.next_revision_days <= 5.0

    def test_minimum_interval_respected(self):
        inp = ScheduleInput(
            retention_score=0.0,
            stability_score=0.01,
            revision_count=0,
            days_until_exam=0.1,
        )
        out = compute_schedule(inp)
        assert out.next_revision_days >= 0.04  # default min

    def test_maximum_interval_respected(self):
        inp = ScheduleInput(
            retention_score=1.0,
            stability_score=200.0,
            revision_count=50,
        )
        out = compute_schedule(inp)
        assert out.next_revision_days <= 90.0  # default max

    def test_output_has_all_fields(self):
        inp = ScheduleInput(retention_score=0.5, stability_score=2.0)
        out = compute_schedule(inp)
        assert isinstance(out.mode, ScheduleMode)
        assert out.schedule_priority >= 0
        assert out.base_interval > 0
        assert len(out.recommendation) > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  7. Multi-Topic Schedule
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateSchedule:
    def test_sorted_chronologically(self):
        inputs = [
            ("late", ScheduleInput(retention_score=0.9, stability_score=10.0, revision_count=5)),
            ("soon", ScheduleInput(retention_score=0.2, stability_score=0.5, revision_count=1)),
            ("mid", ScheduleInput(retention_score=0.5, stability_score=3.0, revision_count=3)),
        ]
        slots = generate_schedule(inputs)
        days = [s.day for s in slots]
        assert days == sorted(days)

    def test_per_day_cap(self):
        """No more than max_per_day topics in a single day bucket."""
        inputs = [
            (f"t{i}", ScheduleInput(retention_score=0.3, stability_score=0.5, revision_count=1))
            for i in range(15)
        ]
        slots = generate_schedule(inputs, max_per_day=5)
        day_counts: dict[int, int] = {}
        for s in slots:
            bucket = int(s.day)
            day_counts[bucket] = day_counts.get(bucket, 0) + 1
        for count in day_counts.values():
            assert count <= 5

    def test_empty_input(self):
        assert generate_schedule([]) == []

    def test_single_topic(self):
        inputs = [("t1", ScheduleInput(retention_score=0.5, stability_score=2.0))]
        slots = generate_schedule(inputs)
        assert len(slots) == 1
        assert isinstance(slots[0], ScheduleSlot)

    def test_all_slots_have_ids(self):
        inputs = [
            (f"topic_{i}", ScheduleInput(retention_score=0.3 + 0.1 * i, stability_score=1.0))
            for i in range(5)
        ]
        slots = generate_schedule(inputs)
        ids = {s.topic_id for s in slots}
        assert len(ids) == 5

    def test_exam_aware_schedule(self):
        """All topics should be scheduled before the exam."""
        inputs = [
            (f"t{i}", ScheduleInput(
                retention_score=0.5, stability_score=3.0,
                revision_count=2, days_until_exam=5.0,
            ))
            for i in range(8)
        ]
        slots = generate_schedule(inputs)
        for s in slots:
            assert s.day <= 5.0  # all before exam


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Recommendations
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecommendations:
    def test_cram_mode(self):
        inp = ScheduleInput(
            retention_score=0.3, stability_score=1.0,
            urgency_score=0.8, days_until_exam=0.5,
        )
        out = compute_schedule(inp)
        assert "CRAM" in out.recommendation

    def test_intensive_mode(self):
        inp = ScheduleInput(
            retention_score=0.3, stability_score=1.0,
            days_until_exam=4.0,
        )
        out = compute_schedule(inp)
        assert "INTENSIVE" in out.recommendation

    def test_balanced_mode(self):
        inp = ScheduleInput(
            retention_score=0.3, stability_score=1.0,
            days_until_exam=15.0,
        )
        out = compute_schedule(inp)
        assert "BALANCED" in out.recommendation

    def test_spaced_mode(self):
        inp = ScheduleInput(
            retention_score=0.7, stability_score=5.0,
            revision_count=3,
        )
        out = compute_schedule(inp)
        assert "SPACED" in out.recommendation


# ═══════════════════════════════════════════════════════════════════════════════
#  9. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_all_defaults(self):
        inp = ScheduleInput()
        out = compute_schedule(inp)
        assert isinstance(out, ScheduleOutput)
        assert out.next_revision_days > 0

    def test_zero_stability(self):
        inp = ScheduleInput(stability_score=0.0)
        out = compute_schedule(inp)
        assert out.next_revision_days >= 0.04

    def test_zero_retention(self):
        inp = ScheduleInput(retention_score=0.0, stability_score=1.0)
        out = compute_schedule(inp)
        assert out.next_revision_days > 0

    def test_perfect_retention(self):
        inp = ScheduleInput(retention_score=1.0, stability_score=10.0, revision_count=10)
        out = compute_schedule(inp)
        assert out.next_revision_days > 5  # should be a long interval


# ═══════════════════════════════════════════════════════════════════════════════
#  10. Monotonicity Properties
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    """Verify directional invariants of the scheduling engine."""

    def _schedule(self, **kwargs) -> float:
        defaults = dict(
            retention_score=0.5,
            stability_score=3.0,
            revision_count=3,
            difficulty=0.5,
        )
        defaults.update(kwargs)
        return compute_schedule(ScheduleInput(**defaults)).next_revision_days

    def test_higher_retention_longer_interval(self):
        short = self._schedule(retention_score=0.2)
        long = self._schedule(retention_score=0.9)
        assert long > short

    def test_higher_stability_longer_interval(self):
        short = self._schedule(stability_score=1.0)
        long = self._schedule(stability_score=8.0)
        assert long > short

    def test_harder_topic_shorter_interval(self):
        long = self._schedule(difficulty=0.1)
        short = self._schedule(difficulty=0.9)
        assert short < long

    def test_more_revisions_longer_interval(self):
        short = self._schedule(revision_count=1)
        long = self._schedule(revision_count=10)
        assert long > short

    def test_exam_compresses_interval(self):
        no_exam = self._schedule()
        with_exam = self._schedule(days_until_exam=5.0)
        assert with_exam < no_exam

    def test_closer_exam_shorter_interval(self):
        far = self._schedule(days_until_exam=20.0)
        close = self._schedule(days_until_exam=3.0)
        assert close < far
