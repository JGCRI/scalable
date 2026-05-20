.. _beginner_caching:

======================================================
Beginner Tutorial 4: Caching — Avoiding Redundant Work
======================================================

.. contents:: In This Tutorial
   :local:
   :depth: 2

The Big Picture
----------------

Imagine you've run a 2-hour simulation pipeline and it fails on step 47 of 50.
You fix the bug and re-run. Without caching, all 50 steps execute again —
including the 46 that already succeeded. That's hours of wasted computation.

**Caching** solves this by saving the results of completed work. On re-run,
Scalable checks: "Have I already computed this exact function with these exact
inputs?" If yes, it returns the saved result instantly. If no, it computes
normally and saves the result for next time.

This tutorial explains how caching works from first principles — hashing,
content-addressable storage, decorators, and the trade-offs involved.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand what caching is and why it matters for scientific workflows.
* Know how hash functions create "fingerprints" of data.
* Understand content-addressable storage.
* Use the ``@cacheable`` decorator in Scalable.
* Handle file-based and directory-based inputs.
* Configure local and remote cache storage.
* Understand cache invalidation strategies.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started`.
* Scalable installed (``pip install scalable``).
* For remote cache concepts: no cloud account needed (follow along).


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: What is Caching?
   :class: tip

   **Caching** is storing the result of an expensive operation so you can
   reuse it later without recomputing. It trades **storage space** for
   **computation time**.

   Real-world examples of caching:

   * **Web browser cache** — stores downloaded images/CSS so pages load
     faster on revisit
   * **CPU cache** — keeps frequently accessed memory close to the processor
   * **DNS cache** — remembers IP addresses so your computer doesn't ask
     "what's google.com's address?" every time

   In Scalable, caching means: "If I've already computed ``f(x)`` and saved
   the result, don't compute it again — just return the saved result."

.. admonition:: 💡 Key Concept: Hash Functions
   :class: tip

   A **hash function** takes input of any size and produces a fixed-size
   "fingerprint." Think of it as a one-way summarizer:

   .. code-block:: text

      Input: "Hello, World!"     → Hash: 65a8e27d8879...
      Input: "Hello, World!!"    → Hash: 7f83b1657ff1...  (totally different!)
      Input: (500MB data file)   → Hash: a3b8c9d2e1f0...

   Key properties:

   * **Deterministic** — same input always produces same hash
   * **Fixed size** — output is always the same length regardless of input
   * **Avalanche effect** — tiny input change → completely different hash
   * **One-way** — you can't reconstruct the input from the hash

   **In Scalable:** When you call a cached function, Scalable hashes the
   function name + all arguments to create a unique key. If that key exists
   in the cache, the result is already known.

.. admonition:: 💡 Key Concept: Content-Addressable Storage
   :class: tip

   **Content-addressable storage** (CAS) uses the *content's hash* as its
   address (filename/key). Instead of naming a file ``results_v3_final.json``,
   you name it ``sha256_a3b8f1c2d4e5.json``.

   **Benefits:**

   * **Deduplication** — identical content has the same hash, stored once
   * **Verification** — you can verify data hasn't been corrupted by
     re-hashing and comparing
   * **Immutability** — content at a hash never changes (any change =
     different hash = different address)

   **Used by:** Git (every commit, file, and tree is content-addressed),
   Docker (image layers), IPFS, and Scalable's cache system.

.. admonition:: 💡 Key Concept: Memoization
   :class: tip

   **Memoization** is a specific caching technique for functions: remember
   the result of a function call based on its inputs.

   .. code-block:: python

      # Without memoization:
      result1 = expensive_function(42)   # Takes 5 minutes
      result2 = expensive_function(42)   # Takes 5 minutes again!

      # With memoization:
      result1 = expensive_function(42)   # Takes 5 minutes, saves result
      result2 = expensive_function(42)   # Instant! Returns saved result

   Memoization requires **determinism** — the same inputs must always produce
   the same output. If your function depends on the current time, random
   numbers, or external state that changes, memoization won't give correct
   results.

.. admonition:: 💡 Key Concept: Python Decorators
   :class: tip

   A **decorator** is a Python pattern that wraps a function to add behavior
   without changing the function's code. Decorators use the ``@`` syntax:

   .. code-block:: python

      @some_decorator
      def my_function(x):
          return x * 2

   This is equivalent to:

   .. code-block:: python

      def my_function(x):
          return x * 2
      my_function = some_decorator(my_function)

   The decorator receives your function and returns a new function that does
   something extra (like checking a cache before calling the original).

   **Common decorators you may have seen:**

   * ``@property`` — makes a method behave like an attribute
   * ``@staticmethod`` — marks a method that doesn't use ``self``
   * ``@functools.lru_cache`` — Python's built-in memoization

   Scalable's ``@cacheable`` is a decorator that adds persistent caching to
   any function.


Step 1: Basic Caching with @cacheable
---------------------------------------

Here's how to make a function cacheable in Scalable:

.. code-block:: python

   from scalable import cacheable


   @cacheable(return_type=dict, scenario_id=int)
   def run_simulation(scenario_id: int) -> dict:
       """Expensive computation — runs an energy demand scenario."""
       import time
       time.sleep(5)  # Simulate 5 seconds of heavy computation
       return {
           "scenario_id": scenario_id,
           "demand_mwh": scenario_id * 1000 + 42,
           "status": "complete",
       }

.. admonition:: What's happening with that decorator?
   :class: note

   ``@cacheable(return_type=dict, scenario_id=int)`` tells Scalable:

   1. **This function can be cached** — wrap it with cache logic
   2. **Return type is ``dict``** — Scalable knows how to serialize/
      deserialize the result
   3. **``scenario_id`` is type ``int``** — Scalable knows how to hash
      this argument deterministically

   The type annotations help Scalable create reliable cache keys. Different
   types hash differently (the integer ``1`` vs. the string ``"1"`` produce
   different cache keys).

**First call** — cache miss (slow):

.. code-block:: python

   result = run_simulation(scenario_id=42)
   # Takes 5 seconds — computes and saves to cache
   print(result)  # {"scenario_id": 42, "demand_mwh": 42042, "status": "complete"}

**Second call** — cache hit (instant):

.. code-block:: python

   result = run_simulation(scenario_id=42)
   # Instant! Returns saved result from cache
   print(result)  # {"scenario_id": 42, "demand_mwh": 42042, "status": "complete"}

.. admonition:: Under the Hood: What happens on each call
   :class: hint

   **Cache miss (first call):**

   1. Scalable hashes: ``hash("run_simulation" + hash(42))`` → key ``abc123``
   2. Looks up key ``abc123`` in cache storage → not found
   3. Calls the actual function → waits 5 seconds → gets result
   4. Serializes the result and stores it at key ``abc123``
   5. Returns the result to you

   **Cache hit (second call):**

   1. Scalable hashes: ``hash("run_simulation" + hash(42))`` → key ``abc123``
   2. Looks up key ``abc123`` in cache storage → found!
   3. Deserializes the stored result
   4. Returns it immediately (no function execution)


Step 2: How Cache Keys Are Computed
-------------------------------------

The cache key is a hash of:

1. The function's **fully qualified name** (module + function name)
2. The function's **arguments** (each individually hashed)

.. code-block:: python

   # These produce DIFFERENT cache keys:
   run_simulation(scenario_id=1)    # key = hash(name + hash(1))
   run_simulation(scenario_id=2)    # key = hash(name + hash(2))

   # These produce the SAME cache key:
   run_simulation(scenario_id=42)   # First call
   run_simulation(scenario_id=42)   # Same key → cache hit!

.. admonition:: 💡 Key Concept: Deterministic Hashing
   :class: tip

   For caching to work correctly, hashing must be **deterministic** — the
   same input must always produce the same hash.

   This is why Scalable asks you to declare argument types. A Python ``dict``
   doesn't have a guaranteed ordering (in practice it does in Python 3.7+,
   but Scalable ensures stability by sorting keys before hashing).

   **What can be hashed reliably:**

   * Primitive types: ``int``, ``float``, ``str``, ``bool``
   * Collections: ``list``, ``tuple``, ``dict`` (with hashable contents)
   * Files: hashed by content (not filename!)

   **What can't be hashed reliably:**

   * Objects with mutable state
   * Functions/lambdas (their code might change)
   * Anything involving randomness or external state


Step 3: Handling File Inputs
------------------------------

Scientific workflows often take files as input. Scalable provides special
types for file-based hashing:

.. code-block:: python

   from scalable import cacheable
   from scalable.caching import FileType, DirType


   @cacheable(return_type=dict, input_file=FileType, config=dict)
   def process_data(input_file: str, config: dict) -> dict:
       """Process a data file according to config."""
       with open(input_file) as f:
           data = f.read()
       # ... processing ...
       return {"rows": len(data.splitlines()), "config": config}

.. admonition:: 💡 Key Concept: FileType and Content Hashing
   :class: tip

   When you annotate an argument as ``FileType``, Scalable hashes the
   **file's contents** (not its path or name).

   Why? Because:

   * Same file at different paths = same computation = should cache-hit
   * Same path with different contents = different computation = should
     NOT cache-hit

   .. code-block:: text

      process_data("/data/input_v1.csv", ...)   # Hashes CSV content
      process_data("/tmp/copy_of_v1.csv", ...)  # Same content → cache hit!
      # (even though the path is different)

   ``DirType`` works similarly but hashes all files in a directory
   (recursively).


Step 4: Cache Storage Configuration
--------------------------------------

By default, Scalable stores cache entries on local disk:

.. code-block:: yaml

   # In scalable.yaml
   project:
     name: my-project
     local_cache: ./cache    # Cache stored here

The cache directory structure looks like:

.. code-block:: text

   ./cache/
   ├── run_simulation/
   │   ├── abc123.json       # Cached result for scenario_id=42
   │   ├── def456.json       # Cached result for scenario_id=7
   │   └── ...
   └── process_data/
       ├── 789ghi.json
       └── ...

For team collaboration or cloud workflows, you can use remote storage:

.. code-block:: yaml

   project:
     name: my-project
     local_cache: s3://my-bucket/scalable-cache/

.. admonition:: 💡 Key Concept: Local vs. Remote Cache
   :class: tip

   **Local cache** (filesystem):

   * Fast (no network latency)
   * Private (only you can access)
   * Lost if machine is destroyed

   **Remote cache** (S3, GCS):

   * Shared across team members and CI/CD
   * Persistent (survives machine changes)
   * Slower (network round-trip for every lookup)
   * Costs money (storage + requests)

   **When to use remote cache:** When your team runs the same pipeline and
   you want to share cached results. Person A computes scenario 1–500,
   Person B starts from 501 but benefits from A's cached results.


Step 5: Cache Invalidation
-----------------------------

.. admonition:: 💡 Key Concept: Cache Invalidation
   :class: tip

   There's a famous saying in computer science:

      *"There are only two hard things in Computer Science: cache
      invalidation and naming things."* — Phil Karlton

   **Cache invalidation** means deciding when cached results are no longer
   valid. A result becomes invalid when:

   * The function's logic changes (you fixed a bug)
   * An input file's content changes
   * External dependencies update (new library version)
   * You explicitly want fresh results

Scalable handles invalidation in several ways:

**Automatic invalidation** (content-based):

* File inputs are hashed by content → changed file = different key = no hit
* Function arguments change → different key = no hit

**Manual invalidation:**

.. code-block:: bash

   # Clear all cache for a project
   rm -rf ./cache/

   # Clear cache for a specific function
   rm -rf ./cache/run_simulation/

**Selective re-computation:**

.. code-block:: python

   # Force re-computation even if cached
   result = run_simulation(scenario_id=42, _cache_bypass=True)

.. admonition:: 🤔 Think About It
   :class: note

   What happens if you change the function's code but not its inputs?

   By default, Scalable hashes the function **name**, not its **code**. So
   if you fix a bug in ``run_simulation``, the cache key is the same and
   you'll get stale results!

   **Solution:** Clear the cache after code changes, or use versioning:

   .. code-block:: python

      @cacheable(return_type=dict, scenario_id=int, _version="2")
      def run_simulation(scenario_id: int) -> dict:
          # Fixed bug — _version="2" creates different cache keys
          ...


Step 6: Monitoring Cache Performance
---------------------------------------

Scalable records cache hit/miss events in telemetry:

.. code-block:: bash

   scalable report --last

.. code-block:: text

   Cache Performance:
     Total lookups: 200
     Hits: 180 (90%)
     Misses: 20 (10%)
     Time saved: ~15 minutes (estimated from hit count × avg task duration)

A high hit rate (>80%) means caching is working well. A low hit rate might
mean:

* Inputs are always changing (cache keys never match)
* The cache was recently cleared
* Tasks aren't deterministic

.. admonition:: 💡 Key Concept: Serialization
   :class: tip

   **Serialization** converts a Python object into bytes that can be stored
   on disk or sent over a network. **Deserialization** converts bytes back
   into a Python object.

   Common serialization formats:

   * **JSON** — human-readable, limited types (no sets, dates, custom objects)
   * **Pickle** — Python-native, supports any object, not human-readable
   * **MessagePack** — fast binary format, limited types

   Scalable uses JSON for simple types (dicts, lists, strings) and pickle
   for complex objects. The ``return_type`` annotation in ``@cacheable``
   helps Scalable choose the best serialization strategy.


Common Questions
-----------------

**Q: Does caching use a lot of disk space?**

It depends on your output sizes. Small results (numbers, short strings) use
negligible space. Large results (DataFrames, arrays) can grow quickly. Monitor
your cache directory size and set up periodic cleanup for old entries.

**Q: What if two people compute the same thing simultaneously?**

With local cache, they each compute independently. With remote cache (S3),
the second writer overwrites the first — but since the result is deterministic,
they're writing the same value, so it's safe.

**Q: Can I cache functions that return different results each time?**

No! Caching assumes **determinism** — same inputs → same output. If your
function involves randomness, time-dependence, or external state that changes,
caching will return stale/incorrect results.

**Q: What's the difference between Scalable's cache and Python's
``functools.lru_cache``?**

* ``lru_cache`` stores results **in memory** (lost when program exits)
* ``@cacheable`` stores results **on disk or remote storage** (persistent
  across runs)

Scalable's caching is designed for expensive computations that span multiple
program invocations.

**Q: Can I cache only some invocations?**

Yes — the ``@cacheable`` decorator checks the cache on every call. If you
want to bypass it for specific calls, use ``_cache_bypass=True``.


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Caching
     - Storing results for reuse to avoid recomputation
   * - Hash Function
     - Produces a fixed-size fingerprint from arbitrary input
   * - Content-Addressable Storage
     - Data addressed by its content's hash, not by name
   * - Memoization
     - Caching function results based on inputs
   * - Decorator
     - Python pattern that wraps a function to add behavior
   * - Cache Key
     - Unique identifier for a cached result (hash of function + args)
   * - Cache Hit
     - Result found in cache (fast, no recomputation)
   * - Cache Miss
     - Result NOT found, must compute and store
   * - Cache Invalidation
     - Deciding when cached results are no longer valid
   * - Serialization
     - Converting objects to bytes for storage/transmission
   * - Determinism
     - Same inputs always produce the same output
   * - FileType
     - Annotation telling Scalable to hash file contents, not path


Next Steps
-----------

You now understand how caching works and can use it to avoid redundant
computation in your workflows.

* **Next beginner tutorial:** :ref:`beginner_cloud_integration` — running
  workflows in the cloud
* **Standard tutorial:** :ref:`tutorial_caching` — advanced caching patterns,
  remote configuration, and cache management
* **Try it:** Add ``@cacheable`` to a function, run it twice, and check the
  ``./cache/`` directory to see the stored results. Modify an input and
  verify you get a cache miss.
