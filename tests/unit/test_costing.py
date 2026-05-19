"""Unit tests for scalable.costing module."""

from __future__ import annotations

import pytest

from scalable.costing import CostEstimate, CostLineItem


class TestCostLineItem:
    def test_compute_basic(self):
        li = CostLineItem.compute(
            resource="compute",
            description="2x m5.xlarge",
            unit="USD/hr",
            quantity=2.0,
            unit_cost=0.192,
        )
        assert li.resource == "compute"
        assert li.quantity == 2.0
        assert li.unit_cost == 0.192
        assert li.total == pytest.approx(0.384, abs=1e-6)

    def test_compute_zero_quantity(self):
        li = CostLineItem.compute(
            resource="storage",
            description="0 GB",
            unit="USD/GB",
            quantity=0.0,
            unit_cost=0.023,
        )
        assert li.total == 0.0


class TestCostEstimate:
    def test_from_line_items(self):
        items = [
            CostLineItem.compute(
                resource="compute",
                description="worker group 'model'",
                unit="USD/hr",
                quantity=3.0,
                unit_cost=0.192,
            ),
            CostLineItem.compute(
                resource="compute",
                description="worker group 'postprocess'",
                unit="USD/hr",
                quantity=1.0,
                unit_cost=0.096,
            ),
        ]
        est = CostEstimate.from_line_items(
            provider="aws",
            region="us-east-1",
            line_items=items,
        )
        assert est.provider == "aws"
        assert est.region == "us-east-1"
        assert est.currency == "USD"
        assert est.total_hourly == pytest.approx(0.672, abs=1e-6)
        assert est.total_monthly == pytest.approx(0.672 * 730, abs=0.01)
        assert len(est.line_items) == 2

    def test_to_dict(self):
        est = CostEstimate(
            provider="gcp",
            region="us-central1",
            total_hourly=0.5,
            total_monthly=365.0,
        )
        d = est.to_dict()
        assert d["provider"] == "gcp"
        assert d["region"] == "us-central1"
        assert d["total_hourly"] == 0.5
        assert d["total_monthly"] == 365.0
        assert d["line_items"] == []
        assert d["metadata"] == {}

    def test_default_values(self):
        est = CostEstimate(provider="local")
        assert est.region is None
        assert est.currency == "USD"
        assert est.total_hourly == 0.0
        assert est.total_monthly == 0.0
