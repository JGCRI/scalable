"""``scalable run`` CLI verb — manifest-driven execution.

Phase 3 provides the ``scalable run`` command which:
1. Loads and validates the manifest (with overlay resolution).
2. Resolves the target provider.
3. Builds a dry-run plan and cost estimate.
4. Executes the workflow (or a user-supplied Python script) on the provider.
5. Persists telemetry and exits with appropriate status code.
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

from scalable.common import logger, settings


def run_run(
    manifest_path: str,
    *,
    target: str | None = None,
    workflow: str | None = None,
    dry_run: bool = False,
) -> int:
    """Execute a manifest-driven workflow.

    Parameters
    ----------
    manifest_path : str
        Path to the ``scalable.yaml`` manifest.
    target : str | None
        Target name override. Defaults to first target or ``SCALABLE_TARGET``.
    workflow : str | None
        Optional path to a Python file containing the workflow to execute.
        If not provided, the run validates and plans only (dry-run style).
    dry_run : bool
        If True, plan and estimate cost but don't execute.

    Returns
    -------
    int
        Exit code: 0 = success, 1 = failure, 2 = usage error.
    """
    from scalable.manifest.parser import load_manifest
    from scalable.manifest.validate import validate_manifest
    from scalable.planning.dryrun import build_dry_run_plan
    from scalable.providers.base import DeploymentSpec
    from scalable.providers.registry import get_provider, iter_provider_names

    # --- Load manifest ---
    try:
        effective_target = target or settings.target
        manifest = load_manifest(manifest_path, target_name=effective_target)
    except Exception as exc:
        print(f"error: failed to load manifest: {exc}", file=sys.stderr)
        return 2

    # --- Resolve target ---
    if effective_target is None:
        if manifest.targets:
            effective_target = next(iter(manifest.targets))
        else:
            print("error: no target specified and manifest has no targets", file=sys.stderr)
            return 2

    if effective_target not in manifest.targets:
        print(
            f"error: target {effective_target!r} not found in manifest "
            f"(available: {sorted(manifest.targets)})",
            file=sys.stderr,
        )
        return 2

    # --- Validate ---
    known = iter_provider_names()
    report = validate_manifest(manifest, known_providers=known)
    if not report.ok:
        print("validation errors:", file=sys.stderr)
        for issue in report.errors:
            print(f"  {issue.path}: {issue.message}", file=sys.stderr)
        return 1

    for w in report.warnings:
        logger.warning("validation warning: %s: %s", w.path, w.message)

    # --- Build spec + plan ---
    spec = DeploymentSpec.from_manifest(manifest, target_name=effective_target)
    plan = build_dry_run_plan(spec)

    # --- Resolve provider ---
    try:
        provider = get_provider(spec.provider_name)
    except (KeyError, ImportError) as exc:
        print(f"error: cannot resolve provider: {exc}", file=sys.stderr)
        return 2

    # --- Cost estimate ---
    cost_estimate = None
    if hasattr(provider, "estimate_cost"):
        cost_estimate = provider.estimate_cost(spec, plan.scale_plan)

    if cost_estimate:
        print(f"cost estimate: ${cost_estimate.total_hourly:.4f}/hr "
              f"(${cost_estimate.total_monthly:.2f}/mo) [{cost_estimate.provider}]")

    # --- Dry-run mode ---
    if dry_run:
        import json

        plan_dict = plan.to_dict()
        if cost_estimate:
            plan_dict["cost_estimate"] = cost_estimate.to_dict()
        print(json.dumps(plan_dict, indent=2))
        return 0

    # --- Execute workflow ---
    print(f"running on target={effective_target} provider={spec.provider_name}")

    if workflow:
        # Load and execute a user Python workflow file
        workflow_path = Path(workflow)
        if not workflow_path.exists():
            print(f"error: workflow file not found: {workflow}", file=sys.stderr)
            return 2

        try:
            spec_mod = importlib.util.spec_from_file_location("__scalable_workflow__", workflow_path)
            if spec_mod is None or spec_mod.loader is None:
                print(f"error: cannot load workflow module: {workflow}", file=sys.stderr)
                return 2
            module = importlib.util.module_from_spec(spec_mod)
            spec_mod.loader.exec_module(module)
            print("workflow completed successfully")
            return 0
        except Exception as exc:
            print(f"error: workflow execution failed: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return 1
    else:
        # Without a workflow file, just validate + plan + report
        print("no workflow file specified; plan generated successfully")
        print(f"manifest_lock: {plan.manifest_lock}")
        if cost_estimate:
            print(f"estimated cost: ${cost_estimate.total_hourly:.4f}/hr")
        return 0


__all__ = ["run_run"]
