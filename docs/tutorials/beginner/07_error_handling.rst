.. _beginner_error_handling:

======================================================
Beginner Tutorial 7: When Things Go Wrong
======================================================

.. contents:: In This Tutorial
   :local:
   :depth: 2

The Big Picture
----------------

In distributed computing, failures aren't just possible — they're expected.
Networks drop connections. Machines run out of memory. Cloud instances get
preempted. HPC job time limits expire. The question isn't "will things fail?"
but "how do we handle failure gracefully?"

This tutorial explains distributed failure modes from first principles: why
errors in distributed systems are harder than local errors, how to make
workflows resilient, and how Scalable helps you diagnose and recover from
failures.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand why distributed errors are harder than local errors.
* Know the common failure modes in distributed computing.
* Implement retry strategies with exponential backoff.
* Understand idempotency and why it matters for retries.
* Handle partial success (some tasks succeed, others fail).
* Use telemetry to diagnose failures.
* Understand Scalable's fault tolerance mechanisms.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started` and :ref:`beginner_telemetry`.
* Scalable installed (``pip install scalable``).


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: Why Distributed Errors Are Harder
   :class: tip

   On your laptop, errors are straightforward:

   * Your function raises an exception → you see a traceback → you fix it

   In distributed systems, additional failure modes exist:

   * **Network failure** — the worker computed the result but the network
     dropped before delivering it (did it succeed or not?)
   * **Partial failure** — 3 of 4 workers succeed, 1 fails (what do you do
     with the partial results?)
   * **Silent failure** — a worker produces wrong results without raising
     an error (harder to detect)
   * **Cascading failure** — one failure triggers others (scheduler overload,
     resource exhaustion)
   * **Timing issues** — a task times out (was it too slow, or did the
     network delay the response?)

   The fundamental challenge: **you can't always tell the difference between
   "failed" and "slow"** in a distributed system.

.. admonition:: 💡 Key Concept: Fault Tolerance
   :class: tip

   **Fault tolerance** is a system's ability to continue operating correctly
   when components fail. It doesn't mean failures don't happen — it means
   the system handles them gracefully.

   **Levels of fault tolerance:**

   1. **Crash and burn** — any failure stops everything (fragile)
   2. **Detect and report** — failures are caught and reported clearly
   3. **Retry** — transient failures are automatically retried
   4. **Partial success** — successful results are preserved even if some
      tasks fail
   5. **Self-healing** — the system automatically recovers (restarts workers,
      reschedules tasks)

   Scalable provides levels 2–5 depending on configuration.

.. admonition:: 💡 Key Concept: Transient vs. Permanent Failures
   :class: tip

   **Transient failures** are temporary — retrying usually succeeds:

   * Network timeout (try again in a moment)
   * Rate limiting (wait and try again)
   * Resource contention (another process was hogging memory)
   * Cloud spot instance preemption (get another instance)

   **Permanent failures** won't be fixed by retrying:

   * Bug in your code (divide by zero)
   * Invalid input data (file doesn't exist)
   * Missing permissions (never had access)
   * Resource genuinely insufficient (need 64GB but only 32GB available)

   **The key insight:** Retry strategies should handle transient failures
   but not waste time on permanent ones. Scalable's error classification
   helps distinguish between them.

.. admonition:: 💡 Key Concept: Exceptions in Python
   :class: tip

   An **exception** is Python's way of signaling that something went wrong.
   When code encounters an error, it "raises" an exception:

   .. code-block:: python

      def divide(a, b):
          if b == 0:
              raise ValueError("Cannot divide by zero")
          return a / b

   Exceptions propagate up the call stack until caught:

   .. code-block:: python

      try:
          result = divide(10, 0)
      except ValueError as e:
          print(f"Error: {e}")  # "Error: Cannot divide by zero"

   In distributed systems, exceptions happen on **remote workers** and must
   be serialized, transmitted back to the client, and re-raised — adding
   complexity to error handling.

.. admonition:: 💡 Key Concept: Idempotency
   :class: tip

   An operation is **idempotent** if running it multiple times produces the
   same result as running it once. This is critical for retry logic.

   **Idempotent operations** (safe to retry):

   * Reading a file
   * Computing ``f(x)`` for a pure function
   * Setting a value: ``x = 5`` (doing it twice still gives ``x = 5``)
   * HTTP GET requests

   **Non-idempotent operations** (dangerous to retry):

   * Sending an email (retry = duplicate email)
   * Incrementing a counter: ``x += 1`` (retry = double increment)
   * Inserting a database row (retry = duplicate row)
   * Charging a credit card

   **For retries to be safe, your tasks must be idempotent.** If retrying
   a task could cause side effects (duplicate writes, double charges), you
   need additional safeguards.

.. admonition:: 💡 Key Concept: Exponential Backoff
   :class: tip

   **Exponential backoff** is a retry strategy where you wait progressively
   longer between attempts:

   * Attempt 1: fail → wait 1 second
   * Attempt 2: fail → wait 2 seconds
   * Attempt 3: fail → wait 4 seconds
   * Attempt 4: fail → wait 8 seconds
   * ...

   **Why exponential?** If the failure is caused by overload (too many
   requests), retrying immediately just makes the overload worse. Backing
   off gives the system time to recover.

   **Jitter** adds randomness to the wait time so that multiple retriers
   don't all retry at the same moment (which would cause another spike).


Step 1: How Scalable Handles Errors
--------------------------------------

When a function raises an exception on a worker:

.. code-block:: text

   ┌────────┐              ┌───────────┐              ┌────────┐
   │ Client │   submit()   │ Scheduler │   execute    │ Worker │
   │        │─────────────▶│           │─────────────▶│        │
   │        │              │           │              │ CRASH! │
   │        │              │           │◀─────────────│ error  │
   │        │◀─────────────│  records  │              └────────┘
   │ raises │   exception  │  in telem │
   └────────┘              └───────────┘

1. Worker executes your function
2. Function raises an exception
3. Exception is **serialized** (converted to bytes) by the worker
4. Sent back to the scheduler
5. Recorded in telemetry (``failures.jsonl``)
6. **Re-raised** on the client when you call ``.result()`` or ``gather()``

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_manifest("./scalable.yaml", target="local")

   def risky_function(x):
       if x == 13:
           raise ValueError(f"Unlucky number: {x}")
       return x * 2

   futures = [session.submit(risky_function, i, task="run_analysis")
              for i in range(20)]

   # This will raise ValueError for x=13
   try:
       results = session.gather(futures)
   except ValueError as e:
       print(f"A task failed: {e}")


Step 2: Retry Strategies
--------------------------

Scalable supports automatic retries for transient failures:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_manifest("./scalable.yaml", target="local")

   # Configure retries
   futures = []
   for i in range(20):
       future = session.submit(
           sometimes_fails,
           i,
           task="run_analysis",
           retries=3,               # Retry up to 3 times
       )
       futures.append(future)

.. admonition:: How retry logic works
   :class: note

   With ``retries=3``:

   1. First attempt fails → wait → retry (attempt 2)
   2. Second attempt fails → wait longer → retry (attempt 3)
   3. Third attempt fails → wait even longer → retry (attempt 4)
   4. Fourth attempt fails → give up, propagate error to client

   Each retry is recorded in telemetry so you can see how many retries
   occurred and whether they eventually succeeded.

**Writing retry-safe functions:**

.. code-block:: python

   import time
   import random

   def fetch_data_from_api(scenario_id: int) -> dict:
       """Fetch data — may fail transiently due to network issues."""
       # This is idempotent: calling it multiple times is safe
       # (it reads data, doesn't modify anything)
       response = requests.get(f"https://api.example.com/scenarios/{scenario_id}")
       response.raise_for_status()  # Raises on HTTP errors
       return response.json()

   def process_and_save(scenario_id: int) -> dict:
       """Process data — write results to file.

       Made idempotent by writing to a deterministic path
       (same input → same output path → overwrite is safe).
       """
       result = expensive_computation(scenario_id)
       output_path = f"./outputs/scenario_{scenario_id}.json"
       with open(output_path, "w") as f:
           json.dump(result, f)
       return result


Step 3: Partial Success
-------------------------

.. admonition:: 💡 Key Concept: Partial Success
   :class: tip

   **Partial success** means some tasks in a batch completed successfully
   while others failed. Rather than losing ALL results because of one
   failure, you keep what succeeded and handle failures separately.

   This is essential for large batch jobs. If 999 of 1000 tasks succeed,
   you don't want to throw away 999 good results because of 1 failure.

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_manifest("./scalable.yaml", target="local")

   # Submit many tasks
   futures = [session.submit(maybe_fails, i, task="run_analysis")
              for i in range(100)]

   # Gather with partial success handling
   results = []
   failures = []
   for i, future in enumerate(futures):
       try:
           result = future.result()  # Get individual result
           results.append(result)
       except Exception as e:
           failures.append({"index": i, "error": str(e)})

   print(f"Succeeded: {len(results)}")
   print(f"Failed: {len(failures)}")

   # You can retry just the failures
   retry_futures = [session.submit(maybe_fails, f["index"], task="run_analysis")
                    for f in failures]

.. admonition:: Under the Hood: Futures and Error Isolation
   :class: hint

   Each future is independent. A failure in one future doesn't affect
   others. This is why ``session.submit()`` returns individual futures
   rather than running everything as a single batch — it gives you
   fine-grained control over error handling.


Step 4: Common Failure Modes
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 30 25 25

   * - Failure Mode
     - What Happens
     - Symptoms
     - Solution
   * - Out of Memory (OOM)
     - Worker exceeds memory limit
     - ``MemoryError`` or worker killed
     - Increase ``memory`` in component
   * - Timeout
     - Task exceeds time limit
     - ``TimeoutError`` or Slurm ``TIMEOUT``
     - Increase ``walltime`` or split task
   * - Network Error
     - Connection between client/worker drops
     - ``CommClosedError``
     - Retry (usually transient)
   * - Spot Preemption
     - Cloud reclaims your instance
     - Worker disappears mid-task
     - Retry + caching
   * - Dependency Missing
     - Import fails on worker
     - ``ModuleNotFoundError``
     - Update container image
   * - Data Not Found
     - Input file doesn't exist
     - ``FileNotFoundError``
     - Fix path or mount configuration


Step 5: Diagnosing Failures with Telemetry
--------------------------------------------

When things fail, telemetry is your investigation tool:

.. code-block:: bash

   # See failure details
   scalable report --last --failures

.. code-block:: text

   Failures (3 of 100 tasks):

   1. run_simulation(scenario_id=47)
      Error: MemoryError — unable to allocate 4.2GB
      Worker: worker-3
      Duration before failure: 180s
      Retries attempted: 3 (all failed)

   2. run_simulation(scenario_id=92)
      Error: TimeoutError — exceeded 300s limit
      Worker: worker-1
      Duration before failure: 300s

   3. run_simulation(scenario_id=13)
      Error: ValueError — invalid input data
      Worker: worker-2
      Duration before failure: 0.1s (fast fail — permanent error)

.. admonition:: 🤔 Think About It
   :class: note

   Notice the patterns in the failure report:

   * **Scenario 47** — OOM after 180s suggests a memory-hungry edge case.
     Solution: increase memory for this component, or investigate why
     scenario 47 uses more memory than others.

   * **Scenario 92** — timeout at exactly 300s means it hit the limit.
     Solution: increase walltime, or investigate why this scenario is slow.

   * **Scenario 13** — fast fail (0.1s) with ``ValueError`` means the input
     is permanently bad. Retrying won't help. Solution: fix the input data.


Step 6: Building Fault-Tolerant Workflows
-------------------------------------------

A complete fault-tolerant pattern:

.. code-block:: python

   from scalable import ScalableSession, cacheable


   @cacheable(return_type=dict, scenario_id=int)
   def run_simulation(scenario_id: int) -> dict:
       """Cached + idempotent = retry-safe."""
       # ... expensive computation ...
       return {"id": scenario_id, "result": compute(scenario_id)}


   def run_workflow():
       session = ScalableSession.from_manifest("./scalable.yaml", target="local")

       # Submit all tasks
       task_map = {}
       for i in range(100):
           future = session.submit(
               run_simulation,
               scenario_id=i,
               task="run_analysis",
               retries=3,
           )
           task_map[i] = future

       # Collect results with error isolation
       results = {}
       permanent_failures = []

       for scenario_id, future in task_map.items():
           try:
               results[scenario_id] = future.result()
           except MemoryError:
               permanent_failures.append(
                   (scenario_id, "OOM — needs more memory"))
           except Exception as e:
               permanent_failures.append(
                   (scenario_id, str(e)))

       print(f"Completed: {len(results)} / {len(task_map)}")
       print(f"Failed: {len(permanent_failures)}")

       # Report permanent failures for human investigation
       for sid, error in permanent_failures:
           print(f"  Scenario {sid}: {error}")

       session.close()
       return results

.. admonition:: Why this pattern works
   :class: hint

   1. **``@cacheable``** — successful computations are cached. If you re-run
      after fixing issues, completed scenarios are instant (cache hit).
   2. **``retries=3``** — transient failures (network, spot preemption) are
      handled automatically.
   3. **Individual error handling** — one failure doesn't crash the whole
      workflow.
   4. **Clear reporting** — permanent failures are collected and reported
      for human investigation.

.. admonition:: 💡 Key Concept: Graceful Degradation
   :class: tip

   **Graceful degradation** means a system reduces its service level rather
   than failing completely. Examples:

   * 95 of 100 scenarios complete → report 95 results + note 5 failures
   * Cloud budget exhausted → stop scaling but finish current tasks
   * One worker type unavailable → fall back to a smaller worker type

   This is the opposite of "all or nothing" behavior. For scientific
   workflows, getting 95% of results now (and investigating 5% of failures)
   is usually better than getting 0% because one failure crashed everything.


Common Questions
-----------------

**Q: Should I always use retries?**

Use retries when failures might be transient. Don't retry if:

* The error is clearly permanent (bad input, missing permission)
* The operation is not idempotent (would cause duplicate side effects)
* You're in a tight feedback loop (development, debugging)

**Q: How many retries should I set?**

3 retries is a common default. More than 5 rarely helps — if it fails 5
times, it's probably not transient. The exponential backoff means 5 retries
with base 2s = up to 32 seconds of waiting.

**Q: What about tasks that are too slow (but don't "fail")?**

That's a performance issue, not an error. Use telemetry to identify slow
tasks and either:

* Increase resources (more CPU/memory)
* Optimize the code
* Split into smaller tasks

**Q: Can failures in one task affect other tasks?**

Normally no — tasks are isolated. But if tasks share state (write to the
same file, use the same database), one failure could corrupt shared state.
This is why idempotency and isolated outputs are important.

**Q: How does caching interact with retries?**

Beautifully! If a task succeeds on retry, the result is cached. On re-run,
that scenario hits the cache and skips entirely. Caching effectively
"remembers" that we eventually got the right answer.


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Fault Tolerance
     - System's ability to continue operating despite component failures
   * - Transient Failure
     - Temporary error that resolves on retry (network, timeout)
   * - Permanent Failure
     - Error that won't be fixed by retrying (bad input, bug)
   * - Idempotency
     - Operation that produces the same result if run multiple times
   * - Exponential Backoff
     - Progressively longer waits between retry attempts
   * - Partial Success
     - Some tasks succeed while others fail in a batch
   * - Exception
     - Python's error signaling mechanism (raise/try/except)
   * - Error Propagation
     - How errors travel from worker back to client
   * - Graceful Degradation
     - Reducing service level rather than failing completely
   * - Jitter
     - Randomness added to retry timing to prevent thundering herd


Next Steps
-----------

You now understand how to build fault-tolerant distributed workflows.

* **Next beginner tutorial:** :ref:`beginner_kubernetes` — container
  orchestration and deployment
* **Standard tutorial:** :ref:`tutorial_error_handling` — advanced resilience
  patterns, AI-assisted diagnosis, and production error handling
* **Try it:** Write a function that randomly fails 20% of the time. Submit
  it 50 times with ``retries=3``. Check telemetry to see how many retries
  occurred and whether all tasks eventually succeeded.
