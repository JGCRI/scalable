"""Active learning for intelligent scenario selection."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from scalable.emulation.surrogate import TrainedEmulator


class ActiveLearner:
    """Select next-best scenarios to maximize emulator training efficiency.

    Uses acquisition functions to identify which candidate scenarios
    would be most informative for improving the emulator, reducing the
    number of expensive full-model runs needed.

    Parameters
    ----------
    emulator
        A trained emulator to query for uncertainty estimates.
    acquisition
        Acquisition strategy: ``"expected_improvement"``,
        ``"uncertainty"``, or ``"random"``.
    batch_size
        Default number of suggestions per call.
    random_state
        Random state for reproducibility.
    """

    def __init__(
        self,
        emulator: TrainedEmulator,
        *,
        acquisition: str = "expected_improvement",
        batch_size: int = 1,
        random_state: int = 42,
    ) -> None:
        valid_strategies = {"expected_improvement", "uncertainty", "random"}
        if acquisition not in valid_strategies:
            raise ValueError(
                f"acquisition must be one of {sorted(valid_strategies)}, got {acquisition!r}"
            )

        self._emulator = emulator
        self._acquisition = acquisition
        self._batch_size = batch_size
        self._rng = np.random.default_rng(random_state)
        self._observations: list[dict[str, Any]] = []

    @property
    def acquisition_strategy(self) -> str:
        """Current acquisition strategy."""
        return self._acquisition

    @property
    def n_observations(self) -> int:
        """Number of observations incorporated."""
        return len(self._observations)

    def suggest(
        self,
        candidates: pd.DataFrame,
        *,
        n_suggestions: int | None = None,
    ) -> pd.DataFrame:
        """Select the most informative candidates for full-model evaluation.

        Parameters
        ----------
        candidates
            DataFrame of candidate scenarios. Each row represents a
            candidate input configuration. Column names should match
            the emulator's input names.
        n_suggestions
            Number of candidates to select. Defaults to ``batch_size``.

        Returns
        -------
        pd.DataFrame
            Selected candidates (subset of input DataFrame).
        """
        n = n_suggestions or self._batch_size
        n = min(n, len(candidates))

        if n <= 0 or candidates.empty:
            return candidates.iloc[:0]

        if self._acquisition == "random":
            return self._suggest_random(candidates, n)
        elif self._acquisition == "uncertainty":
            return self._suggest_max_uncertainty(candidates, n)
        else:  # expected_improvement
            return self._suggest_expected_improvement(candidates, n)

    def _suggest_random(self, candidates: pd.DataFrame, n: int) -> pd.DataFrame:
        """Random baseline selection."""
        indices = self._rng.choice(len(candidates), size=n, replace=False)
        return candidates.iloc[indices].reset_index(drop=True)

    def _suggest_max_uncertainty(self, candidates: pd.DataFrame, n: int) -> pd.DataFrame:
        """Select candidates where emulator is least confident."""
        uncertainties = []
        for _, row in candidates.iterrows():
            inputs = row.to_dict()
            unc = self._emulator.uncertainty(inputs)
            uncertainties.append(unc)

        uncertainties_arr = np.array(uncertainties)
        # Select top-n highest uncertainty candidates
        top_indices = np.argsort(uncertainties_arr)[-n:][::-1]
        return candidates.iloc[top_indices].reset_index(drop=True)

    def _suggest_expected_improvement(
        self, candidates: pd.DataFrame, n: int
    ) -> pd.DataFrame:
        """Select candidates maximizing expected information gain.

        Uses uncertainty as a proxy for expected improvement when the
        full acquisition function requires more sophisticated modeling.
        Also incorporates diversity by penalizing candidates too similar
        to existing observations.
        """
        scores: list[float] = []

        for _, row in candidates.iterrows():
            inputs = row.to_dict()

            # Uncertainty component
            unc = self._emulator.uncertainty(inputs)

            # Diversity component (distance from existing observations)
            diversity = self._compute_diversity(inputs)

            # Combined score: uncertainty * diversity bonus
            score = unc * (1.0 + 0.3 * diversity)
            scores.append(score)

        scores_arr = np.array(scores)
        top_indices = np.argsort(scores_arr)[-n:][::-1]
        return candidates.iloc[top_indices].reset_index(drop=True)

    def _compute_diversity(self, inputs: dict[str, Any]) -> float:
        """Compute diversity score based on distance from observations."""
        if not self._observations:
            return 1.0  # Maximum diversity when no observations

        # Simple Euclidean-like distance in normalized space
        input_vec = np.array([
            float(v) for v in inputs.values() if isinstance(v, (int, float))
        ])

        if len(input_vec) == 0:
            return 1.0

        min_dist = float("inf")
        for obs in self._observations:
            obs_vec = np.array([
                float(obs.get(k, 0))
                for k in inputs.keys()
                if isinstance(inputs.get(k), (int, float))
            ])
            if len(obs_vec) == len(input_vec):
                dist = float(np.linalg.norm(input_vec - obs_vec))
                min_dist = min(min_dist, dist)

        if min_dist == float("inf"):
            return 1.0

        # Normalize to [0, 1] using a sigmoid-like transform
        return float(1.0 - np.exp(-min_dist / (np.linalg.norm(input_vec) + 1e-10)))

    def update(self, new_observations: pd.DataFrame) -> None:
        """Incorporate new full-model results into acquisition state.

        Parameters
        ----------
        new_observations
            DataFrame of new observations. Each row should contain
            the input values that were evaluated with the full model.
        """
        for _, row in new_observations.iterrows():
            self._observations.append(row.to_dict())

    def reset(self) -> None:
        """Clear all observations and reset state."""
        self._observations.clear()


__all__ = ["ActiveLearner"]
