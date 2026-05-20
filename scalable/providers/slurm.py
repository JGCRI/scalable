"""Slurm provider implementation (Phase 1 WU-6).

This provider is intentionally a thin translation layer over the existing
``scalable.slurm.SlurmCluster`` path so Phase 1 can ship provider abstraction
without regressing established HPC behavior.
"""

from __future__ import annotations

import os
import re

from scalable.manifest.adapter import (
    add_components_to_legacy_cluster,
    build_slurm_cluster_kwargs,
    create_legacy_slurm_cluster,
)
from scalable.manifest.validate import ValidationIssue, ValidationReport, validate_manifest
from scalable.slurm import SlurmCluster
from scalable.telemetry.runtime import emit_worker_event

from .base import ClusterHandle, DeploymentProvider, DeploymentSpec, ScalePlan

__all__ = ["SlurmProvider"]

_WALLTIME_RE = re.compile(r"^\d{1,3}:\d{2}:\d{2}$")


class SlurmProvider(DeploymentProvider):
    """Provider wrapper over :class:`scalable.slurm.SlurmCluster`."""

    name = "slurm"

    def validate(self, spec: DeploymentSpec) -> ValidationReport:
        report = ValidationReport()
        options = spec.target.options

        _require_type(report, spec.target_name, options, "queue", str)
        _require_type(report, spec.target_name, options, "account", str)
        _require_type(report, spec.target_name, options, "interface", str)
        _require_type(report, spec.target_name, options, "logs_location", str)
        _require_type(report, spec.target_name, options, "name", str)

        if "suppress_logs" in options and not isinstance(options["suppress_logs"], bool):
            report.errors.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.suppress_logs",
                    message="suppress_logs must be a boolean",
                    code="E_BAD_SUPPRESS_LOGS",
                )
            )

        if "walltime" in options:
            walltime = options["walltime"]
            if not isinstance(walltime, str) or not _WALLTIME_RE.match(walltime):
                report.errors.append(
                    ValidationIssue(
                        path=f"targets.{spec.target_name}.walltime",
                        message="walltime must be a string in HH:MM:SS format",
                        code="E_BAD_WALLTIME",
                    )
                )

        if "comm_port" in options:
            comm_port = options["comm_port"]
            if not isinstance(comm_port, int) or isinstance(comm_port, bool) or comm_port <= 0:
                report.errors.append(
                    ValidationIssue(
                        path=f"targets.{spec.target_name}.comm_port",
                        message="comm_port must be a positive integer",
                        code="E_BAD_COMM_PORT",
                    )
                )
        else:
            if os.environ.get("COMM_PORT") is None:
                report.errors.append(
                    ValidationIssue(
                        path=f"targets.{spec.target_name}.comm_port",
                        message=(
                            "comm_port is required for SlurmProvider (set it in manifest "
                            "or via COMM_PORT environment variable)"
                        ),
                        code="E_MISSING_COMM_PORT",
                    )
                )

        if "container_runtime" in options:
            runtime = options["container_runtime"]
            if not isinstance(runtime, str):
                report.errors.append(
                    ValidationIssue(
                        path=f"targets.{spec.target_name}.container_runtime",
                        message="container_runtime must be a string",
                        code="E_BAD_CONTAINER_RUNTIME",
                    )
                )
            else:
                normalized = runtime.strip().lower()
                if normalized not in {"apptainer", "docker"}:
                    report.errors.append(
                        ValidationIssue(
                            path=f"targets.{spec.target_name}.container_runtime",
                            message="container_runtime must be either 'apptainer' or 'docker'",
                            code="E_BAD_CONTAINER_RUNTIME",
                        )
                    )

        return report

    def build_cluster(self, spec: DeploymentSpec) -> ClusterHandle:
        validation = self.validate(spec)
        if not validation.ok:
            details = "; ".join(
                f"{issue.path}: {issue.message}" for issue in validation.errors
            )
            raise ValueError(f"invalid slurm deployment spec: {details}")

        cluster_kwargs = build_slurm_cluster_kwargs(spec)
        cluster = create_legacy_slurm_cluster(spec, cluster_cls=SlurmCluster)
        add_components_to_legacy_cluster(spec, cluster)

        def _client_factory():
            from scalable.client import ScalableClient

            return ScalableClient(cluster)

        emit_worker_event(
            provider=self.name,
            state="cluster_created",
            details={
                "cluster_kwargs": {k: v for k, v in cluster_kwargs.items() if v is not None},
            },
        )

        return ClusterHandle(
            backend=cluster,
            client_factory=_client_factory,
            metadata={
                "provider": self.name,
                "target": spec.target_name,
                "cluster_kwargs": {k: v for k, v in cluster_kwargs.items() if v is not None},
            },
        )

    def scale(self, cluster: ClusterHandle, plan: ScalePlan) -> None:
        backend = cluster.backend
        if not hasattr(backend, "add_workers"):
            raise TypeError("cluster backend does not support add_workers()")

        for tag, count in plan.workers_by_tag.items():
            n = int(count)
            if n > 0:
                backend.add_workers(tag=tag, n=n)
                emit_worker_event(
                    provider=self.name,
                    state="add_workers",
                    component=tag,
                    details={"n": n},
                )

    def close(self, cluster: ClusterHandle) -> None:
        backend = cluster.backend
        if hasattr(backend, "close"):
            backend.close()
        emit_worker_event(provider=self.name, state="cluster_closed", details={})


def _require_type(
    report: ValidationReport,
    target_name: str,
    options: dict,
    key: str,
    expected_type: type,
) -> None:
    if key in options and not isinstance(options[key], expected_type):
        report.errors.append(
            ValidationIssue(
                path=f"targets.{target_name}.{key}",
                message=f"{key} must be a {expected_type.__name__}",
                code=f"E_BAD_{key.upper()}",
            )
        )
