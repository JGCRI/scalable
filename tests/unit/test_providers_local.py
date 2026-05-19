"""Unit tests for :mod:`scalable.providers.local` (Phase 1 WU-5)."""

from __future__ import annotations

from dataclasses import dataclass

from scalable.manifest.parser import parse_manifest
from scalable.providers.base import ClusterHandle, DeploymentSpec, ScalePlan
from scalable.providers.local import LocalProvider


def _manifest_dict() -> dict:
    return {
        "version": 1,
        "project": {"name": "demo"},
        "targets": {
            "local": {
                "provider": "local",
                "max_workers": 2,
                "threads_per_worker": 1,
                "processes": False,
                "containers": "none",
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


def _spec() -> DeploymentSpec:
    model = parse_manifest(_manifest_dict())
    return DeploymentSpec.from_manifest(model, target_name="local")


def test_validate_local_provider_ok() -> None:
    provider = LocalProvider()

    report = provider.validate(_spec())

    assert report.ok is True
    assert report.errors == []


def test_validate_local_provider_rejects_bad_options() -> None:
    manifest = _manifest_dict()
    manifest["targets"]["local"]["max_workers"] = 0
    manifest["targets"]["local"]["threads_per_worker"] = 0
    manifest["targets"]["local"]["processes"] = "no"
    manifest["targets"]["local"]["containers"] = "podman"
    model = parse_manifest(manifest)
    spec = DeploymentSpec.from_manifest(model, target_name="local")
    provider = LocalProvider()

    report = provider.validate(spec)

    assert report.ok is False
    codes = {issue.code for issue in report.errors}
    assert "E_BAD_MAX_WORKERS" in codes
    assert "E_BAD_THREADS_PER_WORKER" in codes
    assert "E_BAD_PROCESSES_FLAG" in codes
    assert "E_BAD_CONTAINERS_MODE" in codes


def test_validate_local_provider_warns_for_deferred_containers() -> None:
    manifest = _manifest_dict()
    manifest["targets"]["local"]["containers"] = "docker"
    model = parse_manifest(manifest)
    spec = DeploymentSpec.from_manifest(model, target_name="local")
    provider = LocalProvider()

    report = provider.validate(spec)

    assert report.ok is True
    assert any(issue.code == "W_LOCAL_CONTAINERS_DEFERRED" for issue in report.warnings)


def test_build_cluster_returns_handle_and_metadata() -> None:
    provider = LocalProvider()
    handle = provider.build_cluster(_spec())
    try:
        assert isinstance(handle, ClusterHandle)
        assert handle.metadata["provider"] == "local"
        assert handle.metadata["target"] == "local"
        assert handle.metadata["n_workers"] == 2
        assert handle.metadata["worker_resources"] == {"gcam": 1, "stitches": 1}
    finally:
        provider.close(handle)


@dataclass
class _ScaleRecorder:
    value: int | None = None

    def scale(self, target: int) -> None:
        self.value = target


def test_scale_sums_workers_by_tag() -> None:
    provider = LocalProvider()
    backend = _ScaleRecorder()
    handle = ClusterHandle(backend=backend, client_factory=lambda: None)
    plan = ScalePlan(workers_by_tag={"gcam": 2, "stitches": 1})

    provider.scale(handle, plan)

    assert backend.value == 3


@dataclass
class _CloseRecorder:
    closed: bool = False

    def close(self) -> None:
        self.closed = True


def test_close_calls_backend_close() -> None:
    provider = LocalProvider()
    backend = _CloseRecorder()
    handle = ClusterHandle(backend=backend, client_factory=lambda: None)

    provider.close(handle)

    assert backend.closed is True

