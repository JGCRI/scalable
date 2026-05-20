.. _tutorial_manifest_system:

======================================================
Tutorial 2: Mastering the Manifest System
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Understand every section of a ``scalable.yaml`` manifest in depth.
* Use environment variable expansion for portable, credential-free manifests.
* Define multiple targets for local development, HPC, and cloud.
* Configure components with images, mounts, environment variables, and tags.
* Apply overlays to customize resources per deployment environment.
* Validate manifests programmatically and interpret error codes.

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started`.
* Scalable installed (``pip install scalable``).
* A text editor and terminal.

Scenario
--------

You are building a climate modeling pipeline with two stages: a computationally
expensive simulation (GCAM) and a lighter post-processing step (Stitches). The
pipeline must run locally during development, on an HPC cluster for production,
and eventually in the cloud. The manifest system lets you describe all three
targets in a single file.

Step 1: Manifest Schema Overview
---------------------------------

Every manifest has this top-level structure:

.. code-block:: yaml

   version: 1
   project: { ... }
   targets: { ... }
   components: { ... }
   tasks: { ... }
   overlays: { ... }    # optional

The parser (:mod:`scalable.manifest.parser`) enforces:

* ``version`` and ``project`` are **required**.
* Unknown top-level keys are rejected (defense against typos).
* Unknown keys *inside* a target block are passed through to the provider
  (forward compatibility for provider-specific options).
* Unknown keys inside ``components`` are rejected (strict schema).

Step 2: The Project Block
--------------------------

.. code-block:: yaml

   project:
     name: climate-pipeline
     default_storage: ./outputs
     local_cache: ./cache

``name``
  Identifies the project in telemetry run IDs (e.g.,
  ``run-20260520T...-climate-pipeline-a1b2c3d4``). Use lowercase with hyphens.

``default_storage``
  Base URI for artifact output. Can be a local path, S3 URI
  (``s3://bucket/prefix/``), or GCS URI (``gs://bucket/prefix/``). Providers
  that support remote storage will use this as the destination for task outputs.

``local_cache``
  Override for ``SCALABLE_CACHE_DIR``. The manifest value takes precedence over
  the environment variable, which itself takes precedence over the compiled
  default (``./cache``).

Step 3: Defining Targets
-------------------------

Targets are named execution environments. You can define as many as you need:

.. code-block:: yaml

   targets:
     local:
       provider: local
       max_workers: 4
       threads_per_worker: 2
       processes: false
       containers: none

     hpc:
       provider: slurm
       queue: batch
       account: GCIMS
       walltime: "04:00:00"
       interface: ib0

     aws:
       provider: aws
       region: us-east-1
       cluster_type: fargate
       instance_type: m5.xlarge
       worker_cpu: 4096
       worker_mem: 16384
       image: 123456789.dkr.ecr.us-east-1.amazonaws.com/climate:latest
       adaptive:
         minimum: 1
         maximum: 10

Each target has one required key — ``provider`` — that maps to a registered
provider class. All other keys are provider-specific options:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Provider
     - Key Options
   * - ``local``
     - ``max_workers``, ``threads_per_worker``, ``processes``, ``containers``
   * - ``slurm``
     - ``queue``, ``account``, ``walltime``, ``interface``
   * - ``aws``
     - ``region``, ``cluster_type``, ``instance_type``, ``worker_cpu``,
       ``worker_mem``, ``image``, ``adaptive``, ``subnets``, ``security_groups``
   * - ``kubernetes``
     - ``namespace``, ``image``, ``adaptive``, ``overlay``

**Why multiple targets?** A single manifest can describe your entire promotion
path: develop locally → validate on HPC → deploy to cloud. The ``--target``
flag (or ``SCALABLE_TARGET`` env var) selects which environment to activate.

Step 4: Components in Detail
------------------------------

Components are resource profiles for your workloads:

.. code-block:: yaml

   components:
     gcam:
       image: ghcr.io/jgcri/gcam:7.0
       runtime: apptainer
       cpus: 8
       memory: 32G
       mounts:
         /data/gcam: /gcam-core
         /shared/outputs: /outputs
       env:
         GCAM_DATA: /gcam-core/data
       tags: [iam, climate]
       preload_script: ./scripts/gcam_preload.sh

     postprocess:
       cpus: 2
       memory: 4G
       tags: [analysis]

Let's break down each key:

``image``
  Container image URI. Used by providers that support containerized workers
  (Slurm with Apptainer, Kubernetes, cloud). Omit for bare-metal local runs.

``runtime``
  Container runtime hint (``apptainer``, ``docker``). Providers use this to
  determine how to pull and launch the image.

``cpus``
  CPU count allocated per worker in this component group. Maps to Dask worker
  resource annotations and scheduler affinity.

``memory``
  Memory allocation string (e.g., ``32G``, ``512M``). Parsed by
  ``dask.utils.parse_bytes``.

``mounts``
  Volume mount mappings (host path → container path). Only meaningful for
  containerized providers.

``env``
  Environment variables injected into the worker process. Useful for configuring
  model data paths, API keys (prefer ``${VAR}`` references over literals), etc.

``tags``
  Arbitrary labels for grouping and filtering. Tags propagate to telemetry
  events and can be used by the resource advisor for per-tag recommendations.

``preload_script``
  Shell script executed before the Dask worker process starts. Useful for
  activating conda environments, loading modules, or mounting FUSE filesystems.

Step 5: Task Bindings
----------------------

Tasks bind named work units to components:

.. code-block:: yaml

   tasks:
     run_gcam:
       component: gcam
       cache: true
       outputs:
         database: dir

     aggregate_results:
       component: postprocess
       cache: true

``component``
  Must reference a key in the ``components`` map. This determines which workers
  can execute the task and what resources are reserved.

``cache``
  When ``true``, results of functions submitted under this task are eligible
  for the :func:`~scalable.caching.cacheable` disk cache. Cache hits skip
  execution entirely on subsequent runs.

``outputs``
  Declares expected output artifacts and their types (``file`` or ``dir``).
  The artifact store can persist these to remote storage when
  ``project.default_storage`` is configured.

Step 6: Environment Variable Expansion
----------------------------------------

Manifests support ``${VAR}`` and ``${VAR:-default}`` syntax for portability:

.. code-block:: yaml

   project:
     name: ${PROJECT_NAME:-climate-demo}
     default_storage: ${ARTIFACT_BUCKET:-./outputs}

   targets:
     aws:
       provider: aws
       region: ${AWS_REGION:-us-east-1}
       execution_role_arn: ${EXECUTION_ROLE_ARN}

Expansion rules:

* ``${VAR}`` — replaced by the value of the environment variable. If unset,
  the parser raises :class:`~scalable.manifest.errors.ManifestParseError`.
* ``${VAR:-default}`` — replaced by the variable if set, otherwise uses the
  literal default value.
* Bare ``$HOME``-style references are **not** expanded (to avoid ambiguity in
  mount paths). Always use curly braces.

This means you can commit ``scalable.yaml`` to version control without
embedding secrets or machine-specific paths:

.. code-block:: bash

   export AWS_REGION=us-west-2
   export EXECUTION_ROLE_ARN=arn:aws:iam::123456789:role/myRole
   scalable validate ./scalable.yaml

Step 7: Overlays for Environment-Specific Tuning
--------------------------------------------------

Overlays let you define named configuration deltas that are merged onto the
base manifest when a target references them:

.. code-block:: yaml

   targets:
     hpc:
       provider: slurm
       queue: batch
       walltime: "04:00:00"
       overlay: hpc-large

   components:
     gcam:
       cpus: 4
       memory: 16G

   overlays:
     hpc-large:
       components:
         gcam:
           cpus: 16
           memory: 64G

     hpc-debug:
       components:
         gcam:
           cpus: 2
           memory: 8G

When target ``hpc`` is selected, the ``hpc-large`` overlay is merged:
``gcam.cpus`` becomes 16 and ``gcam.memory`` becomes ``64G``. The base values
serve as defaults for targets that don't reference an overlay.

**Design rationale:** Overlays avoid manifest duplication. Instead of
maintaining separate YAML files per environment, you express deltas
declaratively. The merge is shallow per-component-key (not deep recursive),
keeping behavior predictable.

You can also override target options via overlays:

.. code-block:: yaml

   overlays:
     cloud-dev:
       targets:
         aws:
           adaptive:
             minimum: 1
             maximum: 3
       components:
         gcam:
           cpus: 4
           memory: 16G

Step 8: Multi-Target Workflow Selection
----------------------------------------

At runtime you select a target via:

**CLI:**

.. code-block:: bash

   scalable run ./scalable.yaml --target hpc --workflow workflow.py

**Python:**

.. code-block:: python

   session = ScalableSession.from_yaml("./scalable.yaml", target="hpc")

**Environment variable:**

.. code-block:: bash

   export SCALABLE_TARGET=hpc
   python workflow.py   # Session auto-detects from env

The resolution order is: explicit ``target=`` argument → ``SCALABLE_TARGET``
env var → error (no implicit default target).

Step 9: Programmatic Validation
--------------------------------

You can validate manifests from Python for CI/CD integration:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   report = session.validate()

   if report.ok:
       print("Manifest is valid")
   else:
       for issue in report.errors:
           print(f"ERROR [{issue.code}] {issue.path}: {issue.message}")
       for issue in report.warnings:
           print(f"WARN  [{issue.code}] {issue.path}: {issue.message}")

Common error codes:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Code
     - Meaning
   * - ``E_MISSING_KEY``
     - A required key (``version``, ``project``) is absent.
   * - ``E_BAD_VERSION``
     - ``version`` is not a supported schema version.
   * - ``E_UNKNOWN_TOP_KEY``
     - Unrecognized top-level key (probable typo).
   * - ``E_UNKNOWN_COMPONENT_KEY``
     - Unrecognized key inside a component definition.
   * - ``E_TASK_COMPONENT_REF``
     - A task references a component that does not exist.
   * - ``E_UNKNOWN_PROVIDER``
     - The target's provider is not installed or registered.
   * - ``E_BAD_MAX_WORKERS``
     - ``max_workers`` is not a positive integer.

Step 10: Complete Multi-Target Manifest
----------------------------------------

Here is a production-ready manifest combining all concepts:

.. code-block:: yaml

   version: 1
   project:
     name: climate-pipeline
     default_storage: ${ARTIFACT_STORAGE:-./outputs}

   targets:
     local:
       provider: local
       max_workers: 4
       threads_per_worker: 2
       processes: false
       containers: none

     hpc:
       provider: slurm
       queue: batch
       account: ${SLURM_ACCOUNT}
       walltime: "08:00:00"
       interface: ib0
       overlay: hpc-prod

     aws:
       provider: aws
       region: ${AWS_REGION:-us-east-1}
       cluster_type: fargate
       worker_cpu: 4096
       worker_mem: 16384
       image: ${ECR_IMAGE}
       execution_role_arn: ${EXECUTION_ROLE_ARN}
       task_role_arn: ${TASK_ROLE_ARN}
       subnets: [${SUBNET_A}, ${SUBNET_B}]
       security_groups: [${SG_ID}]
       adaptive:
         minimum: 2
         maximum: 20

   components:
     gcam:
       image: ghcr.io/jgcri/gcam:7.0
       cpus: 4
       memory: 16G
       tags: [iam, climate]
       env:
         GCAM_DATA: /gcam-core/data

     postprocess:
       cpus: 2
       memory: 8G
       tags: [analysis]

   tasks:
     run_gcam:
       component: gcam
       cache: true
       outputs:
         database: dir

     aggregate:
       component: postprocess
       cache: true

   overlays:
     hpc-prod:
       components:
         gcam:
           cpus: 16
           memory: 64G
         postprocess:
           cpus: 8
           memory: 32G

     hpc-debug:
       components:
         gcam:
           cpus: 2
           memory: 4G
         postprocess:
           cpus: 1
           memory: 2G

Troubleshooting
---------------

**"ManifestParseError: unresolved variable ${VAR}"**
  You used ``${VAR}`` without a default and the variable is not set in the
  environment. Either export it or use ``${VAR:-fallback}``.

**"ManifestSchemaError: unknown component key 'gpu'"**
  Only recognized component keys are allowed. GPU scheduling is expressed via
  the provider-specific target options, not component definitions.

**Overlay changes not taking effect**
  Ensure the target block includes ``overlay: <name>`` and that the overlay
  name exactly matches a key under ``overlays:``. Overlay merging only applies
  to the selected target.

**"version: 2" rejected**
  Only schema version ``1`` is currently supported. The ``version`` field
  exists for future-proofing.

Next Steps
----------

* :ref:`tutorial_scaling_strategies` — Learn how different providers scale
  workers and how to choose between them.
* :ref:`tutorial_caching` — Cache expensive computations to accelerate
  iterative development.
* :ref:`tutorial_cloud_integration` — Configure AWS and GCP targets with
  real credentials and IAM roles.
