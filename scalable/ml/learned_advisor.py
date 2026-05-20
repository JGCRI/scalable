"""ML-backed resource advisor using telemetry history as training data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from dask.utils import parse_bytes

from scalable.advising.resources import (
    ResourceRecommendation,
    _bytes_to_gib_string,
    _seconds_to_hhmmss,
)
from scalable.ml.features import FeatureExtractor
from scalable.ml.models import ResourceModel
from scalable.telemetry.collectors import iter_run_dirs, read_jsonl


def _memory_to_bytes(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(parse_bytes(value))
    except Exception:
        return None
    return parsed if parsed > 0 else None


class LearnedAdvisor:
    """ML-backed resource advisor using telemetry history as training data.

    Replaces heuristic quantile-based recommendations with feature-based
    predictions from trained ML models. Falls back to percentile estimation
    when insufficient data or sklearn unavailable.
    """

    #: Minimum number of records for a task before activating ML predictions
    MIN_SAMPLES_FOR_ML: int = 10

    def __init__(
        self,
        records: pd.DataFrame,
        *,
        duration_model: ResourceModel | None = None,
        memory_model: ResourceModel | None = None,
        extractor: FeatureExtractor | None = None,
    ) -> None:
        self._records = records.copy()
        self._duration_model = duration_model
        self._memory_model = memory_model
        self._extractor = extractor or FeatureExtractor()

    @classmethod
    def from_history(
        cls,
        runs_dir: str | Path,
        *,
        model_type: str = "gradient_boosting",
        retrain: bool = False,
        cache_dir: str | Path | None = None,
    ) -> LearnedAdvisor:
        """Build and train advisor from telemetry run directories.

        Parameters
        ----------
        runs_dir
            Path to ``.scalable/runs/`` directory.
        model_type
            ML model type: ``gradient_boosting``, ``random_forest``, or
            ``quantile_regression``.
        retrain
            Force retraining even if cached model exists.
        cache_dir
            Directory to cache trained models. Defaults to
            ``<runs_dir>/../models``.
        """
        records = cls._load_records(runs_dir)
        extractor = FeatureExtractor()

        # Attempt to load cached models
        if cache_dir is None:
            cache_dir = Path(runs_dir).parent / "models"
        cache_path = Path(cache_dir)

        duration_model: ResourceModel | None = None
        memory_model: ResourceModel | None = None

        if not retrain and (cache_path / "duration" / "metadata.json").exists():
            try:
                duration_model = ResourceModel.load(cache_path / "duration")
            except Exception:
                duration_model = None

        if not retrain and (cache_path / "memory" / "metadata.json").exists():
            try:
                memory_model = ResourceModel.load(cache_path / "memory")
            except Exception:
                memory_model = None

        # Train if needed
        if duration_model is None or memory_model is None:
            features = extractor.extract_from_history(records)
            if not features.empty and len(features) >= cls.MIN_SAMPLES_FOR_ML:
                if duration_model is None:
                    valid_duration = features[
                        features["duration_num"].notna() & (features["duration_num"] > 0)
                    ]
                    if len(valid_duration) >= cls.MIN_SAMPLES_FOR_ML:
                        y_dur = valid_duration["duration_num"]
                        X_dur = valid_duration.drop(
                            columns=["duration_num", "requested_memory_num"],
                            errors="ignore",
                        )
                        duration_model = ResourceModel(
                            model_type=model_type, random_state=42
                        )
                        duration_model.fit(X_dur, y_dur)
                        try:
                            duration_model.save(cache_path / "duration")
                        except Exception:
                            pass

                if memory_model is None:
                    valid_memory = features[
                        features["requested_memory_num"].notna()
                        & (features["requested_memory_num"] > 0)
                    ]
                    if len(valid_memory) >= cls.MIN_SAMPLES_FOR_ML:
                        y_mem = valid_memory["requested_memory_num"]
                        X_mem = valid_memory.drop(
                            columns=["duration_num", "requested_memory_num"],
                            errors="ignore",
                        )
                        memory_model = ResourceModel(
                            model_type=model_type, random_state=42
                        )
                        memory_model.fit(X_mem, y_mem)
                        try:
                            memory_model.save(cache_path / "memory")
                        except Exception:
                            pass

        return cls(
            records,
            duration_model=duration_model,
            memory_model=memory_model,
            extractor=extractor,
        )

    @classmethod
    def _load_records(cls, runs_dir: str | Path) -> pd.DataFrame:
        """Load telemetry records from run directories."""
        rows: list[dict[str, Any]] = []
        for run_dir in iter_run_dirs(runs_dir):
            run_json = run_dir / "run.json"
            if not run_json.exists():
                continue
            run_meta = pd.read_json(run_json, typ="series")
            run_id = str(run_meta.get("run_id", run_dir.name))
            target_name = run_meta.get("target_name")

            task_rows = read_jsonl(run_dir / "tasks.jsonl")
            resource_rows = read_jsonl(run_dir / "resources.jsonl")

            resources_by_task: dict[str, dict[str, Any]] = {}
            for r in resource_rows:
                if r.get("entity_type") != "task":
                    continue
                entity = str(r.get("entity_id", ""))
                if entity:
                    resources_by_task[entity] = r

            for t in task_rows:
                if t.get("state") not in {"succeeded", "failed", "cancelled"}:
                    continue
                task_id = str(t.get("task_id", ""))
                if not task_id:
                    continue
                resources = resources_by_task.get(task_id, {})
                rows.append(
                    {
                        "run_id": run_id,
                        "target": target_name,
                        "task_id": task_id,
                        "task_name": t.get("task_name"),
                        "component": t.get("component"),
                        "state": t.get("state"),
                        "duration_s": t.get("duration_s"),
                        "requested_workers": resources.get("requested_workers"),
                        "requested_cpus": resources.get("requested_cpus"),
                        "requested_memory": resources.get("requested_memory"),
                        "requested_memory_bytes": _memory_to_bytes(
                            resources.get("requested_memory")
                        ),
                        "requested_walltime": resources.get("requested_walltime"),
                    }
                )

        return pd.DataFrame(rows)

    def recommend(
        self,
        *,
        task: str,
        input_features: dict[str, Any] | None = None,
        target: str | None = None,
        confidence: float = 0.95,
    ) -> ResourceRecommendation:
        """Recommend resources using ML predictions with calibrated intervals.

        Falls back to quantile heuristics when ML is unavailable or data is
        insufficient for the requested task.
        """
        q = min(max(float(confidence), 0.5), 0.99)

        # Check if we have enough data for this task
        scoped = self._records[self._records["task_name"] == task]
        if target is not None and not scoped.empty:
            scoped_target = scoped[scoped["target"] == target]
            if not scoped_target.empty:
                scoped = scoped_target

        if scoped.empty or len(scoped) < self.MIN_SAMPLES_FOR_ML:
            # Fall back to heuristic
            return self._heuristic_recommend(task, target, q, scoped)

        # Compute history stats for feature extraction
        stats = self._extractor.compute_history_stats(self._records, task, target)
        X_pred = self._extractor.extract_from_task(
            task_name=task,
            input_features=input_features,
            component=scoped["component"].dropna().iloc[-1] if scoped["component"].notna().any() else None,
            target=target,
            history_stats=stats,
        )

        # Predict duration
        predicted_walltime: str | None = None
        duration_evidence: dict[str, Any] = {}
        if self._duration_model is not None and self._duration_model.is_fitted:
            dur_preds = self._duration_model.predict(X_pred)
            if dur_preds:
                dur_pred = dur_preds[0]
                # Use upper bound for safety
                walltime_s = dur_pred.upper if dur_pred.upper else dur_pred.point * 1.2
                predicted_walltime = _seconds_to_hhmmss(walltime_s)
                duration_evidence = {
                    "predicted_duration_s": dur_pred.point,
                    "duration_lower": dur_pred.lower,
                    "duration_upper": dur_pred.upper,
                    "feature_importances": self._duration_model.feature_importances(),
                }

        # Predict memory
        predicted_memory: str | None = None
        memory_evidence: dict[str, Any] = {}
        if self._memory_model is not None and self._memory_model.is_fitted:
            mem_preds = self._memory_model.predict(X_pred)
            if mem_preds:
                mem_pred = mem_preds[0]
                # Use upper bound for safety with 10% margin
                memory_bytes = int((mem_pred.upper or mem_pred.point * 1.3) * 1.1)
                predicted_memory = _bytes_to_gib_string(memory_bytes)
                memory_evidence = {
                    "predicted_memory_bytes": mem_pred.point,
                    "memory_lower": mem_pred.lower,
                    "memory_upper": mem_pred.upper,
                }

        # Component and workers from history
        component = str(
            scoped["component"].dropna().iloc[-1]
            if scoped["component"].notna().any()
            else task
        )
        workers_series = pd.to_numeric(scoped["requested_workers"], errors="coerce").dropna()
        workers = int(max(1, round(float(workers_series.quantile(q))))) if not workers_series.empty else 1

        cpus_series = pd.to_numeric(scoped["requested_cpus"], errors="coerce").dropna()
        cpus = int(max(1, round(float(cpus_series.quantile(q))))) if not cpus_series.empty else 1

        evidence: dict[str, Any] = {
            "records": int(len(scoped)),
            "method": "ml",
            "model_type": self._duration_model.model_type if self._duration_model else "none",
            "confidence": q,
            "component": component,
            **duration_evidence,
            **memory_evidence,
        }

        return ResourceRecommendation(
            task=task,
            target=target,
            confidence=q,
            workers={component: workers},
            resources={
                component: {
                    "cpus": cpus,
                    "memory": predicted_memory,
                    "walltime": predicted_walltime,
                }
            },
            evidence=evidence,
        )

    def _heuristic_recommend(
        self,
        task: str,
        target: str | None,
        q: float,
        scoped: pd.DataFrame,
    ) -> ResourceRecommendation:
        """Fallback to simple quantile heuristics (Phase 2 behavior)."""
        if scoped.empty:
            return ResourceRecommendation(
                task=task,
                target=target,
                confidence=q,
                workers={task: 1},
                resources={task: {"cpus": 1, "memory": None, "walltime": None}},
                evidence={"records": 0, "method": "heuristic", "reason": "no history"},
            )

        component = str(
            scoped["component"].dropna().iloc[-1]
            if scoped["component"].notna().any()
            else task
        )

        workers_series = pd.to_numeric(scoped["requested_workers"], errors="coerce").dropna()
        cpus_series = pd.to_numeric(scoped["requested_cpus"], errors="coerce").dropna()
        duration_series = pd.to_numeric(scoped["duration_s"], errors="coerce").dropna()
        mem_series = pd.to_numeric(scoped["requested_memory_bytes"], errors="coerce").dropna()

        workers = int(max(1, round(float(workers_series.quantile(q))))) if not workers_series.empty else 1
        cpus = int(max(1, round(float(cpus_series.quantile(q))))) if not cpus_series.empty else 1

        memory_bytes = int(mem_series.quantile(q) * 1.10) if not mem_series.empty else None
        walltime_s = float(duration_series.quantile(q) * 1.20) if not duration_series.empty else None

        return ResourceRecommendation(
            task=task,
            target=target,
            confidence=q,
            workers={component: workers},
            resources={
                component: {
                    "cpus": cpus,
                    "memory": _bytes_to_gib_string(memory_bytes),
                    "walltime": _seconds_to_hhmmss(walltime_s),
                }
            },
            evidence={
                "records": int(len(scoped)),
                "method": "heuristic",
                "reason": f"insufficient data (need {self.MIN_SAMPLES_FOR_ML})",
                "component": component,
            },
        )

    def explain(self, recommendation: ResourceRecommendation) -> dict[str, Any]:
        """Return detailed explanation including feature importances."""
        explanation: dict[str, Any] = {
            "task": recommendation.task,
            "target": recommendation.target,
            "confidence": recommendation.confidence,
            "method": recommendation.evidence.get("method", "unknown"),
        }

        if recommendation.evidence.get("method") == "ml":
            explanation["feature_importances"] = recommendation.evidence.get(
                "feature_importances", {}
            )
            explanation["prediction_intervals"] = {
                "duration": {
                    "point": recommendation.evidence.get("predicted_duration_s"),
                    "lower": recommendation.evidence.get("duration_lower"),
                    "upper": recommendation.evidence.get("duration_upper"),
                },
                "memory": {
                    "point": recommendation.evidence.get("predicted_memory_bytes"),
                    "lower": recommendation.evidence.get("memory_lower"),
                    "upper": recommendation.evidence.get("memory_upper"),
                },
            }
        else:
            explanation["fallback_reason"] = recommendation.evidence.get("reason", "")

        return explanation

    def evaluate(self, *, test_fraction: float = 0.2) -> dict[str, Any]:
        """Cross-validate models and return quality metrics."""
        from scalable.ml.validation import cross_validate_advisor

        quality_duration = cross_validate_advisor(
            self._records,
            model_type=self._duration_model.model_type if self._duration_model else "gradient_boosting",
            target_column="duration_num",
        )
        quality_memory = cross_validate_advisor(
            self._records,
            model_type=self._memory_model.model_type if self._memory_model else "gradient_boosting",
            target_column="requested_memory_num",
        )

        return {
            "duration_model": quality_duration.to_dict(),
            "memory_model": quality_memory.to_dict(),
        }


__all__ = ["LearnedAdvisor"]
