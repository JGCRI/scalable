"""Run-scoped telemetry persistence primitives."""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from scalable.manifest.schema import ManifestModel
from scalable.planning.dryrun import DryRunPlan
from scalable.providers.base import DeploymentSpec

from .collectors import summarize_run
from .events import (
    ArtifactEvent,
    CacheEvent,
    CostEvent,
    FailureEvent,
    ResourceEvent,
    RunMetadata,
    TaskEvent,
    WorkerEvent,
    utcnow_iso,
)

_PROJECT_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def build_run_id(project_name: str) -> str:
    """Build a deterministic-format run id with UTC timestamp and random suffix."""
    stamp = utcnow_iso().replace("-", "").replace(":", "")
    stamp = stamp.replace("T", "T").replace("Z", "Z")
    safe_project = _PROJECT_RE.sub("-", project_name).strip("-") or "project"
    short = uuid.uuid4().hex[:8]
    return f"run-{stamp}-{safe_project}-{short}"


class TelemetryStore:
    """Persist run telemetry as JSONL records under one run directory."""

    _TASKS_FILE = "tasks.jsonl"
    _RESOURCES_FILE = "resources.jsonl"
    _WORKERS_FILE = "workers.jsonl"
    _FAILURES_FILE = "failures.jsonl"
    _CACHE_FILE = "cache.jsonl"
    _ARTIFACTS_FILE = "artifacts.jsonl"
    _COST_FILE = "cost.jsonl"

    def __init__(
        self,
        *,
        run_dir: Path,
        metadata: RunMetadata,
        component_defaults: dict[str, dict[str, Any]],
        provider_name: str,
        target_walltime: str | None,
        telemetry_parquet: bool,
    ) -> None:
        self.run_dir = run_dir
        self.metadata = metadata
        self.component_defaults = component_defaults
        self.provider_name = provider_name
        self.target_walltime = target_walltime
        self.telemetry_parquet = telemetry_parquet

        self._lock = threading.RLock()
        self._closed = False
        self._task_started_at: dict[str, float] = {}

    @property
    def run_id(self) -> str:
        return self.metadata.run_id

    @classmethod
    def create(
        cls,
        *,
        runs_dir: str | Path,
        manifest: ManifestModel,
        spec: DeploymentSpec,
        plan: DryRunPlan,
        telemetry_parquet: bool = False,
    ) -> TelemetryStore:
        """Create run directory and initialize baseline run metadata files."""
        runs_root = Path(runs_dir)
        runs_root.mkdir(parents=True, exist_ok=True)

        run_id = build_run_id(manifest.project.name)
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)

        metadata = RunMetadata(
            run_id=run_id,
            project_name=manifest.project.name,
            target_name=spec.target_name,
            provider_name=spec.provider_name,
            manifest_lock=plan.manifest_lock,
            source_manifest_path=manifest.source_path,
        )

        component_defaults: dict[str, dict[str, Any]] = {}
        for cname, c in spec.components.items():
            component_defaults[cname] = {
                "cpus": c.cpus,
                "memory": c.memory,
            }

        walltime = spec.target.options.get("walltime")
        target_walltime = walltime if isinstance(walltime, str) else None

        store = cls(
            run_dir=run_dir,
            metadata=metadata,
            component_defaults=component_defaults,
            provider_name=spec.provider_name,
            target_walltime=target_walltime,
            telemetry_parquet=telemetry_parquet,
        )
        store._write_bootstrap_files(manifest=manifest, plan=plan)
        return store

    def _write_bootstrap_files(self, *, manifest: ManifestModel, plan: DryRunPlan) -> None:
        (self.run_dir / "manifest.yaml").write_text(
            yaml.safe_dump(manifest.raw, sort_keys=True),
            encoding="utf-8",
        )
        (self.run_dir / "plan.json").write_text(
            json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (self.run_dir / "manifest.lock").write_text(plan.manifest_lock + "\n", encoding="utf-8")
        (self.run_dir / "run.json").write_text(
            json.dumps(self.metadata.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _append_jsonl(self, filename: str, payload: dict[str, Any]) -> None:
        text = json.dumps(payload, sort_keys=True)
        with self._lock:
            with (self.run_dir / filename).open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")

    def record_task_submission(
        self,
        *,
        task_id: str,
        task_name: str,
        component: str | None,
        tag: str | None,
        function_name: str,
        requested_workers: int,
    ) -> None:
        """Record a task submission and a synthetic running transition."""
        self._task_started_at[task_id] = time.monotonic()

        self._append_jsonl(
            self._TASKS_FILE,
            TaskEvent(
                run_id=self.run_id,
                task_id=task_id,
                task_name=task_name,
                component=component,
                tag=tag,
                state="submitted",
                function_name=function_name,
                requested_workers=requested_workers,
            ).to_dict(),
        )
        self._append_jsonl(
            self._TASKS_FILE,
            TaskEvent(
                run_id=self.run_id,
                task_id=task_id,
                task_name=task_name,
                component=component,
                tag=tag,
                state="running",
                function_name=function_name,
                requested_workers=requested_workers,
            ).to_dict(),
        )

        default_cpus = None
        default_memory = None
        if component and component in self.component_defaults:
            default_cpus = self.component_defaults[component].get("cpus")
            default_memory = self.component_defaults[component].get("memory")

        self._append_jsonl(
            self._RESOURCES_FILE,
            ResourceEvent(
                run_id=self.run_id,
                entity_type="task",
                entity_id=task_id,
                component=component,
                provider=self.provider_name,
                requested_cpus=default_cpus if isinstance(default_cpus, int) else None,
                requested_memory=default_memory if isinstance(default_memory, str) else None,
                requested_walltime=self.target_walltime,
                requested_workers=requested_workers,
            ).to_dict(),
        )

    def record_task_result(
        self,
        *,
        task_id: str,
        task_name: str,
        component: str | None,
        tag: str | None,
        function_name: str,
        requested_workers: int,
        state: str,
        worker: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record terminal task state and optional failure event."""
        start = self._task_started_at.pop(task_id, None)
        duration = None
        if start is not None:
            duration = max(time.monotonic() - start, 0.0)

        self._append_jsonl(
            self._TASKS_FILE,
            TaskEvent(
                run_id=self.run_id,
                task_id=task_id,
                task_name=task_name,
                component=component,
                tag=tag,
                state=state,
                function_name=function_name,
                requested_workers=requested_workers,
                duration_s=duration,
                worker=worker,
                error_type=error_type,
                error_message=error_message,
            ).to_dict(),
        )

        if state == "failed":
            self._append_jsonl(
                self._FAILURES_FILE,
                FailureEvent(
                    run_id=self.run_id,
                    failure_class=error_type or "TaskError",
                    message=error_message or "task failed",
                    provider=self.provider_name,
                    task_id=task_id,
                ).to_dict(),
            )

    def record_cache_event(
        self,
        *,
        function_name: str,
        key_digest: str,
        hit: bool,
        duration_s: float,
        task_name: str | None,
        component: str | None,
        tag: str | None,
    ) -> None:
        """Record one cache hit or miss event."""
        self._append_jsonl(
            self._CACHE_FILE,
            CacheEvent(
                run_id=self.run_id,
                function_name=function_name,
                key_digest=key_digest,
                hit=hit,
                duration_s=duration_s,
                task_name=task_name,
                component=component,
                tag=tag,
            ).to_dict(),
        )

    def record_worker_event(
        self,
        *,
        provider: str,
        state: str,
        component: str | None,
        details: dict[str, Any],
    ) -> None:
        """Record provider worker/cluster telemetry events."""
        self._append_jsonl(
            self._WORKERS_FILE,
            WorkerEvent(
                run_id=self.run_id,
                provider=provider,
                state=state,
                component=component,
                details=details,
            ).to_dict(),
        )

    def record_failure(
        self,
        *,
        failure_class: str,
        message: str,
        details: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> None:
        """Record a non-task-scoped failure."""
        self._append_jsonl(
            self._FAILURES_FILE,
            FailureEvent(
                run_id=self.run_id,
                failure_class=failure_class,
                message=message,
                provider=self.provider_name,
                task_id=task_id,
                details=details or {},
            ).to_dict(),
        )

    def record_artifact(
        self,
        *,
        task_name: str,
        component: str | None,
        artifact_name: str,
        location: str,
        kind: str | None = None,
        size_bytes: int | None = None,
        digest: str | None = None,
    ) -> None:
        """Record artifact metadata emitted by a run."""
        self._append_jsonl(
            self._ARTIFACTS_FILE,
            ArtifactEvent(
                run_id=self.run_id,
                task_name=task_name,
                component=component,
                artifact_name=artifact_name,
                location=location,
                kind=kind,
                size_bytes=size_bytes,
                digest=digest,
            ).to_dict(),
        )

    def record_cost(
        self,
        *,
        provider: str,
        region: str | None,
        currency: str,
        total_hourly: float,
        total_monthly: float,
        line_items: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a cost estimation event (Phase 3)."""
        self._append_jsonl(
            self._COST_FILE,
            CostEvent(
                run_id=self.run_id,
                provider=provider,
                region=region,
                currency=currency,
                total_hourly=total_hourly,
                total_monthly=total_monthly,
                line_items=line_items or [],
                metadata=metadata or {},
            ).to_dict(),
        )

    def _write_summary(self) -> None:
        summary = summarize_run(self.run_dir)
        (self.run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_parquet_snapshots(self) -> None:
        if not self.telemetry_parquet:
            return
        snapshots = {
            self._TASKS_FILE: "tasks.parquet",
            self._RESOURCES_FILE: "resources.parquet",
            self._WORKERS_FILE: "workers.parquet",
        }
        for src_name, dst_name in snapshots.items():
            src = self.run_dir / src_name
            if not src.exists() or src.stat().st_size == 0:
                continue
            try:
                df = pd.read_json(src, lines=True)
                if not df.empty:
                    df.to_parquet(self.run_dir / dst_name, index=False)
            except (ImportError, ValueError):
                # Parquet dependencies and row shape validation are optional.
                continue

    def close(self, *, status: str = "completed") -> None:
        """Flush summary and finalize run metadata."""
        with self._lock:
            if self._closed:
                return
            self._closed = True

            self.metadata = replace(self.metadata, status=status, finished_at=utcnow_iso())
            (self.run_dir / "run.json").write_text(
                json.dumps(self.metadata.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._write_summary()
            self._write_parquet_snapshots()


__all__ = ["TelemetryStore", "build_run_id"]
