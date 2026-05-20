"""Unit tests for Phase 3 telemetry extensions (CostEvent, cost.jsonl)."""

from __future__ import annotations

from scalable.telemetry.events import CostEvent, RemoteCacheEvent


class TestCostEvent:
    def test_creation(self):
        event = CostEvent(
            run_id="test-run-123",
            provider="aws",
            region="us-east-1",
            currency="USD",
            total_hourly=0.384,
            total_monthly=280.32,
        )
        assert event.event_type == "cost"
        assert event.provider == "aws"
        assert event.total_hourly == 0.384

    def test_to_dict(self):
        event = CostEvent(
            run_id="test-run-123",
            provider="gcp",
            region="us-central1",
            currency="USD",
            total_hourly=0.5,
            total_monthly=365.0,
            line_items=[{"resource": "compute", "total": 0.5}],
            metadata={"instance_type": "n1-standard-4"},
        )
        d = event.to_dict()
        assert d["event_type"] == "cost"
        assert d["provider"] == "gcp"
        assert d["region"] == "us-central1"
        assert len(d["line_items"]) == 1
        assert d["metadata"]["instance_type"] == "n1-standard-4"

    def test_schema_version(self):
        from scalable.telemetry.events import SCHEMA_VERSION

        event = CostEvent(
            run_id="x",
            provider="aws",
            region=None,
            currency="USD",
            total_hourly=0,
            total_monthly=0,
        )
        assert event.schema_version == SCHEMA_VERSION


class TestRemoteCacheEvent:
    def test_creation(self):
        event = RemoteCacheEvent(
            run_id="test-run-456",
            function_name="compute_climate",
            key_digest="abcdef12",
            hit=True,
            remote=True,
            remote_uri="s3://bucket/cache/ab/abcdef12",
        )
        assert event.event_type == "remote_cache"
        assert event.remote is True
        assert event.hit is True

    def test_to_dict(self):
        event = RemoteCacheEvent(
            run_id="test-run-456",
            function_name="run_model",
            key_digest="fedcba98",
            hit=False,
            remote=True,
        )
        d = event.to_dict()
        assert d["event_type"] == "remote_cache"
        assert d["hit"] is False
        assert d["remote"] is True
