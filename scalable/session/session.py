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
        if objective is not None or policy is not None:
            raise NotImplementedError(
                "objective/policy planning is planned for later phases; "
                "Phase 1 supports deterministic dry-run planning only"
            )

        _ = dry_run  # Phase 1 currently only supports dry-run behavior.

        report = self.validate()
        if not report.ok:
            details = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
            raise ValueError(f"manifest validation failed: {details}")

        return build_dry_run_plan(self.spec)

    def start(self, plan: DryRunPlan | None = None) -> ScalableClient:
        if self._client is not None:
            return self._client

        if plan is None:
            plan = self.plan(dry_run=True)
        elif plan.target_name != self.target_name:
            raise ValueError(
                f"plan target {plan.target_name!r} does not match session target {self.target_name!r}"
            )

        self._provider = get_provider(self.spec.provider_name)
        self._cluster = self._provider.build_cluster(self.spec)
        self._provider.scale(self._cluster, plan.scale_plan)
        self._client = self._cluster.client_factory()
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

        if self._cluster is not None and self._provider is not None:
            self._provider.close(self._cluster)
            self._cluster = None

    def __enter__(self) -> ScalableClient:
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
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
