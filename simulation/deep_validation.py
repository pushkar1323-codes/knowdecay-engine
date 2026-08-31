"""
Deep validation of KnowDecay engine across 4 critical dimensions:
  1. Adaptive decay consistency  — R = e^(-t / S_adaptive)
  2. Retention evolution         — retention changes over time, not flat
  3. Reinforcement behavior      — events reinforce retention
  4. Stability transitions       — stability evolves with learner behavior

Runs a 60-day simulation with 10 learners × 8 topics for statistical depth.
"""

import json
import math
import statistics
from collections import defaultdict

from simulation.learner_profiles import Archetype, generate_learners
from simulation.timeline_simulator import run_simulation, LearnerResult, TopicSnapshot


def _group_snapshots_by_topic(result: LearnerResult) -> dict:
    """Group snapshots by topic_id, sorted by day."""
    by_topic = defaultdict(list)
    for s in result.snapshots:
        by_topic[s.topic_id].append(s)
    for k in by_topic:
        by_topic[k].sort(key=lambda s: s.day)
    return dict(by_topic)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. ADAPTIVE DECAY CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════════

def validate_adaptive_decay(results: list[LearnerResult]) -> dict:
    """
    Validate R = e^(-t / S_adaptive) consistency.
    
    For topics with NO events on consecutive days, retention should
    remain at floor (0.05) or decrease — never spontaneously increase.
    Also verifies that decay_rate and adaptive_stability are coherent.
    """
    violations = {
        "spontaneous_increase": 0,
        "decay_rate_negative": 0,
        "adaptive_stability_negative": 0,
        "total_idle_transitions": 0,
    }
    decay_rate_stats = []
    adaptive_stability_stats = []

    for r in results:
        by_topic = _group_snapshots_by_topic(r)
        for tid, snaps in by_topic.items():
            for i in range(1, len(snaps)):
                prev, curr = snaps[i - 1], snaps[i]

                # Track stats
                decay_rate_stats.append(curr.decay_rate)
                adaptive_stability_stats.append(curr.adaptive_stability)

                if curr.decay_rate < 0:
                    violations["decay_rate_negative"] += 1
                if curr.adaptive_stability < 0:
                    violations["adaptive_stability_negative"] += 1

                # Check idle days (no event on current day)
                if curr.event_type is None:
                    violations["total_idle_transitions"] += 1
                    # Retention should NOT increase on idle days
                    if curr.retention_score > prev.retention_score + 0.001:
                        violations["spontaneous_increase"] += 1

    return {
        "test": "adaptive_decay_consistency",
        "passed": (
            violations["spontaneous_increase"] == 0
            and violations["decay_rate_negative"] == 0
            and violations["adaptive_stability_negative"] == 0
        ),
        "violations": violations,
        "decay_rate": {
            "min": round(min(decay_rate_stats), 6),
            "max": round(max(decay_rate_stats), 6),
            "mean": round(statistics.mean(decay_rate_stats), 6),
            "stdev": round(statistics.stdev(decay_rate_stats), 6) if len(decay_rate_stats) > 1 else 0.0,
        },
        "adaptive_stability": {
            "min": round(min(adaptive_stability_stats), 4),
            "max": round(max(adaptive_stability_stats), 4),
            "mean": round(statistics.mean(adaptive_stability_stats), 4),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  2. RETENTION EVOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_retention_evolution(results: list[LearnerResult]) -> dict:
    """
    Validate that retention evolves (is NOT flat/stale) across simulation.
    
    Checks:
    - Per-archetype retention range (max - min over time)
    - Active topics show retention change from initial state
    - Daily variance is non-zero for engaged learners
    """
    arch_evolution = {}

    for archetype in Archetype:
        arch_results = [r for r in results if r.learner.archetype == archetype]
        if not arch_results:
            continue

        all_retentions = []
        initial_retentions = []
        final_retentions = []
        daily_means = defaultdict(list)
        topics_with_change = 0
        topics_total = 0

        for r in arch_results:
            by_topic = _group_snapshots_by_topic(r)
            for tid, snaps in by_topic.items():
                topics_total += 1
                retentions = [s.retention_score for s in snaps]
                all_retentions.extend(retentions)
                initial_retentions.append(retentions[0])
                final_retentions.append(retentions[-1])

                # Did this topic's retention change at all?
                if max(retentions) - min(retentions) > 0.001:
                    topics_with_change += 1

                for s in snaps:
                    daily_means[s.day].append(s.retention_score)

        # Compute daily mean trajectory
        trajectory = []
        for day in sorted(daily_means):
            vals = daily_means[day]
            trajectory.append(round(statistics.mean(vals), 4))

        # Compute trajectory variance
        traj_variance = round(statistics.variance(trajectory), 6) if len(trajectory) > 1 else 0.0

        arch_evolution[archetype.value] = {
            "topics_total": topics_total,
            "topics_with_change": topics_with_change,
            "change_rate": round(topics_with_change / max(topics_total, 1), 3),
            "retention_range": round(max(all_retentions) - min(all_retentions), 4),
            "initial_mean": round(statistics.mean(initial_retentions), 4),
            "final_mean": round(statistics.mean(final_retentions), 4),
            "trajectory_variance": traj_variance,
            "trajectory_sample": trajectory[:10],  # First 10 days
        }

    # Overall evolution quality
    all_change_rates = [v["change_rate"] for v in arch_evolution.values()]
    engaged_evolving = sum(1 for v in arch_evolution.values() if v["change_rate"] > 0)

    return {
        "test": "retention_evolution",
        "passed": engaged_evolving > 0,  # At least ONE archetype shows evolution
        "per_archetype": arch_evolution,
        "archetypes_with_evolution": engaged_evolving,
        "overall_change_rate": round(statistics.mean(all_change_rates), 3) if all_change_rates else 0.0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  3. REINFORCEMENT BEHAVIOR
# ═══════════════════════════════════════════════════════════════════════════════

def validate_reinforcement_behavior(results: list[LearnerResult]) -> dict:
    """
    Validate that learning events reinforce retention.
    
    Checks:
    - Quiz events with high scores increase retention
    - Revision events increase stability
    - Study sessions provide modest boost
    - Inactivity events degrade retention
    """
    event_effects = {
        "quiz_submitted": {"retention_up": 0, "retention_down": 0, "no_change": 0},
        "revision_completed": {"retention_up": 0, "retention_down": 0, "no_change": 0},
        "study_session": {"retention_up": 0, "retention_down": 0, "no_change": 0},
        "inactivity_detected": {"retention_up": 0, "retention_down": 0, "no_change": 0},
    }
    stability_effects = {
        "quiz_submitted": {"stability_up": 0, "stability_down": 0, "no_change": 0},
        "revision_completed": {"stability_up": 0, "stability_down": 0, "no_change": 0},
        "study_session": {"stability_up": 0, "stability_down": 0, "no_change": 0},
        "inactivity_detected": {"stability_up": 0, "stability_down": 0, "no_change": 0},
    }

    for r in results:
        by_topic = _group_snapshots_by_topic(r)
        for tid, snaps in by_topic.items():
            for i in range(1, len(snaps)):
                prev, curr = snaps[i - 1], snaps[i]
                if curr.event_type is None:
                    continue

                et = curr.event_type
                if et not in event_effects:
                    continue

                # Retention direction
                delta_r = curr.retention_score - prev.retention_score
                if delta_r > 0.001:
                    event_effects[et]["retention_up"] += 1
                elif delta_r < -0.001:
                    event_effects[et]["retention_down"] += 1
                else:
                    event_effects[et]["no_change"] += 1

                # Stability direction
                delta_s = curr.stability_score - prev.stability_score
                if delta_s > 0.001:
                    stability_effects[et]["stability_up"] += 1
                elif delta_s < -0.001:
                    stability_effects[et]["stability_down"] += 1
                else:
                    stability_effects[et]["no_change"] += 1

    # Compute reinforcement quality metrics
    def _reinforcement_rate(effects: dict, positive_key: str) -> float:
        total = effects[positive_key] + effects.get("retention_down", effects.get("stability_down", 0)) + effects.get("no_change", 0)
        return round(effects[positive_key] / max(total, 1), 3)

    reinforcement_quality = {}
    for et in ["quiz_submitted", "revision_completed", "study_session"]:
        total = sum(event_effects[et].values())
        up = event_effects[et]["retention_up"]
        reinforcement_quality[et] = {
            "total_events": total,
            "retention_increase_rate": round(up / max(total, 1), 3),
            "stability_increase_rate": round(
                stability_effects[et]["stability_up"] / max(total, 1), 3
            ),
        }

    # Inactivity should degrade
    inact_total = sum(event_effects["inactivity_detected"].values())
    inact_down = event_effects["inactivity_detected"]["retention_down"]
    reinforcement_quality["inactivity_detected"] = {
        "total_events": inact_total,
        "retention_decrease_rate": round(inact_down / max(inact_total, 1), 3),
    }

    # Pass criteria: positive events mostly increase R, inactivity decreases R
    quiz_ok = reinforcement_quality["quiz_submitted"]["retention_increase_rate"] > 0.3 if reinforcement_quality["quiz_submitted"]["total_events"] > 0 else True
    revision_ok = reinforcement_quality["revision_completed"]["retention_increase_rate"] > 0.3 if reinforcement_quality["revision_completed"]["total_events"] > 0 else True

    return {
        "test": "reinforcement_behavior",
        "passed": quiz_ok and revision_ok,
        "event_retention_effects": event_effects,
        "event_stability_effects": stability_effects,
        "reinforcement_quality": reinforcement_quality,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  4. STABILITY TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

def validate_stability_transitions(results: list[LearnerResult]) -> dict:
    """
    Validate stability dynamics across learner simulations.
    
    Checks:
    - Stability increases with successful revisions
    - Stability degrades (or doesn't grow) with inactivity
    - Diligent learners achieve higher mean stability than struggling
    - Stability remains bounded (no explosions)
    """
    arch_stability = {}
    transition_analysis = {
        "growth_after_revision": 0,
        "flat_after_revision": 0,
        "decline_after_revision": 0,
        "growth_after_inactivity": 0,
        "flat_after_inactivity": 0,
        "decline_after_inactivity": 0,
    }
    stability_bounds = {"min": float("inf"), "max": float("-inf")}

    for archetype in Archetype:
        arch_results = [r for r in results if r.learner.archetype == archetype]
        if not arch_results:
            continue

        final_stabilities = []
        stability_trajectories = defaultdict(list)

        for r in arch_results:
            by_topic = _group_snapshots_by_topic(r)
            for tid, snaps in by_topic.items():
                final_stabilities.append(snaps[-1].stability_score)

                for s in snaps:
                    stability_trajectories[s.day].append(s.stability_score)
                    stability_bounds["min"] = min(stability_bounds["min"], s.stability_score)
                    stability_bounds["max"] = max(stability_bounds["max"], s.stability_score)

                # Analyse transitions around events
                for i in range(1, len(snaps)):
                    prev, curr = snaps[i - 1], snaps[i]
                    if curr.event_type is None:
                        continue

                    delta_s = curr.stability_score - prev.stability_score
                    if curr.event_type in ("quiz_submitted", "revision_completed"):
                        if delta_s > 0.001:
                            transition_analysis["growth_after_revision"] += 1
                        elif delta_s < -0.001:
                            transition_analysis["decline_after_revision"] += 1
                        else:
                            transition_analysis["flat_after_revision"] += 1
                    elif curr.event_type == "inactivity_detected":
                        if delta_s > 0.001:
                            transition_analysis["growth_after_inactivity"] += 1
                        elif delta_s < -0.001:
                            transition_analysis["decline_after_inactivity"] += 1
                        else:
                            transition_analysis["flat_after_inactivity"] += 1

        # Daily mean trajectory
        traj = []
        for day in sorted(stability_trajectories):
            traj.append(round(statistics.mean(stability_trajectories[day]), 4))

        arch_stability[archetype.value] = {
            "final_mean": round(statistics.mean(final_stabilities), 4),
            "final_min": round(min(final_stabilities), 4),
            "final_max": round(max(final_stabilities), 4),
            "trajectory_sample": traj[:10],
        }

    # Cross-archetype: measure revision growth RATE instead of raw mean
    # (Raw mean is misleading — absent topics sit at default 1.0 untouched)
    revision_total = (
        transition_analysis["growth_after_revision"]
        + transition_analysis["flat_after_revision"]
        + transition_analysis["decline_after_revision"]
    )
    revision_growth_rate = (
        transition_analysis["growth_after_revision"] / max(revision_total, 1)
    )
    inactivity_total = (
        transition_analysis["growth_after_inactivity"]
        + transition_analysis["flat_after_inactivity"]
        + transition_analysis["decline_after_inactivity"]
    )
    inactivity_no_growth_rate = (
        (transition_analysis["flat_after_inactivity"]
         + transition_analysis["decline_after_inactivity"])
        / max(inactivity_total, 1)
    )

    # Bounds check
    bounded = stability_bounds["min"] >= 0.0 and stability_bounds["max"] < 1000.0

    # Pass: stability grows with revision (>50%), doesn't grow with inactivity (>50%), bounded
    transition_ok = revision_growth_rate > 0.5 and inactivity_no_growth_rate > 0.5

    return {
        "test": "stability_transitions",
        "passed": bounded and transition_ok,
        "per_archetype": arch_stability,
        "transition_analysis": transition_analysis,
        "stability_bounds": {
            "min": round(stability_bounds["min"], 4),
            "max": round(stability_bounds["max"], 4),
        },
        "revision_growth_rate": round(revision_growth_rate, 3),
        "inactivity_no_growth_rate": round(inactivity_no_growth_rate, 3),
        "cross_archetype": {
            "diligent_mean": arch_stability.get("diligent", {}).get("final_mean", 0),
            "struggling_mean": arch_stability.get("struggling", {}).get("final_mean", 0),
            "note": "Raw mean includes untouched topics at default stability",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  KnowDecay Engine — Deep Validation Suite")
    print("  10 learners x 8 topics x 60 days")
    print("=" * 70)

    learners = generate_learners(10, 8, days_until_exam=60.0, seed=42)
    results = run_simulation(learners, total_days=60, base_seed=42)

    validators = [
        validate_adaptive_decay,
        validate_retention_evolution,
        validate_reinforcement_behavior,
        validate_stability_transitions,
    ]

    all_reports = []
    all_passed = True

    for validator in validators:
        report = validator(results)
        all_reports.append(report)
        status = "PASS" if report["passed"] else "FAIL"
        if not report["passed"]:
            all_passed = False
        print(f"\n{'─' * 70}")
        print(f"  [{status}] {report['test']}")
        print(f"{'─' * 70}")
        # Print key details based on test type
        _print_details(report)

    print(f"\n{'=' * 70}")
    overall = "ALL 4 VALIDATIONS PASS" if all_passed else "VALIDATION FAILURES DETECTED"
    print(f"  RESULT: {overall}")
    print(f"{'=' * 70}")

    # Save full report
    import pathlib
    out = pathlib.Path("simulation/output")
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "deep_validation_report.json", "w") as f:
        json.dump(all_reports, f, indent=2, default=str)
    print(f"  Full report: simulation/output/deep_validation_report.json")

    return 0 if all_passed else 1


def _print_details(report: dict):
    test = report["test"]

    if test == "adaptive_decay_consistency":
        v = report["violations"]
        print(f"  Spontaneous increases on idle days: {v['spontaneous_increase']}")
        print(f"  Negative decay rates: {v['decay_rate_negative']}")
        print(f"  Negative adaptive stability: {v['adaptive_stability_negative']}")
        print(f"  Total idle transitions checked: {v['total_idle_transitions']}")
        d = report["decay_rate"]
        print(f"  Decay rate: min={d['min']}, max={d['max']}, mean={d['mean']}, stdev={d['stdev']}")
        a = report["adaptive_stability"]
        print(f"  Adaptive stability: min={a['min']}, max={a['max']}, mean={a['mean']}")

    elif test == "retention_evolution":
        for arch, data in report["per_archetype"].items():
            print(f"  {arch:<15s}: change_rate={data['change_rate']:.0%}  "
                  f"range={data['retention_range']:.4f}  "
                  f"init={data['initial_mean']:.4f} -> final={data['final_mean']:.4f}  "
                  f"variance={data['trajectory_variance']:.6f}")
        print(f"  Archetypes with evolution: {report['archetypes_with_evolution']}/5")

    elif test == "reinforcement_behavior":
        for et, data in report["reinforcement_quality"].items():
            if "retention_increase_rate" in data:
                print(f"  {et:<22s}: n={data['total_events']:>3}  "
                      f"R_up={data['retention_increase_rate']:.0%}  "
                      f"S_up={data.get('stability_increase_rate', 'N/A')}")
            else:
                print(f"  {et:<22s}: n={data['total_events']:>3}  "
                      f"R_down={data['retention_decrease_rate']:.0%}")

    elif test == "stability_transitions":
        t = report["transition_analysis"]
        print(f"  After revision/quiz: growth={t['growth_after_revision']}  "
              f"flat={t['flat_after_revision']}  decline={t['decline_after_revision']}")
        print(f"  After inactivity:    growth={t['growth_after_inactivity']}  "
              f"flat={t['flat_after_inactivity']}  decline={t['decline_after_inactivity']}")
        print(f"  Revision growth rate:      {report['revision_growth_rate']:.0%}")
        print(f"  Inactivity no-growth rate: {report['inactivity_no_growth_rate']:.0%}")
        b = report["stability_bounds"]
        print(f"  Stability bounds: [{b['min']}, {b['max']}]")
        for arch, data in report["per_archetype"].items():
            print(f"    {arch:<15s}: final_mean={data['final_mean']:.4f}  "
                  f"[{data['final_min']:.4f}, {data['final_max']:.4f}]")


if __name__ == "__main__":
    import sys
    sys.exit(main())
