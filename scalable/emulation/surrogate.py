"""Surrogate model abstractions for scientific model emulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np


@dataclass(frozen=True)
class EmulatorPrediction:
    """Prediction result with uncertainty information."""

    outputs: dict[str, Any]
    confidence: float
    uncertainty_bounds: dict[str, tuple[float, float]] | None = None
    is_emulated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "outputs": self.outputs,
            "confidence": self.confidence,
            "uncertainty_bounds": self.uncertainty_bounds,
            "is_emulated": self.is_emulated,
        }


@dataclass(frozen=True)
class EmulatorMetadata:
    """Provenance and quality metadata for a trained emulator."""

    name: str
    version: str
    training_runs: list[str]
    training_samples: int
    validation_score: float
    domain_bounds: dict[str, tuple[float, float]]
    created_at: str
    model_type: str
    output_names: list[str] = field(default_factory=list)
    input_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "training_runs": self.training_runs,
            "training_samples": self.training_samples,
            "validation_score": self.validation_score,
            "domain_bounds": self.domain_bounds,
            "created_at": self.created_at,
            "model_type": self.model_type,
            "output_names": self.output_names,
            "input_names": self.input_names,
        }


class TrainedEmulator(Protocol):
    """Protocol for trained surrogate models."""

    def predict(self, inputs: dict[str, Any]) -> EmulatorPrediction:
        """Produce predictions with uncertainty for the given inputs."""
        ...

    def uncertainty(self, inputs: dict[str, Any]) -> float:
        """Return scalar uncertainty estimate for the given inputs."""
        ...

    @property
    def metadata(self) -> EmulatorMetadata:
        """Return emulator provenance and quality metadata."""
        ...


class GradientBoostingEmulator:
    """Gradient boosting-based surrogate model.

    Uses sklearn's GradientBoostingRegressor for tabular scenario features.
    Uncertainty is estimated from ensemble variance.
    """

    def __init__(
        self,
        *,
        metadata: EmulatorMetadata,
        models: dict[str, Any] | None = None,
    ) -> None:
        self._metadata = metadata
        self._models: dict[str, Any] = models or {}
        self._input_names = list(metadata.input_names)
        self._output_names = list(metadata.output_names)

    @property
    def metadata(self) -> EmulatorMetadata:
        return self._metadata

    def train(
        self,
        X: Any,
        y: dict[str, Any],
        *,
        n_estimators: int = 100,
        max_depth: int = 5,
        random_state: int = 42,
    ) -> None:
        """Train the emulator on input/output data.

        Parameters
        ----------
        X
            Input features (numpy array or DataFrame).
        y
            Dict mapping output name to target arrays.
        """
        try:
            from sklearn.ensemble import GradientBoostingRegressor

            for output_name, y_vals in y.items():
                model = GradientBoostingRegressor(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    random_state=random_state,
                )
                model.fit(X, y_vals)
                self._models[output_name] = model
        except ImportError:
            pass

    def predict(self, inputs: dict[str, Any]) -> EmulatorPrediction:
        """Predict outputs with uncertainty estimation."""
        if not self._models:
            return EmulatorPrediction(
                outputs={},
                confidence=0.0,
                uncertainty_bounds=None,
                is_emulated=True,
            )

        # Build input vector
        X = np.array([[inputs.get(name, 0) for name in self._input_names]])

        outputs: dict[str, Any] = {}
        bounds: dict[str, tuple[float, float]] = {}
        confidences: list[float] = []

        for output_name, model in self._models.items():
            pred = float(model.predict(X)[0])
            outputs[output_name] = pred

            # Estimate uncertainty from staged predictions variance
            if hasattr(model, "estimators_"):
                staged_preds = np.array(
                    [est[0].predict(X)[0] for est in model.estimators_]
                )
                std = float(np.std(staged_preds))
                lower = pred - 2 * std
                upper = pred + 2 * std
                bounds[output_name] = (lower, upper)
                # Confidence inversely proportional to relative uncertainty
                rel_uncertainty = std / (abs(pred) + 1e-10)
                conf = max(0.0, min(1.0, 1.0 - rel_uncertainty))
                confidences.append(conf)
            else:
                bounds[output_name] = (pred * 0.8, pred * 1.2)
                confidences.append(0.7)

        overall_confidence = float(np.mean(confidences)) if confidences else 0.5

        return EmulatorPrediction(
            outputs=outputs,
            confidence=overall_confidence,
            uncertainty_bounds=bounds,
            is_emulated=True,
        )

    def uncertainty(self, inputs: dict[str, Any]) -> float:
        """Return scalar uncertainty (1 - confidence)."""
        pred = self.predict(inputs)
        return 1.0 - pred.confidence


class RandomForestEmulator:
    """Random forest-based surrogate model.

    Uses sklearn's RandomForestRegressor. Uncertainty estimated from
    individual tree prediction variance.
    """

    def __init__(
        self,
        *,
        metadata: EmulatorMetadata,
        models: dict[str, Any] | None = None,
    ) -> None:
        self._metadata = metadata
        self._models: dict[str, Any] = models or {}
        self._input_names = list(metadata.input_names)
        self._output_names = list(metadata.output_names)

    @property
    def metadata(self) -> EmulatorMetadata:
        return self._metadata

    def train(
        self,
        X: Any,
        y: dict[str, Any],
        *,
        n_estimators: int = 100,
        max_depth: int = 10,
        random_state: int = 42,
    ) -> None:
        """Train the emulator on input/output data."""
        try:
            from sklearn.ensemble import RandomForestRegressor

            for output_name, y_vals in y.items():
                model = RandomForestRegressor(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    random_state=random_state,
                    n_jobs=-1,
                )
                model.fit(X, y_vals)
                self._models[output_name] = model
        except ImportError:
            pass

    def predict(self, inputs: dict[str, Any]) -> EmulatorPrediction:
        """Predict outputs with tree-based uncertainty estimation."""
        if not self._models:
            return EmulatorPrediction(
                outputs={},
                confidence=0.0,
                uncertainty_bounds=None,
                is_emulated=True,
            )

        X = np.array([[inputs.get(name, 0) for name in self._input_names]])

        outputs: dict[str, Any] = {}
        bounds: dict[str, tuple[float, float]] = {}
        confidences: list[float] = []

        for output_name, model in self._models.items():
            # Get individual tree predictions
            tree_preds = np.array([t.predict(X)[0] for t in model.estimators_])
            pred = float(np.mean(tree_preds))
            std = float(np.std(tree_preds))

            outputs[output_name] = pred
            bounds[output_name] = (pred - 2 * std, pred + 2 * std)

            rel_uncertainty = std / (abs(pred) + 1e-10)
            conf = max(0.0, min(1.0, 1.0 - rel_uncertainty))
            confidences.append(conf)

        overall_confidence = float(np.mean(confidences)) if confidences else 0.5

        return EmulatorPrediction(
            outputs=outputs,
            confidence=overall_confidence,
            uncertainty_bounds=bounds,
            is_emulated=True,
        )

    def uncertainty(self, inputs: dict[str, Any]) -> float:
        """Return scalar uncertainty (1 - confidence)."""
        pred = self.predict(inputs)
        return 1.0 - pred.confidence


__all__ = [
    "EmulatorMetadata",
    "EmulatorPrediction",
    "GradientBoostingEmulator",
    "RandomForestEmulator",
    "TrainedEmulator",
]
