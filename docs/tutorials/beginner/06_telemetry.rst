.. _beginner_telemetry:

======================================================
Beginner Tutorial 6: Understanding What Happened
======================================================

The Big Picture
----------------

You've run a workflow. It completed. But did it perform well? Were some tasks
slower than expected? Did workers sit idle? How much did it cost?

**Telemetry** is the automated recording of everything that happens during a
run — every task start, every completion, every failure, every resource
measurement. It's like a flight recorder for your workflow, letting you
understand what happened after the fact and make informed decisions about
optimization.

This tutorial explains observability from first principles: what telemetry is,
why structured logging matters, how to read event data, and how to generate
useful reports.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand what telemetry and observability mean.
* Know the difference between metrics, logs, and traces.
* Read JSONL telemetry files and understand their structure.
* Generate reports from the CLI and Python API.
* Use telemetry data to identify performance bottlenecks.
* Understand how historical telemetry informs future decisions.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started`.
* At least one completed Scalable run (to have telemetry data).
* ``pandas`` installed (included with Scalable's core dependencies).


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: What is Telemetry?
   :class: tip

   **Telemetry** is the automated collection and transmission of data from
   remote systems. The word comes from Greek: *tele* (remote) + *metron*
   (measurement).

   In software, telemetry means recording what your program did:

   * When did tasks start and finish?
   * How much memory did workers use?
   * Which tasks failed and why?
   * How many cache hits occurred?

   **Analogy:** A car's dashboard shows speed, fuel level, and engine
   temperature in real-time. Telemetry is like a dashcam that records
   everything so you can review it later.

.. admonition:: 💡 Key Concept: Observability
   :class: tip

   **Observability** is the ability to understand a system's internal state
   by examining its outputs. A system is "observable" if you can answer
   "why is this slow?" or "why did this fail?" from the data it produces.

   The three pillars of observability:

   **1. Metrics** — numerical measurements over time
     * "CPU utilization was 87% at 14:03:22"
     * "Average task duration was 4.2 seconds"
     * Good for dashboards and alerting

   **2. Logs** — discrete events with context
     * "Task run_simulation(42) started at 14:03:22 on worker-3"
     * "Worker-2 failed with OutOfMemoryError at 14:05:11"
     * Good for debugging specific incidents

   **3. Traces** — the journey of a request through the system
     * "Task 42: submitted → queued 0.3s → scheduled to worker-3 → executed 4.1s → completed"
     * Good for understanding latency and bottlenecks

   Scalable's telemetry provides all three through structured event files.

.. admonition:: 💡 Key Concept: Structured Logging
   :class: tip

   **Structured logging** means recording events as machine-parseable data
   (typically JSON) rather than free-form text.

   **Unstructured log** (hard to parse programmatically):

   .. code-block:: text

      2026-05-20 14:03:22 INFO Task run_simulation(42) completed in 4.2s on worker-3

   **Structured log** (easy to parse, filter, aggregate):

   .. code-block:: json

      {
        "timestamp": "2026-05-20T14:03:22Z",
        "event": "task_completed",
        "task": "run_simulation",
        "args": {"scenario_id": 42},
        "duration_s": 4.2,
        "worker": "worker-3"
      }

   Structured logs can be:

   * Filtered: "show me only failures"
   * Aggregated: "average duration per task type"
   * Queried: "which worker handled the most tasks?"
   * Visualized: plotted on timelines and dashboards

.. admonition:: 💡 Key Concept: JSONL (JSON Lines)
   :class: tip

   **JSONL** (JSON Lines) is a format where each line is a complete JSON
   object. It's perfect for event streams because:

   * **Appendable** — just add a new line (no need to rewrite the file)
   * **Streamable** — process one line at a time (no need to load entire file)
   * **Parseable** — each line is valid JSON

   .. code-block:: text

      {"event": "task_started", "task": "sim", "time": "14:03:22"}
      {"event": "task_completed", "task": "sim", "time": "14:03:26", "duration": 4.2}
      {"event": "task_started", "task": "sim", "time": "14:03:22"}

   Compare to a single large JSON array (which requires loading the entire
   file to append or read):

   .. code-block:: json

      [
        {"event": "task_started", ...},
        {"event": "task_completed", ...}
      ]

.. admonition:: 💡 Key Concept: Events
   :class: tip

   An **event** is a discrete occurrence at a specific point in time. Events
   have:

   * **Timestamp** — when it happened
   * **Type** — what kind of event (task_started, worker_added, etc.)
   * **Payload** — additional context (task name, duration, error message)

   Events form the foundation of Scalable's telemetry system. Everything
   that happens is recorded as an event.


Step 1: Telemetry File Structure
----------------------------------

After every run, Scalable creates a run directory with structured telemetry:

.. code-block:: text

   .scalable/runs/
   └── run-20260520T035200Z-energy-forecast-a1b2c3d4/
       ├── run.json           # Run metadata (start time, target, manifest)
       ├── manifest.yaml      # Snapshot of the manifest used
       ├── plan.json          # Execution plan snapshot
       ├── tasks.jsonl        # Task lifecycle events
       ├── resources.jsonl    # Resource utilization snapshots
       ├── workers.jsonl      # Worker lifecycle events
       ├── cache.jsonl        # Cache hit/miss events
       └── failures.jsonl     # Error details (if any)

Each file serves a purpose:

``run.json``
   High-level metadata: when the run started, which target was used, the
   manifest hash for reproducibility verification.

``tasks.jsonl``
   The most important file — every task submission, start, completion, and
   failure is recorded here.

``resources.jsonl``
   Periodic snapshots of CPU and memory usage per worker.

``workers.jsonl``
   Worker lifecycle: when workers started, stopped, or crashed.

``cache.jsonl``
   Every cache lookup: hit (saved time) or miss (had to compute).

``failures.jsonl``
   Detailed error information including tracebacks.


Step 2: Reading Telemetry Data
--------------------------------

You can read telemetry files directly:

.. code-block:: python

   import json

   # Read task events line by line
   with open(".scalable/runs/run-.../tasks.jsonl") as f:
       for line in f:
           event = json.loads(line)
           print(f"{event['timestamp']} | {event['event']} | {event.get('task', '')}")

Output:

.. code-block:: text

   2026-05-20T14:03:22Z | task_submitted | run_simulation
   2026-05-20T14:03:22Z | task_started   | run_simulation
   2026-05-20T14:03:26Z | task_completed | run_simulation
   2026-05-20T14:03:22Z | task_submitted | run_simulation
   ...

Or use pandas for analysis:

.. code-block:: python

   import pandas as pd

   # Load all task events into a DataFrame
   tasks = pd.read_json(".scalable/runs/run-.../tasks.jsonl", lines=True)

   # Filter to completions and compute statistics
   completed = tasks[tasks["event"] == "task_completed"]
   print(f"Total tasks: {len(completed)}")
   print(f"Average duration: {completed['duration_s'].mean():.2f}s")
   print(f"Slowest task: {completed['duration_s'].max():.2f}s")
   print(f"Fastest task: {completed['duration_s'].min():.2f}s")

.. admonition:: Under the Hood
   :class: hint

   Scalable records telemetry **automatically** — you don't need to add
   logging to your functions. The ``ScalableSession`` instruments:

   1. Every ``submit()`` → ``task_submitted`` event
   2. When a worker picks up a task → ``task_started``
   3. When a task completes → ``task_completed`` (with duration)
   4. When a task fails → ``task_failed`` (with error details)
   5. Periodic resource snapshots → ``resource_sample``


Step 3: Generating Reports
-----------------------------

The CLI provides quick summaries:

.. code-block:: bash

   # Report on the most recent run
   scalable report --last

.. code-block:: text

   ═══════════════════════════════════════════════
   Run Report: run-20260520T035200Z-energy-forecast-a1b2c3d4
   ═══════════════════════════════════════════════
   Target: local (provider: local)
   Duration: 45.2s
   Status: completed

   Tasks:
     Submitted: 100
     Completed: 100
     Failed: 0
     Avg duration: 4.2s
     Max duration: 8.7s (run_simulation, scenario_id=47)

   Workers:
     Peak: 4
     Avg utilization: 87%

   Cache:
     Lookups: 100
     Hits: 0 (0%) — first run, no prior cache
     Misses: 100

   Estimated Cost: $0.00 (local provider)

You can also compare runs:

.. code-block:: bash

   scalable report --compare run-abc123 run-def456

This shows performance differences between two runs — useful for verifying
that optimization changes actually helped.


Step 4: Using Telemetry for Optimization
------------------------------------------

Telemetry answers critical questions:

**"Which tasks are slowest?"**

.. code-block:: python

   # Find the 5 slowest tasks
   slowest = completed.nlargest(5, "duration_s")[["task", "duration_s"]]
   print(slowest)

**"Are workers sitting idle?"**

.. code-block:: python

   resources = pd.read_json(".scalable/runs/run-.../resources.jsonl", lines=True)
   print(f"Average CPU utilization: {resources['cpu_percent'].mean():.1f}%")
   # Below 70% suggests you have too many workers for the workload

**"Is caching helping?"**

.. code-block:: python

   cache = pd.read_json(".scalable/runs/run-.../cache.jsonl", lines=True)
   hit_rate = cache[cache["result"] == "hit"].shape[0] / len(cache) * 100
   print(f"Cache hit rate: {hit_rate:.1f}%")

.. admonition:: 💡 Key Concept: Utilization and Efficiency
   :class: tip

   **Utilization** measures how much of your allocated resources are actually
   being used:

   * **100% utilization** = every worker is busy all the time (ideal)
   * **50% utilization** = workers are idle half the time (wasteful)
   * **Low utilization** usually means: too many workers, or tasks are too
     quick (overhead dominates)

   **Efficiency** considers the ratio of useful work to total time:

   .. code-block:: text

      Efficiency = (total task computation time) / (total worker uptime × worker count)

   If you have 4 workers running for 60 seconds each (240 worker-seconds)
   but only 180 seconds of actual task computation, efficiency is 75%.


Step 5: Historical Analysis
------------------------------

.. admonition:: 💡 Key Concept: Trend Analysis
   :class: tip

   **Trend analysis** looks at how metrics change over time:

   * Are runs getting slower? (regression detection)
   * Are resource needs growing? (capacity planning)
   * Is cache hit rate improving? (optimization validation)

   Scalable stores all runs in ``.scalable/runs/`` so you can analyze trends
   across your project's history.

.. code-block:: python

   import os
   import json

   # Load metadata from all runs
   runs_dir = ".scalable/runs"
   runs = []
   for run_name in sorted(os.listdir(runs_dir)):
       run_meta = os.path.join(runs_dir, run_name, "run.json")
       if os.path.exists(run_meta):
           with open(run_meta) as f:
               runs.append(json.load(f))

   # Plot duration over time (if matplotlib available)
   for r in runs:
       print(f"{r['start_time']}: {r['duration_s']:.1f}s ({r['tasks_completed']} tasks)")


Step 6: Telemetry-Driven Resource Recommendations
----------------------------------------------------

Scalable's resource advisor uses telemetry history to recommend better
resource allocations:

.. code-block:: bash

   scalable advise --task run_simulation

.. code-block:: text

   Resource Recommendation for 'run_simulation':
     Current: 4 CPUs, 16G memory
     Recommended: 2 CPUs, 8G memory
     Reason: 95th percentile usage is 1.8 CPUs and 6.2G memory
     Potential savings: 50% compute cost reduction

.. admonition:: 🤔 Think About It
   :class: note

   Without telemetry, resource allocation is guesswork ("let's try 32G and
   see"). With telemetry, it's data-driven ("historical usage shows 6G is
   the 95th percentile, so 8G gives comfortable headroom").

   This is why Scalable records telemetry by default — even if you don't
   look at it now, it enables smarter decisions later.


Common Questions
-----------------

**Q: Does telemetry slow down my workflow?**

Negligibly. Writing a JSON line to a file takes microseconds. Compared to
tasks that take seconds or minutes, the overhead is unmeasurable.

**Q: How much disk space does telemetry use?**

Typically 1–10 MB per run (for hundreds of tasks). You can periodically
archive or delete old runs. For long-term storage, telemetry can be exported
to Parquet format (compressed columnar storage).

**Q: Can I disable telemetry?**

Yes, but it's not recommended. Telemetry is what enables caching verification,
resource recommendations, and debugging. Without it, you're flying blind.

**Q: What's the difference between telemetry and logging?**

* **Logging** = messages for developers to debug issues (often unstructured,
  verbose, human-oriented)
* **Telemetry** = structured data for analysis and automation
  (machine-parseable, consistent schema)

Scalable provides both: Python logging for debugging, telemetry for analysis.

**Q: Can I send telemetry to external systems?**

Yes — telemetry files are standard JSONL that can be ingested by any log
aggregation system (Elasticsearch, Splunk, CloudWatch). Export to Parquet for
data warehouse analytics.


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Telemetry
     - Automated collection of system behavior data
   * - Observability
     - Ability to understand internal state from outputs
   * - Metrics
     - Numerical measurements over time (CPU %, duration)
   * - Logs
     - Discrete events with context (structured or unstructured)
   * - Traces
     - Journey of a request through the system
   * - Structured Logging
     - Recording events as machine-parseable data (JSON)
   * - JSONL
     - JSON Lines — one JSON object per line
   * - Event
     - Discrete occurrence with timestamp, type, and payload
   * - Utilization
     - Percentage of allocated resources actually being used
   * - Trend Analysis
     - Examining how metrics change over time
   * - Run Directory
     - Folder containing all telemetry for a single execution


Next Steps
-----------

You now understand telemetry and observability, and can use Scalable's data
to optimize your workflows.

* **Next beginner tutorial:** :ref:`beginner_error_handling` — what happens
  when things go wrong
* **Standard tutorial:** :ref:`tutorial_telemetry` — custom dashboards,
  Parquet export, and advanced analysis
* **Try it:** After running a workflow, explore the ``.scalable/runs/``
  directory. Open a ``tasks.jsonl`` file and look at the event structure.
  Can you find the slowest task?
