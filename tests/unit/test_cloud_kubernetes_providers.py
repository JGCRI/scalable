"""Unit tests for cloud and kubernetes providers."""

from __future__ import annotations

import pytest

from scalable.manifest.schema import (
    ComponentConfig,
    ManifestModel,
    ProjectConfig,
    TargetConfig,
    TaskConfig,
)
from scalable.manifest.validate import ValidationReport
from scalable.providers.base import DeploymentSpec, ResourceRequest, ScalePlan


def _make_spec(
    provider: str,
    target_name: str = "test",
    options: dict | None = None,
) -> DeploymentSpec:
    """Helper to build a minimal DeploymentSpec."""
    target = TargetConfig(name=target_name, provider=provider, options=options or {})
    manifest = ManifestModel(
        version=1,
        project=ProjectConfig(name="test-project"),
        targets={target_name: target},
        components={
            "model": ComponentConfig(name="model", cpus=4, memory="8G"),
        },
        tasks={
            "run": TaskConfig(name="run", component="model"),
        },
        raw={"version": 1, "project": {"name": "test-project"}},
    )
    return DeploymentSpec(
        target_name=target_name,
        provider_name=provider,
        manifest=manifest,
        target=target,
        components=dict(manifest.components),
        tasks=dict(manifest.tasks),
        raw_manifest=manifest.raw,
    )


class TestGCPProvider:
    def test_validate_passes_clean_manifest(self):
        from scalable.providers.cloud.gcp import GCPProvider

        provider = GCPProvider()
        spec = _make_spec("gcp", options={"region": "us-central1", "project_id": "my-project"})
        report = provider.validate(spec)
        assert report.ok

    def test_validate_warns_on_missing_project_id(self):
        from scalable.providers.cloud.gcp import GCPProvider

        provider = GCPProvider()
        spec = _make_spec("gcp", options={"region": "us-central1"})
        report = provider.validate(spec)
        assert any("project_id" in w.message for w in report.warnings)

    def test_validate_warns_on_unknown_options(self):
        from scalable.providers.cloud.gcp import GCPProvider

        provider = GCPProvider()
        spec = _make_spec("gcp", options={"unknown_key": "value"})
        report = provider.validate(spec)
        assert any("unknown_key" in w.message for w in report.warnings)

    def test_build_cluster_raises_not_implemented(self):
        from scalable.providers.cloud.gcp import GCPProvider

        provider = GCPProvider()
        spec = _make_spec("gcp")
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            provider.build_cluster(spec)

    def test_name(self):
        from scalable.providers.cloud.gcp import GCPProvider

        provider = GCPProvider()
        assert provider.name == "gcp"


class TestAWSBatchProvider:
    def test_validate_passes_clean_manifest(self):
        from scalable.providers.cloud.aws import AWSBatchProvider

        provider = AWSBatchProvider()
        spec = _make_spec("aws", options={"region": "us-east-1", "cluster_type": "fargate"})
        report = provider.validate(spec)
        assert report.ok

    def test_validate_rejects_invalid_cluster_type(self):
        from scalable.providers.cloud.aws import AWSBatchProvider

        provider = AWSBatchProvider()
        spec = _make_spec("aws", options={"cluster_type": "invalid"})
        report = provider.validate(spec)
        assert not report.ok
        assert any("cluster_type" in e.message for e in report.errors)

    def test_validate_warns_unknown_options(self):
        from scalable.providers.cloud.aws import AWSBatchProvider

        provider = AWSBatchProvider()
        spec = _make_spec("aws", options={"random_key": "val"})
        report = provider.validate(spec)
        assert any("random_key" in w.message for w in report.warnings)

    def test_name(self):
        from scalable.providers.cloud.aws import AWSBatchProvider

        provider = AWSBatchProvider()
        assert provider.name == "aws"

    def test_estimate_cost(self):
        from scalable.providers.cloud.aws import AWSBatchProvider

        provider = AWSBatchProvider()
        spec = _make_spec("aws", options={"region": "us-east-1", "instance_type": "m5.xlarge"})
        plan = ScalePlan(
            workers_by_tag={"model": 2},
            resources_by_tag={"model": ResourceRequest(cpus=4, memory="8G")},
        )
        estimate = provider.estimate_cost(spec, plan)
        assert estimate is not None
        assert estimate.provider == "aws"
        assert estimate.total_hourly > 0


class TestKubernetesProvider:
    def test_validate_passes_clean_manifest(self):
        from scalable.providers.kubernetes import KubernetesProvider

        provider = KubernetesProvider()
        spec = _make_spec("kubernetes", options={"namespace": "default", "image": "python:3.11"})
        report = provider.validate(spec)
        assert report.ok

    def test_validate_warns_missing_image(self):
        from scalable.providers.kubernetes import KubernetesProvider

        provider = KubernetesProvider()
        spec = _make_spec("kubernetes", options={"namespace": "default"})
        report = provider.validate(spec)
        assert any("image" in w.message for w in report.warnings)

    def test_validate_warns_unknown_options(self):
        from scalable.providers.kubernetes import KubernetesProvider

        provider = KubernetesProvider()
        spec = _make_spec("kubernetes", options={"unknown_opt": "val"})
        report = provider.validate(spec)
        assert any("unknown_opt" in w.message for w in report.warnings)

    def test_name(self):
        from scalable.providers.kubernetes import KubernetesProvider

        provider = KubernetesProvider()
        assert provider.name == "kubernetes"

    def test_estimate_cost_returns_none(self):
        from scalable.providers.kubernetes import KubernetesProvider

        provider = KubernetesProvider()
        spec = _make_spec("kubernetes")
        plan = ScalePlan(workers_by_tag={"model": 1}, resources_by_tag={})
        assert provider.estimate_cost(spec, plan) is None


class TestProviderRegistryPhase3:
    def test_kubernetes_in_builtin(self):
        from scalable.providers.registry import _load_builtin_provider

        factory = _load_builtin_provider("kubernetes")
        assert factory is not None

    def test_aws_in_builtin(self):
        from scalable.providers.registry import _load_builtin_provider

        factory = _load_builtin_provider("aws")
        assert factory is not None

    def test_gcp_in_builtin(self):
        from scalable.providers.registry import _load_builtin_provider

        factory = _load_builtin_provider("gcp")
        assert factory is not None
