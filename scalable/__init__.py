"""Scalable — distributed orchestration for HPC workflows.

Public API re-exports (kept stable for downstream code):

* Legacy v1 runtime classes: :class:`SlurmCluster`, :class:`JobQueueCluster`,
  :class:`ScalableClient`
* v2 session + provider surface: :class:`ScalableSession`,
  :class:`DeploymentProvider`, :class:`LocalProvider`, :class:`SlurmProvider`
* Phase 3 cloud/k8s providers (optional deps):
  :class:`KubernetesProvider`, :class:`CloudProvider`, :class:`ArtifactStore`
* :func:`cacheable` and the :class:`*Type` hash wrappers from
  :mod:`scalable.caching`
* :data:`SEED` and the :data:`settings` singleton from :mod:`scalable.common`
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from dask.distributed import Security  # noqa: F401  (re-exported for users)
from distributed import get_worker  # noqa: F401  (re-exported for users)

from .advising import ResourceAdvisor, ResourceRecommendation
from .caching import *  # noqa: F401,F403  (legacy star-export)
from .client import ScalableClient
from .common import SEED, settings
from .core import JobQueueCluster
from .costing import CostEstimate
from .providers import DeploymentProvider, LocalProvider, SlurmProvider
from .session import ScalableSession
from .slurm import SlurmCluster

# Phase 3: optional-dependency-gated imports
try:
    from .providers.kubernetes import KubernetesProvider
except ImportError:  # pragma: no cover
    KubernetesProvider = None  # type: ignore[assignment,misc]

try:
    from .providers.cloud import AWSBatchProvider, CloudProvider, GCPProvider
except ImportError:  # pragma: no cover
    AWSBatchProvider = None  # type: ignore[assignment,misc]
    CloudProvider = None  # type: ignore[assignment,misc]
    GCPProvider = None  # type: ignore[assignment,misc]

try:
    from .artifacts import ArtifactStore, LocalArtifactStore, build_artifact_store
except ImportError:  # pragma: no cover
    ArtifactStore = None  # type: ignore[assignment,misc]
    LocalArtifactStore = None  # type: ignore[assignment,misc]
    build_artifact_store = None  # type: ignore[assignment,misc]

try:
    __version__ = _pkg_version("scalable")
except PackageNotFoundError:  # pragma: no cover - source checkout w/o install
    __version__ = "0.0.0+unknown"

__all__ = [
    "AWSBatchProvider",
    "ArtifactStore",
    "CloudProvider",
    "CostEstimate",
    "DeploymentProvider",
    "GCPProvider",
    "JobQueueCluster",
    "KubernetesProvider",
    "LocalArtifactStore",
    "LocalProvider",
    "ResourceAdvisor",
    "ResourceRecommendation",
    "SEED",
    "ScalableClient",
    "ScalableSession",
    "Security",
    "SlurmCluster",
    "SlurmProvider",
    "__version__",
    "build_artifact_store",
    "get_worker",
    "settings",
]
