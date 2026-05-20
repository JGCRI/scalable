"""ML optimization subsystem for Scalable (Phase 5).

This package provides machine-learning-backed resource prediction, adaptive
scaling, and distributed hyperparameter tuning. All features degrade gracefully
to Phase 2 heuristics when ``scalable[ml]`` is not installed.

Key components:

* :class:`LearnedAdvisor` — ML-based resource recommendations
* :class:`AdaptiveScaler` — real-time adaptive worker scaling
* :class:`HyperparameterSearch` — Dask-ML distributed tuning
* :class:`FeatureExtractor` — telemetry feature engineering
"""

from __future__ import annotations

from .adaptive_scaler import AdaptiveScaler, ScaleDecision
from .features import FeatureExtractor
from .learned_advisor import LearnedAdvisor
from .models import ModelQuality, PredictionResult
from .tuning import HyperparameterSearch, TuningResult
from .validation import cross_validate_advisor

__all__ = [
    "AdaptiveScaler",
    "FeatureExtractor",
    "HyperparameterSearch",
    "LearnedAdvisor",
    "ModelQuality",
    "PredictionResult",
    "ScaleDecision",
    "TuningResult",
    "cross_validate_advisor",
]
