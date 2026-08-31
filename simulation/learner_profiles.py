"""
simulation/learner_profiles.py
──────────────────────────────
Learner archetype definitions and synthetic data generators.

10 Archetypes:
  DILIGENT       — high quiz scores, regular revisions, low inactivity
  CRAMMING       — bursts before exam, variable quiz performance
  STRUGGLING     — low quiz scores, irregular timing, moderate inactivity
  COASTING       — decent but declining, sporadic effort
  ABSENT         — very low engagement, frequent long gaps
  BEGINNER       — new learner, moderate effort, low initial scores
  AVERAGE        — balanced across all dimensions
  ADVANCED       — high scores, efficient study, strong retention
  INCONSISTENT   — alternating good/bad sessions, erratic gaps
  HIGH_FREQUENCY — daily engagement, short sessions, rapid feedback

All generation is deterministic when seeded.
"""

import uuid
import random
from dataclasses import dataclass, field
from enum import Enum


class Archetype(str, Enum):
    DILIGENT = "diligent"
    CRAMMING = "cramming"
    STRUGGLING = "struggling"
    COASTING = "coasting"
    ABSENT = "absent"
    # Phase 11 archetypes
    BEGINNER = "beginner"
    AVERAGE = "average"
    ADVANCED = "advanced"
    INCONSISTENT = "inconsistent"
    HIGH_FREQUENCY = "high_frequency"


@dataclass
class TopicProfile:
    """A simulated topic with difficulty and importance."""
    topic_id: uuid.UUID
    name: str
    difficulty: float       # 0.0–1.0
    importance_weight: float  # 0.5–2.0


@dataclass
class LearnerProfile:
    """A simulated learner with behaviour parameters."""
    user_id: uuid.UUID
    name: str
    archetype: Archetype
    topics: list[TopicProfile]
    days_until_exam: float

    # Behaviour parameters
    quiz_score_range: tuple[float, float]   # (min, max)
    revision_probability: float              # chance of revision per day
    study_duration_range: tuple[float, float]  # (min, max) minutes
    inactivity_probability: float            # chance of multi-day gap
    inactivity_duration_range: tuple[int, int]  # (min, max) days


# ── Archetype Configurations ──────────────────────────────────────────────────

ARCHETYPE_CONFIGS = {
    Archetype.DILIGENT: {
        "quiz_score_range": (0.75, 0.95),
        "revision_probability": 0.85,
        "study_duration_range": (30.0, 60.0),
        "inactivity_probability": 0.05,
        "inactivity_duration_range": (1, 3),
    },
    Archetype.CRAMMING: {
        "quiz_score_range": (0.50, 0.85),
        "revision_probability": 0.30,
        "study_duration_range": (60.0, 120.0),
        "inactivity_probability": 0.25,
        "inactivity_duration_range": (3, 10),
    },
    Archetype.STRUGGLING: {
        "quiz_score_range": (0.30, 0.60),
        "revision_probability": 0.40,
        "study_duration_range": (15.0, 30.0),
        "inactivity_probability": 0.20,
        "inactivity_duration_range": (2, 7),
    },
    Archetype.COASTING: {
        "quiz_score_range": (0.60, 0.80),
        "revision_probability": 0.50,
        "study_duration_range": (20.0, 40.0),
        "inactivity_probability": 0.15,
        "inactivity_duration_range": (2, 5),
    },
    Archetype.ABSENT: {
        "quiz_score_range": (0.20, 0.40),
        "revision_probability": 0.10,
        "study_duration_range": (10.0, 20.0),
        "inactivity_probability": 0.40,
        "inactivity_duration_range": (5, 14),
    },
    # ── Phase 11 Archetypes ───────────────────────────────────────────────────
    Archetype.BEGINNER: {
        "quiz_score_range": (0.35, 0.55),
        "revision_probability": 0.45,
        "study_duration_range": (20.0, 40.0),
        "inactivity_probability": 0.15,
        "inactivity_duration_range": (2, 5),
    },
    Archetype.AVERAGE: {
        "quiz_score_range": (0.55, 0.75),
        "revision_probability": 0.55,
        "study_duration_range": (25.0, 45.0),
        "inactivity_probability": 0.12,
        "inactivity_duration_range": (2, 4),
    },
    Archetype.ADVANCED: {
        "quiz_score_range": (0.80, 0.98),
        "revision_probability": 0.75,
        "study_duration_range": (25.0, 50.0),
        "inactivity_probability": 0.05,
        "inactivity_duration_range": (1, 2),
    },
    Archetype.INCONSISTENT: {
        "quiz_score_range": (0.25, 0.90),
        "revision_probability": 0.40,
        "study_duration_range": (10.0, 90.0),
        "inactivity_probability": 0.30,
        "inactivity_duration_range": (1, 12),
    },
    Archetype.HIGH_FREQUENCY: {
        "quiz_score_range": (0.55, 0.85),
        "revision_probability": 0.90,
        "study_duration_range": (10.0, 25.0),
        "inactivity_probability": 0.03,
        "inactivity_duration_range": (1, 2),
    },
}

_TOPIC_NAMES = [
    "Calculus Limits", "Photosynthesis", "French Revolution",
    "Ohm's Law", "Cell Division", "Thermodynamics",
    "Organic Chemistry", "Linear Algebra", "Genetics",
    "Neural Networks", "Wave Optics", "Quantum Mechanics",
    "Statistical Inference", "Fluid Dynamics", "Enzyme Kinetics",
    "Electromagnetic Induction", "Game Theory", "Graph Theory",
    "Protein Folding", "Compiler Design",
]


def generate_topics(n: int, rng: random.Random) -> list[TopicProfile]:
    """Generate n topics with varied difficulty and importance."""
    topics = []
    for i in range(n):
        name = _TOPIC_NAMES[i % len(_TOPIC_NAMES)]
        if i >= len(_TOPIC_NAMES):
            name = f"{name} (Adv {i // len(_TOPIC_NAMES)})"
        topics.append(TopicProfile(
            topic_id=uuid.UUID(int=rng.getrandbits(128)),
            name=name,
            difficulty=round(rng.uniform(0.1, 0.9), 2),
            importance_weight=round(rng.uniform(0.5, 2.0), 2),
        ))
    return topics


def generate_learners(
    n_learners: int,
    n_topics: int,
    days_until_exam: float = 30.0,
    seed: int = 42,
) -> list[LearnerProfile]:
    """
    Generate n_learners with round-robin archetype assignment.
    Each learner gets the same shared topic set (different UUIDs per learner).
    Deterministic when seeded.
    """
    rng = random.Random(seed)
    archetypes = list(Archetype)
    learners = []

    for i in range(n_learners):
        archetype = archetypes[i % len(archetypes)]
        config = ARCHETYPE_CONFIGS[archetype]
        topics = generate_topics(n_topics, rng)

        learners.append(LearnerProfile(
            user_id=uuid.UUID(int=rng.getrandbits(128)),
            name=f"Learner_{i:03d}_{archetype.value}",
            archetype=archetype,
            topics=topics,
            days_until_exam=days_until_exam,
            **config,
        ))

    return learners
