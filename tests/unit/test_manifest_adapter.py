"""Unit tests for :mod:`scalable.manifest.adapter` (Phase 1 WU-7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scalable.manifest.adapter import (
    add_components_to_legacy_cluster,
    build_slurm_cluster_kwargs,
    create_legacy_slurm_cluster,
)
from scalable.manifest.parser import parse_manifest
from scalable.providers.base import DeploymentSpec


def _spec() -> DeploymentSpec:
    model = parse_manifest(
        {
            "version": 1,
            "project": {"name": "demo"},
            "targets": {
                "hpc": {
                    "provider": "slurm",
                    "queue": "short",
                    "account": "GCIMS",
                    "walltime": "02:00:00",
                    "interface": "ib0",
                    "comm_port": 50051,
                    "logs_location": "/tmp/scalable-logs",
                    "suppress_logs": False,
                }
            },
            "components": {
                "gcam": {
                    "image": "/containers/gcam.sif",
                    "cpus": 2,
                    "memory": "8G",
                    "mounts": {"/host/data": "/data"},
                    "preload_script": "/tmp/preload.py",
                },
                "stitches": {
                    "image": "/containers/stitches.sif",
                    "cpus": 1,
                    "memory": "4G",
                    "mounts": {"/host/data": "/data"},
                },
            },
            "tasks": {
                "run_gcam": {"component": "gcam"},
                "run_stitches": {"component": "stitches"},
            },
        }
    )
    return DeploymentSpec.from_manifest(model, target_name="hpc")


def test_build_slurm_cluster_kwargs_translation() -> None:
    kwargs = build_slurm_cluster_kwargs(_spec())

    assert kwargs == {
        "queue": "short",
        "account": "GCIMS",
        "walltime": "02:00:00",
        "interface": "ib0",
        "name": None,
        "logs_location": "/tmp/scalable-logs",
        "suppress_logs": False,
        "comm_port": 50051,
    }


@dataclass
class _FakeCluster:
    add_container_calls: list[dict[str, Any]] = field(default_factory=list)

    def add_container(self, **kwargs: Any) -> None:
        self.add_container_calls.append(kwargs)


def test_add_components_to_legacy_cluster_all_components() -> None:
    spec = _spec()
    cluster = _FakeCluster()

    added = add_components_to_legacy_cluster(spec, cluster)

    assert added == ["gcam", "stitches"]
    assert len(cluster.add_container_calls) == 2
    assert cluster.add_container_calls[0]["tag"] == "gcam"
    assert cluster.add_container_calls[0]["dirs"] == {"/host/data": "/data"}
    assert cluster.add_container_calls[0]["path"] == "/containers/gcam.sif"
    assert cluster.add_container_calls[0]["cpus"] == 2
    assert cluster.add_container_calls[0]["memory"] == "8G"
    assert cluster.add_container_calls[0]["preload_script"] == "/tmp/preload.py"


def test_add_components_to_legacy_cluster_subset() -> None:
    spec = _spec()
    cluster = _FakeCluster()

    added = add_components_to_legacy_cluster(spec, cluster, components=["stitches"])

    assert added == ["stitches"]
    assert len(cluster.add_container_calls) == 1
    assert cluster.add_container_calls[0]["tag"] == "stitches"


@dataclass
class _FactoryCapture:
    kwargs: dict[str, Any]


def test_create_legacy_slurm_cluster_uses_factory() -> None:
    captured: list[_FactoryCapture] = []

    def _factory(**kwargs: Any) -> _FactoryCapture:
        obj = _FactoryCapture(kwargs=kwargs)
        captured.append(obj)
        return obj

    result = create_legacy_slurm_cluster(_spec(), cluster_cls=_factory)

    assert len(captured) == 1
    assert result is captured[0]
    assert captured[0].kwargs["queue"] == "short"
    assert captured[0].kwargs["comm_port"] == 50051

