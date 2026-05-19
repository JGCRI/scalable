"""Kubernetes provider using dask-kubernetes operator.

Provides :class:`KubernetesProvider` which wraps the Dask Kubernetes
Operator's ``KubeCluster`` behind the Scalable
:class:`DeploymentProvider` protocol.
"""

from __future__ import annotations

from typing import Any

from scalable.common import logger
from scalable.costing import CostEstimate
from scalable.manifest.validate import ValidationIssue, ValidationReport
from scalable.providers.base import (
    ClusterHandle,
    DeploymentSpec,
    ScalePlan,
    _BaseProviderMixin,
)


def _import_dask_kubernetes():
    """Import dask-kubernetes with a clear error."""
    try:
        import dask_kubernetes

        return dask_kubernetes
    except ImportError as exc:
        raise ImportError(
            "dask-kubernetes is required for the Kubernetes provider. "
            "Install with: pip install scalable[kubernetes]"
        ) from exc


class KubernetesProvider(_BaseProviderMixin):
    """Kubernetes provider using the Dask Kubernetes Operator.

    Target options:
    - ``namespace``: Kubernetes namespace (default: ``"default"``)
    - ``image``: Default container image for scheduler/workers
    - ``n_workers``: Initial worker count per group
    - ``worker_service_account``: Service account for worker pods
    - ``adaptive``: Dict with ``minimum`` and ``maximum`` for adaptive scaling
    - ``resources``: Default resource requests (cpu, memory)
    - ``env``: Extra environment variables for pods
    - ``tolerations``: Kubernetes tolerations list
    - ``node_selector``: Node selector dict
    """

    name: str = "kubernetes"

    _KNOWN_OPTIONS: frozenset[str] = frozenset({
        "namespace",
        "image",
        "n_workers",
        "worker_service_account",
        "adaptive",
        "resources",
        "env",
        "tolerations",
        "node_selector",
        "scheduler_memory",
        "scheduler_cpu",
    })

    def validate(self, spec: DeploymentSpec) -> ValidationReport:
        """Validate Kubernetes-specific target options."""
        report = ValidationReport()
        options = spec.target.options

        unknown = set(options) - self._KNOWN_OPTIONS
        for key in sorted(unknown):
            report.warnings.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.{key}",
                    message=f"unknown Kubernetes provider option {key!r}",
                    code="W_UNKNOWN_K8S_OPTION",
                )
            )

        if not options.get("image"):
            report.warnings.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.image",
                    message="Kubernetes provider recommends setting 'image' for worker pods",
                    code="W_MISSING_IMAGE",
                )
            )

        return report

    def build_cluster(self, spec: DeploymentSpec) -> ClusterHandle:
        """Create a Dask Kubernetes Operator cluster.

        Creates a ``KubeCluster`` and adds worker groups per manifest
        component.
        """
        _import_dask_kubernetes()
        from dask_kubernetes.operator import KubeCluster

        options = spec.target.options
        namespace = options.get("namespace", "default")
        image = options.get("image")
        n_workers = options.get("n_workers", 1)

        logger.info("creating KubeCluster in namespace %s", namespace)

        cluster_kwargs: dict[str, Any] = {
            "namespace": namespace,
        }
        if image:
            cluster_kwargs["image"] = image

        cluster = KubeCluster(**cluster_kwargs)

        # Add worker groups per component
        for component_name, component in spec.components.items():
            worker_image = component.image or image
            resources_kwargs: dict[str, Any] = {}
            if component.memory:
                resources_kwargs["memory"] = component.memory
            if component.cpus:
                resources_kwargs["cpu"] = str(component.cpus)

            try:
                cluster.add_worker_group(
                    name=component_name,
                    n_workers=n_workers,
                    image=worker_image,
                    resources=resources_kwargs if resources_kwargs else None,
                )
            except Exception as exc:
                logger.warning(
                    "failed to add worker group %s: %s", component_name, exc
                )

        # Adaptive scaling
        adaptive = options.get("adaptive")
        if isinstance(adaptive, dict):
            cluster.adapt(
                minimum=adaptive.get("minimum", 1),
                maximum=adaptive.get("maximum", 10),
            )

        from scalable.client import ScalableClient

        def _client_factory() -> ScalableClient:
            from distributed import Client

            client = Client(cluster)
            return ScalableClient(client=client)

        return ClusterHandle(
            backend=cluster,
            client_factory=_client_factory,
            metadata={
                "provider": "kubernetes",
                "namespace": namespace,
            },
        )

    def scale(self, cluster: ClusterHandle, plan: ScalePlan) -> None:
        """Scale worker groups according to the plan."""
        backend = cluster.backend
        for tag, count in plan.workers_by_tag.items():
            try:
                if hasattr(backend, "scale"):
                    backend.scale(count, worker_group=tag)
            except Exception as exc:
                logger.warning("failed to scale worker group %s: %s", tag, exc)

    def close(self, cluster: ClusterHandle) -> None:
        """Close the Kubernetes cluster."""
        backend = cluster.backend
        if backend is not None and hasattr(backend, "close"):
            backend.close()

    def estimate_cost(
        self, spec: DeploymentSpec, plan: ScalePlan
    ) -> CostEstimate | None:
        """Kubernetes provider returns None (on-prem k8s has no direct cost)."""
        return None


__all__ = ["KubernetesProvider"]
