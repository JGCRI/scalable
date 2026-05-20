.. _tutorial_getting_started:

======================================================
Tutorial 1: Getting Started with Scalable
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Install Scalable and verify its dependencies are satisfied.
* Understand the project layout Scalable expects.
* Create a minimal ``scalable.yaml`` manifest.
* Validate, plan, and execute a local workflow end-to-end.
* Inspect the telemetry output of a successful run.

This tutorial establishes the foundation for every subsequent tutorial in the
series. If you are new to Scalable, start here.

Prerequisites
-------------

* Python 3.11 or later (3.12 and 3.13 are also supported).
* A working ``pip`` (or equivalent package manager such as ``uv``).
* Familiarity with the command line.
* Basic Python fluency (functions, imports, virtual environments).

No HPC cluster, Docker installation, or cloud credentials are required for this
tutorial — we run everything locally.

Step 1: Install Scalable
------------------------

Create a fresh virtual environment and install Scalable from PyPI:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install scalable

Verify the installation:

.. code-block:: bash

   scalable --help

Expected output (abbreviated):

.. code-block:: text

   usage: scalable [-h] {validate,plan,run,report,advise,...} ...

   Scalable CLI — orchestrate distributed workflows.

   positional arguments:
     {validate,plan,run,report,advise,...}

**Why this matters:** The ``scalable`` CLI entry point is the primary interface
for validating manifests, planning executions, and generating reports. You can
also drive everything from Python — the CLI wraps the same public API.

.. note::

   If your shell cannot find the ``scalable`` command after installation, ensure
   that the scripts directory for your virtual environment is on ``PATH``.

Step 2: Create a Project Directory
-----------------------------------

Scalable workflows live in a dedicated project directory. The minimal layout
looks like this:

.. code-block:: text

   my-project/
   ├── scalable.yaml       # Manifest (single source of truth)
   └── workflow.py          # Your Python workflow script

Create it:

.. code-block:: bash

   mkdir my-project && cd my-project

Step 3: Write a Minimal Manifest
---------------------------------

The manifest (``scalable.yaml``) is a declarative document describing your
project, execution targets, compute components, and task bindings. Create the
file:

.. code-block:: yaml

   # scalable.yaml
   version: 1
   project:
     name: hello-scalable

   targets:
     local:
       provider: local
       max_workers: 2
       threads_per_worker: 1
       processes: false
       containers: none

   components:
     analysis:
       cpus: 1
       memory: 1G

   tasks:
     run_analysis:
       component: analysis

Let's unpack this:

``version``
  Schema version. Currently ``1`` is the only supported version.

``project.name``
  A human-readable project identifier. It is embedded in telemetry run IDs
  and artifact paths.

``targets``
  Named execution environments. Here we define a single target called
  ``local`` using the built-in :class:`~scalable.providers.local.LocalProvider`.
  The provider spawns a Dask ``LocalCluster`` under the hood with the specified
  worker configuration.

``components``
  Resource profiles for your workloads. Each component declares CPU and memory
  requirements. Components map to Dask worker resource annotations.

``tasks``
  Named work units that bind to a component. Tasks are the scheduling atoms —
  when you ``submit`` a function you associate it with a task definition.

**Trade-off note:** Setting ``processes: false`` runs Dask workers as threads
within a single process. This is fast to start and avoids serialization overhead
but provides no memory isolation between tasks. For CPU-bound workloads or tasks
that hold the GIL, set ``processes: true``.

Step 4: Validate the Manifest
------------------------------

Before running anything, validate the manifest for structural and semantic
errors:

.. code-block:: bash

   scalable validate ./scalable.yaml

Expected output:

.. code-block:: text

   ✓ Manifest is valid (0 errors, 0 warnings)

If you introduce a typo — say ``providr: local`` — validation will report:

.. code-block:: text

   ERROR targets.local: unknown provider 'providr'

The validator checks:

* Required top-level keys (``version``, ``project``).
* Component key spelling (``cpus``, ``memory``, ``image``, etc.).
* Task-component references resolve.
* Provider-specific option constraints (e.g., ``max_workers`` must be a positive
  integer for the local provider).

Step 5: Plan the Execution
---------------------------

Planning produces a dry-run execution plan without allocating real resources:

.. code-block:: bash

   scalable plan ./scalable.yaml --target local --dry-run --output plan.json

.. code-block:: text

   Plan created for target 'local' (provider: local)
   Workers: 2 × analysis (1 cpu, 1G memory)
   Manifest lock: sha256:a3b8f1...

Inspect the generated ``plan.json``:

.. code-block:: json

   {
     "target_name": "local",
     "provider": "local",
     "manifest_lock": "sha256:a3b8f1...",
     "scale_plan": {
       "analysis": {
         "count": 2,
         "resources": {"cpus": 1, "memory": "1G"}
       }
     }
   }

**Architectural note:** The ``manifest_lock`` is a content-addressable hash of
the expanded manifest. It guarantees reproducibility — if two plans share the
same lock fingerprint they were derived from byte-identical configurations
(modulo environment variable expansion).

Step 6: Write a Workflow Script
--------------------------------

Create ``workflow.py``:

.. code-block:: python

   """A minimal Scalable workflow."""

   from scalable import ScalableSession


   def analyze(scenario_id: int) -> dict:
       """Simulate an expensive computation."""
       import time
       time.sleep(1)
       return {"scenario": scenario_id, "result": scenario_id * 42}


   def main():
       # Initialize a session from the manifest
       session = ScalableSession.from_yaml("./scalable.yaml", target="local")

       # Plan (validates + computes resource allocation)
       plan = session.plan(dry_run=True)
       print(f"Manifest lock: {plan.manifest_lock}")

       # Start the cluster and get a client
       client = session.start(plan)

       # Submit tasks tagged to the 'analysis' component
       futures = []
       for i in range(5):
           fut = client.submit(analyze, i, tag="analysis")
           futures.append(fut)

       # Gather results
       results = client.gather(futures)
       for r in results:
           print(r)

       # Tear down
       session.close()


   if __name__ == "__main__":
       main()

Step 7: Run the Workflow
-------------------------

Execute the workflow using the CLI:

.. code-block:: bash

   scalable run ./scalable.yaml --target local --workflow workflow.py

Or run it directly with Python:

.. code-block:: bash

   python workflow.py

Expected output:

.. code-block:: text

   Manifest lock: sha256:a3b8f1...
   {'scenario': 0, 'result': 0}
   {'scenario': 1, 'result': 42}
   {'scenario': 2, 'result': 84}
   {'scenario': 3, 'result': 126}
   {'scenario': 4, 'result': 168}

**What happened under the hood:**

1. ``ScalableSession.from_yaml`` parsed the manifest, resolved environment
   variables, and built a :class:`~scalable.providers.base.DeploymentSpec`.
2. ``session.plan()`` validated the spec and computed a
   :class:`~scalable.planning.dryrun.DryRunPlan` including worker counts and
   resource annotations.
3. ``session.start()`` instantiated a
   :class:`~scalable.providers.local.LocalProvider`, which created a Dask
   ``LocalCluster`` with 2 workers each annotated with 1 CPU / 1 GB.
4. Each ``client.submit(..., tag="analysis")`` routed the function to workers
   matching the ``analysis`` component's resource profile.
5. ``session.close()`` shut down workers and finalized telemetry.

Step 8: Inspect Telemetry
--------------------------

Every manifest-driven run records structured telemetry. Check what was
persisted:

.. code-block:: bash

   scalable report --latest

Expected output:

.. code-block:: text

   Run: run-20260520T035200Z-hello-scalable-a1b2c3d4
   Status: completed
   Target: local (provider: local)
   Duration: 6.2s
   Tasks: 5 submitted, 5 succeeded, 0 failed

The telemetry lives under ``.scalable/runs/<run-id>/``:

.. code-block:: text

   .scalable/runs/run-20260520T035200Z-hello-scalable-a1b2c3d4/
   ├── run.json          # Run metadata
   ├── tasks.jsonl       # Per-task lifecycle events
   ├── resources.jsonl   # Resource utilization snapshots
   └── workers.jsonl     # Worker lifecycle events

These structured records power the resource advising and ML optimization
features covered in later tutorials.

Step 9: Environment Variables
------------------------------

Scalable is configured through environment variables for deployment flexibility.
The most relevant ones for getting started:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``SCALABLE_MANIFEST``
     - ``./scalable.yaml``
     - Default manifest path (avoids passing ``--manifest`` every time)
   * - ``SCALABLE_TARGET``
     - *(unset)*
     - Default target override
   * - ``SCALABLE_CACHE_DIR``
     - ``./cache``
     - Disk cache directory for ``@cacheable`` functions
   * - ``SCALABLE_TELEMETRY``
     - ``1``
     - Set to ``0`` to disable telemetry recording
   * - ``SCALABLE_LOG_LEVEL``
     - *(unset)*
     - Set to ``DEBUG`` for verbose library logging

Example — run with debug logging and a custom cache directory:

.. code-block:: bash

   export SCALABLE_LOG_LEVEL=DEBUG
   export SCALABLE_CACHE_DIR=/tmp/scalable-cache
   python workflow.py

Troubleshooting
---------------

**"scalable: command not found"**
  Ensure your virtual environment is activated and the scripts directory is on
  ``PATH``. On some systems you may need ``python -m scalable.cli.main`` as a
  fallback.

**"ModuleNotFoundError: No module named 'dask'"**
  Scalable's core dependencies (``dask``, ``distributed``) should be installed
  automatically. If missing, run ``pip install scalable`` again in your
  environment.

**Manifest validation reports "unknown provider"**
  Double-check the ``provider:`` value matches a built-in name (``local``,
  ``slurm``) or that you have installed the relevant extra (``scalable[cloud]``,
  ``scalable[kubernetes]``).

**Tasks complete but results are None**
  Ensure your function returns a value and that all data passed as arguments is
  serializable by ``dill`` (Scalable's default serializer). Lambda functions and
  module-level functions are fine; nested closures over non-picklable objects
  will fail silently.

Next Steps
----------

Now that you have a working local workflow:

* :ref:`tutorial_manifest_system` — Deep-dive into the manifest schema, environment
  variable expansion, and multi-target configurations.
* :ref:`tutorial_caching` — Add the ``@cacheable`` decorator to skip redundant
  computation across retries.
* :ref:`tutorial_telemetry` — Understand the telemetry data model and generate
  custom reports.
