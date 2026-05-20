"""Static cost tables for cloud providers.

Phase 3 uses static lookup tables for cost estimation. These provide
representative on-demand pricing for common instance types. Future phases
may integrate live pricing APIs.
"""

from __future__ import annotations

# Instance pricing: provider -> instance_type -> region -> USD/hr
# Representative on-demand Linux pricing as of 2024.
_COST_TABLE: dict[str, dict[str, dict[str, float]]] = {
    "aws": {
        "m5.large": {"us-east-1": 0.096, "us-west-2": 0.096, "eu-west-1": 0.107},
        "m5.xlarge": {"us-east-1": 0.192, "us-west-2": 0.192, "eu-west-1": 0.214},
        "m5.2xlarge": {"us-east-1": 0.384, "us-west-2": 0.384, "eu-west-1": 0.428},
        "m5.4xlarge": {"us-east-1": 0.768, "us-west-2": 0.768, "eu-west-1": 0.856},
        "c5.large": {"us-east-1": 0.085, "us-west-2": 0.085, "eu-west-1": 0.096},
        "c5.xlarge": {"us-east-1": 0.170, "us-west-2": 0.170, "eu-west-1": 0.192},
        "c5.2xlarge": {"us-east-1": 0.340, "us-west-2": 0.340, "eu-west-1": 0.384},
        "r5.large": {"us-east-1": 0.126, "us-west-2": 0.126, "eu-west-1": 0.141},
        "r5.xlarge": {"us-east-1": 0.252, "us-west-2": 0.252, "eu-west-1": 0.282},
        "r5.2xlarge": {"us-east-1": 0.504, "us-west-2": 0.504, "eu-west-1": 0.564},
        "t3.medium": {"us-east-1": 0.0416, "us-west-2": 0.0416, "eu-west-1": 0.0468},
        "t3.large": {"us-east-1": 0.0832, "us-west-2": 0.0832, "eu-west-1": 0.0936},
    },
    "gcp": {
        "n1-standard-2": {"us-central1": 0.095, "us-east1": 0.095, "europe-west1": 0.104},
        "n1-standard-4": {"us-central1": 0.190, "us-east1": 0.190, "europe-west1": 0.209},
        "n1-standard-8": {"us-central1": 0.380, "us-east1": 0.380, "europe-west1": 0.418},
        "n1-standard-16": {"us-central1": 0.760, "us-east1": 0.760, "europe-west1": 0.836},
        "n1-highmem-4": {"us-central1": 0.237, "us-east1": 0.237, "europe-west1": 0.260},
        "n1-highmem-8": {"us-central1": 0.474, "us-east1": 0.474, "europe-west1": 0.520},
        "n1-highcpu-4": {"us-central1": 0.142, "us-east1": 0.142, "europe-west1": 0.156},
        "n1-highcpu-8": {"us-central1": 0.284, "us-east1": 0.284, "europe-west1": 0.312},
        "e2-standard-2": {"us-central1": 0.067, "us-east1": 0.067, "europe-west1": 0.074},
        "e2-standard-4": {"us-central1": 0.134, "us-east1": 0.134, "europe-west1": 0.147},
    },
}


def get_instance_cost(
    *,
    provider: str,
    instance_type: str,
    region: str,
) -> float | None:
    """Look up hourly cost for an instance type.

    Parameters
    ----------
    provider : str
        Cloud provider name (``"aws"`` or ``"gcp"``).
    instance_type : str
        Instance type identifier.
    region : str
        Cloud region.

    Returns
    -------
    float | None
        Hourly cost in USD, or None if not found in tables.
    """
    provider_table = _COST_TABLE.get(provider, {})
    instance_table = provider_table.get(instance_type, {})
    return instance_table.get(region)


def list_instance_types(provider: str) -> list[str]:
    """List known instance types for a provider."""
    return sorted(_COST_TABLE.get(provider, {}).keys())


def list_regions(provider: str, instance_type: str) -> list[str]:
    """List known regions for a provider/instance combination."""
    return sorted(_COST_TABLE.get(provider, {}).get(instance_type, {}).keys())


__all__ = ["get_instance_cost", "list_instance_types", "list_regions"]
