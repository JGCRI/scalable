"""Deterministic, explainable resource recommendations from run telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from dask.utils import parse_bytes

from scalable.telemetry.collectors import iter_run_dirs, read_jsonl


def _memory_to_bytes(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(parse_bytes(value))
    except Exception:
        return None
    if parsed <= 0:
        return None
    return parsed


def _bytes_to_gib_string(value: int | None) -> str | None:
    if value is None or value <= 0:
        return None
    gib = (value + (1024**3 - 1)) // (1024**3)
    return f"{int(gib)}G"


def _seconds_to_hhmmss(seconds: float | None) -> str | None:
    if seconds is None or seconds <= 0:
        return None
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass(frozen=True)
class ResourceRecommendation:
    """Explainable recommendation payload returned by :class:`ResourceAdvisor`."""

    task: str
    target: str | None
    confidence: float
    workers: dict[str, int]
    resources: dict[str, dict[str, Any]]
    evidence: dict[str, Any]


class ResourceAdvisor:
    """Heuristic advisor using historical quantiles from telemetry."""

    def __init__(self, records: pd.DataFrame) -> None:
        self._records = records.copy()

    @classmethod
    def from_history(cls, runs_dir: str | Path) -> ResourceAdvisor:
        """Build advisor state from telemetry run directories."""
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
                if not entity:
                    continue
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
                        "requested_memory_bytes": _memory_to_bytes(resources.get("requested_memory")),
                        "requested_walltime": resources.get("requested_walltime"),
                    }
                )

        frame = pd.DataFrame(rows)
        return cls(frame)

    def recommend(
        self,
        *,
        task: str,
        input_features: dict[str, Any] | None = None,
        target: str | None = None,
        confidence: float = 0.95,
    ) -> ResourceRecommendation:
        """Recommend workers/resources using confidence-indexed quantiles."""
        _ = input_features  # reserved for Phase 5 learned models

        q = min(max(float(confidence), 0.5), 0.99)
        frame = self._records
        if frame.empty:
            return ResourceRecommendation(
                task=task,
                target=target,
                confidence=q,
                workers={task: 1},
                resources={task: {"cpus": 1, "memory": None, "walltime": None}},
                evidence={"records": 0, "reason": "no history"},
            )

        scoped = frame[frame["task_name"] == task]
        if target is not None and not scoped.empty:
            scoped_target = scoped[scoped["target"] == target]
            if not scoped_target.empty:
                scoped = scoped_target

        if scoped.empty:
            return ResourceRecommendation(
                task=task,
                target=target,
                confidence=q,
                workers={task: 1},
                resources={task: {"cpus": 1, "memory": None, "walltime": None}},
                evidence={"records": 0, "reason": "task not found in history"},
            )

        component = scoped["component"].dropna().iloc[-1] if scoped["component"].notna().any() else task
        component = str(component)

        workers_series = pd.to_numeric(scoped["requested_workers"], errors="coerce").dropna()
        cpus_series = pd.to_numeric(scoped["requested_cpus"], errors="coerce").dropna()
        duration_series = pd.to_numeric(scoped["duration_s"], errors="coerce").dropna()
        mem_series = pd.to_numeric(scoped["requested_memory_bytes"], errors="coerce").dropna()

        workers = int(max(1, round(float(workers_series.quantile(q))))) if not workers_series.empty else 1
        cpus = int(max(1, round(float(cpus_series.quantile(q))))) if not cpus_series.empty else 1

        memory_bytes = int(mem_series.quantile(q)) if not mem_series.empty else None
        if memory_bytes is not None:
            memory_bytes = int(memory_bytes * 1.10)
        walltime_seconds = float(duration_series.quantile(q) * 1.20) if not duration_series.empty else None

        memory = _bytes_to_gib_string(memory_bytes)
        walltime = _seconds_to_hhmmss(walltime_seconds)

        evidence = {
            "records": int(len(scoped.index)),
            "quantile": q,
            "component": component,
            "state_counts": scoped["state"].value_counts().to_dict(),
        }

        return ResourceRecommendation(
            task=task,
            target=target,
            confidence=q,
            workers={component: workers},
            resources={
                component: {
                    "cpus": cpus,
                    "memory": memory,
                    "walltime": walltime,
                }
            },
            evidence=evidence,
        )


__all__ = ["ResourceAdvisor", "ResourceRecommendation"]
