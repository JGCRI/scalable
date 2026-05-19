"""Typed telemetry event schema records for Phase 2."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION: int = 1


def utcnow_iso() -> str:
    """Return a UTC timestamp in stable ISO-8601 form."""
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RunMetadata:
    """Top-level run metadata persisted to ``run.json``."""

    run_id: str
    project_name: str
    target_name: str
    provider_name: str
    manifest_lock: str
    source_manifest_path: str | None
    started_at: str = field(default_factory=utcnow_iso)
    finished_at: str | None = None
    status: str = "running"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskEvent:
    """Task lifecycle event record."""

    run_id: str
    task_id: str
    task_name: str
    component: str | None
    tag: str | None
    state: str
    function_name: str
    requested_workers: int
    timestamp: str = field(default_factory=utcnow_iso)
    duration_s: float | None = None
    worker: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    event_type: str = "task"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResourceEvent:
    """Resource request/observation event record."""

    run_id: str
    entity_type: str
    entity_id: str
    component: str | None
    provider: str
    timestamp: str = field(default_factory=utcnow_iso)
    requested_cpus: int | None = None
    requested_memory: str | None = None
    requested_walltime: str | None = None
    requested_workers: int | None = None
    observed_cpu: float | None = None
    observed_memory_gb: float | None = None
    event_type: str = "resource"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkerEvent:
    """Worker/cluster lifecycle event record."""

    run_id: str
    provider: str
    state: str
    timestamp: str = field(default_factory=utcnow_iso)
    worker_id: str | None = None
    component: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    event_type: str = "worker"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FailureEvent:
    """Failure classification event record."""

    run_id: str
    failure_class: str
    message: str
    timestamp: str = field(default_factory=utcnow_iso)
    provider: str | None = None
    task_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    event_type: str = "failure"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CacheEvent:
    """Cache hit/miss event record."""

    run_id: str
    function_name: str
    key_digest: str
    hit: bool
    timestamp: str = field(default_factory=utcnow_iso)
    duration_s: float | None = None
    task_name: str | None = None
    component: str | None = None
    tag: str | None = None
    event_type: str = "cache"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactEvent:
    """Artifact metadata event record."""

    run_id: str
    task_name: str
    component: str | None
    artifact_name: str
    location: str
    timestamp: str = field(default_factory=utcnow_iso)
    kind: str | None = None
    size_bytes: int | None = None
    digest: str | None = None
    event_type: str = "artifact"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CostEvent:
    """Cost estimation event record (Phase 3).

    Recorded when a provider produces a cost estimate for a deployment plan.
    """

    run_id: str
    provider: str
    region: str | None
    currency: str
    total_hourly: float
    total_monthly: float
    timestamp: str = field(default_factory=utcnow_iso)
    line_items: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    event_type: str = "cost"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RemoteCacheEvent:
    """Remote cache interaction event record (Phase 3).

    Extends CacheEvent with remote-specific fields.
    """

    run_id: str
    function_name: str
    key_digest: str
    hit: bool
    remote: bool
    timestamp: str = field(default_factory=utcnow_iso)
    duration_s: float | None = None
    remote_uri: str | None = None
    task_name: str | None = None
    component: str | None = None
    event_type: str = "remote_cache"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "ArtifactEvent",
    "CacheEvent",
    "CostEvent",
    "FailureEvent",
    "RemoteCacheEvent",
    "ResourceEvent",
    "RunMetadata",
    "SCHEMA_VERSION",
    "TaskEvent",
    "WorkerEvent",
    "utcnow_iso",
]
