"""Unit tests for cloud provider cost tables."""

from __future__ import annotations

from scalable.providers.cloud.cost_tables import (
    get_instance_cost,
    list_instance_types,
    list_regions,
)


class TestCostTables:
    def test_aws_m5_xlarge_us_east_1(self):
        cost = get_instance_cost(
            provider="aws", instance_type="m5.xlarge", region="us-east-1"
        )
        assert cost == 0.192

    def test_gcp_n1_standard_4_us_central1(self):
        cost = get_instance_cost(
            provider="gcp", instance_type="n1-standard-4", region="us-central1"
        )
        assert cost == 0.190

    def test_unknown_provider(self):
        cost = get_instance_cost(
            provider="azure", instance_type="m5.xlarge", region="us-east-1"
        )
        assert cost is None

    def test_unknown_instance_type(self):
        cost = get_instance_cost(
            provider="aws", instance_type="p4d.24xlarge", region="us-east-1"
        )
        assert cost is None

    def test_unknown_region(self):
        cost = get_instance_cost(
            provider="aws", instance_type="m5.xlarge", region="ap-southeast-1"
        )
        assert cost is None

    def test_list_instance_types_aws(self):
        types = list_instance_types("aws")
        assert "m5.xlarge" in types
        assert "c5.large" in types

    def test_list_instance_types_gcp(self):
        types = list_instance_types("gcp")
        assert "n1-standard-4" in types

    def test_list_regions(self):
        regions = list_regions("aws", "m5.xlarge")
        assert "us-east-1" in regions
        assert "us-west-2" in regions
