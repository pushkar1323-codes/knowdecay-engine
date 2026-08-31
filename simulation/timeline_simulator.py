"""
simulation/timeline_simulator.py
─────────────────────────────────
Multi-week simulation orchestrator.

Runs day-by-day through a timeline, generating events from learner profiles
and processing them through the pure engine stack. Records daily snapshots
of retention, stability, priority, and scheduling for post-hoc analysis.

All computation is pure — no DB, no I/O.

KnowDecay Intelligence Backbone (per event):
  1. MemoryState        → in-memory state dict
  2. Adaptive Stability → compute_adaptive_stability()
  3. Decay + Retention  → recalibrate()
  4. Priority           → compute_priority()
  5. Scheduling         → compute_schedule()
  6. Analytics          → TopicSnapshot recording
"""

import random
from dataclasses import dataclass, field as dc_field

from app.engine.recalibration_engine import (
    CurrentState,
    EventType,
    RecalibrationOutput,
    StateDelta,
    recalibrate,
    apply_delta,
)
from app.engine.priority_engine import (
    PriorityInput,
    compute_priority,
)
from app.engine.scheduling_engine import (
    ScheduleInput,
    compute_schedule,
)
from app.engine.stability_engine import (
    StabilityInput,
    compute_adaptive_stability,
)
from simulation.learner_profiles import LearnerProfile, TopicProfile
from simulation.event_generator import (
    generate_daily_events,
    generate_inactivity_gaps,
)


@dataclass
class TopicSnapshot:
    """Daily snapshot of a topic's state."""
    day: int
    topic_id: object
    topic_name: str
    retention_score: float
    stability_score: float
    adaptive_stability: float
    decay_rate: float
    urgency_score: float
    revision_count: int
    priority_score: float
    priority_tier: str
    next_revision_days: float
    peak_retention: float
    total_forgetting_events: int
    event_type: str | None = None  # Event that occurred this day, if any


@dataclass
class LearnerResult:
    """Complete simulation result for one learner."""
    learner: LearnerProfile
    snapshots: list[TopicSnapshot] = dc_field(default_factory=list)
    total_events: int = 0
    event_counts: dict = dc_field(default_factory=dict)
    final_states: dict = dc_field(default_factory=dict)  # topic_id -> dict


def _state_dict_to_current_state(d: dict) -> CurrentState:
    """Convert apply_delta output dict to CurrentState."""
    # CurrentState uses frozen dataclass, extract matching fields
    cs_fields = {f for f in CurrentState.__dataclass_fields__}
    filtered = {k: v for k, v in d.items() if k in cs_fields}
    return CurrentState(**filtered)


def _compute_priority_for_topic(
    state_dict: dict,
    topic: TopicProfile,
    days_until_exam: float | None,
    day: int,
    last_event_day: int,
) -> tuple[float, str]:
    """Compute priority score and tier for a topic."""
    p_input = PriorityInput(
        retention_score=state_dict.get("retention_score", 0.0),
        forgetting_probability=state_dict.get("forgetting_probability", 1.0),
        stability_score=state_dict.get("stability_score", 1.0),
        decay_rate=state_dict.get("decay_rate", 0.1),
        revision_count=state_dict.get("revision_count", 0),
        days_since_last_revision=float(day - last_event_day) if last_event_day >= 0 else float(day),
        difficulty=topic.difficulty,
        importance_weight=topic.importance_weight,
        days_until_exam=max(0.0, days_until_exam - day) if days_until_exam else None,
    )
    p_out = compute_priority(p_input)
    return p_out.priority_score, p_out.tier.value


def _compute_schedule_for_topic(
    state_dict: dict,
    topic: TopicProfile,
    days_until_exam: float | None,
    day: int,
    last_event_day: int,
) -> float:
    """Compute next revision interval for a topic."""
    s_input = ScheduleInput(
        retention_score=state_dict.get("retention_score", 0.0),
        stability_score=state_dict.get("stability_score", 1.0),
        decay_rate=state_dict.get("decay_rate", 0.1),
        urgency_score=state_dict.get("urgency_score", 0.0),
        revision_count=state_dict.get("revision_count", 0),
        forgetting_probability=state_dict.get("forgetting_probability", 0.5),
        difficulty=topic.difficulty,
        days_until_exam=max(0.0, days_until_exam - day) if days_until_exam else None,
        days_since_last_revision=float(day - last_event_day) if last_event_day >= 0 else float(day),
        adaptive_stability=state_dict.get("adaptive_stability"),
    )
    s_out = compute_schedule(s_input)
    return s_out.next_revision_days


def simulate_learner(
    learner: LearnerProfile,
    total_days: int,
    seed: int,
) -> LearnerResult:
    """
    Run a full timeline simulation for a single learner.

    KnowDecay Intelligence Backbone (per event):
      1. MemoryState        → load in-memory state
      2. Adaptive Stability → compute S_adaptive
      3. Decay + Retention  → recalibrate (inject S_adaptive)
      4. Priority           → compute_priority (end-of-day)
      5. Scheduling         → compute_schedule (end-of-day)
      6. Analytics          → snapshot recording
    """
    rng = random.Random(seed)
    result = LearnerResult(learner=learner)

    # In-memory states: topic_id -> dict (apply_delta output format)
    states: dict = {}
    topic_last_event_day: dict = {}  # topic_id -> last event day

    # Pre-generate inactivity gaps
    inactive_days = generate_inactivity_gaps(learner, total_days, rng)

    # Initialise all topics with default state
    for topic in learner.topics:
        default = apply_delta(CurrentState(), StateDelta())
        states[topic.topic_id] = default

    for day in range(total_days):
        day_events = []

        if day not in inactive_days:
            day_events = generate_daily_events(
                learner, day, total_days, rng, topic_last_event_day
            )

        # Process events through the backbone pipeline
        for sim_event in day_events:
            tid = sim_event.topic.topic_id
            current_dict = states[tid]
            current_state = _state_dict_to_current_state(current_dict)

            # Stage 2: Adaptive Stability (BEFORE decay/retention)
            stab_input = StabilityInput(
                base_stability=current_state.base_stability,
                revision_count=current_state.revision_count,
                revision_quality=current_state.revision_quality,
                quiz_score=sim_event.event_data.quiz_score,
                confidence_score=current_state.confidence_score,
                performance_trend=current_state.performance_trend,
                difficulty=sim_event.topic.difficulty,
            )
            stab_out = compute_adaptive_stability(stab_input)

            # Inject S_adaptive into current state for decay computation
            current_state = CurrentState(**{
                **{f: getattr(current_state, f) for f in CurrentState.__dataclass_fields__},
                "adaptive_stability": stab_out.adaptive_stability,
            })

            # Stage 3+4: Decay -> Retention (inside recalibrate)
            out: RecalibrationOutput = recalibrate(current_state, sim_event.event_data)
            new_dict = apply_delta(current_state, out.delta)

            # Persist S_adaptive in state dict (backbone persistence)
            new_dict["adaptive_stability"] = stab_out.adaptive_stability
            states[tid] = new_dict

            # Track event counts
            et = sim_event.event_data.event_type.value
            result.event_counts[et] = result.event_counts.get(et, 0) + 1
            result.total_events += 1

        # Record end-of-day snapshots for each topic
        for topic in learner.topics:
            tid = topic.topic_id
            sd = states[tid]
            last_day = topic_last_event_day.get(tid, -1)

            priority_score, priority_tier = _compute_priority_for_topic(
                sd, topic, learner.days_until_exam, day, last_day
            )
            next_rev = _compute_schedule_for_topic(
                sd, topic, learner.days_until_exam, day, last_day
            )

            # Find if there was an event for this topic today
            day_event_type = None
            for e in day_events:
                if e.topic.topic_id == tid:
                    day_event_type = e.event_data.event_type.value
                    break

            result.snapshots.append(TopicSnapshot(
                day=day,
                topic_id=tid,
                topic_name=topic.name,
                retention_score=sd.get("retention_score", 0.0),
                stability_score=sd.get("stability_score", 1.0),
                adaptive_stability=sd.get("adaptive_stability", 1.0),
                decay_rate=sd.get("decay_rate", 0.1),
                urgency_score=sd.get("urgency_score", 0.0),
                revision_count=sd.get("revision_count", 0),
                priority_score=priority_score,
                priority_tier=priority_tier,
                next_revision_days=next_rev,
                peak_retention=sd.get("peak_retention", 0.0),
                total_forgetting_events=sd.get("total_forgetting_events", 0),
                event_type=day_event_type,
            ))

    # Store final states
    result.final_states = {tid: dict(sd) for tid, sd in states.items()}
    return result


def run_simulation(
    learners: list[LearnerProfile],
    total_days: int = 30,
    base_seed: int = 42,
) -> list[LearnerResult]:
    """
    Run simulation for all learners.
    Each learner gets a unique seed derived from base_seed.
    """
    results = []
    for i, learner in enumerate(learners):
        result = simulate_learner(learner, total_days, seed=base_seed + i)
        results.append(result)
    return results
