.. _tutorial_caching:

======================================================
Tutorial 4: Performance Optimization and Caching
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Use the ``@cacheable`` decorator to skip redundant computation.
* Understand how Scalable hashes function arguments for cache keys.
* Handle file-based and directory-based inputs with type-safe hashing.
* Configure cache storage (local disk, remote S3/GCS).
* Monitor cache hit/miss rates through telemetry.
* Implement cache invalidation strategies for evolving workflows.

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started`.
* Scalable installed (``pip install scalable``).
* For remote cache: ``pip install scalable[cloud]``.

Scenario
--------

Your pipeline executes expensive energy demand simulations that take 30+
minutes per scenario. During development you frequently restart runs after
fixing downstream bugs. Without caching, every restart recomputes scenarios
that already succeeded. The ``@cacheable`` decorator lets completed tasks skip
execution on retry.

Step 1: Basic Caching with @cacheable
---------------------------------------

The :func:`~scalable.caching.cacheable` decorator intercepts function calls,
computes a content-addressable cache key from the function's name and
arguments, and returns cached results when available:

.. code-block:: python

   from scalable import cacheable


   @cacheable(return_type=dict, scenario_id=int)
   def run_simulation(scenario_id: int) -> dict:
       """Expensive computation — runs an energy demand scenario."""
       import time
       time.sleep(30)  # Simulating expensive work
       return {"scenario": scenario_id, "demand_mw": scenario_id * 1.5}

First call:

.. code-block:: python

   result = run_simulation(42)
   # Takes 30 seconds — cache MISS
   print(result)
   # {'scenario': 42, 'demand_mw': 63.0}

Second call with the same argument:

.. code-block:: python

   result = run_simulation(42)
   # Returns instantly — cache HIT
   print(result)
   # {'scenario': 42, 'demand_mw': 63.0}

**How it works:**

1. The decorator serializes each argument using ``dill`` and hashes the bytes
   with ``xxhash`` (seeded by ``SCALABLE_SEED``).
2. The function name and hash form a composite cache key.
3. On a hit, the stored result is deserialized and returned without executing
   the function body.
4. On a miss, the function executes normally and the result is stored.

Step 2: Type Annotations for Reliable Hashing
-----------------------------------------------

Scalable's cache key depends on how arguments are hashed. Without type hints,
the decorator falls back to generic serialization, which may produce
inconsistent keys for complex objects. Explicit type annotations are preferred:

.. code-block:: python

   from scalable import cacheable

   @cacheable(return_type=str, name=str, count=int)
   def greet(name: str, count: int) -> str:
       return f"Hello {name}! (x{count})"

The decorator parameters mirror the function signature:

* ``return_type=str`` — declares the return type for safe deserialization.
* ``name=str, count=int`` — declares argument types for deterministic hashing.

**Why this matters:** Python objects hash differently depending on their
runtime type. A ``numpy.int64(42)`` and Python ``int(42)`` produce different
byte representations. Explicit type annotations ensure the decorator coerces
inputs consistently.

Step 3: Hashing Files and Directories
---------------------------------------

Scientific workflows frequently operate on input files. Scalable provides
specialized type wrappers that hash file *content* rather than paths:

.. code-block:: python

   from scalable import cacheable, FileType, DirType


   @cacheable(return_type=dict, config=FileType, data_dir=DirType)
   def process_data(config: str, data_dir: str) -> dict:
       """Process data files. Cache key includes file contents."""
       import json
       with open(config) as f:
           cfg = json.load(f)
       # ... process files in data_dir ...
       return {"records_processed": 1000, "config_version": cfg["version"]}

How each type hashes:

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Type
     - Hashing Strategy
   * - ``FileType``
     - Streams file content in 1 MB chunks through xxhash. Includes the
       filename (basename only) in the hash. If the file doesn't exist, raises
       ``ValueError``.
   * - ``DirType``
     - Walks the directory tree, hashes each file's relative path and content.
       Order is sorted for determinism. Missing directory raises ``ValueError``.
   * - ``str``
     - Hashes the string bytes directly (UTF-8 encoded).
   * - ``int``
     - Hashes the integer's byte representation.

**Trade-off:** ``FileType`` hashing reads the entire file on every call to
compute the key. For very large files (multi-GB), this adds I/O overhead even
on cache hits. Consider whether your workflow modifies input files between
runs — if inputs are immutable, a simpler path-based key might suffice.

Step 4: Forcing Recomputation
------------------------------

Sometimes you need to invalidate the cache for a specific function, for
example after fixing a bug in the computation logic:

.. code-block:: python

   @cacheable(return_type=dict, recompute=True, scenario_id=int)
   def run_simulation(scenario_id: int) -> dict:
       """Always recompute — ignores cached results."""
       # Fixed version of the computation
       return {"scenario": scenario_id, "demand_mw": scenario_id * 1.7}

Setting ``recompute=True`` forces the function to execute every time. The
result still gets written to the cache, so subsequent calls (once you remove
``recompute=True``) will find fresh entries.

**Alternative: Change the seed.** If you want to invalidate *all* cache entries
globally, change the ``SCALABLE_SEED`` environment variable:

.. code-block:: bash

   export SCALABLE_SEED=123456789
   python workflow.py  # All cache keys change — full recomputation

Step 5: The Minimal @cacheable Form
--------------------------------------

For quick prototyping, ``@cacheable`` works without explicit types:

.. code-block:: python

   @cacheable
   def quick_computation(x, y):
       return x + y

In this form:

* Arguments are serialized with ``dill`` and hashed generically.
* Return type is inferred from the actual return value.
* This is less reliable for complex objects but convenient during exploration.

**Recommendation:** Always add explicit types for production code. The minimal
form is acceptable for quick experiments where cache key stability isn't
critical.

Step 6: Cache Configuration
-----------------------------

Configure cache storage via environment variables or the manifest:

**Local disk cache (default):**

.. code-block:: bash

   export SCALABLE_CACHE_DIR=./cache
   # Or in the manifest:
   # project:
   #   local_cache: ./my-cache

**Remote cache (S3/GCS):**

.. code-block:: bash

   export SCALABLE_CACHE_REMOTE=s3://my-bucket/scalable-cache/

When a remote cache is configured, Scalable checks the remote store on cache
miss before executing the function. This enables cache sharing across machines
and CI runs:

.. code-block:: text

   Cache lookup order:
   1. Local disk (fast, per-machine)
   2. Remote store (slower, shared across team)
   3. Execute function (slowest, produces new cache entry)

**Cache directory structure:**

.. code-block:: text

   ./cache/
   ├── cache.db          # SQLite index (diskcache)
   ├── 00/              # Sharded data files
   │   ├── a3b8f1...
   │   └── ...
   └── tmp/             # Temporary write staging

The cache is process-safe (uses SQLite locking) and can be shared between
concurrent workflows on the same machine.

Step 7: Cache-Aware Task Definitions
--------------------------------------

In the manifest, marking a task with ``cache: true`` signals to the Session
that functions submitted under that task should honor the cache:

.. code-block:: yaml

   tasks:
     run_gcam:
       component: gcam
       cache: true

     postprocess:
       component: analysis
       cache: false   # Always recompute (e.g., aggregation is cheap)

When ``cache: true``, the session emits cache hit/miss events to telemetry,
allowing you to track cache effectiveness over time.

Step 8: Monitoring Cache Performance
--------------------------------------

Cache events are recorded in telemetry when running through the Session API:

.. code-block:: bash

   scalable report --latest

.. code-block:: text

   Cache Performance:
     Total calls: 50
     Hits: 35 (70%)
     Misses: 15 (30%)
     Estimated time saved: 17.5 minutes

Programmatic access:

.. code-block:: python

   import json
   from pathlib import Path

   run_dir = Path(".scalable/runs/run-20260520T.../")
   cache_events = []
   with open(run_dir / "cache.jsonl") as f:
       for line in f:
           cache_events.append(json.loads(line))

   hits = sum(1 for e in cache_events if e["hit"])
   misses = sum(1 for e in cache_events if not e["hit"])
   print(f"Hit rate: {hits}/{hits+misses} = {hits/(hits+misses)*100:.0f}%")

Step 9: Cache Invalidation Strategies
---------------------------------------

Effective caching requires a strategy for when to invalidate:

**Strategy 1: Seed rotation**

Change ``SCALABLE_SEED`` to invalidate all entries. Use this after major code
changes that affect all functions:

.. code-block:: bash

   export SCALABLE_SEED=$(date +%s)  # New seed each day

**Strategy 2: Per-function recompute**

Set ``recompute=True`` on specific functions during development. Remove once
verified:

.. code-block:: python

   @cacheable(return_type=dict, recompute=True, params=dict)
   def run_gcam(params: dict) -> dict:
       ...

**Strategy 3: Version the function name**

Include a version suffix in the function name to naturally invalidate when
logic changes:

.. code-block:: python

   @cacheable(return_type=dict, params=dict)
   def run_gcam_v3(params: dict) -> dict:
       # v3: fixed fuel cost calculation
       ...

**Strategy 4: Delete the cache directory**

Nuclear option — simply remove the cache directory:

.. code-block:: bash

   rm -rf ./cache
   python workflow.py  # Full recomputation

Step 10: Distributed Caching Pattern
--------------------------------------

For team workflows where multiple developers run the same pipeline, use a
shared remote cache:

.. code-block:: bash

   # All team members set the same remote cache
   export SCALABLE_CACHE_REMOTE=s3://team-bucket/scalable-cache/

Workflow:

1. Developer A runs the pipeline. All 50 scenarios compute and cache remotely.
2. Developer B runs the same pipeline. All 50 scenarios hit the remote cache.
3. Developer A modifies scenario 7's parameters. Only scenario 7 recomputes.

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   client = session.start()

   # These will check local cache, then remote, then compute
   futures = [
       client.submit(run_gcam, scenario, tag="gcam")
       for scenario in range(50)
   ]
   results = client.gather(futures)
   # First run: 50 misses. Subsequent runs: 50 hits.

Troubleshooting
---------------

**Cache never hits despite identical arguments**
  Check that ``SCALABLE_SEED`` hasn't changed between runs. Also verify that
  argument types are consistent — passing ``numpy.int64`` vs ``int`` may
  produce different keys. Use explicit type annotations.

**"ValueError: File does not exist" from FileType**
  ``FileType`` validates file existence at hash time. Ensure the file path is
  accessible from the worker process (relevant for containerized workers where
  paths differ from the host).

**Cache grows unboundedly**
  ``diskcache`` doesn't auto-evict by default. Periodically clean old entries:

  .. code-block:: python

     from diskcache import Cache
     cache = Cache("./cache")
     cache.clear()  # Remove all entries
     # Or set a size limit:
     cache = Cache("./cache", size_limit=10 * 1024**3)  # 10 GB

**Remote cache is slow**
  S3/GCS lookups add latency per call (50–200ms). For workflows with thousands
  of small tasks, the overhead may exceed computation time. Use remote caching
  only for expensive tasks (>1 minute per call) or batch cache lookups.

Next Steps
----------

* :ref:`tutorial_cloud_integration` — Deploy cached workflows to AWS/GCP with
  shared remote storage.
* :ref:`tutorial_telemetry` — Analyze cache performance across historical runs.
* :ref:`tutorial_error_handling` — Handle cache corruption and partial failures
  gracefully.
