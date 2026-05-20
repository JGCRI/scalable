"""Local provider implementation for laptops/CI (Phase 1 WU-5)."""

from __future__ import annotations

from typing import Any

from distributed import LocalCluster

from scalable.client import ScalableClient
from scalable.manifest.validate import ValidationIssue, ValidationReport, validate_manifest
from scalable.telemetry.runtime import emit_worker_event

from .base import ClusterHandle, DeploymentProvider, DeploymentSpec, ScalePlan

__all__ = ["LocalProvider"]


class LocalProvider(DeploymentProvider):
    """Run Scalable workloads on a local Dask cluster.

    Phase 1 scope:
    - deterministic local execution for development and CI,
    - tag-aware worker resources compatible with
      :meth:`scalable.client.ScalableClient.submit(..., tag=...)`,
    - no container runtime orchestration beyond validating option flags.
    """

    name = "local"

    _ALLOWED_CONTAINER_MODES = {"none", "auto", "docker"}

    def validate(self, spec: DeploymentSpec) -> ValidationReport:
        report = ValidationReport()
        options = spec.target.options

        if "max_workers" in options:
            max_workers = options["max_workers"]
            if (
                not isinstance(max_workers, int)
                or isinstance(max_workers, bool)
                or max_workers < 1
            ):
                report.errors.append(
                    ValidationIssue(
                        path=f"targets.{spec.target_name}.max_workers",
                        message="max_workers must be a positive integer",
                        code="E_BAD_MAX_WORKERS",
                    )
                )

        if "threads_per_worker" in options:
            threads = options["threads_per_worker"]
            if not isinstance(threads, int) or isinstance(threads, bool) or threads < 1:
                report.errors.append(
                    ValidationIssue(
                        path=f"targets.{spec.target_name}.threads_per_worker",
                        message="threads_per_worker must be a positive integer",
                        code="E_BAD_THREADS_PER_WORKER",
                    )
                )

        if "processes" in options and not isinstance(options["processes"], bool):
            report.errors.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.processes",
                    message="processes must be a boolean",
                    code="E_BAD_PROCESSES_FLAG",
                )
            )

        containers_mode = options.get("containers", "none")
        if not isinstance(containers_mode, str):
            report.errors.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.containers",
                    message="containers must be one of: none, auto, docker",
                    code="E_BAD_CONTAINERS_MODE",
                )
            )
        else:
            normalized = containers_mode.strip().lower()
            if normalized not in self._ALLOWED_CONTAINER_MODES:
                report.errors.append(
                    ValidationIssue(
                        path=f"targets.{spec.target_name}.containers",
                        message=(
                            f"unsupported containers mode {containers_mode!r}; "
                            f"allowed values: {sorted(self._ALLOWED_CONTAINER_MODES)}"
                        ),
                        code="E_BAD_CONTAINERS_MODE",
                    )
                )
            elif normalized in {"auto", "docker"}:
                report.warnings.append(
                    ValidationIssue(
                        path=f"targets.{spec.target_name}.containers",
                        message=(
                            "container orchestration in LocalProvider is deferred; "
                            "Phase 1 runs in no-container mode"
                        ),
                        code="W_LOCAL_CONTAINERS_DEFERRED",
                    )
                )

        return report

    def build_cluster(self, spec: DeploymentSpec) -> ClusterHandle:
        validation = self.validate(spec)
        if not validation.ok:
            details = "; ".join(
                f"{issue.path}: {issue.message}" for issue in validation.errors
            )
            raise ValueError(f"invalid local deployment spec: {details}")

        options = spec.target.options
        # Default worker count: one worker per component, minimum one.
        default_workers = max(1, len(spec.components))
        n_workers = int(options.get("max_workers", default_workers))
        threads_per_worker = int(options.get("threads_per_worker", 1))
        processes = bool(options.get("processes", False))
        dashboard_address = options.get("dashboard_address")

        # Preserve tag routing semantics from ScalableClient.submit(tag=...):
        # every worker advertises every component tag with 1 unit.
        worker_resources = {component_name: 1 for component_name in spec.components}

        cluster = LocalCluster(
            n_workers=n_workers,
            threads_per_worker=threads_per_worker,
            processes=processes,
            scheduler_port=0,
            dashboard_address=dashboard_address,
            silence_logs="error",
            resources=worker_resources,
        )

        emit_worker_event(
            provider=self.name,
            state="cluster_created",
            details={
                "n_workers": n_workers,
                "threads_per_worker": threads_per_worker,
                "processes": processes,
            },
        )

        def _client_factory() -> ScalableClient:
            return ScalableClient(cluster)

        return ClusterHandle(
            backend=cluster,
            client_factory=_client_factory,
            metadata={
                "provider": self.name,
                "target": spec.target_name,
                "n_workers": n_workers,
                "threads_per_worker": threads_per_worker,
                "processes": processes,
                "worker_resources": worker_resources,
            },
        )

    def scale(self, cluster: ClusterHandle, plan: ScalePlan) -> None:
        backend = cluster.backend
        if not hasattr(backend, "scale"):
            raise TypeError("cluster backend does not support scale()")

        if plan.workers_by_tag:
            target_workers = sum(max(int(n), 0) for n in plan.workers_by_tag.values())
            backend.scale(target_workers)
            emit_worker_event(
                provider=self.name,
                state="scaled",
                details={
                    "target_workers": target_workers,
                    "workers_by_tag": dict(plan.workers_by_tag),
                },
            )

    def close(self, cluster: ClusterHandle) -> None:
        backend = cluster.backend
        if hasattr(backend, "close"):
            backend.close()
        emit_worker_event(provider=self.name, state="cluster_closed", details={})


def _debug_options_snapshot(options: dict[str, Any]) -> dict[str, Any]:
    """Return a stable options snapshot for debugging/tests if needed."""
    return {k: options[k] for k in sorted(options)}
