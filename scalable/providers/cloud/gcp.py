"""GCP cloud provider scaffold.

This module provides a validation-only :class:`GCPProvider` that verifies
manifest options but raises ``NotImplementedError`` on ``build_cluster``.
Full GCP execution support is deferred to a future iteration.
"""

from __future__ import annotations

from scalable.manifest.validate import ValidationIssue, ValidationReport
from scalable.providers.base import (
    ClusterHandle,
    DeploymentSpec,
)

from .base import CloudProvider


class GCPProvider(CloudProvider):
    """GCP provider scaffold (validation-only).

    Target options:
    - ``region``: GCP region (e.g. ``us-central1``)
    - ``project_id``: GCP project identifier
    - ``instance_type``: GCE machine type for cost estimation
    - ``image``: Container image for workers
    - ``n_workers``: Number of workers
    - ``network``: VPC network name
    - ``zone``: Specific zone within region
    - ``service_account``: GCP service account email
    """

    name: str = "gcp"

    _KNOWN_OPTIONS: frozenset[str] = frozenset({
        "region",
        "project_id",
        "instance_type",
        "image",
        "n_workers",
        "network",
        "zone",
        "service_account",
        "machine_type",
        "adaptive",
    })

    def validate(self, spec: DeploymentSpec) -> ValidationReport:
        """Validate GCP-specific target options."""
        report = ValidationReport()
        options = spec.target.options

        unknown = set(options) - self._KNOWN_OPTIONS
        for key in sorted(unknown):
            report.warnings.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.{key}",
                    message=f"unknown GCP provider option {key!r}",
                    code="W_UNKNOWN_GCP_OPTION",
                )
            )

        if not options.get("project_id"):
            report.warnings.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.project_id",
                    message="GCP provider recommends setting 'project_id'",
                    code="W_MISSING_PROJECT_ID",
                )
            )

        return report

    def build_cluster(self, spec: DeploymentSpec) -> ClusterHandle:
        """Not implemented — GCP cluster creation is deferred.

        Raises
        ------
        NotImplementedError
            Always. GCP execution support is a validation-only scaffold.
        """
        raise NotImplementedError(
            "GCPProvider.build_cluster() is not yet implemented. "
            "Phase 3 provides validation-only GCP support. "
            "Use 'scalable validate' to check your GCP manifest, or "
            "target AWS/Kubernetes for execution."
        )


__all__ = ["GCPProvider"]
