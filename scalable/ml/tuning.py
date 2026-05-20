"""Distributed hyperparameter tuning via Dask-ML (Phase 5).

Provides a thin wrapper around Dask-ML search strategies for distributed
model selection within a Scalable session. Falls back to sequential sklearn
search when Dask-ML is unavailable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class TuningResult:
    """Result of a hyperparameter search."""

    best_params: dict[str, Any]
    best_score: float
    all_results: pd.DataFrame
    best_estimator: Any
    n_iterations: int
    wall_time_s: float
    strategy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_params": self.best_params,
            "best_score": self.best_score,
            "n_iterations": self.n_iterations,
            "wall_time_s": self.wall_time_s,
            "strategy": self.strategy,
        }


class HyperparameterSearch:
    """Distributed hyperparameter tuning via Dask-ML.

    Supports hyperband, successive halving, and random search strategies.
    Falls back to sklearn's ``RandomizedSearchCV`` when Dask-ML is not
    available.

    Parameters
    ----------
    estimator
        An sklearn-compatible estimator to tune.
    param_space
        Parameter search space. For Dask-ML hyperband, use scipy
        distributions. For random search, use lists or distributions.
    strategy
        Search strategy: ``"hyperband"``, ``"successive_halving"``, or
        ``"random"``.
    n_iter
        Maximum number of parameter combinations to evaluate.
    scoring
        Scoring metric name (sklearn convention, e.g., ``"neg_mean_absolute_error"``).
    random_state
        Random state for reproducibility.
    """

    def __init__(
        self,
        estimator: Any,
        param_space: dict[str, Any],
        *,
        strategy: str = "hyperband",
        n_iter: int = 50,
        scoring: str | None = None,
        random_state: int = 42,
    ) -> None:
        self.estimator = estimator
        self.param_space = param_space
        self.strategy = strategy
        self.n_iter = n_iter
        self.scoring = scoring or "neg_mean_absolute_error"
        self.random_state = random_state

    def fit(
        self,
        X: Any,
        y: Any,
        *,
        client: Any | None = None,
    ) -> TuningResult:
        """Run the hyperparameter search.

        Parameters
        ----------
        X
            Training features (numpy array, pandas DataFrame, or dask array).
        y
            Training target.
        client
            Optional Dask client for distributed execution. If ``None``,
            falls back to local sequential search.

        Returns
        -------
        TuningResult
            Best parameters, score, and full results.
        """
        start_time = time.time()

        try:
            result = self._fit_dask_ml(X, y, client=client)
        except ImportError:
            result = self._fit_sklearn_fallback(X, y)

        wall_time = time.time() - start_time
        return TuningResult(
            best_params=result["best_params"],
            best_score=result["best_score"],
            all_results=result.get("all_results", pd.DataFrame()),
            best_estimator=result["best_estimator"],
            n_iterations=result.get("n_iterations", self.n_iter),
            wall_time_s=wall_time,
            strategy=self.strategy,
        )

    def _fit_dask_ml(self, X: Any, y: Any, *, client: Any) -> dict[str, Any]:
        """Fit using Dask-ML search strategies."""
        from dask_ml.model_selection import HyperbandSearchCV, RandomizedSearchCV

        if self.strategy == "hyperband":
            search = HyperbandSearchCV(
                self.estimator,
                self.param_space,
                max_iter=self.n_iter,
                random_state=self.random_state,
            )
        elif self.strategy == "successive_halving":
            # Dask-ML's HyperbandSearchCV with aggressive_elimination is
            # equivalent to successive halving
            search = HyperbandSearchCV(
                self.estimator,
                self.param_space,
                max_iter=self.n_iter,
                aggressiveness=4,
                random_state=self.random_state,
            )
        else:
            # random
            search = RandomizedSearchCV(
                self.estimator,
                self.param_space,
                n_iter=self.n_iter,
                scoring=self.scoring,
                random_state=self.random_state,
            )

        search.fit(X, y)

        cv_results = pd.DataFrame(search.cv_results_) if hasattr(search, "cv_results_") else pd.DataFrame()

        return {
            "best_params": search.best_params_,
            "best_score": float(search.best_score_),
            "best_estimator": search.best_estimator_,
            "all_results": cv_results,
            "n_iterations": len(cv_results) if not cv_results.empty else self.n_iter,
        }

    def _fit_sklearn_fallback(self, X: Any, y: Any) -> dict[str, Any]:
        """Fallback to sklearn's RandomizedSearchCV."""
        try:
            from sklearn.model_selection import RandomizedSearchCV

            search = RandomizedSearchCV(
                self.estimator,
                self.param_space,
                n_iter=min(self.n_iter, 20),  # Cap for sequential search
                scoring=self.scoring,
                cv=3,
                random_state=self.random_state,
                n_jobs=-1,
            )
            search.fit(X, y)

            cv_results = pd.DataFrame(search.cv_results_)
            return {
                "best_params": search.best_params_,
                "best_score": float(search.best_score_),
                "best_estimator": search.best_estimator_,
                "all_results": cv_results,
                "n_iterations": len(cv_results),
            }
        except ImportError:
            # No sklearn either — return trivial result
            return {
                "best_params": {},
                "best_score": 0.0,
                "best_estimator": self.estimator,
                "all_results": pd.DataFrame(),
                "n_iterations": 0,
            }


__all__ = ["HyperparameterSearch", "TuningResult"]
