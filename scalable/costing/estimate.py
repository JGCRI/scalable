"""CostEstimate dataclass and helper utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CostLineItem:
    """A single line item in a cost breakdown.

    Attributes
    ----------
    resource : str
        Resource being charged (e.g. ``"compute"``, ``"storage"``,
        ``"network"``).
    description : str
        Human-readable description of the charge.
    unit : str
        Unit of measurement (e.g. ``"USD/hr"``, ``"USD/GB"``).
    quantity : float
        Number of units consumed.
    unit_cost : float
        Cost per unit in USD.
    total : float
        ``quantity * unit_cost``.
    """

    resource: str
    description: str
    unit: str
    quantity: float
    unit_cost: float
    total: float

    @classmethod
    def compute(
        cls,
        *,
        resource: str,
        description: str,
        unit: str,
        quantity: float,
        unit_cost: float,
    ) -> CostLineItem:
        """Create a line item and auto-compute total."""
        return cls(
            resource=resource,
            description=description,
            unit=unit,
            quantity=quantity,
            unit_cost=unit_cost,
            total=round(quantity * unit_cost, 6),
        )


@dataclass(frozen=True)
class CostEstimate:
    """Provider-neutral cost estimate for a deployment plan.

    Returned by :meth:`DeploymentProvider.estimate_cost`. Phase 3 uses
    static cost tables; future phases may integrate live pricing APIs.

    Attributes
    ----------
    provider : str
        Provider name that produced this estimate.
    region : str | None
        Cloud region (e.g. ``"us-east-1"``). ``None`` for on-prem.
    currency : str
        ISO 4217 currency code (default ``"USD"``).
    total_hourly : float
        Estimated total hourly cost in ``currency``.
    total_monthly : float
        Estimated total monthly cost (730 hours).
    line_items : list[CostLineItem]
        Itemized breakdown.
    metadata : dict[str, Any]
        Provider-specific extra metadata (instance types, spot flags, etc.).
    """

    provider: str
    region: str | None = None
    currency: str = "USD"
    total_hourly: float = 0.0
    total_monthly: float = 0.0
    line_items: list[CostLineItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON/telemetry persistence."""
        return {
            "provider": self.provider,
            "region": self.region,
            "currency": self.currency,
            "total_hourly": self.total_hourly,
            "total_monthly": self.total_monthly,
            "line_items": [
                {
                    "resource": li.resource,
                    "description": li.description,
                    "unit": li.unit,
                    "quantity": li.quantity,
                    "unit_cost": li.unit_cost,
                    "total": li.total,
                }
                for li in self.line_items
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_line_items(
        cls,
        *,
        provider: str,
        region: str | None = None,
        currency: str = "USD",
        line_items: list[CostLineItem],
        metadata: dict[str, Any] | None = None,
    ) -> CostEstimate:
        """Build a CostEstimate summing line items."""
        total = sum(li.total for li in line_items)
        return cls(
            provider=provider,
            region=region,
            currency=currency,
            total_hourly=round(total, 6),
            total_monthly=round(total * 730, 4),
            line_items=list(line_items),
            metadata=metadata or {},
        )


__all__ = ["CostEstimate", "CostLineItem"]
