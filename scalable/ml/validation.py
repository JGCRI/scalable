"""Cross-validation and model quality assessment for resource models."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scalable.ml.features import FeatureExtractor
from scalable.ml.models import ModelQuality, ResourceModel


def cross_validate_advisor(
    records: pd.DataFrame,
    *,
    model_type: str = "gradient_boosting",
    target_column: str = "duration_num",
    n_splits: int = 5,
    random_state: int = 42,
) -> ModelQuality:
    """Cross-validate a resource model against historical telemetry.

    Parameters
    ----------
    records
        Raw telemetry records (same format as ResourceAdvisor internal frame).
    model_type
        Model type to evaluate (``gradient_boosting``, ``random_forest``,
        ``quantile_regression``).
    target_column
        Target column to predict (``duration_num`` or ``requested_memory_num``).
    n_splits
        Number of cross-validation folds.
    random_state
        Random state for reproducibility.

    Returns
    -------
    ModelQuality
        Aggregated quality metrics across all folds.
    """
    extractor = FeatureExtractor()
    features = extractor.extract_from_history(records)

    if features.empty or target_column not in features.columns:
        return ModelQuality(
            mae=float("inf"),
            rmse=float("inf"),
            r2=0.0,
            coverage=0.0,
            n_samples=0,
            model_type=model_type,
            target_name=target_column,
        )

    # Filter rows with valid target
    valid_mask = features[target_column].notna() & (features[target_column] > 0)
    features = features[valid_mask].reset_index(drop=True)

    if len(features) < n_splits * 2:
        return ModelQuality(
            mae=float("inf"),
            rmse=float("inf"),
            r2=0.0,
            coverage=0.0,
            n_samples=len(features),
            model_type=model_type,
            target_name=target_column,
        )

    y = features[target_column]
    X = features.drop(columns=[target_column, "requested_memory_num"], errors="ignore")

    # Simple k-fold (no sklearn dependency required for splitting)
    indices = np.arange(len(features))
    rng = np.random.default_rng(random_state)
    rng.shuffle(indices)
    folds = np.array_split(indices, n_splits)

    all_errors: list[float] = []
    all_sq_errors: list[float] = []
    all_in_interval: list[bool] = []
    all_y_true: list[float] = []
    all_y_pred: list[float] = []

    for i in range(n_splits):
        test_idx = folds[i]
        train_idx = np.concatenate([folds[j] for j in range(n_splits) if j != i])

        X_train = X.iloc[train_idx]
        y_train = y.iloc[train_idx]
        X_test = X.iloc[test_idx]
        y_test = y.iloc[test_idx]

        model = ResourceModel(model_type=model_type, random_state=random_state)
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)

        for pred, true_val in zip(predictions, y_test, strict=False):
            error = abs(pred.point - true_val)
            all_errors.append(error)
            all_sq_errors.append(error**2)
            all_y_true.append(true_val)
            all_y_pred.append(pred.point)

            # Check if true value is within predicted interval
            if pred.lower is not None and pred.upper is not None:
                in_interval = pred.lower <= true_val <= pred.upper
            else:
                in_interval = True  # No interval means no coverage check
            all_in_interval.append(in_interval)

    mae = float(np.mean(all_errors))
    rmse = float(np.sqrt(np.mean(all_sq_errors)))
    coverage = float(np.mean(all_in_interval))

    # R² calculation
    y_true_arr = np.array(all_y_true)
    y_pred_arr = np.array(all_y_pred)
    ss_res = np.sum((y_true_arr - y_pred_arr) ** 2)
    ss_tot = np.sum((y_true_arr - np.mean(y_true_arr)) ** 2)
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    return ModelQuality(
        mae=mae,
        rmse=rmse,
        r2=r2,
        coverage=coverage,
        n_samples=len(features),
        model_type=model_type,
        target_name=target_column,
    )


__all__ = ["cross_validate_advisor"]
