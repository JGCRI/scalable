"""ScalableSession implementation (Phase 1 WU-8)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from scalable.client import ScalableClient
from scalable.common import settings
from scalable.manifest.parser import load_manifest
from scalable.manifest.schema import ManifestModel
from scalable.manifest.validate import ValidationIssue, ValidationReport, validate_manifest
from scalable.planning.dryrun import DryRunPlan, build_dry_run_plan
from scalable.providers.base import ClusterHandle, DeploymentSpec
from scalable.providers.registry import get_provider, iter_provider_names
from scalable.telemetry.runtime import reset_active_store, set_active_store
from scalable.telemetry.store import TelemetryStore

__all__ = ["ScalableSession"]


@dataclass
class ScalableSession:
    """Session lifecycle wrapper for manifest-driven execution."""

    manifest: ManifestModel
    target_name: str
    spec: DeploymentSpec

    _provider: Any = None
    _cluster: ClusterHandle | None = None
    _client: ScalableClient | None = None
    _telemetry: TelemetryStore | None = None
    _telemetry_token: Any = None

    @classmethod
    def from_yaml(
        cls,
        path: str | os.PathLike[str] | None = None,
        *,
        target: str | None = None,
    ) -> ScalableSession:
        manifest_path = str(path or settings.manifest_path)
        manifest = load_manifest(manifest_path)
        selected_target = _resolve_target_name(manifest, requested=target)
        spec = DeploymentSpec.from_manifest(manifest, target_name=selected_target)
        return cls(manifest=manifest, target_name=selected_target, spec=spec)

    def validate(self) -> ValidationReport:
        known = set(iter_provider_names(include_entrypoints=True))
        # Keep built-ins discoverable even before first runtime lookup.
        known.update({"local", "slurm"})
        report = validate_manifest(self.manifest, known_providers=known)

        try:
            provider = get_provider(self.spec.provider_name)
        except KeyError as exc:
            report.errors.append(
                ValidationIssue(
                    path=f"targets.{self.target_name}.provider",
                    message=str(exc),
                    code="E_UNKNOWN_PROVIDER",
                )
            )
            return report

        preport = provider.validate(self.spec)
        report.errors.extend(preport.errors)
        report.warnings.extend(preport.warnings)
        return report

    def plan(
        self,
        *,
        dry_run: bool = False,
        objective: str | None = None,
        policy: str | None = None,
    ) -> DryRunPlan:
        _ = dry_run  # Currently all planning is non-destructive.

        report = self.validate()
        if not report.ok:
            details = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
            raise ValueError(f"manifest validation failed: {details}")

        base_plan = build_dry_run_plan(self.spec)

        # Phase 4: apply objective/policy-based adjustments
        if objective is not None or policy is not None:
            return _apply_objective_policy(base_plan, self.spec, objective, policy)

        return base_plan

    def start(self, plan: DryRunPlan | None = None) -> ScalableClient:
        if self._client is not None:
            return self._client

        if plan is None:
            plan = self.plan(dry_run=True)
        elif plan.target_name != self.target_name:
            raise ValueError(
                f"plan target {plan.target_name!r} does not match session target {self.target_name!r}"
            )

        if settings.telemetry_enabled:
            self._telemetry = TelemetryStore.create(
                runs_dir=settings.runs_dir,
                manifest=self.manifest,
                spec=self.spec,
                plan=plan,
                telemetry_parquet=settings.telemetry_parquet,
            )
            self._telemetry_token = set_active_store(self._telemetry)

        try:
            self._provider = get_provider(self.spec.provider_name)
            self._cluster = self._provider.build_cluster(self.spec)
            self._provider.scale(self._cluster, plan.scale_plan)
            self._client = self._cluster.client_factory()
            if self._telemetry is not None:
                self._client.set_telemetry_store(self._telemetry)
            return self._client
        except Exception as exc:
            if self._telemetry is not None:
                self._telemetry.record_failure(
                    failure_class=type(exc).__name__,
                    message=str(exc),
                    details={"phase": "session.start"},
                )
                self._telemetry.close(status="failed")
                self._telemetry = None
            if self._telemetry_token is not None:
                reset_active_store(self._telemetry_token)
                self._telemetry_token = None
            raise

    def close(self) -> None:
        close_error: Exception | None = None
        status = "completed"

        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:  # pragma: no cover - defensive
                close_error = exc
                status = "failed"
                if self._telemetry is not None:
                    self._telemetry.record_failure(
                        failure_class=type(exc).__name__,
                        message=str(exc),
                        details={"phase": "session.close.client"},
                    )
            finally:
                self._client = None

        if self._cluster is not None and self._provider is not None:
            try:
                self._provider.close(self._cluster)
            except Exception as exc:  # pragma: no cover - defensive
                close_error = exc
                status = "failed"
                if self._telemetry is not None:
                    self._telemetry.record_failure(
                        failure_class=type(exc).__name__,
                        message=str(exc),
                        details={"phase": "session.close.provider"},
                    )
            finally:
                self._cluster = None

        if self._telemetry is not None:
            self._telemetry.close(status=status)
            self._telemetry = None

        if self._telemetry_token is not None:
            reset_active_store(self._telemetry_token)
            self._telemetry_token = None

        if close_error is not None:
            raise close_error

    def record_artifact(
        self,
        *,
        task_name: str,
        artifact_name: str,
        location: str,
        component: str | None = None,
        kind: str | None = None,
        size_bytes: int | None = None,
        digest: str | None = None,
    ) -> None:
        """Record artifact metadata for the active run, if telemetry is enabled."""
        if self._telemetry is None:
            return
        self._telemetry.record_artifact(
            task_name=task_name,
            component=component,
            artifact_name=artifact_name,
            location=location,
            kind=kind,
            size_bytes=size_bytes,
            digest=digest,
        )

    def __enter__(self) -> ScalableClient:
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None and self._telemetry is not None:
            self._telemetry.record_failure(
                failure_class=type(exc).__name__,
                message=str(exc),
                details={"phase": "session.context"},
            )
        self.close()


def _resolve_target_name(manifest: ManifestModel, *, requested: str | None) -> str:
    """Resolve session target from explicit input, settings, or auto mode."""
    if not manifest.targets:
        raise ValueError("manifest declares no targets")

    desired = requested if requested is not None else settings.target
    desired = desired or "auto"

    if desired != "auto":
        if desired not in manifest.targets:
            raise KeyError(
                f"target {desired!r} not found in manifest; available targets: "
                f"{sorted(manifest.targets)}"
            )
        return desired

    # Auto-resolution heuristic for Phase 1.
    running_in_slurm = bool(os.environ.get("SLURM_JOB_ID") or os.environ.get("SLURM_CLUSTER_NAME"))
    if running_in_slurm:
        # Prefer target key named "slurm" then any target using slurm provider.
        if "slurm" in manifest.targets:
            return "slurm"
        for tname, tcfg in manifest.targets.items():
            if tcfg.provider == "slurm":
                return tname

    # Prefer target key named "local" then any target using local provider.
    if "local" in manifest.targets:
        return "local"
    for tname, tcfg in manifest.targets.items():
        if tcfg.provider == "local":
            return tname

    # Fallback: deterministic first key order from parsed mapping.
    return next(iter(manifest.targets.keys()))


#: Supported objectives for heuristic planning
_SUPPORTED_OBJECTIVES = {"minimize cost", "minimize time", "balance"}

#: Supported policies
_SUPPORTED_POLICIES = {"safe", "aggressive", "manual"}


def _apply_objective_policy(
    base_plan: DryRunPlan,
    spec: DeploymentSpec,
    objective: str | None,
    policy: str | None,
) -> DryRunPlan:
    """Apply objective/policy-based adjustments to a base plan.

    Phase 4 implementation uses heuristic rules. Phase 5 will add
    ML-backed optimizations using the same API surface.
    """
    from scalable.providers.base import ResourceRequest, ScalePlan

    effective_objective = (objective or "balance").lower().strip()
    effective_policy = (policy or "safe").lower().strip()

    if effective_objective not in _SUPPORTED_OBJECTIVES:
        raise NotImplementedError(
            f"Unsupported objective: {objective!r}. "
            f"Supported objectives: {sorted(_SUPPORTED_OBJECTIVES)}"
        )
    if effective_policy not in _SUPPORTED_POLICIES:
        raise NotImplementedError(
            f"Unsupported policy: {policy!r}. "
            f"Supported policies: {sorted(_SUPPORTED_POLICIES)}"
        )

    # Start from base plan values
    workers = dict(base_plan.scale_plan.workers_by_tag)
    resources = dict(base_plan.scale_plan.resources_by_tag)

    # Apply objective-based adjustments
    if effective_objective == "minimize cost":
        # Reduce worker counts; keep resources tight
        for tag in workers:
            workers[tag] = max(1, workers[tag])
        # With safe policy, add memory margin
        if effective_policy == "safe":
            for tag, req in resources.items():
                resources[tag] = req  # Keep as-is (conservative)

    elif effective_objective == "minimize time":
        # Scale up workers for parallelism
        multiplier = 2 if effective_policy == "aggressive" else 1
        for tag in workers:
            workers[tag] = max(1, workers[tag] * (1 + multiplier))
        # With aggressive policy, request more resources
        if effective_policy == "aggressive":
            for tag, req in resources.items():
                new_cpus = req.cpus * 2 if req.cpus else 2
                resources[tag] = ResourceRequest(
                    cpus=new_cpus,
                    memory=req.memory,
                    walltime=req.walltime,
                    gpus=req.gpus,
                )

    elif effective_objective == "balance":
        # Moderate scaling with safety margins
        if effective_policy == "safe":
            pass  # Keep base plan as-is with safety margins
        elif effective_policy == "aggressive":
            for tag in workers:
                workers[tag] = max(1, workers[tag] + 1)

    # manual policy means: use exactly what the manifest says
    if effective_policy == "manual":
        workers = dict(base_plan.scale_plan.workers_by_tag)
        resources = dict(base_plan.scale_plan.resources_by_tag)

    adjusted_plan = ScalePlan(
        workers_by_tag=workers,
        resources_by_tag=resources,
    )

    return DryRunPlan(
        target_name=base_plan.target_name,
        provider_name=base_plan.provider_name,
        manifest_lock=base_plan.manifest_lock,
        scale_plan=adjusted_plan,
        task_to_component=base_plan.task_to_component,
    )
