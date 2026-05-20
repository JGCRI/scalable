"""Tests for deterministic dry-run planning (WU-9 foundations)."""

from __future__ import annotations

from scalable.manifest.parser import parse_manifest
from scalable.planning.dryrun import build_dry_run_plan, compute_manifest_lock
from scalable.providers.base import DeploymentSpec


def _spec() -> DeploymentSpec:
    model = parse_manifest(
        {
            "version": 1,
            "project": {"name": "demo"},
            "targets": {
                "hpc": {
                    "provider": "slurm",
                    "walltime": "02:00:00",
                    "comm_port": 50051,
                }
            },
            "components": {
                "gcam": {"cpus": 2, "memory": "8G"},
                "stitches": {"cpus": 1, "memory": "4G"},
            },
            "tasks": {
                "run_gcam": {"component": "gcam"},
                "run_stitches": {"component": "stitches"},
            },
        }
    )
    return DeploymentSpec.from_manifest(model, target_name="hpc")


def test_compute_manifest_lock_deterministic() -> None:
    payload_a = {"b": 2, "a": 1, "nested": {"x": [3, 2, 1]}}
    payload_b = {"nested": {"x": [3, 2, 1]}, "a": 1, "b": 2}

    lock_a = compute_manifest_lock(payload_a)
    lock_b = compute_manifest_lock(payload_b)

    assert lock_a == lock_b
    assert len(lock_a) == 64


def test_build_dry_run_plan_maps_tasks_and_resources() -> None:
    plan = build_dry_run_plan(_spec())

    assert plan.target_name == "hpc"
    assert plan.provider_name == "slurm"
    assert len(plan.manifest_lock) == 64
    assert plan.task_to_component == {
        "run_gcam": "gcam",
        "run_stitches": "stitches",
    }

    assert plan.scale_plan.workers_by_tag == {"gcam": 1, "stitches": 1}
    assert plan.scale_plan.resources_by_tag["gcam"].cpus == 2
    assert plan.scale_plan.resources_by_tag["gcam"].memory == "8G"
    assert plan.scale_plan.resources_by_tag["gcam"].walltime == "02:00:00"
    assert plan.scale_plan.resources_by_tag["stitches"].cpus == 1


def test_dry_run_plan_to_dict_shape() -> None:
    plan = build_dry_run_plan(_spec())
    payload = plan.to_dict()

    assert payload["version"] == 1
    assert payload["target"] == "hpc"
    assert payload["provider"] == "slurm"
    assert payload["manifest_lock"] == plan.manifest_lock
    assert payload["task_to_component"]["run_gcam"] == "gcam"
    assert payload["scale_plan"]["workers_by_tag"]["gcam"] == 1
    assert payload["scale_plan"]["resources_by_tag"]["gcam"]["cpus"] == 2

