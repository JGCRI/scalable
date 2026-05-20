"""Uncertainty calibration utilities for emulators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class CalibrationResult:
    """Result of emulator uncertainty calibration assessment."""

    coverage_90: float  # Fraction of true values within 90% interval
    coverage_95: float  # Fraction of true values within 95% interval
    mean_interval_width: float
    sharpness: float  # Average interval width relative to prediction magnitude
    n_samples: int
    is_calibrated: bool  # True if coverage is within acceptable range

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_90": self.coverage_90,
            "coverage_95": self.coverage_95,
            "mean_interval_width": self.mean_interval_width,
            "sharpness": self.sharpness,
            "n_samples": self.n_samples,
            "is_calibrated": self.is_calibrated,
        }


def calibrate_emulator(
    predictions: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
    *,
    output_name: str,
    tolerance: float = 0.1,
) -> CalibrationResult:
    """Assess calibration of emulator uncertainty estimates.

    Checks whether the stated confidence intervals actually contain
    the true values at the stated rate.

    Parameters
    ----------
    predictions
        List of emulator prediction dicts (from ``EmulatorPrediction.to_dict()``).
        Each should have ``outputs`` and ``uncertainty_bounds``.
    actuals
        List of actual output dicts from full-model runs.
        Each should have the ``output_name`` key with the true value.
    output_name
        Which output variable to assess calibration for.
    tolerance
        Acceptable deviation from nominal coverage (e.g., 0.1 means
        90% coverage for a 95% interval is acceptable).

    Returns
    -------
    CalibrationResult
        Calibration assessment with coverage and sharpness metrics.
    """
    if not predictions or not actuals or len(predictions) != len(actuals):
        return CalibrationResult(
            coverage_90=0.0,
            coverage_95=0.0,
            mean_interval_width=0.0,
            sharpness=0.0,
            n_samples=0,
            is_calibrated=False,
        )

    in_90: list[bool] = []
    in_95: list[bool] = []
    widths: list[float] = []
    relative_widths: list[float] = []

    for pred, actual in zip(predictions, actuals, strict=False):
        true_value = actual.get(output_name)
        if true_value is None:
            continue

        true_value = float(true_value)
        outputs = pred.get("outputs", {})
        bounds = pred.get("uncertainty_bounds", {})

        if output_name not in bounds:
            continue

        bound = bounds[output_name]
        if not isinstance(bound, (list, tuple)) or len(bound) != 2:
            continue

        lower, upper = float(bound[0]), float(bound[1])
        width = upper - lower
        widths.append(width)

        pred_value = float(outputs.get(output_name, 0))
        mag = abs(pred_value) + 1e-10
        relative_widths.append(width / mag)

        # 95% interval check (using full bounds)
        in_95.append(lower <= true_value <= upper)

        # 90% interval (shrink bounds by ~5% on each side)
        shrink = width * 0.05
        in_90.append((lower + shrink) <= true_value <= (upper - shrink))

    n = len(in_95)
    if n == 0:
        return CalibrationResult(
            coverage_90=0.0,
            coverage_95=0.0,
            mean_interval_width=0.0,
            sharpness=0.0,
            n_samples=0,
            is_calibrated=False,
        )

    coverage_90 = float(np.mean(in_90))
    coverage_95 = float(np.mean(in_95))
    mean_width = float(np.mean(widths))
    sharpness = float(np.mean(relative_widths))

    # Check if calibration is acceptable
    # For 95% intervals, coverage should be at least 95% - tolerance
    is_calibrated = coverage_95 >= (0.95 - tolerance)

    return CalibrationResult(
        coverage_90=coverage_90,
        coverage_95=coverage_95,
        mean_interval_width=mean_width,
        sharpness=sharpness,
        n_samples=n,
        is_calibrated=is_calibrated,
    )


def compute_confidence_from_uncertainty(
    uncertainty: float,
    *,
    max_uncertainty: float = 1.0,
) -> float:
    """Convert a scalar uncertainty value to a confidence score.

    Parameters
    ----------
    uncertainty
        Raw uncertainty value (higher = less confident).
    max_uncertainty
        Maximum expected uncertainty for normalization.

    Returns
    -------
    float
        Confidence in [0, 1] range (higher = more confident).
    """
    if uncertainty <= 0:
        return 1.0
    if uncertainty >= max_uncertainty:
        return 0.0
    return 1.0 - (uncertainty / max_uncertainty)


def is_in_domain(
    inputs: dict[str, Any],
    domain_bounds: dict[str, tuple[float, float]],
) -> bool:
    """Check if all inputs are within declared domain bounds.

    Parameters
    ----------
    inputs
        Input values to check.
    domain_bounds
        Dict mapping input names to (min, max) tuples.

    Returns
    -------
    bool
        ``True`` if all specified inputs are within bounds.
    """
    for key, (lower, upper) in domain_bounds.items():
        if key in inputs:
            value = inputs[key]
            if isinstance(value, (int, float)):
                if value < lower or value > upper:
                    return False
    return True


__all__ = ["CalibrationResult", "calibrate_emulator", "compute_confidence_from_uncertainty", "is_in_domain"]
