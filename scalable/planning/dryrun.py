"""Deterministic dry-run planning primitives (Phase 1 WU-9)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from scalable.providers.base import DeploymentSpec, ResourceRequest, ScalePlan

__all__ = [
    "DryRunPlan",
    "build_dry_run_plan",
    "compute_manifest_lock",
]


@dataclass(frozen=True)
class DryRunPlan:
    """Serializable dry-run result for CLI/session APIs."""

    target_name: str
    provider_name: str
    manifest_lock: str
    scale_plan: ScalePlan
    task_to_component: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "target": self.target_name,
            "provider": self.provider_name,
            "manifest_lock": self.manifest_lock,
            "task_to_component": dict(self.task_to_component),
            "scale_plan": {
                "workers_by_tag": dict(self.scale_plan.workers_by_tag),
                "resources_by_tag": {
                    tag: {
                        "cpus": req.cpus,
                        "memory": req.memory,
                        "walltime": req.walltime,
                        "gpus": req.gpus,
                    }
                    for tag, req in self.scale_plan.resources_by_tag.items()
                },
            },
        }


def compute_manifest_lock(raw_manifest: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 fingerprint of canonicalized manifest."""
    canonical = json.dumps(raw_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_dry_run_plan(spec: DeploymentSpec) -> DryRunPlan:
    """Build a deterministic provider-neutral dry-run plan from spec."""
    task_to_component = {task_name: task.component for task_name, task in spec.tasks.items()}

    # Start from task usage so only referenced components are scaled by default.
    referenced_components = {task.component for task in spec.tasks.values()}

    workers_by_tag: dict[str, int] = {}
    resources_by_tag: dict[str, ResourceRequest] = {}
    walltime = spec.target.options.get("walltime")

    for component_name in sorted(referenced_components):
        component = spec.components[component_name]
        workers_by_tag[component_name] = 1
        resources_by_tag[component_name] = ResourceRequest(
            cpus=component.cpus,
            memory=component.memory,
            walltime=walltime if isinstance(walltime, str) else None,
            gpus=None,
        )

    scale_plan = ScalePlan(
        workers_by_tag=workers_by_tag,
        resources_by_tag=resources_by_tag,
    )

    return DryRunPlan(
        target_name=spec.target_name,
        provider_name=spec.provider_name,
        manifest_lock=compute_manifest_lock(spec.raw_manifest),
        scale_plan=scale_plan,
        task_to_component=task_to_component,
    )

