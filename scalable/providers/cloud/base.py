"""Abstract base class for cloud deployment providers."""

from __future__ import annotations

from scalable.costing import CostEstimate, CostLineItem
from scalable.manifest.validate import ValidationReport
from scalable.providers.base import (
    ClusterHandle,
    DeploymentSpec,
    ScalePlan,
    _BaseProviderMixin,
)

from .cost_tables import get_instance_cost


class CloudProvider(_BaseProviderMixin):
    """Abstract base for cloud providers (AWS, GCP, Azure).

    Subclasses must override ``build_cluster`` and ``validate``.
    Shared cost-estimation logic lives here.
    """

    name: str = "cloud"

    def validate(self, spec: DeploymentSpec) -> ValidationReport:
        """Subclasses must override."""
        raise NotImplementedError

    def build_cluster(self, spec: DeploymentSpec) -> ClusterHandle:
        """Subclasses must override."""
        raise NotImplementedError

    def scale(self, cluster: ClusterHandle, plan: ScalePlan) -> None:
        """Default scale: no-op for cloud providers using adaptive scaling."""
        pass

    def close(self, cluster: ClusterHandle) -> None:
        """Close cloud cluster resources."""
        backend = cluster.backend
        if backend is not None and hasattr(backend, "close"):
            backend.close()

    def estimate_cost(
        self, spec: DeploymentSpec, plan: ScalePlan
    ) -> CostEstimate | None:
        """Estimate cost from static cost tables.

        Uses instance type and region from target options.
        """
        region = spec.target.options.get("region", "us-east-1")
        instance_type = spec.target.options.get("instance_type", "m5.xlarge")

        hourly_rate = get_instance_cost(
            provider=self.name,
            instance_type=instance_type,
            region=region,
        )
        if hourly_rate is None:
            return None

        line_items: list[CostLineItem] = []
        for tag, count in plan.workers_by_tag.items():
            line_items.append(
                CostLineItem.compute(
                    resource="compute",
                    description=f"{count}x {instance_type} for worker group '{tag}'",
                    unit="USD/hr",
                    quantity=float(count),
                    unit_cost=hourly_rate,
                )
            )

        return CostEstimate.from_line_items(
            provider=self.name,
            region=region,
            line_items=line_items,
            metadata={"instance_type": instance_type},
        )


__all__ = ["CloudProvider"]
