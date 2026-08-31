"""
simulation/event_generator.py
──────────────────────────────
Synthetic event generation from learner profiles.
Generates daily event lists based on archetype behaviour parameters.
"""

import random
from dataclasses import dataclass

from app.engine.recalibration_engine import EventData, EventType
from simulation.learner_profiles import LearnerProfile, TopicProfile


@dataclass
class SimulationEvent:
    """A scheduled simulation event with day and topic context."""
    day: int
    topic: TopicProfile
    event_data: EventData


def _exam_urgency_multiplier(day: int, total_days: int, days_until_exam: float) -> float:
    """Increase activity as exam approaches. Returns 1.0–2.0."""
    days_remaining = days_until_exam - day
    if days_remaining <= 0:
        return 2.0
    if days_remaining <= 7:
        return 1.5 + 0.5 * (1.0 - days_remaining / 7.0)
    if days_remaining <= 14:
        return 1.2 + 0.3 * (1.0 - days_remaining / 14.0)
    return 1.0


def generate_daily_events(
    learner: LearnerProfile,
    day: int,
    total_days: int,
    rng: random.Random,
    topic_last_event_day: dict,  # topic_id -> last event day
) -> list[SimulationEvent]:
    """
    Generate events for a single day based on learner archetype.

    Event generation logic:
    1. Check each topic for inactivity (gap since last event)
    2. For non-inactive topics, probabilistically generate quiz/revision/study
    3. Exam pressure increases event probability
    """
    events = []
    urgency = _exam_urgency_multiplier(day, total_days, learner.days_until_exam)

    for topic in learner.topics:
        tid = topic.topic_id
        last_day = topic_last_event_day.get(tid, -1)
        gap = day - last_day if last_day >= 0 else day

        # ── Inactivity detection ──────────────────────────────────────────
        if gap >= 7 and last_day >= 0:
            events.append(SimulationEvent(
                day=day,
                topic=topic,
                event_data=EventData(
                    event_type=EventType.INACTIVITY_DETECTED,
                    days_inactive=float(gap),
                    difficulty=topic.difficulty,
                    importance_weight=topic.importance_weight,
                ),
            ))
            # Don't also generate an active event for this topic today
            continue

        # ── Active event probability ──────────────────────────────────────
        # Will this learner engage with this topic today?
        base_prob = learner.revision_probability / max(len(learner.topics), 1)
        adjusted_prob = min(1.0, base_prob * urgency)

        if rng.random() > adjusted_prob:
            continue  # No event today for this topic

        # ── Decide event type ─────────────────────────────────────────────
        roll = rng.random()
        if roll < 0.35:  # 35% quiz
            score_min, score_max = learner.quiz_score_range
            quiz_score = round(rng.uniform(score_min, score_max), 3)
            events.append(SimulationEvent(
                day=day,
                topic=topic,
                event_data=EventData(
                    event_type=EventType.QUIZ_SUBMITTED,
                    quiz_score=quiz_score,
                    quiz_confidence=round(rng.uniform(0.3, 0.9), 2),
                    elapsed_days=float(gap),
                    difficulty=topic.difficulty,
                    importance_weight=topic.importance_weight,
                ),
            ))
        elif roll < 0.65:  # 30% revision
            events.append(SimulationEvent(
                day=day,
                topic=topic,
                event_data=EventData(
                    event_type=EventType.REVISION_COMPLETED,
                    elapsed_days=float(gap),
                    difficulty=topic.difficulty,
                    importance_weight=topic.importance_weight,
                ),
            ))
        else:  # 35% study
            dur_min, dur_max = learner.study_duration_range
            events.append(SimulationEvent(
                day=day,
                topic=topic,
                event_data=EventData(
                    event_type=EventType.STUDY_SESSION,
                    study_duration_minutes=round(rng.uniform(dur_min, dur_max), 1),
                    elapsed_days=float(gap),
                    difficulty=topic.difficulty,
                    importance_weight=topic.importance_weight,
                ),
            ))

        topic_last_event_day[tid] = day

    return events


def generate_inactivity_gaps(
    learner: LearnerProfile,
    total_days: int,
    rng: random.Random,
) -> set[int]:
    """
    Pre-generate days where the learner is completely inactive.
    Returns a set of day numbers where no events should be generated.
    """
    inactive_days = set()
    day = 0
    while day < total_days:
        if rng.random() < learner.inactivity_probability:
            gap_min, gap_max = learner.inactivity_duration_range
            gap_len = rng.randint(gap_min, gap_max)
            for d in range(day, min(day + gap_len, total_days)):
                inactive_days.add(d)
            day += gap_len
        else:
            day += 1
    return inactive_days
