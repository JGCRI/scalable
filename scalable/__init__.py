"""Scalable — distributed orchestration for HPC workflows.

Public API re-exports (kept stable for downstream code):

* Legacy v1 runtime classes: :class:`SlurmCluster`, :class:`JobQueueCluster`,
  :class:`ScalableClient`
* v2 session + provider surface: :class:`ScalableSession`,
  :class:`DeploymentProvider`, :class:`LocalProvider`, :class:`SlurmProvider`
* Phase 3 cloud/k8s providers (optional deps):
  :class:`KubernetesProvider`, :class:`CloudProvider`, :class:`ArtifactStore`
* Phase 4 AI assistants (optional deps):
  :func:`onboard_component`, :func:`diagnose_run`, :func:`explain_plan`,
  :func:`compose_workflow`, :func:`migrate_manifest`
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

# Phase 4: AI assistant exports (optional deps)
try:
    from .ai import (
        ComposeResult,
        DiagnosisResult,
        ExplanationResult,
        MigrationResult,
        OnboardingResult,
        compose_workflow,
        diagnose_run,
        explain_plan,
        migrate_manifest,
        onboard_component,
    )
except ImportError:  # pragma: no cover
    ComposeResult = None  # type: ignore[assignment,misc]
    DiagnosisResult = None  # type: ignore[assignment,misc]
    ExplanationResult = None  # type: ignore[assignment,misc]
    MigrationResult = None  # type: ignore[assignment,misc]
    OnboardingResult = None  # type: ignore[assignment,misc]
    compose_workflow = None  # type: ignore[assignment,misc]
    diagnose_run = None  # type: ignore[assignment,misc]
    explain_plan = None  # type: ignore[assignment,misc]
    migrate_manifest = None  # type: ignore[assignment,misc]
    onboard_component = None  # type: ignore[assignment,misc]

# Phase 5: ML optimization and emulation exports (optional deps)
try:
    from .ml import AdaptiveScaler, HyperparameterSearch, LearnedAdvisor
except ImportError:  # pragma: no cover
    LearnedAdvisor = None  # type: ignore[assignment,misc]
    AdaptiveScaler = None  # type: ignore[assignment,misc]
    HyperparameterSearch = None  # type: ignore[assignment,misc]

try:
    from .emulation import (
        ActiveLearner,
        EmulatorDispatch,
        EmulatorRegistry,
        emulatable,
    )
except ImportError:  # pragma: no cover
    ActiveLearner = None  # type: ignore[assignment,misc]
    EmulatorDispatch = None  # type: ignore[assignment,misc]
    EmulatorRegistry = None  # type: ignore[assignment,misc]
    emulatable = None  # type: ignore[assignment,misc]

try:
    __version__ = _pkg_version("scalable")
except PackageNotFoundError:  # pragma: no cover - source checkout w/o install
    __version__ = "0.0.0+unknown"

__all__ = [
    "AWSBatchProvider",
    "ArtifactStore",
    "CloudProvider",
    "ComposeResult",
    "CostEstimate",
    "DeploymentProvider",
    "DiagnosisResult",
    "ExplanationResult",
    "GCPProvider",
    "JobQueueCluster",
    "KubernetesProvider",
    "LearnedAdvisor",
    "LocalArtifactStore",
    "LocalProvider",
    "MigrationResult",
    "OnboardingResult",
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
    "compose_workflow",
    "diagnose_run",
    "emulatable",
    "explain_plan",
    "get_worker",
    "migrate_manifest",
    "onboard_component",
    "settings",
    # Phase 5 ML/emulation
    "ActiveLearner",
    "AdaptiveScaler",
    "EmulatorDispatch",
    "EmulatorRegistry",
    "HyperparameterSearch",
]
