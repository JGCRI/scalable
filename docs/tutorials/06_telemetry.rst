.. _tutorial_telemetry:

========================================================
Tutorial 6: Monitoring and Observability with Telemetry
========================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Understand Scalable's telemetry data model and event types.
* Read and analyze JSONL telemetry files programmatically.
* Generate reports from the CLI and Python API.
* Build custom dashboards from telemetry data.
* Use telemetry history to inform resource recommendations.
* Configure telemetry persistence and export (Parquet, remote storage).

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started`.
* At least one completed Scalable run (to have telemetry data).
* ``pandas`` installed (part of Scalable's core dependencies).

Scenario
--------

Your team runs the climate pipeline multiple times per week. You need to
track performance trends, identify slow tasks, monitor resource utilization,
and justify cloud spending to stakeholders. Scalable's built-in telemetry
provides all this data without external observability infrastructure.

Step 1: Telemetry Architecture
-------------------------------

Every manifest-driven run (via ``ScalableSession`` or ``scalable run``)
automatically records structured events to disk:

.. code-block:: text

   .scalable/runs/
   └── run-20260520T035200Z-climate-pipeline-a1b2c3d4/
       ├── run.json           # Run metadata (start time, target, manifest lock)
       ├── manifest.yaml      # Snapshot of the manifest used
       ├── plan.json          # Execution plan snapshot
       ├── tasks.jsonl        # Task lifecycle events
       ├── resources.jsonl    # Resource utilization snapshots
       ├── workers.jsonl      # Worker lifecycle events
       ├── cache.jsonl        # Cache hit/miss events
       ├── failures.jsonl     # Error/failure records
       ├── artifacts.jsonl    # Artifact store operations
       └── cost.jsonl         # Cost tracking events

Each ``.jsonl`` file contains one JSON object per line — a format optimized
for append-only writes and streaming reads.

**Design rationale:** JSONL was chosen over SQLite or a time-series database
because it requires no external dependencies, survives process crashes (each
line is independently valid), and can be trivially loaded into pandas, jq, or
any JSON-capable tool.

Step 2: Run Metadata
---------------------

The ``run.json`` file contains the run's identity and configuration:

.. code-block:: json

   {
     "run_id": "run-20260520T035200Z-climate-pipeline-a1b2c3d4",
     "project_name": "climate-pipeline",
     "target_name": "local",
     "provider_name": "local",
     "manifest_lock": "sha256:a3b8f1...",
     "started_at": "2026-05-20T03:52:00Z",
     "status": "completed",
     "ended_at": "2026-05-20T03:58:30Z"
   }

Key fields:

* ``manifest_lock`` — content hash proving which exact configuration produced
  this run. Two runs with identical locks are reproducible.
* ``status`` — one of ``running``, ``completed``, ``failed``, ``cancelled``.

Step 3: Task Events
--------------------

``tasks.jsonl`` records the full lifecycle of every submitted task:

.. code-block:: json

   {"task_id": "run_gcam-0", "task_name": "run_gcam", "state": "submitted", "timestamp": "2026-05-20T03:52:01Z", "tag": "gcam"}
   {"task_id": "run_gcam-0", "task_name": "run_gcam", "state": "running", "timestamp": "2026-05-20T03:52:02Z", "worker_id": "worker-gcam-0"}
   {"task_id": "run_gcam-0", "task_name": "run_gcam", "state": "succeeded", "timestamp": "2026-05-20T03:55:30Z", "duration_s": 208.5}

States: ``submitted`` → ``running`` → ``succeeded`` | ``failed`` | ``cancelled``

Analyzing task durations:

.. code-block:: python

   import json
   import pandas as pd
   from pathlib import Path

   run_dir = Path(".scalable/runs/run-20260520T035200Z-climate-pipeline-a1b2c3d4")

   tasks = []
   with open(run_dir / "tasks.jsonl") as f:
       for line in f:
           tasks.append(json.loads(line))

   df = pd.DataFrame(tasks)
   completed = df[df["state"] == "succeeded"]

   print(f"Total tasks: {len(completed)}")
   print(f"Mean duration: {completed['duration_s'].mean():.1f}s")
   print(f"Max duration: {completed['duration_s'].max():.1f}s")
   print(f"P95 duration: {completed['duration_s'].quantile(0.95):.1f}s")

Expected output:

.. code-block:: text

   Total tasks: 50
   Mean duration: 185.3s
   Max duration: 312.7s
   P95 duration: 280.1s

Step 4: Resource Utilization Events
-------------------------------------

``resources.jsonl`` tracks CPU and memory usage per task and per worker:

.. code-block:: json

   {"entity_type": "task", "entity_id": "run_gcam-0", "cpu_percent": 78.5, "memory_mb": 14200, "timestamp": "2026-05-20T03:53:00Z"}
   {"entity_type": "worker", "entity_id": "worker-gcam-0", "cpu_percent": 82.1, "memory_mb": 15800, "timestamp": "2026-05-20T03:53:00Z"}

Build a utilization timeline:

.. code-block:: python

   resources = []
   with open(run_dir / "resources.jsonl") as f:
       for line in f:
           resources.append(json.loads(line))

   res_df = pd.DataFrame(resources)
   res_df["timestamp"] = pd.to_datetime(res_df["timestamp"])

   # Average CPU utilization over time
   worker_resources = res_df[res_df["entity_type"] == "worker"]
   timeline = worker_resources.groupby(
       pd.Grouper(key="timestamp", freq="30s")
   ).agg({"cpu_percent": "mean", "memory_mb": "mean"})

   print(timeline.head(10))

This data helps identify:

* **Under-provisioned workers** — consistently >90% CPU means you need more
  workers or larger instance types.
* **Over-provisioned workers** — consistently <30% CPU means you're paying
  for unused capacity.
* **Memory pressure** — memory approaching the limit suggests increasing
  the component's memory allocation.

Step 5: Worker Lifecycle Events
--------------------------------

``workers.jsonl`` records when workers start, become idle, and terminate:

.. code-block:: json

   {"worker_id": "worker-gcam-0", "event": "started", "tag": "gcam", "timestamp": "2026-05-20T03:52:00Z"}
   {"worker_id": "worker-gcam-0", "event": "task_assigned", "task_id": "run_gcam-0", "timestamp": "2026-05-20T03:52:01Z"}
   {"worker_id": "worker-gcam-0", "event": "idle", "timestamp": "2026-05-20T03:55:30Z"}
   {"worker_id": "worker-gcam-0", "event": "removed", "timestamp": "2026-05-20T03:58:00Z", "reason": "scale_down"}

This lets you calculate:

* **Worker utilization** — fraction of time each worker spent executing vs idle.
* **Scale efficiency** — whether adaptive scaling decisions were timely.
* **Cold-start overhead** — time between ``started`` and first ``task_assigned``.

Step 6: CLI Reports
--------------------

The quickest way to review a run:

.. code-block:: bash

   # Latest run summary
   scalable report --latest

.. code-block:: text

   ═══════════════════════════════════════════════════════════
   Run Report: run-20260520T035200Z-climate-pipeline-a1b2c3d4
   ═══════════════════════════════════════════════════════════
   Status: completed
   Target: local (provider: local)
   Duration: 6m 30s
   Manifest lock: sha256:a3b8f1...

   Tasks:
     Submitted: 50
     Succeeded: 50
     Failed: 0
     Cache hits: 12

   Workers:
     gcam: 4 started, 0 failed
     postprocess: 2 started, 0 failed

   Resource Usage (mean):
     CPU: 72.4%
     Memory: 11.2 GiB / 16.0 GiB (70%)

Export as JSON for downstream processing:

.. code-block:: bash

   scalable report --latest --format json --output report.json

.. code-block:: json

   {
     "run_id": "run-20260520T035200Z-climate-pipeline-a1b2c3d4",
     "status": "completed",
     "duration_seconds": 390,
     "tasks": {"submitted": 50, "succeeded": 50, "failed": 0},
     "cache": {"hits": 12, "misses": 38},
     "cost_estimate": {"total": 0.0, "compute": 0.0}
   }

Step 7: Programmatic Report Access
------------------------------------

Use the telemetry collectors for rich programmatic analysis:

.. code-block:: python

   from scalable.telemetry.collectors import summarize_run, iter_run_dirs
   from pathlib import Path

   # Get the latest run directory
   runs_dir = Path(".scalable/runs")
   run_dirs = sorted(iter_run_dirs(runs_dir))
   latest = run_dirs[-1]

   # Generate summary
   summary = summarize_run(latest)
   print(f"Run: {summary['run_id']}")
   print(f"Duration: {summary['duration_seconds']:.0f}s")
   print(f"Tasks succeeded: {summary['tasks_succeeded']}")
   print(f"Tasks failed: {summary['tasks_failed']}")

Step 8: Historical Trend Analysis
-----------------------------------

Compare performance across multiple runs:

.. code-block:: python

   from scalable.telemetry.collectors import iter_run_dirs, read_jsonl
   from pathlib import Path
   import pandas as pd

   runs_dir = Path(".scalable/runs")
   run_summaries = []

   for run_dir in iter_run_dirs(runs_dir):
       run_json = run_dir / "run.json"
       if not run_json.exists():
           continue

       meta = pd.read_json(run_json, typ="series")
       tasks = read_jsonl(run_dir / "tasks.jsonl")
       succeeded = [t for t in tasks if t.get("state") == "succeeded"]

       run_summaries.append({
           "run_id": meta.get("run_id"),
           "started_at": meta.get("started_at"),
           "target": meta.get("target_name"),
           "total_tasks": len(succeeded),
           "mean_duration": (
               sum(t.get("duration_s", 0) for t in succeeded) / len(succeeded)
               if succeeded else 0
           ),
       })

   history = pd.DataFrame(run_summaries)
   history["started_at"] = pd.to_datetime(history["started_at"])
   history = history.sort_values("started_at")

   print("Performance trend (last 10 runs):")
   print(history[["started_at", "target", "total_tasks", "mean_duration"]].tail(10))

Expected output:

.. code-block:: text

   Performance trend (last 10 runs):
     started_at           target  total_tasks  mean_duration
     2026-05-10 14:00:00  local   50           210.5
     2026-05-12 09:30:00  local   50           205.2
     2026-05-14 16:00:00  hpc     50           45.8
     2026-05-15 10:00:00  hpc     50           44.1
     2026-05-18 08:00:00  aws     100          38.2
     ...

Step 9: Parquet Export for Analytics
-------------------------------------

For large-scale analysis or integration with data warehouses, enable Parquet
snapshots:

.. code-block:: bash

   export SCALABLE_TELEMETRY_PARQUET=1
   python workflow.py

This writes columnar Parquet files alongside the JSONL:

.. code-block:: text

   .scalable/runs/run-.../
   ├── tasks.jsonl
   ├── tasks.parquet      # ← Parquet snapshot
   ├── resources.jsonl
   ├── resources.parquet  # ← Parquet snapshot
   └── ...

Load directly into pandas or any Parquet-compatible tool:

.. code-block:: python

   import pandas as pd
   df = pd.read_parquet(".scalable/runs/run-.../tasks.parquet")
   print(df.describe())

Step 10: Telemetry Configuration
----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Effect
   * - ``SCALABLE_TELEMETRY``
     - ``1``
     - Set to ``0`` to disable all telemetry recording.
   * - ``SCALABLE_TELEMETRY_PARQUET``
     - ``0``
     - Set to ``1`` to emit Parquet snapshots at run close.
   * - ``SCALABLE_RUNS_DIR``
     - ``.scalable/runs``
     - Base directory for run telemetry.

**When to disable telemetry:** Unit tests, benchmarking micro-operations, or
environments where disk I/O is constrained. For production runs, always leave
telemetry enabled — the overhead is negligible (<1% of total runtime) and the
data is invaluable for debugging.

Troubleshooting
---------------

**No telemetry data after a run**
  Ensure you are using the Session API (``ScalableSession``) or the
  ``scalable run`` CLI. The legacy imperative API (``SlurmCluster`` directly)
  does not automatically record telemetry unless you manually configure a
  ``TelemetryStore``.

**"FileNotFoundError: .scalable/runs"**
  The runs directory is created automatically on first run. If you're querying
  before any run has completed, the directory won't exist yet.

**Parquet files not generated**
  Set ``SCALABLE_TELEMETRY_PARQUET=1`` *before* starting the session. The
  setting is read at session creation time.

**Report shows "0 tasks" but workflow completed**
  The telemetry store must be active when tasks are submitted. If you create
  a ``ScalableClient`` outside a session (e.g., connecting to an existing
  cluster), telemetry won't be recorded unless explicitly configured.

Next Steps
----------

* :ref:`tutorial_error_handling` — Use failure events to diagnose and recover
  from errors.
* :ref:`tutorial_ml_advanced` — Feed telemetry history into the ML advisor for
  predictive resource recommendations.
* :ref:`tutorial_cloud_integration` — Monitor cloud costs through telemetry
  cost events.
