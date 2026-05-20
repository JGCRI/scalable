"""Feature extraction from telemetry records and task arguments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class FeatureExtractor:
    """Extract ML features from telemetry records and task arguments.

    Engineered features include:
    - Task identity (component name hash, tag hash)
    - Resource request features (requested cpus/memory/walltime)
    - Temporal features (hour of day, day of week)
    - Historical aggregates (rolling mean/p95 for same task)
    - Input complexity features (from user-provided input_features dict)
    """

    #: Minimum rows per task group for rolling aggregates
    min_group_size: int = 3

    #: Known numeric input feature names (auto-discovered if not set)
    known_input_features: list[str] = field(default_factory=list)

    def extract_from_history(self, records: pd.DataFrame) -> pd.DataFrame:
        """Engineer features from historical telemetry records.

        Parameters
        ----------
        records
            DataFrame from :class:`~scalable.advising.resources.ResourceAdvisor`
            internal format: columns include ``task_name``, ``component``,
            ``duration_s``, ``requested_cpus``, ``requested_memory_bytes``, etc.

        Returns
        -------
        pd.DataFrame
            Feature matrix suitable for ML model training with target columns
            preserved (``duration_s``, ``requested_memory_bytes``).
        """
        if records.empty:
            return pd.DataFrame()

        df = records.copy()

        # Task identity features (hashed for model consumption)
        df["task_name_hash"] = df["task_name"].apply(
            lambda x: hash(str(x)) % 10000 if pd.notna(x) else 0
        )
        df["component_hash"] = df["component"].apply(
            lambda x: hash(str(x)) % 10000 if pd.notna(x) else 0
        )

        # Numeric resource features
        df["requested_cpus_num"] = pd.to_numeric(
            df.get("requested_cpus"), errors="coerce"
        ).fillna(1)
        df["requested_memory_num"] = pd.to_numeric(
            df.get("requested_memory_bytes"), errors="coerce"
        ).fillna(0)
        df["requested_workers_num"] = pd.to_numeric(
            df.get("requested_workers"), errors="coerce"
        ).fillna(1)

        # Duration target (kept for training, not used as input feature)
        df["duration_num"] = pd.to_numeric(
            df.get("duration_s"), errors="coerce"
        )

        # Historical rolling aggregates per task_name
        df = df.sort_index()
        grouped = df.groupby("task_name", sort=False)
        df["hist_mean_duration"] = grouped["duration_num"].transform(
            lambda s: s.expanding(min_periods=1).mean().shift(1)
        )
        df["hist_p95_duration"] = grouped["duration_num"].transform(
            lambda s: s.expanding(min_periods=1).quantile(0.95).shift(1)
        )
        df["hist_mean_memory"] = grouped["requested_memory_num"].transform(
            lambda s: s.expanding(min_periods=1).mean().shift(1)
        )
        df["hist_count"] = grouped["duration_num"].transform(
            lambda s: s.expanding(min_periods=1).count().shift(1)
        )

        # Fill NaN from rolling aggregates with global means
        for col in ["hist_mean_duration", "hist_p95_duration", "hist_mean_memory", "hist_count"]:
            df[col] = df[col].fillna(0)

        feature_cols = [
            "task_name_hash",
            "component_hash",
            "requested_cpus_num",
            "requested_memory_num",
            "requested_workers_num",
            "hist_mean_duration",
            "hist_p95_duration",
            "hist_mean_memory",
            "hist_count",
        ]

        # Keep targets for training
        target_cols = ["duration_num", "requested_memory_num"]
        available_targets = [c for c in target_cols if c in df.columns]

        return df[feature_cols + available_targets].copy()

    def extract_from_task(
        self,
        task_name: str,
        input_features: dict[str, Any] | None,
        component: str | None,
        target: str | None,
        *,
        history_stats: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Build feature vector for a new prediction request.

        Parameters
        ----------
        task_name
            Name of the task to predict for.
        input_features
            User-provided features (scenario count, input size, etc.).
        component
            Component name associated with the task.
        target
            Deployment target name.
        history_stats
            Pre-computed rolling stats from history (mean_duration, p95, count).

        Returns
        -------
        pd.DataFrame
            Single-row feature DataFrame for model prediction.
        """
        stats = history_stats or {}
        row: dict[str, Any] = {
            "task_name_hash": hash(str(task_name)) % 10000,
            "component_hash": hash(str(component)) % 10000 if component else 0,
            "requested_cpus_num": 1,
            "requested_memory_num": 0,
            "requested_workers_num": 1,
            "hist_mean_duration": stats.get("mean_duration", 0),
            "hist_p95_duration": stats.get("p95_duration", 0),
            "hist_mean_memory": stats.get("mean_memory", 0),
            "hist_count": stats.get("count", 0),
        }

        # Incorporate user-provided numeric input features
        if input_features:
            for key, value in input_features.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    col_name = f"input_{key}"
                    row[col_name] = value

        return pd.DataFrame([row])

    def compute_history_stats(
        self,
        records: pd.DataFrame,
        task_name: str,
        target: str | None = None,
    ) -> dict[str, Any]:
        """Compute summary statistics for a task from historical records.

        These can be passed to :meth:`extract_from_task` as ``history_stats``.
        """
        if records.empty:
            return {"mean_duration": 0, "p95_duration": 0, "mean_memory": 0, "count": 0}

        scoped = records[records["task_name"] == task_name]
        if target is not None and not scoped.empty:
            scoped_target = scoped[scoped.get("target") == target]
            if not scoped_target.empty:
                scoped = scoped_target

        if scoped.empty:
            return {"mean_duration": 0, "p95_duration": 0, "mean_memory": 0, "count": 0}

        duration = pd.to_numeric(scoped.get("duration_s"), errors="coerce").dropna()
        memory = pd.to_numeric(scoped.get("requested_memory_bytes"), errors="coerce").dropna()

        return {
            "mean_duration": float(duration.mean()) if not duration.empty else 0,
            "p95_duration": float(np.percentile(duration, 95)) if not duration.empty else 0,
            "mean_memory": float(memory.mean()) if not memory.empty else 0,
            "count": int(len(scoped)),
        }


__all__ = ["FeatureExtractor"]
