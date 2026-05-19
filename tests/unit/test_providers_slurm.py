"""Unit tests for :mod:`scalable.providers.slurm` (Phase 1 WU-6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from scalable.manifest.parser import parse_manifest
from scalable.providers.base import ClusterHandle, DeploymentSpec, ScalePlan
from scalable.providers.slurm import SlurmProvider


def _manifest_dict() -> dict:
    return {
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
                "mounts": {
                    "/host/data": "/data",
                },
                "preload_script": "/tmp/preload.py",
            }
        },
        "tasks": {
            "run_gcam": {"component": "gcam"},
        },
    }


def _spec() -> DeploymentSpec:
    model = parse_manifest(_manifest_dict())
    return DeploymentSpec.from_manifest(model, target_name="hpc")


def test_validate_slurm_provider_ok() -> None:
    provider = SlurmProvider()

    report = provider.validate(_spec())

    assert report.ok is True
    assert report.errors == []


def test_validate_slurm_provider_comm_port_required_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("COMM_PORT", raising=False)
    manifest = _manifest_dict()
    manifest["targets"]["hpc"].pop("comm_port")
    spec = DeploymentSpec.from_manifest(parse_manifest(manifest), target_name="hpc")
    provider = SlurmProvider()

    report = provider.validate(spec)

    assert report.ok is False
    assert any(issue.code == "E_MISSING_COMM_PORT" for issue in report.errors)


def test_validate_slurm_provider_rejects_bad_option_types() -> None:
    manifest = _manifest_dict()
    manifest["targets"]["hpc"]["walltime"] = "2h"
    manifest["targets"]["hpc"]["comm_port"] = -1
    manifest["targets"]["hpc"]["suppress_logs"] = "no"
    manifest["targets"]["hpc"]["container_runtime"] = "podman"
    spec = DeploymentSpec.from_manifest(parse_manifest(manifest), target_name="hpc")
    provider = SlurmProvider()

    report = provider.validate(spec)

    assert report.ok is False
    codes = {issue.code for issue in report.errors}
    assert "E_BAD_WALLTIME" in codes
    assert "E_BAD_COMM_PORT" in codes
    assert "E_BAD_SUPPRESS_LOGS" in codes
    assert "E_BAD_CONTAINER_RUNTIME" in codes


@dataclass
class _FakeSlurmCluster:
    kwargs: dict[str, Any]
    add_container_calls: list[dict[str, Any]] = field(default_factory=list)
    add_workers_calls: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    def add_container(self, **kwargs: Any) -> None:
        self.add_container_calls.append(kwargs)

    def add_workers(self, **kwargs: Any) -> None:
        self.add_workers_calls.append(kwargs)

    def close(self) -> None:
        self.closed = True


def test_build_cluster_translates_manifest_to_slurm_calls(monkeypatch) -> None:
    created: list[_FakeSlurmCluster] = []

    def _factory(**kwargs: Any) -> _FakeSlurmCluster:
        instance = _FakeSlurmCluster(kwargs=kwargs)
        created.append(instance)
        return instance

    monkeypatch.setattr("scalable.providers.slurm.SlurmCluster", _factory)

    provider = SlurmProvider()
    handle = provider.build_cluster(_spec())

    assert isinstance(handle, ClusterHandle)
    assert len(created) == 1
    cluster = created[0]
    assert cluster.kwargs["queue"] == "short"
    assert cluster.kwargs["account"] == "GCIMS"
    assert cluster.kwargs["walltime"] == "02:00:00"
    assert cluster.kwargs["interface"] == "ib0"
    assert cluster.kwargs["comm_port"] == 50051
    assert cluster.kwargs["logs_location"] == "/tmp/scalable-logs"
    assert cluster.kwargs["suppress_logs"] is False

    assert len(cluster.add_container_calls) == 1
    call = cluster.add_container_calls[0]
    assert call["tag"] == "gcam"
    assert call["dirs"] == {"/host/data": "/data"}
    assert call["path"] == "/containers/gcam.sif"
    assert call["cpus"] == 2
    assert call["memory"] == "8G"
    assert call["preload_script"] == "/tmp/preload.py"

    assert handle.metadata["provider"] == "slurm"
    assert handle.metadata["target"] == "hpc"


def test_scale_calls_add_workers_per_tag() -> None:
    provider = SlurmProvider()
    backend = _FakeSlurmCluster(kwargs={})
    handle = ClusterHandle(backend=backend, client_factory=lambda: None)
    plan = ScalePlan(workers_by_tag={"gcam": 2, "stitches": 1, "noop": 0})

    provider.scale(handle, plan)

    assert backend.add_workers_calls == [
        {"tag": "gcam", "n": 2},
        {"tag": "stitches", "n": 1},
    ]


def test_close_calls_cluster_close() -> None:
    provider = SlurmProvider()
    backend = _FakeSlurmCluster(kwargs={})
    handle = ClusterHandle(backend=backend, client_factory=lambda: None)

    provider.close(handle)

    assert backend.closed is True

