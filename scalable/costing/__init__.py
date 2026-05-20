"""Cost estimation primitives for Scalable providers.

This module exposes :class:`CostEstimate` — the provider-neutral cost
dataclass returned by ``DeploymentProvider.estimate_cost()``.
"""

from __future__ import annotations

from .estimate import CostEstimate, CostLineItem

__all__ = ["CostEstimate", "CostLineItem"]
