"""ML model wrappers for resource prediction (Phase 5).

Provides sklearn-compatible model abstractions with unified interface for
training, prediction, and interval estimation. All sklearn imports are lazy
so the module loads without ``scalable[ml]`` installed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PredictionResult:
    """Prediction output with optional confidence intervals."""

    point: float
    lower: float | None = None
    upper: float | None = None
    confidence: float = 0.95

    def to_dict(self) -> dict[str, Any]:
        return {
            "point": self.point,
            "lower": self.lower,
            "upper": self.upper,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ModelQuality:
    """Quality metrics from cross-validation or holdout evaluation."""

    mae: float
    rmse: float
    r2: float
    coverage: float  # Fraction of true values within predicted intervals
    n_samples: int
    model_type: str
    target_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mae": self.mae,
            "rmse": self.rmse,
            "r2": self.r2,
            "coverage": self.coverage,
            "n_samples": self.n_samples,
            "model_type": self.model_type,
            "target_name": self.target_name,
        }


class ResourceModel:
    """Unified wrapper around sklearn estimators for resource prediction.

    Supports gradient boosting, random forest, and quantile regression.
    Falls back to simple percentile estimator if sklearn is unavailable.
    """

    def __init__(
        self,
        model_type: str = "gradient_boosting",
        *,
        quantile_lower: float = 0.05,
        quantile_upper: float = 0.95,
        random_state: int = 42,
    ) -> None:
        self.model_type = model_type
        self.quantile_lower = quantile_lower
        self.quantile_upper = quantile_upper
        self.random_state = random_state
        self._model: Any = None
        self._model_lower: Any = None
        self._model_upper: Any = None
        self._feature_names: list[str] = []
        self._is_fitted = False
        self._fallback_percentiles: dict[str, float] | None = None

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> ResourceModel:
        """Train the model on feature matrix X and target y.

        Parameters
        ----------
        X
            Feature matrix (from :class:`FeatureExtractor`).
        y
            Target variable (e.g., duration_s or memory_bytes).

        Returns
        -------
        self
        """
        if X.empty or len(y) < 2:
            # Too few samples — store percentile fallback
            self._fallback_percentiles = {
                "median": float(y.median()) if not y.empty else 0,
                "lower": float(y.quantile(self.quantile_lower)) if not y.empty else 0,
                "upper": float(y.quantile(self.quantile_upper)) if not y.empty else 0,
            }
            self._is_fitted = True
            return self

        self._feature_names = list(X.columns)

        try:
            self._fit_sklearn(X, y)
        except ImportError:
            # sklearn not available — use percentile fallback
            self._fallback_percentiles = {
                "median": float(y.median()),
                "lower": float(y.quantile(self.quantile_lower)),
                "upper": float(y.quantile(self.quantile_upper)),
            }

        self._is_fitted = True
        return self

    def _fit_sklearn(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit using sklearn estimators."""
        from sklearn.ensemble import (
            GradientBoostingRegressor,
            RandomForestRegressor,
        )

        X_arr = X.values.astype(np.float64)
        y_arr = y.values.astype(np.float64)

        # Remove NaN rows
        mask = ~(np.isnan(X_arr).any(axis=1) | np.isnan(y_arr))
        X_arr = X_arr[mask]
        y_arr = y_arr[mask]

        if len(y_arr) < 2:
            self._fallback_percentiles = {
                "median": float(np.median(y_arr)) if len(y_arr) > 0 else 0,
                "lower": 0,
                "upper": float(np.max(y_arr)) if len(y_arr) > 0 else 0,
            }
            return

        if self.model_type == "random_forest":
            self._model = RandomForestRegressor(
                n_estimators=50,
                max_depth=8,
                random_state=self.random_state,
                n_jobs=-1,
            )
            self._model.fit(X_arr, y_arr)
            # For RF, use quantile estimation from tree predictions
            self._model_lower = None
            self._model_upper = None
        elif self.model_type == "quantile_regression":
            # Use gradient boosting with quantile loss
            self._model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                loss="squared_error",
                random_state=self.random_state,
            )
            self._model.fit(X_arr, y_arr)
            self._model_lower = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                loss="quantile",
                alpha=self.quantile_lower,
                random_state=self.random_state,
            )
            self._model_lower.fit(X_arr, y_arr)
            self._model_upper = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                loss="quantile",
                alpha=self.quantile_upper,
                random_state=self.random_state,
            )
            self._model_upper.fit(X_arr, y_arr)
        else:
            # Default: gradient_boosting
            self._model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                loss="squared_error",
                random_state=self.random_state,
            )
            self._model.fit(X_arr, y_arr)
            # Use residuals for interval estimation
            self._model_lower = None
            self._model_upper = None

    def predict(self, X: pd.DataFrame) -> list[PredictionResult]:
        """Predict target values with confidence intervals.

        Parameters
        ----------
        X
            Feature matrix (same columns as training data).

        Returns
        -------
        list[PredictionResult]
            One prediction per row in X.
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted. Call .fit() first.")

        if self._fallback_percentiles is not None:
            # Percentile fallback
            return [
                PredictionResult(
                    point=self._fallback_percentiles["median"],
                    lower=self._fallback_percentiles["lower"],
                    upper=self._fallback_percentiles["upper"],
                    confidence=self.quantile_upper - self.quantile_lower,
                )
                for _ in range(len(X))
            ]

        return self._predict_sklearn(X)

    def _predict_sklearn(self, X: pd.DataFrame) -> list[PredictionResult]:
        """Predict using fitted sklearn models."""
        # Align columns with training
        aligned = X.reindex(columns=self._feature_names, fill_value=0)
        X_arr = aligned.values.astype(np.float64)
        np.nan_to_num(X_arr, copy=False)

        points = self._model.predict(X_arr)

        if self._model_lower is not None and self._model_upper is not None:
            lowers = self._model_lower.predict(X_arr)
            uppers = self._model_upper.predict(X_arr)
        elif self.model_type == "random_forest":
            # Use individual tree predictions for intervals
            tree_preds = np.array([t.predict(X_arr) for t in self._model.estimators_])
            lowers = np.percentile(tree_preds, self.quantile_lower * 100, axis=0)
            uppers = np.percentile(tree_preds, self.quantile_upper * 100, axis=0)
        else:
            # Heuristic interval: ±30% of point prediction
            lowers = points * 0.7
            uppers = points * 1.3

        results = []
        for i in range(len(points)):
            results.append(
                PredictionResult(
                    point=float(max(0, points[i])),
                    lower=float(max(0, lowers[i])),
                    upper=float(max(0, uppers[i])),
                    confidence=self.quantile_upper - self.quantile_lower,
                )
            )
        return results

    def feature_importances(self) -> dict[str, float]:
        """Return feature importance scores if available."""
        if self._model is None or not hasattr(self._model, "feature_importances_"):
            return {}
        importances = self._model.feature_importances_
        return dict(zip(self._feature_names, [float(v) for v in importances], strict=False))

    def save(self, path: str | Path) -> None:
        """Persist model to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        meta = {
            "model_type": self.model_type,
            "quantile_lower": self.quantile_lower,
            "quantile_upper": self.quantile_upper,
            "feature_names": self._feature_names,
            "is_fitted": self._is_fitted,
            "fallback_percentiles": self._fallback_percentiles,
        }
        (path / "metadata.json").write_text(json.dumps(meta, indent=2))

        if self._model is not None:
            try:
                import joblib

                joblib.dump(self._model, path / "model.joblib")
                if self._model_lower is not None:
                    joblib.dump(self._model_lower, path / "model_lower.joblib")
                if self._model_upper is not None:
                    joblib.dump(self._model_upper, path / "model_upper.joblib")
            except ImportError:
                pass  # Cannot persist without joblib

    @classmethod
    def load(cls, path: str | Path) -> ResourceModel:
        """Load a persisted model from disk."""
        path = Path(path)
        meta_text = (path / "metadata.json").read_text()
        meta = json.loads(meta_text)

        instance = cls(
            model_type=meta["model_type"],
            quantile_lower=meta.get("quantile_lower", 0.05),
            quantile_upper=meta.get("quantile_upper", 0.95),
        )
        instance._feature_names = meta.get("feature_names", [])
        instance._is_fitted = meta.get("is_fitted", False)
        instance._fallback_percentiles = meta.get("fallback_percentiles")

        model_path = path / "model.joblib"
        if model_path.exists():
            try:
                import joblib

                instance._model = joblib.load(model_path)
                lower_path = path / "model_lower.joblib"
                upper_path = path / "model_upper.joblib"
                if lower_path.exists():
                    instance._model_lower = joblib.load(lower_path)
                if upper_path.exists():
                    instance._model_upper = joblib.load(upper_path)
            except ImportError:
                pass

        return instance


__all__ = ["ModelQuality", "PredictionResult", "ResourceModel"]
