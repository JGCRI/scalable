.. _tutorial_error_handling:

======================================================
Tutorial 7: Error Handling and Resilience Patterns
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Understand how Scalable propagates and records errors across distributed
  workers.
* Implement retry strategies for transient failures.
* Use the telemetry failure log to diagnose root causes.
* Handle worker crashes, timeouts, and preemption gracefully.
* Build fault-tolerant workflows with partial-result recovery.
* Use the AI diagnostic assistant to analyze failures.

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started` and :ref:`tutorial_telemetry`.
* Scalable installed (``pip install scalable``).
* For AI diagnosis: ``pip install scalable[ai]``.

Scenario
--------

Your production pipeline runs 200 climate scenarios overnight. Some scenarios
fail due to transient issues (network timeouts pulling data, OOM on edge-case
inputs, worker preemption on shared HPC clusters). You need a workflow that
tolerates partial failures, recovers what it can, and provides clear
diagnostics for what went wrong.

Step 1: Understanding Error Propagation
-----------------------------------------

When a function submitted to Scalable raises an exception, the error is:

1. Captured by the Dask worker.
2. Serialized and transmitted back to the client.
3. Recorded in telemetry (``failures.jsonl``).
4. Re-raised when you call ``.result()`` or ``client.gather()``.

.. code-block:: python

   from scalable import ScalableSession


   def flaky_simulation(scenario_id: int) -> dict:
       """Simulates a function that sometimes fails."""
       if scenario_id % 7 == 0:
           raise RuntimeError(f"OOM: scenario {scenario_id} exceeded memory limit")
       return {"scenario": scenario_id, "result": scenario_id * 42}


   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   client = session.start()

   futures = [client.submit(flaky_simulation, i, tag="analysis") for i in range(20)]

   # This will raise on the first failed future:
   try:
       results = client.gather(futures)
   except RuntimeError as e:
       print(f"Workflow failed: {e}")

Step 2: Gathering with Error Tolerance
----------------------------------------

Instead of failing on the first error, collect results and errors separately:

.. code-block:: python

   from distributed import as_completed

   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   client = session.start()

   futures = [client.submit(flaky_simulation, i, tag="analysis") for i in range(20)]

   succeeded = []
   failed = []

   for future in as_completed(futures):
       try:
           result = future.result()
           succeeded.append(result)
       except Exception as e:
           failed.append({
               "error": str(e),
               "type": type(e).__name__,
               "key": future.key,
           })

   print(f"Succeeded: {len(succeeded)}, Failed: {len(failed)}")
   for f in failed:
       print(f"  [{f['type']}] {f['error']}")

   session.close()

Expected output:

.. code-block:: text

   Succeeded: 17, Failed: 3
     [RuntimeError] OOM: scenario 0 exceeded memory limit
     [RuntimeError] OOM: scenario 7 exceeded memory limit
     [RuntimeError] OOM: scenario 14 exceeded memory limit

**Pattern: Partial Success.** This is the recommended approach for batch
workflows. Gather all results, log failures, and decide whether to proceed
with partial data or abort.

Step 3: Implementing Retry Logic
---------------------------------

For transient failures (network issues, preempted workers), retries often
succeed. Implement exponential backoff:

.. code-block:: python

   import time
   from distributed import as_completed


   def submit_with_retry(client, func, *args, tag, max_retries=3, backoff=2.0):
       """Submit a function with exponential backoff retry."""
       last_error = None

       for attempt in range(max_retries + 1):
           future = client.submit(func, *args, tag=tag)
           try:
               return future.result(timeout=300)  # 5-minute timeout
           except Exception as e:
               last_error = e
               if attempt < max_retries:
                   wait = backoff ** attempt
                   print(f"  Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                   time.sleep(wait)
               else:
                   raise last_error


   # Usage
   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   client = session.start()

   results = []
   permanent_failures = []

   for scenario_id in range(20):
       try:
           result = submit_with_retry(
               client, flaky_simulation, scenario_id,
               tag="analysis", max_retries=3
           )
           results.append(result)
       except Exception as e:
           permanent_failures.append({"scenario": scenario_id, "error": str(e)})

   print(f"Completed: {len(results)}, Permanent failures: {len(permanent_failures)}")
   session.close()

**When to retry vs. fail fast:**

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Failure Type
     - Strategy
     - Rationale
   * - Network timeout
     - Retry (3x, exponential)
     - Transient; usually resolves
   * - OOM (out of memory)
     - Fail fast or retry with more resources
     - Persistent; same inputs will fail again
   * - Worker preemption
     - Retry (unlimited, with backoff)
     - External; will succeed when rescheduled
   * - Input validation error
     - Fail fast
     - Bug in data; retrying won't help
   * - Dependency import error
     - Fail fast
     - Container/environment issue

Step 4: Timeout Management
---------------------------

Long-running tasks need timeouts to prevent runaway processes:

.. code-block:: python

   from concurrent.futures import TimeoutError

   future = client.submit(expensive_simulation, params, tag="gcam")

   try:
       result = future.result(timeout=3600)  # 1-hour timeout
   except TimeoutError:
       print("Task exceeded 1-hour timeout")
       future.cancel()
       # Log and continue with remaining tasks

For Slurm-backed workers, walltime provides a hard ceiling:

.. code-block:: yaml

   targets:
     hpc:
       provider: slurm
       walltime: "04:00:00"   # Workers killed after 4 hours

If a worker hits its walltime, Slurm terminates the process. Dask detects the
lost worker and marks its tasks as failed with a ``KilledWorker`` exception.
Your error-handling code should treat this as a retryable failure.

Step 5: Telemetry Failure Records
----------------------------------

Every failure is recorded in ``failures.jsonl``:

.. code-block:: json

   {
     "failure_class": "RuntimeError",
     "message": "OOM: scenario 7 exceeded memory limit",
     "timestamp": "2026-05-20T04:15:30Z",
     "details": {
       "phase": "task_execution",
       "task_id": "run_gcam-7",
       "worker_id": "worker-gcam-2",
       "traceback": "Traceback (most recent call last):\n  ..."
     }
   }

Analyze failure patterns:

.. code-block:: python

   import json
   from pathlib import Path
   from collections import Counter

   run_dir = Path(".scalable/runs/run-20260520T.../")
   failures = []
   with open(run_dir / "failures.jsonl") as f:
       for line in f:
           failures.append(json.loads(line))

   # Group by failure class
   by_class = Counter(f["failure_class"] for f in failures)
   print("Failures by type:")
   for cls, count in by_class.most_common():
       print(f"  {cls}: {count}")

   # Find the most common error message pattern
   by_message = Counter(f["message"].split(":")[0] for f in failures)
   print("\nTop error patterns:")
   for msg, count in by_message.most_common(5):
       print(f"  {msg}: {count}")

Expected output:

.. code-block:: text

   Failures by type:
     RuntimeError: 8
     MemoryError: 3
     TimeoutError: 2

   Top error patterns:
     OOM: 8
     MemoryError: 3
     TimeoutError: 2

Step 6: AI-Assisted Diagnosis
-------------------------------

When failures are complex, the AI diagnostic assistant (``scalable[ai]``)
analyzes telemetry and provides human-readable explanations:

.. code-block:: bash

   scalable diagnose --latest --no-ai

.. code-block:: text

   Diagnosis for run-20260520T...-climate-pipeline-a1b2c3d4:

   ⚠ 13 failures detected across 3 categories:

   1. RuntimeError (OOM) — 8 occurrences
      Pattern: Scenarios with large input datasets (>2GB) exceed the 16G
      memory allocation for gcam workers.
      Suggestion: Increase component memory to 32G or chunk large inputs.

   2. MemoryError — 3 occurrences
      Pattern: Worker process exhausted system memory during pandas concat.
      Suggestion: Use chunked processing or increase max_workers to spread load.

   3. TimeoutError — 2 occurrences
      Pattern: Network calls to external data API timed out after 300s.
      Suggestion: Increase timeout or add retry logic for external calls.

Programmatic API:

.. code-block:: python

   from scalable.ai import diagnose_run

   result = diagnose_run(
       run_dir=".scalable/runs/run-20260520T.../",
       no_ai=True,  # Use heuristic analysis (no LLM required)
   )

   print(result.summary)
   for finding in result.findings:
       print(f"  [{finding.severity}] {finding.category}: {finding.suggestion}")

Step 7: Graceful Session Shutdown
----------------------------------

Proper shutdown ensures telemetry is finalized even when errors occur:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="local")

   try:
       client = session.start()

       futures = [client.submit(process, i, tag="analysis") for i in range(100)]

       results = []
       for future in as_completed(futures):
           try:
               results.append(future.result())
           except Exception as e:
               print(f"Task failed: {e}")

   except Exception as e:
       print(f"Fatal error: {e}")
   finally:
       # ALWAYS close the session — this finalizes telemetry
       session.close()

The ``session.close()`` method:

1. Shuts down the Dask client.
2. Records the final run status (``completed`` or ``failed``).
3. Writes summary statistics to ``run.json``.
4. Generates Parquet snapshots if enabled.
5. Resets the telemetry context.

**If you skip ``session.close()``:** Telemetry files remain valid (JSONL is
append-safe) but the run status stays ``running`` and summary stats won't be
computed.

Step 8: Fault-Tolerant Pipeline Pattern
-----------------------------------------

For production pipelines, combine all resilience patterns:

.. code-block:: python

   """Fault-tolerant pipeline with retry, partial success, and diagnostics."""

   from scalable import ScalableSession, cacheable
   from distributed import as_completed
   import time


   @cacheable(return_type=dict, scenario_id=int)
   def run_scenario(scenario_id: int) -> dict:
       """Cached computation — won't re-run on retry if previously succeeded."""
       # ... expensive computation ...
       return {"scenario": scenario_id, "result": scenario_id * 42}


   def run_pipeline():
       session = ScalableSession.from_yaml("./scalable.yaml", target="local")

       try:
           client = session.start()
           scenarios = list(range(200))

           # Phase 1: Submit all with retry
           succeeded = {}
           failed = {}
           retry_queue = [(s, 0) for s in scenarios]  # (scenario, attempt)

           while retry_queue:
               batch = retry_queue[:50]  # Process in batches of 50
               retry_queue = retry_queue[50:]

               futures = {
                   client.submit(run_scenario, s, tag="analysis"): (s, attempt)
                   for s, attempt in batch
               }

               for future in as_completed(futures):
                   scenario_id, attempt = futures[future]
                   try:
                       result = future.result(timeout=600)
                       succeeded[scenario_id] = result
                   except Exception as e:
                       if attempt < 3:
                           # Retry with backoff
                           time.sleep(2 ** attempt)
                           retry_queue.append((scenario_id, attempt + 1))
                       else:
                           failed[scenario_id] = str(e)

           # Phase 2: Report results
           print(f"Pipeline complete: {len(succeeded)} succeeded, {len(failed)} failed")

           if failed:
               print("Permanent failures:")
               for s, err in sorted(failed.items()):
                   print(f"  Scenario {s}: {err}")

           return succeeded

       finally:
           session.close()


   if __name__ == "__main__":
       results = run_pipeline()

Step 9: Worker Health Monitoring
---------------------------------

Detect and respond to unhealthy workers:

.. code-block:: python

   # Check worker status during long-running workflows
   info = client.scheduler_info()
   workers = info.get("workers", {})

   for addr, worker_info in workers.items():
       memory_used = worker_info.get("metrics", {}).get("memory", 0)
       memory_limit = worker_info.get("memory_limit", 1)
       utilization = memory_used / memory_limit

       if utilization > 0.9:
           print(f"WARNING: Worker {addr} at {utilization*100:.0f}% memory")
           # Consider scaling up or migrating tasks

Step 10: Post-Failure Recovery
-------------------------------

After a failed run, use caching and telemetry to resume efficiently:

.. code-block:: python

   """Resume a pipeline from where it left off."""
   import json
   from pathlib import Path

   # Find what succeeded in the previous run
   prev_run = Path(".scalable/runs/run-20260519T.../")
   prev_tasks = []
   with open(prev_run / "tasks.jsonl") as f:
       for line in f:
           prev_tasks.append(json.loads(line))

   completed_scenarios = {
       t["task_id"] for t in prev_tasks if t.get("state") == "succeeded"
   }

   # Only run what failed or wasn't attempted
   all_scenarios = set(range(200))
   remaining = all_scenarios - completed_scenarios
   print(f"Resuming: {len(remaining)} scenarios remaining (skipping {len(completed_scenarios)} cached)")

   # The @cacheable decorator handles this automatically — even without
   # explicit resume logic, cached scenarios will return instantly.
   # This pattern is useful when you want explicit control.

Troubleshooting
---------------

**"KilledWorker" exception but task should have succeeded**
  The Slurm job hit its walltime or was preempted. Increase ``walltime`` in
  the target or reduce per-task computation time by splitting into smaller
  chunks.

**Retry logic causes duplicate computation**
  If using ``@cacheable``, retried tasks automatically hit the cache (they
  won't recompute). Without caching, retries execute the function again. For
  idempotent functions this is safe; for functions with side effects, add
  deduplication logic.

**"Cannot serialize" errors on exception propagation**
  Some custom exception classes aren't serializable. Dask workers must
  serialize exceptions to send them back to the client. Keep exception
  classes simple (inherit from built-in exceptions, avoid unpicklable
  attributes).

**Session status shows "running" after crash**
  If the process crashes before ``session.close()`` runs, the run status stays
  ``running``. The telemetry data is still valid — inspect it manually or run
  ``scalable diagnose --run-id <id>`` to analyze.

Next Steps
----------

* :ref:`tutorial_kubernetes` — Handle pod evictions and node failures in
  Kubernetes deployments.
* :ref:`tutorial_caching` — Use caching to make retries free after partial
  completion.
* :ref:`tutorial_ml_advanced` — Let ML-driven advising predict and prevent
  resource-related failures.
