"""Integration test for LocalProvider (Phase 1 WU-5)."""

from __future__ import annotations

import pytest

from scalable.manifest.parser import parse_manifest
from scalable.providers.base import DeploymentSpec
from scalable.providers.local import LocalProvider


def _increment(value: int) -> int:
    return value + 1


@pytest.mark.integration
def test_local_provider_end_to_end_submit_tagged_task() -> None:
    manifest = {
        "version": 1,
        "project": {"name": "demo"},
        "targets": {
            "local": {
                "provider": "local",
                "max_workers": 1,
                "threads_per_worker": 1,
                "processes": False,
                "containers": "none",
            }
        },
        "components": {
            "gcam": {"cpus": 1, "memory": "1G"},
        },
        "tasks": {
            "run_gcam": {"component": "gcam"},
        },
    }

    model = parse_manifest(manifest)
    spec = DeploymentSpec.from_manifest(model, target_name="local")
    provider = LocalProvider()
    handle = provider.build_cluster(spec)
    client = handle.client_factory()
    try:
        future = client.submit(_increment, 41, tag="gcam")
        assert future.result(timeout=10) == 42
    finally:
        client.close()
        provider.close(handle)

