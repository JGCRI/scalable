"""Plan and dry-run primitives (v2.0.0 Phase 1).

Phase 1 ships a deterministic dry-run planner that converts a
:class:`~scalable.manifest.schema.ManifestModel` plus a target into a
provider-neutral :class:`~scalable.providers.base.ScalePlan` plus a
``manifest_lock`` SHA-256 fingerprint. No workers are launched.

Phase 4 plugs the AI workflow planner in here (objective/policy-driven
plan synthesis); Phase 5 layers an ML-trained resource advisor on top.
The Phase 1 ``manifest_lock`` canonicalisation rules are documented and
test-pinned so Phase 2 telemetry can durably reference manifests.
"""

from __future__ import annotations

from .dryrun import DryRunPlan, build_dry_run_plan, compute_manifest_lock

__all__ = ["DryRunPlan", "build_dry_run_plan", "compute_manifest_lock"]
