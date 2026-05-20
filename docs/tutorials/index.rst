.. _tutorials:

======================================================
Tutorials
======================================================

Hands-on, step-by-step guides that walk you through Scalable's features from
first installation to advanced production workflows. Each tutorial builds on a
realistic scenario, includes full code examples with expected output, and ends
with suggested next steps.

Beginner Tutorials
-------------------

.. toctree::
   :maxdepth: 1

   beginner/index

.. tip::

   **New to Scalable or distributed computing?** Start with the beginner
   tutorials above. They cover the same 10 topics as the advanced tutorials
   below but explain every concept from first principles — no prior distributed
   systems, cloud, or container experience required. Once you're comfortable
   with the concepts, graduate to the advanced tutorials for production patterns.

Advanced Tutorials
-------------------

.. toctree::
   :maxdepth: 1

   advanced/index

Recommended Learning Path
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 10 50 40

   * - #
     - Tutorial
     - You'll Learn
   * - 1
     - :ref:`tutorial_getting_started`
     - Install, configure, run your first workflow
   * - 2
     - :ref:`tutorial_manifest_system`
     - Manifest schema, targets, overlays, validation
   * - 3
     - :ref:`tutorial_scaling_strategies`
     - Providers, manual/adaptive/objective scaling
   * - 4
     - :ref:`tutorial_caching`
     - @cacheable, FileType/DirType, remote cache
   * - 5
     - :ref:`tutorial_cloud_integration`
     - AWS Fargate, GCP, cost estimation, artifacts
   * - 6
     - :ref:`tutorial_telemetry`
     - JSONL events, reports, historical analysis
   * - 7
     - :ref:`tutorial_error_handling`
     - Retry, partial success, diagnostics
   * - 8
     - :ref:`tutorial_kubernetes`
     - Dask Operator, namespaces, pod management
   * - 9
     - :ref:`tutorial_ml_advanced`
     - LearnedAdvisor, AdaptiveScaler, @emulatable
   * - 10
     - :ref:`tutorial_ai_composition`
     - init-component, diagnose, compose, migrate

Prerequisites by Tutorial
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Tutorial
     - Install Extra
     - External Requirements
   * - 1–4
     - ``pip install scalable``
     - None (local only)
   * - 5
     - ``pip install scalable[cloud]``
     - AWS/GCP credentials
   * - 6–7
     - ``pip install scalable``
     - None
   * - 8
     - ``pip install scalable[kubernetes]``
     - Kubernetes cluster + kubectl
   * - 9
     - ``pip install scalable[ml]``
     - 5+ telemetry runs
   * - 10
     - ``pip install scalable[ai]``
     - None (optional: LLM API key)

Conventions Used
-----------------

Throughout these tutorials:

* All code examples use Python 3.11+ syntax.
* Shell commands assume a Unix-like environment (macOS/Linux). Windows
  equivalents are noted where they differ.
* The project name ``energy-forecast`` and component names ``gridlabd``,
  ``watershed``, ``postprocess`` appear consistently across tutorials as a
  running example.
* Environment variables use the ``${VAR:-default}`` pattern for portability.
* Expected output blocks show representative output — exact values (timestamps,
  hashes, run IDs) will differ on your machine.
