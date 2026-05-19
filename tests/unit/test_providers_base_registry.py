"""Unit tests for provider base types and registry (Phase 1 WU-4)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from scalable.manifest.parser import parse_manifest
from scalable.providers.base import (
    ClusterHandle,
    DeploymentSpec,
    ResourceRequest,
    ScalePlan,
)
from scalable.providers.registry import (
    clear_registry,
    get_provider,
    iter_provider_names,
    register_provider,
    register_providers,
)


@dataclass
class DummyProvider:
    name: str = "dummy"

    def validate(self, spec):  # pragma: no cover - not needed in this suite
        raise NotImplementedError

    def build_cluster(self, spec):  # pragma: no cover - not needed in this suite
        raise NotImplementedError

    def scale(self, cluster, plan):  # pragma: no cover - not needed in this suite
        raise NotImplementedError

    def close(self, cluster):  # pragma: no cover - not needed in this suite
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_deployment_spec_from_manifest() -> None:
    model = parse_manifest(
        {
            "version": 1,
            "project": {"name": "demo"},
            "targets": {"local": {"provider": "local", "max_workers": 2}},
            "components": {"gcam": {"cpus": 2, "memory": "8G"}},
            "tasks": {"run_gcam": {"component": "gcam"}},
        }
    )

    spec = DeploymentSpec.from_manifest(model, target_name="local")

    assert spec.target_name == "local"
    assert spec.provider_name == "local"
    assert spec.target.options["max_workers"] == 2
    assert "gcam" in spec.components
    assert "run_gcam" in spec.tasks
    assert spec.raw_manifest["version"] == 1


def test_deployment_spec_from_manifest_missing_target_raises_keyerror() -> None:
    model = parse_manifest({"version": 1, "project": {"name": "demo"}, "targets": {}})

    with pytest.raises(KeyError):
        DeploymentSpec.from_manifest(model, target_name="missing")


def test_scale_plan_and_resource_request_defaults() -> None:
    rr = ResourceRequest()
    assert rr.cpus == 1
    assert rr.memory is None
    assert rr.walltime is None
    assert rr.gpus is None

    plan = ScalePlan()
    assert plan.workers_by_tag == {}
    assert plan.resources_by_tag == {}


def test_cluster_handle_stores_backend_and_factory() -> None:
    marker = object()

    def _factory():
        return marker

    handle = ClusterHandle(backend="backend", client_factory=_factory, metadata={"k": "v"})

    assert handle.backend == "backend"
    assert handle.client_factory() is marker
    assert handle.metadata == {"k": "v"}


def test_register_provider_and_get_provider_from_class() -> None:
    register_provider("dummy", DummyProvider)

    provider = get_provider("dummy")

    assert isinstance(provider, DummyProvider)
    assert provider.name == "dummy"


def test_register_provider_and_get_provider_from_callable_factory() -> None:
    def factory():
        return DummyProvider(name="dummy-factory")

    register_provider("dummy", factory)

    provider = get_provider("dummy")

    assert isinstance(provider, DummyProvider)
    assert provider.name == "dummy-factory"


def test_register_provider_normalizes_name_and_lookup() -> None:
    register_provider("  DuMmY  ", DummyProvider)

    provider = get_provider("dummy")

    assert isinstance(provider, DummyProvider)


def test_register_provider_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        register_provider("   ", DummyProvider)


def test_register_provider_rejects_duplicates() -> None:
    register_provider("dummy", DummyProvider)

    with pytest.raises(ValueError, match="already registered"):
        register_provider("dummy", DummyProvider)


def test_register_providers_bulk() -> None:
    register_providers(
        [
            ("dummy1", DummyProvider),
            ("dummy2", lambda: DummyProvider(name="dummy2")),
        ]
    )

    p1 = get_provider("dummy1")
    p2 = get_provider("dummy2")

    assert isinstance(p1, DummyProvider)
    assert isinstance(p2, DummyProvider)
    assert p2.name == "dummy2"


def test_get_provider_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="unknown provider"):
        get_provider("missing")


def test_iter_provider_names_from_runtime_registry() -> None:
    register_provider("dummy", DummyProvider)

    names = iter_provider_names(include_entrypoints=False)

    assert names == {"dummy"}

