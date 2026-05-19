"""Provider protocol and core provider-neutral data structures.

Phase 1 introduces an explicit deployment seam so Scalable can target local,
Slurm, Kubernetes, and cloud backends through one stable contract.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from scalable.client import ScalableClient
from scalable.manifest.schema import (
    ComponentConfig,
    ManifestModel,
    TargetConfig,
    TaskConfig,
)
from scalable.manifest.validate import ValidationReport

__all__ = [
    "ClusterHandle",
    "DeploymentProvider",
    "DeploymentSpec",
    "ResourceRequest",
    "ScalePlan",
]


@dataclass(frozen=True)
class DeploymentSpec:
    """Provider-neutral deployment request derived from a manifest target.

    Attributes
    ----------
    target_name
        Name under ``targets:`` selected by the caller.
    provider_name
        Provider identifier from ``targets.<name>.provider``.
    manifest
        Full parsed manifest model.
    target
        Target block selected from the manifest.
    components
        Components map copied from the manifest.
    tasks
        Tasks map copied from the manifest.
    raw_manifest
        Expanded raw manifest data used for deterministic fingerprinting.
    """

    target_name: str
    provider_name: str
    manifest: ManifestModel
    target: TargetConfig
    components: dict[str, ComponentConfig]
    tasks: dict[str, TaskConfig]
    raw_manifest: dict[str, Any]

    @classmethod
    def from_manifest(
        cls,
        manifest: ManifestModel,
        *,
        target_name: str,
    ) -> DeploymentSpec:
        """Build a :class:`DeploymentSpec` from a parsed manifest.

        Raises
        ------
        KeyError
            If ``target_name`` is not present in ``manifest.targets``.
        """
        target = manifest.targets[target_name]
        return cls(
            target_name=target_name,
            provider_name=target.provider,
            manifest=manifest,
            target=target,
            components=dict(manifest.components),
            tasks=dict(manifest.tasks),
            raw_manifest=dict(manifest.raw),
        )


@dataclass(frozen=True)
class ResourceRequest:
    """Resource request for one worker group/tag."""

    cpus: int = 1
    memory: str | None = None
    walltime: str | None = None
    gpus: int | None = None


@dataclass(frozen=True)
class ScalePlan:
    """Provider-neutral scaling intent generated from the manifest."""

    workers_by_tag: dict[str, int] = field(default_factory=dict)
    resources_by_tag: dict[str, ResourceRequest] = field(default_factory=dict)


@dataclass
class ClusterHandle:
    """Opaque holder for provider-specific cluster state.

    Providers return this instead of raw cluster objects so higher layers can
    remain provider-neutral while still creating :class:`ScalableClient`
    instances through ``client_factory``.
    """

    backend: Any
    client_factory: Callable[[], ScalableClient]
    metadata: dict[str, Any] = field(default_factory=dict)


class DeploymentProvider(Protocol):
    """Protocol implemented by all execution providers."""

    name: str

    def validate(self, spec: DeploymentSpec) -> ValidationReport:
        """Validate provider-specific options and constraints."""

    def build_cluster(self, spec: DeploymentSpec) -> ClusterHandle:
        """Create or connect to a backend cluster and return a handle."""

    def scale(self, cluster: ClusterHandle, plan: ScalePlan) -> None:
        """Apply scaling operations for this provider."""

    def close(self, cluster: ClusterHandle) -> None:
        """Close provider-managed resources."""
