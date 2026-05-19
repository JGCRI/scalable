"""Deployment provider layer (v2.0.0 Phase 1).

A :class:`~scalable.providers.base.DeploymentProvider` is the seam between
the declarative :class:`~scalable.manifest.schema.ManifestModel` and a
concrete Dask cluster backend. Phase 1 ships:

* :class:`~scalable.providers.local.LocalProvider` -- Dask ``LocalCluster``
  for laptops and CI.
* :class:`~scalable.providers.slurm.SlurmProvider` -- adapter around the
  existing :class:`scalable.slurm.SlurmCluster` HPC path.

Phase 3 will register :class:`KubernetesProvider`, :class:`CloudProvider`,
and :class:`StaticProvider` against the same protocol via the registry's
``entry_points("scalable.providers")`` hook (see
:mod:`scalable.providers.registry`). The protocol is intentionally free of
Slurm-specific fields so AI planners (Phase 4) and ML resource advisors
(Phase 5) can operate on a provider-neutral plan.
"""

from __future__ import annotations

from .base import ClusterHandle, DeploymentProvider, DeploymentSpec, ResourceRequest, ScalePlan
from .local import LocalProvider
from .registry import (
    clear_registry,
    get_provider,
    iter_provider_names,
    register_provider,
    register_providers,
)

__all__ = [
    "ClusterHandle",
    "DeploymentProvider",
    "DeploymentSpec",
    "LocalProvider",
    "ResourceRequest",
    "ScalePlan",
    "clear_registry",
    "get_provider",
    "iter_provider_names",
    "register_provider",
    "register_providers",
]
