"""
app/services/ml_feature_builder.py
────────────────────────────────────
Shared utility for building ML augmentation features from MemoryState.

This module is used by all service layers (priority, schedule, analytics)
to extract behavioural features from the learner's memory state and
compute ML augmentation signals.

When ML is disabled (ml_enabled=False or ml_blend_weight=0.0), these
functions return None values which cause zero effect in the forgetting
engine — maintaining identical behaviour to the pure deterministic system.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.engine.ml_augmentor import (
    AugmentorInput,
    AugmentorOutput,
    compute_augmentation,
)
from app.models.memory_state import MemoryState


@dataclass(frozen=True, slots=True)
class MLFeatures:
    """
    ML features ready to inject into ForgettingInput.

    When ML is disabled, all fields are set to their no-effect defaults:
      stability_correction = None
      decay_modifier = None
      blend_weight = 0.0
    """
    stability_correction: float | None
    decay_modifier: float | None
    blend_weight: float
    augmentor_output: AugmentorOutput | None  # for audit/logging


# Singleton sentinel for "ML disabled"
_ML_DISABLED = MLFeatures(
    stability_correction=None,
    decay_modifier=None,
    blend_weight=0.0,
    augmentor_output=None,
)


def build_ml_features(
    state: MemoryState,
    difficulty: float = 0.5,
) -> MLFeatures:
    """
    Extract ML augmentation features from a MemoryState.

    Returns MLFeatures that can be injected into ForgettingInput.
    When ML is disabled, returns _ML_DISABLED (zero effect).

    Feature derivation from MemoryState:
      - avg_revision_quality  → state.revision_quality (running average)
      - quality_variance      → estimated from trend amplitude
      - stability_growth_rate → base_stability / max(revision_count, 1)
      - time_pattern_regularity → inferred from performance_trend stability
      - confidence_calibration_error → |confidence − retention| as proxy
      - revision_effectiveness_ratio → retention × quality as proxy
    """
    settings = get_settings()

    if not settings.ml_enabled or settings.ml_blend_weight <= 0:
        return _ML_DISABLED

    # ── Extract features directly from MemoryState ─────────────────────────
    aug_input = AugmentorInput(
        revision_count=state.revision_count,
        avg_revision_quality=state.revision_quality,
        quality_variance=state.quality_variance,
        stability_growth_rate=state.stability_growth_rate,
        time_pattern_regularity=state.time_pattern_regularity,
        confidence_calibration_error=state.confidence_calibration_error,
        revision_effectiveness_ratio=state.revision_effectiveness_ratio,
        difficulty=difficulty,
    )

    aug_output = compute_augmentation(
        aug_input,
        max_correction=settings.ml_max_stability_correction,
        max_decay_range=settings.ml_max_decay_modifier_range,
    )

    return MLFeatures(
        stability_correction=aug_output.stability_correction,
        decay_modifier=aug_output.decay_modifier,
        blend_weight=settings.ml_blend_weight,
        augmentor_output=aug_output,
    )
