.. _tutorial_scaling_strategies:

======================================================
Tutorial 3: Scaling Strategies with Providers
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Understand Scalable's provider architecture and how it abstracts execution
  backends.
* Configure and use the Local, Slurm, and Cloud providers.
* Choose appropriate scaling strategies for different workload profiles.
* Implement manual scaling, adaptive scaling, and policy-driven planning.
* Monitor scaling decisions through the Session API.

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started` and :ref:`tutorial_manifest_system`.
* For HPC sections: access to a Slurm cluster (or follow along conceptually).
* For cloud sections: ``pip install scalable[cloud]`` (or follow along
  conceptually).

Scenario
--------

Your climate pipeline has grown. Development happens locally with 2–4 workers.
Production runs on an HPC cluster with 64+ workers. Burst capacity uses cloud
auto-scaling. You need a unified scaling approach that works across all three
environments.

Step 1: The Provider Architecture
----------------------------------

Scalable separates **what** runs from **where** it runs through the
:class:`~scalable.providers.base.DeploymentProvider` protocol:

.. code-block:: text

   ┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
   │  Manifest    │────▶│ DeploymentSpec    │────▶│  Provider   │
   │ (scalable.yaml)    │ (provider-neutral)│     │ (backend)   │
   └──────────────┘     └──────────────────┘     └──────┬──────┘
                                                         │
                        ┌────────────────────────────────┼────────┐
                        │                                │        │
                  ┌─────▼──────┐  ┌──────▼──────┐  ┌───▼────────┐
                  │   Local    │  │    Slurm    │  │Cloud / K8s  │
                  │  Provider  │  │  Provider   │  │  Provider   │
                  └────────────┘  └─────────────┘  └─────────────┘

Every provider implements the same interface:

.. code-block:: python

   class DeploymentProvider(Protocol):
       name: str

       def validate(self, spec: DeploymentSpec) -> ValidationReport: ...
       def build_cluster(self, spec: DeploymentSpec) -> ClusterHandle: ...
       def scale(self, cluster: ClusterHandle, plan: ScalePlan) -> None: ...
       def estimate_cost(self, spec: DeploymentSpec, plan: ScalePlan) -> CostEstimate | None: ...

This means your workflow code is **provider-agnostic** — the same
``client.submit(func, arg, tag="gcam")`` call works identically whether the
cluster is local threads, Slurm jobs, or Kubernetes pods.

Step 2: Local Provider — Development & CI
-------------------------------------------

The :class:`~scalable.providers.local.LocalProvider` wraps Dask's
``LocalCluster``. It is the fastest way to iterate:

.. code-block:: yaml

   targets:
     local:
       provider: local
       max_workers: 4
       threads_per_worker: 2
       processes: false
       containers: none

Key options:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Option
     - Default
     - Behavior
   * - ``max_workers``
     - 1
     - Total worker count across all component groups.
   * - ``threads_per_worker``
     - 1
     - Threads per Dask worker process/thread.
   * - ``processes``
     - ``false``
     - ``true`` → each worker is a separate process (memory isolation).
       ``false`` → threaded workers (faster startup, shared memory).
   * - ``containers``
     - ``none``
     - ``none`` = bare-metal; ``docker`` = future container support.

**When to use processes vs threads:**

* **Threads** (``processes: false``): Best for I/O-bound tasks, quick
  iteration, and CI where startup speed matters. All workers share one process,
  so a memory leak in one affects all.
* **Processes** (``processes: true``): Best for CPU-bound tasks or tasks that
  hold the GIL (e.g., calling C extensions that don't release it). Each worker
  is isolated but has serialization overhead.

Running with the local provider:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   plan = session.plan(dry_run=True)
   print(f"Scale plan: {plan.scale_plan}")
   # {'analysis': ResourceRequest(cpus=1, memory='1G'), count=4}

   client = session.start(plan)
   # ... submit work ...
   session.close()

Step 3: Slurm Provider — HPC Scaling
--------------------------------------

The :class:`~scalable.providers.slurm.SlurmProvider` submits Dask workers as
Slurm batch jobs. Each job runs inside a container (via Apptainer) on allocated
HPC nodes:

.. code-block:: yaml

   targets:
     hpc:
       provider: slurm
       queue: batch
       account: GCIMS
       walltime: "04:00:00"
       interface: ib0

   components:
     gcam:
       image: ghcr.io/jgcri/gcam:7.0
       cpus: 10
       memory: 20G
       mounts:
         /qfs/people/user/work/gcam-core: /gcam-core
         /rcfs: /rcfs

The Slurm provider:

1. Generates ``sbatch`` scripts for each worker (one job per worker).
2. Passes resource requests (CPUs, memory, walltime) to the scheduler.
3. Launches workers inside Apptainer containers with the specified mounts.
4. Workers connect back to the Dask scheduler on the host via the network
   interface (``ib0`` for InfiniBand, ``eth0`` for Ethernet).

**Scaling Slurm workers manually:**

.. code-block:: python

   from scalable import SlurmCluster, ScalableClient

   cluster = SlurmCluster(
       queue="batch",
       account="GCIMS",
       walltime="04:00:00",
       interface="ib0",
   )

   # Register component profiles
   cluster.add_container(
       tag="gcam",
       cpus=10,
       memory="20G",
       dirs={"/qfs/people/user/work/gcam-core": "/gcam-core"},
   )

   # Scale up — submits 5 Slurm jobs
   cluster.add_workers(n=5, tag="gcam")

   # Submit work
   client = ScalableClient(cluster)
   futures = [client.submit(run_gcam, scenario, tag="gcam") for scenario in scenarios]
   results = client.gather(futures)

   # Scale down — cancels 3 Slurm jobs
   cluster.remove_workers(n=3, tag="gcam")

**Why explicit tag-based scaling?** HPC jobs are expensive. Unlike cloud
auto-scaling where you can spin up instances in seconds, Slurm jobs may wait
in queue for minutes or hours. Scalable gives you explicit control over how
many workers to allocate per component, so you can match your budget and queue
availability.

Step 4: Session-Based Scaling with Objectives
-----------------------------------------------

The Session API supports policy-driven planning that automatically determines
worker counts:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="hpc")

   # Minimize cost: fewest workers that finish within walltime
   plan = session.plan(
       objective="minimize cost",
       policy="safe",
   )
   print(f"Workers: {plan.scale_plan}")
   # Might allocate 3 workers × gcam

   # Minimize time: maximum parallelism within resource limits
   plan = session.plan(
       objective="minimize time",
       policy="aggressive",
   )
   print(f"Workers: {plan.scale_plan}")
   # Might allocate 16 workers × gcam

   # Balance: cost-time Pareto front midpoint
   plan = session.plan(
       objective="balance",
       policy="safe",
   )

Objectives:

* ``"minimize cost"`` — Fewest workers that keep total runtime within walltime.
* ``"minimize time"`` — Maximum workers within resource bounds.
* ``"balance"`` — Midpoint between the two extremes.

Policies:

* ``"safe"`` — Add headroom (20% over predicted requirements). Prefer fewer
  scaling decisions.
* ``"aggressive"`` — Pack tightly. Scale immediately on threshold.
* ``"manual"`` — Use exactly the worker counts from the manifest (no
  adjustment).

Step 5: Adaptive Scaling at Runtime
-------------------------------------

For long-running workflows where task load varies, the
:class:`~scalable.ml.adaptive_scaler.AdaptiveScaler` monitors queue depth
and adjusts workers in real-time:

.. code-block:: python

   from scalable import AdaptiveScaler, ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="aws")
   client = session.start()

   scaler = AdaptiveScaler(
       min_workers={"gcam": 2, "postprocess": 1},
       max_workers={"gcam": 20, "postprocess": 10},
       scale_up_threshold=0.8,    # Scale up when 80% of workers are busy
       scale_down_threshold=0.2,  # Scale down when <20% utilization
       cooldown_seconds=120,      # Wait 2 min between decisions
   )

   # In your task submission loop:
   for batch in scenario_batches:
       futures = [client.submit(run_gcam, s, tag="gcam") for s in batch]

       # Evaluate scaling after each batch
       decision = scaler.evaluate(
           pending_tasks=[{"tag": "gcam"} for _ in range(len(batch))],
           active_workers={"gcam": client.worker_count("gcam")},
       )

       if decision.has_changes:
           print(f"Scaling: +{decision.workers_to_add} -{decision.workers_to_remove}")
           print(f"Reason: {decision.reasoning}")
           # Apply the decision (provider-specific)
           # ...

The ``AdaptiveScaler`` returns a :class:`~scalable.ml.adaptive_scaler.ScaleDecision`
with:

* ``workers_to_add``: dict mapping tag → count to add.
* ``workers_to_remove``: dict mapping tag → count to remove.
* ``reasoning``: human-readable explanation of the decision.
* ``confidence``: model confidence (0.0–1.0) in the recommendation.
* ``predicted_completion_time``: estimated seconds to finish remaining tasks.

Step 6: Cloud Provider Auto-Scaling
-------------------------------------

Cloud providers (AWS, GCP) support declarative adaptive scaling via manifest
configuration:

.. code-block:: yaml

   targets:
     aws:
       provider: aws
       region: us-east-1
       cluster_type: fargate
       adaptive:
         minimum: 2
         maximum: 20

The cloud provider handles scale-up/down automatically based on the Dask
scheduler's task backlog. The ``minimum`` and ``maximum`` set hard bounds:

* **Minimum** workers are always running (reduces cold-start latency).
* **Maximum** caps costs during burst periods.

**Cost-performance trade-off:**

.. code-block:: text

   ┌────────────────────────────────────────────────────────┐
   │  Aggressive (max workers)                              │
   │  ├── Fastest completion                                │
   │  ├── Highest cost                                      │
   │  └── Risk: idle workers during low-load phases         │
   │                                                        │
   │  Conservative (min workers)                            │
   │  ├── Lowest cost                                       │
   │  ├── Slowest completion                                │
   │  └── Risk: queue buildup during bursts                 │
   │                                                        │
   │  Adaptive (dynamic scaling)                            │
   │  ├── Best cost-performance ratio                       │
   │  ├── Requires cooldown tuning                          │
   │  └── Latency: scale-up takes 30–90s for cloud          │
   └────────────────────────────────────────────────────────┘

Step 7: Heterogeneous Worker Pools
-----------------------------------

Real workflows often need different resource profiles running simultaneously.
Scalable supports heterogeneous pools via multiple components:

.. code-block:: yaml

   components:
     gcam:
       cpus: 8
       memory: 32G
       tags: [compute-heavy]

     postprocess:
       cpus: 2
       memory: 4G
       tags: [io-bound]

   tasks:
     simulate:
       component: gcam
     analyze:
       component: postprocess

In your workflow, you submit to each pool independently:

.. code-block:: python

   # Compute-heavy tasks go to gcam workers
   sim_futures = [
       client.submit(run_simulation, params, tag="gcam")
       for params in simulation_params
   ]

   # Wait for simulations, then post-process on lighter workers
   sim_results = client.gather(sim_futures)

   analysis_futures = [
       client.submit(aggregate, result, tag="postprocess")
       for result in sim_results
   ]

   final = client.gather(analysis_futures)

This pattern avoids over-provisioning: expensive 32 GB workers handle the heavy
lifting while cheap 4 GB workers handle aggregation.

Step 8: Scaling Decision Monitoring
-------------------------------------

Track all scaling decisions via telemetry:

.. code-block:: python

   # After workflow completes
   session.close()

   # Review scaling history
   for decision in scaler.decision_history:
       print(
           f"[{decision.timestamp}] "
           f"+{decision.workers_to_add} "
           f"-{decision.workers_to_remove} "
           f"({decision.reasoning})"
       )

Telemetry also records worker lifecycle events:

.. code-block:: bash

   scalable report --latest

.. code-block:: text

   Workers:
     gcam: 5 started, 3 removed, 2 final
     postprocess: 2 started, 0 removed, 2 final
   Scaling events: 3 scale-up, 1 scale-down

Troubleshooting
---------------

**Slurm workers never connect**
  Check that the ``interface`` option matches your cluster's high-speed
  network (``ib0``, ``eth0``, etc.). Workers must reach the scheduler host on
  this interface. Also ensure firewall rules allow the Dask scheduler port
  (default 8786).

**Cloud workers take too long to start**
  Fargate cold-start can take 30–90 seconds. Set ``adaptive.minimum`` to at
  least 1–2 so warm workers are always available. For EC2-backed clusters,
  pre-warmed AMIs reduce startup time.

**"max_workers must be a positive integer"**
  This validation error means ``max_workers`` was set to ``0``, a negative
  number, or a non-integer type. Check for YAML parsing issues (e.g., quoting
  numbers as strings).

**Workers idle but no tasks are submitted**
  If using adaptive scaling with a high minimum, workers persist even when no
  work is available. Lower ``adaptive.minimum`` or add a ``cooldown_seconds``
  of at least 60 to the ``AdaptiveScaler``.

Next Steps
----------

* :ref:`tutorial_caching` — Reduce redundant computation when scaling means
  re-running failed tasks.
* :ref:`tutorial_cloud_integration` — Full AWS and GCP deployment walkthrough.
* :ref:`tutorial_telemetry` — Use telemetry data to inform scaling decisions.
