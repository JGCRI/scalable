"""Scalable — distributed orchestration for HPC workflows.

Public API re-exports (kept stable for downstream code):

* Legacy v1 runtime classes: :class:`SlurmCluster`, :class:`JobQueueCluster`,
  :class:`ScalableClient`
* v2 session + provider surface: :class:`ScalableSession`,
  :class:`DeploymentProvider`, :class:`LocalProvider`, :class:`SlurmProvider`
* :func:`cacheable` and the :class:`*Type` hash wrappers from
  :mod:`scalable.caching`
* :data:`SEED` and the :data:`settings` singleton from :mod:`scalable.common`
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from dask.distributed import Security  # noqa: F401  (re-exported for users)
from distributed import get_worker  # noqa: F401  (re-exported for users)

from .caching import *  # noqa: F401,F403  (legacy star-export)
from .client import ScalableClient
from .common import SEED, settings
from .core import JobQueueCluster
from .providers import DeploymentProvider, LocalProvider, SlurmProvider
from .session import ScalableSession
from .slurm import SlurmCluster

try:
    __version__ = _pkg_version("scalable")
except PackageNotFoundError:  # pragma: no cover - source checkout w/o install
    __version__ = "0.0.0+unknown"

__all__ = [
    "JobQueueCluster",
    "DeploymentProvider",
    "LocalProvider",
    "SEED",
    "ScalableClient",
    "ScalableSession",
    "Security",
    "SlurmCluster",
    "SlurmProvider",
    "__version__",
    "get_worker",
    "settings",
]
