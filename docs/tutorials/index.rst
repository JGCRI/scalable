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

**New to distributed computing?** Start with the beginner tutorials. They cover
the same 10 topics as the standard tutorials below but explain all concepts
from first principles — no prior distributed systems, cloud, or container
experience required.

Getting Started
---------------

.. toctree::
   :maxdepth: 1

   01_getting_started
   02_manifest_system

These introductory tutorials assume no prior Scalable experience. Start here
if you are new to the framework.

Core Capabilities
-----------------

.. toctree::
   :maxdepth: 1

   03_scaling_strategies
   04_caching_performance
   05_cloud_integration
   06_telemetry
   07_error_handling

These tutorials cover Scalable's primary feature set. They assume you have
completed the Getting Started tutorials and have a working local environment.

Advanced Topics
---------------

.. toctree::
   :maxdepth: 1

   08_kubernetes
   09_ml_emulation
   10_ai_composition

These tutorials explore Scalable's advanced and differentiating capabilities.
They assume familiarity with the core features and, in some cases, access to
external infrastructure (Kubernetes clusters, cloud accounts).

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
