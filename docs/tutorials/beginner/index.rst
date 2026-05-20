.. _beginner_tutorials:

======================================================
Beginner Tutorials
======================================================

Welcome! These tutorials are designed for people who are **new to Scalable and
new to distributed computing**. Unlike the standard tutorials (which assume
familiarity with clusters, containers, and cloud infrastructure), these
beginner tutorials explain every concept from first principles.

Who Are These For?
-------------------

These tutorials are perfect if you:

* Have basic Python experience (functions, imports, loops) but haven't used
  distributed computing frameworks before.
* Are unfamiliar with terms like "workers," "schedulers," "containers," or
  "declarative programming."
* Want to understand not just *how* to use Scalable, but *why* it works the
  way it does.
* Prefer learning with extensive explanations, analogies, and context before
  diving into code.

If you already understand distributed computing, YAML configuration, and
cloud/Kubernetes concepts, the :ref:`standard tutorials <tutorials>` will be
more efficient for you.

How These Tutorials Work
-------------------------

Each beginner tutorial mirrors a standard tutorial topic but adds:

* **Key Concept boxes** — definitions of terms you'll encounter
* **Why This Approach?** — design rationale and alternatives considered
* **Under the Hood** — peeks at what Scalable is doing internally
* **Common Questions** — FAQ-style answers to typical beginner questions
* **Vocabulary Summary** — list of terms you mastered in each tutorial

Learning Path
--------------

.. toctree::
   :maxdepth: 1

   01_getting_started
   02_manifest_system
   03_scaling_strategies
   04_caching_performance
   05_cloud_integration
   06_telemetry
   07_error_handling
   08_kubernetes
   09_ml_emulation
   10_ai_composition

.. list-table::
   :header-rows: 1
   :widths: 5 40 55

   * - #
     - Tutorial
     - Concepts You'll Learn
   * - 1
     - :ref:`beginner_getting_started`
     - Workflows, Dask, CLI, virtual environments, manifests
   * - 2
     - :ref:`beginner_manifest_system`
     - Declarative programming, YAML, schemas, overlays
   * - 3
     - :ref:`beginner_scaling_strategies`
     - Distributed computing, clusters, schedulers, providers
   * - 4
     - :ref:`beginner_caching`
     - Hashing, memoization, content-addressable storage, decorators
   * - 5
     - :ref:`beginner_cloud_integration`
     - Cloud computing, object storage, serverless, IAM
   * - 6
     - :ref:`beginner_telemetry`
     - Observability, structured logging, event streams, metrics
   * - 7
     - :ref:`beginner_error_handling`
     - Fault tolerance, retries, idempotency, partial success
   * - 8
     - :ref:`beginner_kubernetes`
     - Containers, orchestration, pods, operators, namespaces
   * - 9
     - :ref:`beginner_ml_emulation`
     - Machine learning, surrogate models, uncertainty, active learning
   * - 10
     - :ref:`beginner_ai_composition`
     - LLMs, heuristics, code generation, templates

Prerequisites
--------------

You need:

* Python 3.11 or later installed on your computer.
* A text editor (VS Code, PyCharm, or even Notepad).
* A terminal/command prompt.
* Basic Python knowledge: you can write functions, use ``import``, and run
  ``.py`` files.

You do **NOT** need:

* Docker or container experience.
* Cloud accounts (AWS, GCP).
* A Kubernetes cluster.
* Machine learning background.
* Experience with distributed systems.

All of these are explained as you encounter them.

Graduating to Standard Tutorials
----------------------------------

After completing a beginner tutorial, you can move to the corresponding
standard tutorial for deeper technical content, production patterns, and
advanced configuration. Each beginner tutorial ends with a "Next Steps" section
that bridges you to the standard version.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Beginner Tutorial
     - Standard Tutorial
   * - :ref:`beginner_getting_started`
     - :ref:`tutorial_getting_started`
   * - :ref:`beginner_manifest_system`
     - :ref:`tutorial_manifest_system`
   * - :ref:`beginner_scaling_strategies`
     - :ref:`tutorial_scaling_strategies`
   * - :ref:`beginner_caching`
     - :ref:`tutorial_caching`
   * - :ref:`beginner_cloud_integration`
     - :ref:`tutorial_cloud_integration`
   * - :ref:`beginner_telemetry`
     - :ref:`tutorial_telemetry`
   * - :ref:`beginner_error_handling`
     - :ref:`tutorial_error_handling`
   * - :ref:`beginner_kubernetes`
     - :ref:`tutorial_kubernetes`
   * - :ref:`beginner_ml_emulation`
     - :ref:`tutorial_ml_advanced`
   * - :ref:`beginner_ai_composition`
     - :ref:`tutorial_ai_composition`
