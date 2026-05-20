.. _beginner_scaling_strategies:

======================================================
Beginner Tutorial 3: How Distributed Computing Works
======================================================

.. contents:: In This Tutorial
   :local:
   :depth: 2

The Big Picture
----------------

You've written a workflow that runs on your laptop with 2 workers. But what
happens when your data grows 100× and you need 64 workers on an HPC cluster?
Or when you need to burst into the cloud during peak demand?

This tutorial explains the **fundamentals of distributed computing** — how
work gets split up, how multiple machines coordinate, and how Scalable's
provider architecture lets you switch between execution backends without
changing your code.

.. admonition:: 💡 Key Concept: Why Distribute at All?
   :class: tip

   **The fundamental problem:** Some computations take too long on one
   machine.

   Consider running 1000 climate scenarios where each takes 5 minutes:

   * **Sequential (1 CPU):** 1000 × 5 min = 83 hours (3.5 days)
   * **Parallel (10 CPUs):** 1000 ÷ 10 × 5 min = 8.3 hours
   * **Parallel (100 CPUs):** 1000 ÷ 100 × 5 min = 50 minutes

   Distributed computing trades **hardware** for **time**. But it introduces
   complexity: coordination, communication, failure handling. Scalable manages
   that complexity for you.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand the client-scheduler-worker architecture.
* Know the difference between vertical and horizontal scaling.
* Grasp concurrency vs. parallelism.
* Use the Local, Slurm, and Cloud providers.
* Configure manual, adaptive, and objective-driven scaling.
* Understand Amdahl's Law and when NOT to distribute.
* Monitor scaling decisions through telemetry.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started` and :ref:`beginner_manifest_system`.
* Scalable installed (``pip install scalable``).
* For HPC concepts: no cluster needed (follow along conceptually).


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: Vertical vs. Horizontal Scaling
   :class: tip

   There are two ways to get more computing power:

   **Vertical scaling (scale UP):**
     Get a bigger machine — more CPUs, more RAM. Like buying a faster car.

     * Pros: Simple (no coordination needed), works for any workload
     * Cons: Expensive, has physical limits (you can't buy a 10,000-core laptop)

   **Horizontal scaling (scale OUT):**
     Get more machines working together. Like having a fleet of cars.

     * Pros: Nearly unlimited capacity, cost-effective
     * Cons: Requires coordination, not all problems can be split

   Scalable focuses on **horizontal scaling** — distributing work across
   multiple workers. But the workers themselves can be vertically scaled
   (bigger instances with more RAM per worker).

.. admonition:: 💡 Key Concept: The Scheduler-Worker Architecture
   :class: tip

   Distributed systems typically have three roles:

   **Client** (you):
     Submits work and collects results. This is your Python script.

   **Scheduler** (traffic controller):
     Receives tasks from clients and assigns them to workers. It tracks
     which workers are available, which tasks are queued, and which are
     complete. It makes the decisions about *where* each task runs.

   **Workers** (the labor force):
     Actually execute the functions. Each worker is a separate process (or
     thread) that can run independently.

   .. code-block:: text

      ┌──────────┐         ┌────────────┐         ┌──────────┐
      │  Client  │────────▶│  Scheduler │────────▶│ Worker 1 │
      │ (you)    │         │ (Dask)     │────────▶│ Worker 2 │
      │          │◀────────│            │────────▶│ Worker 3 │
      └──────────┘         └────────────┘         └──────────┘
         submit()            assigns tasks          executes &
         gather()            tracks state           returns results

   In Scalable:

   * The **client** is your Python script using ``ScalableSession``
   * The **scheduler** is Dask's scheduler (managed automatically)
   * The **workers** are spawned by the provider (local processes, Slurm
     jobs, cloud containers, K8s pods)

.. admonition:: 💡 Key Concept: Concurrency vs. Parallelism
   :class: tip

   These terms are related but different:

   **Concurrency:** Multiple tasks *in progress* at the same time (but maybe
   not literally simultaneous). Like a chef working on 3 dishes — chopping
   for one, checking the oven for another.

   **Parallelism:** Multiple tasks *executing* at the exact same instant on
   different CPUs. Like 3 chefs each cooking their own dish simultaneously.

   * **Threads** give you concurrency (and parallelism for I/O, but not for
     CPU-bound Python code due to the GIL).
   * **Processes** give you true parallelism (each has its own Python
     interpreter and memory space).

   Scalable supports both modes via the ``processes`` setting in your target.

.. admonition:: 💡 Key Concept: What is an HPC Cluster?
   :class: tip

   An **HPC (High-Performance Computing) cluster** is a collection of
   powerful computers (called "nodes") connected by a fast network, managed
   by a job scheduler.

   Key components:

   * **Login nodes** — where you SSH in and submit jobs
   * **Compute nodes** — where actual work runs
   * **Job scheduler** (e.g., Slurm) — queues and allocates jobs to nodes
   * **Shared filesystem** — storage accessible from all nodes

   **How it works:** You don't directly pick which computer runs your code.
   Instead, you submit a job request ("I need 4 nodes for 2 hours") and the
   scheduler finds available resources.

.. admonition:: 💡 Key Concept: What is Slurm?
   :class: tip

   **Slurm** (Simple Linux Utility for Resource Management) is the most
   popular job scheduler for HPC clusters. It's the "traffic controller"
   that decides when and where your computation runs.

   Key Slurm concepts:

   * **Queue/Partition** — groups of nodes with similar properties
   * **Account** — billing/allocation identifier for your group
   * **Walltime** — maximum allowed runtime for your job
   * **Job** — a unit of work submitted to the scheduler

   Scalable's Slurm provider translates your manifest's target configuration
   into Slurm job submissions automatically.

.. admonition:: 💡 Key Concept: Amdahl's Law
   :class: tip

   **Amdahl's Law** says that the speedup from parallelism is limited by the
   sequential portion of your program.

   If 90% of your work can be parallelized and 10% must be sequential:

   * 10 workers → ~5.3× speedup (not 10×)
   * 100 workers → ~9.2× speedup (not 100×)
   * 1000 workers → ~9.9× speedup (not 1000×)

   **Lesson:** Don't throw more workers at a problem than necessary. There's
   always a point of diminishing returns. Scalable's telemetry helps you
   find the sweet spot.


Step 1: The Provider Architecture
-----------------------------------

Scalable separates **what** runs from **where** it runs:

.. code-block:: text

   ┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
   │  Manifest    │────▶│ DeploymentSpec    │────▶│  Provider   │
   │(scalable.yaml)│    │(provider-neutral) │     │ (backend)   │
   └──────────────┘     └──────────────────┘     └──────┬──────┘
                                                         │
                        ┌────────────────────────────────┼────────┐
                        │                                │        │
                  ┌─────▼──────┐  ┌──────▼──────┐  ┌───▼────────┐
                  │   Local    │  │    Slurm    │  │    Cloud    │
                  │ (threads/  │  │  (HPC jobs) │  │  (Fargate/  │
                  │  processes)│  │             │  │   EC2/GKE)  │
                  └────────────┘  └─────────────┘  └─────────────┘

.. admonition:: 💡 Key Concept: Abstraction Layer
   :class: tip

   An **abstraction layer** hides complexity behind a simple interface. You
   interact with the abstraction (the provider API) without knowing the
   details underneath.

   **Real-world analogy:** When you flip a light switch, you don't need to
   know whether your electricity comes from solar panels, a nuclear plant,
   or a gas turbine. The switch is the abstraction layer.

   In Scalable, the provider abstraction means your workflow code
   (``client.submit()``) works identically regardless of whether tasks run
   locally, on Slurm, or in AWS.


Step 2: The Local Provider (Development)
------------------------------------------

The simplest provider runs everything on your machine:

.. code-block:: yaml

   targets:
     local:
       provider: local
       max_workers: 4
       threads_per_worker: 2
       processes: false
       containers: none

**What each setting controls:**

``max_workers: 4``
   The maximum number of parallel executors. With 4 workers, up to 4 tasks
   can run simultaneously.

``threads_per_worker: 2``
   Each worker can handle 2 threads. This matters for I/O-bound tasks
   (network calls, file reads) that spend time waiting.

``processes: false``
   Workers run as threads in a single process (fast startup, shared memory).
   Set to ``true`` for CPU-bound work that needs to bypass the GIL.

``containers: none``
   No containerization — functions run in your current Python environment.

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   plan = session.plan()
   client = session.start(plan)

   # Submit work — it runs on local workers
   futures = [client.submit(my_func, i, tag="analysis") for i in range(20)]
   results = client.gather(futures)
   session.close()

.. admonition:: Under the Hood
   :class: hint

   When you create a ``ScalableSession`` with the local provider:

   1. Scalable reads the manifest and parses the ``local`` target
   2. It creates a Dask ``LocalCluster`` with the specified workers
   3. A Dask ``Client`` connects to the cluster's scheduler
   4. Your ``submit()`` calls become Dask ``client.submit()`` calls
   5. The scheduler distributes tasks across the local workers
   6. Results flow back through the client to your script


Step 3: The Slurm Provider (HPC)
----------------------------------

For HPC clusters, the Slurm provider translates your manifest into job
submissions:

.. code-block:: yaml

   targets:
     hpc:
       provider: slurm
       queue: batch
       account: GCIMS
       walltime: "04:00:00"
       interface: ib0

.. admonition:: What these settings mean in HPC terms
   :class: note

   ``queue: batch``
     Which partition (group of nodes) to submit to. Clusters often have
     ``batch`` (general), ``gpu`` (GPU nodes), ``debug`` (quick, limited).

   ``account: GCIMS``
     Your team's allocation identifier. HPC centers track usage by account
     for billing and fairness.

   ``walltime: "04:00:00"``
     Maximum runtime (4 hours). The job is killed if it exceeds this.
     Quoted because ``04:00:00`` looks like a time to YAML.

   ``interface: ib0``
     Network interface for worker communication. ``ib0`` = InfiniBand
     (high-speed interconnect common in HPC).

When you run with ``--target hpc``, Scalable:

1. Generates Slurm job scripts automatically
2. Submits them to the Slurm scheduler
3. Workers start on allocated nodes
4. Your tasks distribute across the HPC workers
5. Results flow back to your client

**You don't write Slurm scripts manually** — the manifest declares what you
need and the provider handles the "how."


Step 4: Scaling Strategies
----------------------------

.. admonition:: 💡 Key Concept: Scaling Strategy
   :class: tip

   A **scaling strategy** determines how many workers are active at any time.
   Options range from fixed (always N workers) to fully dynamic (workers
   spin up/down based on demand).

**Manual (Fixed) Scaling:**

.. code-block:: yaml

   targets:
     local:
       provider: local
       max_workers: 4     # Always exactly 4 workers

You decide the worker count upfront. Simple and predictable.

**Adaptive Scaling:**

.. code-block:: yaml

   targets:
     cloud:
       provider: aws
       adaptive:
         minimum: 1       # At least 1 worker always running
         maximum: 20      # Scale up to 20 when busy

.. admonition:: 💡 Key Concept: Adaptive Scaling
   :class: tip

   **Adaptive scaling** automatically adjusts worker count based on workload:

   * Queue growing → add workers (scale up)
   * Workers idle → remove workers (scale down)

   **Benefits:**

   * Cost efficiency — don't pay for idle workers
   * Responsiveness — handle bursts without pre-provisioning
   * Simplicity — no need to predict workload size

   **Trade-offs:**

   * Latency — spinning up new workers takes time
   * Thrashing — rapid up/down cycles waste resources
   * Minimum guarantee — you need at least some workers ready

   Scalable implements adaptive scaling with configurable thresholds and
   cooldown periods to prevent thrashing.

**Objective-Driven Scaling:**

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml(
       "./scalable.yaml",
       target="cloud",
       objectives={"budget_usd": 50.0, "deadline_hours": 2.0},
   )

.. admonition:: 💡 Key Concept: Objective-Driven Planning
   :class: tip

   **Objective-driven planning** lets you specify goals (budget, deadline)
   and Scalable figures out the optimal resource allocation:

   * "I have $50 and need results in 2 hours" → Scalable calculates how
     many workers fit within budget and meet the deadline
   * Based on telemetry history, it predicts task duration and scales
     accordingly

   This is the most sophisticated scaling mode — it requires telemetry
   history to make predictions.


Step 5: Monitoring Scaling Decisions
--------------------------------------

Every scaling decision is recorded in telemetry:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   plan = session.plan()
   client = session.start(plan)

   # After your run, check what happened
   # Telemetry records scaling events:
   # - worker_added (when a new worker started)
   # - worker_removed (when a worker was stopped)
   # - scale_decision (why the system scaled up/down)

The ``scalable report`` command summarizes scaling behavior:

.. code-block:: bash

   scalable report --last

.. code-block:: text

   Run: run-20260520T...-energy-forecast-abc123
   Target: local (provider: local)
   Workers: peak=4, avg=3.2
   Tasks: 20 completed, 0 failed
   Duration: 12.4s
   Efficiency: 87% (worker utilization)


Step 6: Choosing the Right Strategy
--------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 30 30

   * - Scenario
     - Strategy
     - Why
     - Config
   * - Development
     - Fixed (2–4 workers)
     - Fast startup, predictable
     - ``max_workers: 4``
   * - Batch production
     - Fixed (many workers)
     - Known workload size
     - ``max_workers: 64``
   * - Variable workload
     - Adaptive
     - Cost-efficient
     - ``adaptive: {min: 2, max: 50}``
   * - Budget-constrained
     - Objective-driven
     - Optimize cost/time
     - ``objectives: {budget_usd: 100}``

.. admonition:: 🤔 Think About It
   :class: note

   If you have 100 independent tasks that each take 1 minute:

   * 1 worker → 100 minutes
   * 10 workers → 10 minutes
   * 100 workers → ~1 minute (plus ~30s startup overhead)
   * 200 workers → ~1 minute (half the workers sit idle!)

   The sweet spot depends on task count, task duration, and worker startup
   cost. Telemetry from past runs helps you find it.


Common Questions
-----------------

**Q: What if I only have one computer?**

The local provider still gives you parallelism through multiple processes or
threads. A modern laptop with 8 cores can run 8 workers doing genuine
parallel work (with ``processes: true``).

**Q: Do workers communicate with each other?**

Not directly in most cases. Workers communicate through the scheduler (via
futures and results). If Task B depends on Task A's output, the scheduler
ensures A completes before B starts, and transfers the result.

**Q: What happens if a worker crashes?**

Scalable (via Dask) detects the failure and can reassign the task to another
worker. Tutorial 7 covers this in detail.

**Q: Is there overhead to distributing work?**

Yes! Each task has overhead: serialization, network transfer, scheduling
decisions. For very small tasks (< 1ms), the overhead exceeds the computation.
Rule of thumb: tasks should take at least 100ms to benefit from distribution.

**Q: Can I mix providers in one run?**

No — a single run uses one target (one provider). But you can run the same
manifest with different targets for different purposes (dev locally, run in
production on HPC).


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Horizontal Scaling
     - Adding more machines/workers to handle more work
   * - Vertical Scaling
     - Getting a bigger/faster single machine
   * - Scheduler
     - Component that assigns tasks to workers
   * - Worker
     - Process/thread that executes tasks
   * - Client
     - Your script that submits work and collects results
   * - Concurrency
     - Multiple tasks in progress (maybe not simultaneous)
   * - Parallelism
     - Multiple tasks executing at the same instant
   * - HPC Cluster
     - Collection of computers managed by a job scheduler
   * - Slurm
     - Popular HPC job scheduler
   * - Provider
     - Abstraction over an execution backend
   * - Adaptive Scaling
     - Automatically adjusting worker count based on demand
   * - Amdahl's Law
     - Parallelism speedup limited by sequential portion
   * - Abstraction Layer
     - Simple interface hiding complex implementation details


Next Steps
-----------

You now understand how distributed computing works and how Scalable's provider
architecture makes it portable across environments.

* **Next beginner tutorial:** :ref:`beginner_caching` — avoid repeating
  expensive computation
* **Standard tutorial:** :ref:`tutorial_scaling_strategies` — advanced
  provider configuration and production scaling patterns
* **Experiment:** Change ``max_workers`` in your manifest from 2 to 8.
  Submit 100 tasks and time the difference. At what point do more workers
  stop helping?
