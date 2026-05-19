"""Frozen ``scalable.yaml`` v1 schema dataclasses.

The schema is intentionally implemented with stdlib :mod:`dataclasses` rather
than :mod:`pydantic` so manifest validation works without the optional
``scalable[ai]`` extra installed (see Phase 1 plan, open question #1).

The shape mirrors the canonical example in
``plans/v2.0.0_development_phases.md`` and is **frozen for v2.0.0**: any
schema change requires bumping :data:`SCHEMA_VERSION`. Phase 3 overlays and
Phase 4 AI migration assistants are expected to layer on top of this v1
without breaking existing manifests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Current manifest schema version. The parser refuses higher versions with
#: an actionable error so users on older Scalable releases see a clear
#: incompatibility message rather than a silent partial parse.
SCHEMA_VERSION: int = 1


@dataclass(frozen=True)
class ProjectConfig:
    """Top-level project metadata block.

    Attributes
    ----------
    name : str
        Human-readable project name. Used in run identifiers (Phase 2) and
        plan/manifest fingerprints.
    default_storage : str | None
        Default artifact/output storage URI (e.g. ``s3://bucket/runs/``,
        ``/shared/scalable/runs``). Phase 1 records the value but does not
        write to it; Phase 3 wires up the artifact backends.
    local_cache : str | None
        Per-project local cache path; complements the process-wide
        :class:`scalable.common.Settings` cache directory.
    """

    name: str
    default_storage: str | None = None
    local_cache: str | None = None


@dataclass(frozen=True)
class TargetConfig:
    """A named execution target that selects a deployment provider.

    Attributes
    ----------
    name : str
        The key under ``targets:`` in the manifest (e.g. ``"local"``,
        ``"hpc"``, ``"gke"``).
    provider : str
        The :class:`~scalable.providers.base.DeploymentProvider` ``name``
        attribute that handles this target. Phase 1 supports ``"local"``
        and ``"slurm"``; later phases register additional providers.
    options : Mapping[str, Any]
        Provider-specific options (queue, account, walltime, namespace, ...).
        Unknown keys are passed through to the provider and surfaced as
        warnings rather than errors so Phase 1 manifests can carry
        forward-compatible fields for Phase 3 cloud/k8s providers.
    """

    name: str
    provider: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComponentConfig:
    """A reusable container/runtime profile referenced by tasks and providers.

    Maps directly onto the legacy ``add_container(tag=..., dirs=..., path=...,
    cpus=..., memory=..., preload_script=...)`` call in
    :class:`scalable.core.JobQueueCluster`. The manifest-to-legacy adapter
    in :mod:`scalable.manifest.adapter` performs that translation in one
    pure function so every provider shares it.

    Attributes
    ----------
    name : str
        The component key under ``components:`` in the manifest. This is
        also the Dask resource ``tag`` used by
        :meth:`scalable.client.ScalableClient.submit`.
    image : str | None
        Container image reference (e.g. ``ghcr.io/jgcri/scalable-gcam:7.0``).
        Optional in Phase 1 ``local`` mode (``containers: none``).
    runtime : str | None
        Container runtime (``"apptainer"`` or ``"docker"``). When omitted,
        the provider's default applies (``apptainer`` on Slurm, ``none``
        on local).
    cpus : int
        CPU cores reserved per worker. Defaults to ``1``.
    memory : str | None
        Memory string parseable by :func:`dask.utils.parse_bytes`
        (``"8G"``, ``"500MB"``, ``"20G"``).
    mounts : Mapping[str, str]
        Bind-mount mapping. Schema convention is ``{host_path:
        container_path}`` (matches the example in the master plan); the
        adapter normalises this to the legacy ``dirs`` argument expected by
        :meth:`scalable.core.JobQueueCluster.add_container`.
    env : Mapping[str, str]
        Environment variables forwarded into the container at worker launch.
    tags : list[str]
        Free-form labels (``"iam"``, ``"climate"``, ``"compiled"``). Reserved
        for Phase 4 AI assistants and Phase 2 telemetry filtering; not used
        for routing in Phase 1.
    preload_script : str | None
        Optional Dask worker preload script path; passes through to
        ``add_container(preload_script=...)``.
    """

    name: str
    image: str | None = None
    runtime: str | None = None
    cpus: int = 1
    memory: str | None = None
    mounts: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    preload_script: str | None = None


@dataclass(frozen=True)
class TaskConfig:
    """A logical task definition pinned to a component.

    Phase 1 records task definitions but does not yet execute on them; the
    dry-run planner uses them to size worker groups. Phase 4 AI planners
    use this map to infer DAG structure.

    Attributes
    ----------
    name : str
        Task key under ``tasks:`` in the manifest.
    component : str
        Name of the :class:`ComponentConfig` this task runs in. Validated
        for existence by :mod:`scalable.manifest.validate`.
    cache : bool
        Whether the task's results should be cached. Phase 1 honours this
        flag only at the manifest level; Phase 2 wires it into the
        :func:`scalable.caching.cacheable` decorator metadata, and Phase 3
        extends it to remote artifact stores.
    outputs : Mapping[str, str]
        Declared outputs (``{"database": "dir"}``). Reserved for Phase 3
        artifact tracking.
    """

    name: str
    component: str
    cache: bool = False
    outputs: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ManifestModel:
    """Parsed, validated representation of a ``scalable.yaml`` document.

    Instances are immutable so the canonicalised JSON used for
    ``manifest_lock`` (Phase 1 §3.3) is stable across the lifetime of a
    :class:`scalable.session.ScalableSession`.

    Attributes
    ----------
    version : int
        Schema version (always equal to :data:`SCHEMA_VERSION` once parsed).
    project : ProjectConfig
        Project metadata block.
    targets : Mapping[str, TargetConfig]
        Named execution targets; the key matches ``TargetConfig.name``.
    components : Mapping[str, ComponentConfig]
        Component definitions; the key matches ``ComponentConfig.name``.
    tasks : Mapping[str, TaskConfig]
        Task definitions; the key matches ``TaskConfig.name``.
    raw : Mapping[str, Any]
        The raw, post-overlay-resolution, post-env-expansion document.
        Carried so providers can introspect forward-compatible keys without
        losing fidelity, and so telemetry can record the exact manifest a
        run was launched from. This is the *resolved* form.
    raw_unresolved : Mapping[str, Any] | None
        The pre-overlay form of the document (sans ``overlays:`` key).
        ``None`` when no overlay was applied.  Retained for provenance
        tracking (Phase 3).
    source_path : str | None
        Filesystem path the manifest was loaded from, if any.
    """

    version: int
    project: ProjectConfig
    targets: dict[str, TargetConfig]
    components: dict[str, ComponentConfig]
    tasks: dict[str, TaskConfig]
    raw: dict[str, Any]
    raw_unresolved: dict[str, Any] | None = None
    source_path: str | None = None


__all__ = [
    "ComponentConfig",
    "ManifestModel",
    "ProjectConfig",
    "SCHEMA_VERSION",
    "TargetConfig",
    "TaskConfig",
]
