Cost Estimation
===============

Scalable provides static-table-based cost estimation for cloud providers,
helping users understand the financial impact of their deployment plans
before execution.

Overview
--------

The :mod:`scalable.costing` module defines:

- :class:`~scalable.costing.CostEstimate` — provider-neutral cost estimate
- :class:`~scalable.costing.CostLineItem` — itemized cost breakdown

Providers implement the optional ``estimate_cost()`` method:

- **AWS** — estimates from static on-demand pricing tables
- **GCP** — estimates from static on-demand pricing tables
- **Kubernetes** — returns ``None`` (on-prem k8s has no direct cost)
- **Local/Slurm** — returns ``None`` (no monetary cost)

Usage
-----

Via CLI (dry-run mode):

.. code-block:: bash

   scalable run scalable.yaml --target aws --dry-run

This prints the cost estimate and includes it in the plan output.

Programmatic access:

.. code-block:: python

   from scalable.providers.registry import get_provider
   from scalable.providers.base import DeploymentSpec, ScalePlan

   provider = get_provider("aws")
   estimate = provider.estimate_cost(spec, plan)
   if estimate:
       print(f"${estimate.total_hourly:.4f}/hr")
       print(f"${estimate.total_monthly:.2f}/mo")

Telemetry Integration
---------------------

When a cost estimate is produced during a run, it is recorded as a
``CostEvent`` in the telemetry store (``cost.jsonl``). The
``scalable report`` command includes cost summary data:

.. code-block:: text

   cost:
     hourly_usd: 0.384
     monthly_usd: 280.32

Cost Tables
-----------

Static cost tables cover common AWS and GCP instance types across major
regions. These are representative on-demand Linux pricing as of 2024.

Supported AWS instances: ``m5.*``, ``c5.*``, ``r5.*``, ``t3.*``

Supported GCP machines: ``n1-standard-*``, ``n1-highmem-*``,
``n1-highcpu-*``, ``e2-standard-*``

Future Phases
-------------

Phase 5 will extend cost estimation with:

- Live pricing API integration
- Spot/preemptible instance pricing
- Cost-aware scheduling recommendations
- Historical cost tracking and budgets
