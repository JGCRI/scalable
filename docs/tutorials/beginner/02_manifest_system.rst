.. _beginner_manifest_system:

======================================================
Beginner Tutorial 2: Understanding the Manifest System
======================================================

.. contents:: In This Tutorial
   :local:
   :depth: 2

The Big Picture
----------------

In the previous tutorial, you wrote a simple ``scalable.yaml`` file. But what
*is* a manifest, really? Why does Scalable use one? And what's this
"declarative programming" idea all about?

This tutorial takes you deep into the manifest system — not just the syntax,
but the *philosophy* behind it. You'll understand why configuration-as-code
exists, how YAML works, what schemas enforce, and how overlays let you
customize behavior across different environments.

.. admonition:: 💡 Key Concept: Configuration as Code
   :class: tip

   **Configuration as code** means storing your system's settings in version-
   controlled text files rather than clicking through GUIs or typing ad-hoc
   commands.

   Benefits:

   * **Reproducibility** — anyone can recreate your exact setup
   * **History** — Git shows who changed what and when
   * **Review** — teammates can review config changes like code changes
   * **Automation** — CI/CD pipelines can validate and deploy configs

   Scalable's manifest is configuration as code: your entire workflow setup
   lives in a single YAML file that you check into version control.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand declarative programming deeply and why it matters.
* Read and write YAML confidently (indentation, data types, references).
* Know every section of a ``scalable.yaml`` manifest and its purpose.
* Use environment variables in manifests for portability.
* Define multiple targets for different environments.
* Apply overlays to customize settings per deployment.
* Validate manifests and interpret error messages.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started`.
* Scalable installed (``pip install scalable``).
* A text editor and terminal.


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: Declarative Programming (Deep Dive)
   :class: tip

   In :ref:`beginner_getting_started`, we introduced declarative vs. imperative.
   Let's go deeper with a real example.

   **Imperative approach** to setting up 4 workers:

   .. code-block:: python

      # Pseudocode: imperative style
      for i in range(4):
          worker = start_process()
          worker.set_memory("4G")
          worker.set_cpus(2)
          worker.connect_to_scheduler(scheduler_address)
          if not worker.is_healthy():
              worker.restart()

   **Declarative approach** (what Scalable uses):

   .. code-block:: yaml

      targets:
        local:
          provider: local
          max_workers: 4
      components:
        analysis:
          cpus: 2
          memory: 4G

   The declarative version doesn't say *how* to start workers — it says
   *what state you want*. Scalable's runtime figures out the "how."

   **Why is declarative better here?**

   1. **Portability** — The same declaration works on your laptop or a
      1000-node cluster. The "how" differs, but the "what" doesn't.
   2. **Idempotency** — You can apply the same manifest repeatedly; the
      system converges to the desired state without duplicating resources.
   3. **Separation of concerns** — You (the scientist) declare what you
      need; the platform (Scalable) handles infrastructure details.

.. admonition:: 💡 Key Concept: YAML Syntax
   :class: tip

   YAML is a data serialization format designed to be human-readable. Here
   are the essential rules:

   **Indentation matters** (use spaces, NEVER tabs):

   .. code-block:: yaml

      parent:
        child: value      # 2-space indent = child of "parent"
        another: value2

   **Data types** are inferred:

   .. code-block:: yaml

      string_value: hello         # String
      number_value: 42            # Integer
      float_value: 3.14           # Float
      boolean_value: true         # Boolean (true/false)
      quoted_string: "04:00:00"   # Quoted to prevent time interpretation
      null_value: null            # Null/None

   **Lists** use dashes:

   .. code-block:: yaml

      fruits:
        - apple
        - banana
        - cherry

   **Nested maps**:

   .. code-block:: yaml

      targets:
        local:
          provider: local
          max_workers: 2

   **Comments** start with ``#``.

   **Common mistakes:**

   * Using tabs instead of spaces (causes parse errors)
   * Inconsistent indentation (2 spaces is conventional)
   * Forgetting to quote strings that look like other types
     (``version: 1`` is a number, ``version: "1"`` is a string)

.. admonition:: 💡 Key Concept: Schema
   :class: tip

   A **schema** defines the valid structure for data. Think of it like a
   form with labeled fields — some fields are required, some are optional,
   and each has rules about what values are acceptable.

   For Scalable's manifest:

   * ``version`` is required and must be an integer
   * ``project.name`` is required and must be a string
   * ``targets`` must be a map where each value has a ``provider`` key
   * ``components`` must have ``cpus`` and ``memory`` keys

   The schema catches errors *before* you run (fail fast), saving you from
   discovering problems 30 minutes into an expensive cloud run.

.. admonition:: 💡 Key Concept: Environment Variables
   :class: tip

   **Environment variables** are system-level settings available to all
   programs. They store configuration that varies between machines or users:

   .. code-block:: bash

      # Setting an environment variable
      export AWS_REGION=us-east-1

      # Reading it in a program
      echo $AWS_REGION   # Prints: us-east-1

   In Scalable manifests, you can reference them with ``${VAR_NAME}``
   syntax. This keeps secrets (API keys, passwords) out of your config
   files and makes manifests portable across environments.

.. admonition:: 💡 Key Concept: Single Source of Truth
   :class: tip

   The **single source of truth** (SSOT) principle means there's exactly one
   authoritative place where a piece of information lives. If you need to
   change something, you change it in one place, and everything else picks
   up the change.

   The manifest is Scalable's SSOT for workflow configuration. You don't
   need to remember "I set max_workers in the CLI, memory in an env var,
   and the image in a script." It's all in one file.


Step 1: The Complete Manifest Structure
-----------------------------------------

Every ``scalable.yaml`` manifest has this top-level structure:

.. code-block:: yaml

   version: 1              # Required: schema version
   project: { ... }        # Required: project metadata
   targets: { ... }        # Required: where code runs
   components: { ... }     # Required: resource profiles
   tasks: { ... }          # Required: work unit definitions
   overlays: { ... }       # Optional: environment-specific overrides

Let's explore each section in depth.


Step 2: The Project Block
---------------------------

.. code-block:: yaml

   project:
     name: energy-forecast
     default_storage: ./outputs
     local_cache: ./cache

**What each key does:**

``name``
   A human-readable identifier for your project. It appears in:

   * Telemetry run IDs (e.g., ``run-20260520T...-energy-forecast-a1b2c3d4``)
   * Log messages
   * Artifact storage paths

   Use lowercase with hyphens (``my-project``, not ``My Project``).

``default_storage``
   Where output artifacts are saved. Can be:

   * A local path: ``./outputs``
   * An S3 URI: ``s3://my-bucket/scalable-runs/``
   * A GCS URI: ``gs://my-bucket/scalable-runs/``

``local_cache``
   Where cached results are stored locally. Defaults to ``./cache``. Can also
   be set via the ``SCALABLE_CACHE_DIR`` environment variable (the manifest
   value takes precedence).


Step 3: Defining Targets
--------------------------

Targets answer the question: **"Where does my code run?"**

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
       image: 123456789.dkr.ecr.us-east-1.amazonaws.com/energy-model:latest
       adaptive:
         minimum: 1
         maximum: 10

.. admonition:: 💡 Key Concept: Provider Pattern
   :class: tip

   A **provider** is an abstraction over an execution backend. It's like an
   electrical outlet standard — you can plug any appliance into any outlet
   because they share a common interface.

   Scalable's providers share a common interface but work differently
   internally:

   * ``local`` — spawns workers on your machine
   * ``slurm`` — submits jobs to an HPC scheduler
   * ``aws`` — launches containers on AWS Fargate/EC2
   * ``kubernetes`` — creates pods in a K8s cluster

   **Why multiple targets in one file?** A single manifest can describe your
   entire promotion path:

   1. Develop locally (``--target local``)
   2. Validate on HPC (``--target hpc``)
   3. Deploy to cloud (``--target aws``)

   The ``--target`` flag (or ``SCALABLE_TARGET`` env var) selects which
   environment to activate.

**Key options by provider:**

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Provider
     - Key Options
   * - ``local``
     - ``max_workers``, ``threads_per_worker``, ``processes``, ``containers``
   * - ``slurm``
     - ``queue``, ``account``, ``walltime``, ``interface``
   * - ``aws``
     - ``region``, ``cluster_type``, ``instance_type``, ``worker_cpu``,
       ``worker_mem``, ``image``, ``adaptive``
   * - ``kubernetes``
     - ``namespace``, ``image``, ``adaptive``, ``overlay``


Step 4: Components — Resource Profiles
----------------------------------------

Components define how much computational resources each piece of work needs:

.. code-block:: yaml

   components:
     gridlabd:
       image: ghcr.io/gridlab-d/gridlabd:5.0
       runtime: apptainer
       cpus: 8
       memory: 32G
       mounts:
         /data/gridlabd: /gridlabd-core
         /shared/outputs: /outputs
       env:
         GRIDLABD_DATA: /gridlabd-core/data
       tags: [multi-sector-dynamics, energy]

     postprocess:
       cpus: 2
       memory: 4G
       tags: [analysis]

.. admonition:: Why not just specify resources per task directly?
   :class: hint

   Separating components from tasks follows the **DRY principle** (Don't
   Repeat Yourself). If 20 tasks all need the same resources, you define
   the component once and reference it 20 times. Change the resource
   allocation in one place → all 20 tasks update.

**Component keys explained:**

``cpus``
   Number of CPU cores allocated per worker. Maps to Dask worker resource
   annotations.

``memory``
   Memory allocation (e.g., ``32G``, ``512M``, ``2T``). Parsed using standard
   byte suffixes.

``image`` (optional)
   Container image URI for containerized providers. Ignored for bare-metal
   local runs.

``runtime`` (optional)
   Container runtime hint: ``apptainer`` (HPC) or ``docker`` (cloud/local).

``mounts`` (optional)
   Volume mappings (host path → container path). Only meaningful for
   containerized runs.

``env`` (optional)
   Environment variables injected into the worker process. Useful for model
   paths or configuration.

``tags`` (optional)
   Labels for grouping and filtering. Appear in telemetry and can inform
   resource recommendations.


Step 5: Task Bindings
-----------------------

Tasks connect your Python functions to resource profiles:

.. code-block:: yaml

   tasks:
     run_gridlabd:
       component: gridlabd

     aggregate_demand:
       component: postprocess

When you write Python code like:

.. code-block:: python

   client.submit(my_function, args, tag="gridlabd")

Scalable looks up the ``run_gridlabd`` task, finds it uses the ``gridlabd``
component, and schedules it on a worker with 8 CPUs and 32G memory.

.. admonition:: 💡 Key Concept: Binding
   :class: tip

   **Binding** means creating a connection between two things. Here, we bind:

   * Task name → component (resource profile)
   * Python function → task name (at submit time)

   This indirection lets you change resource allocations without touching
   your Python code, and vice versa.


Step 6: Environment Variable Expansion
----------------------------------------

Manifests support ``${VAR}`` syntax for environment variables:

.. code-block:: yaml

   project:
     name: energy-model
     default_storage: s3://${S3_BUCKET}/scalable-runs/

   targets:
     aws:
       provider: aws
       region: ${AWS_REGION:-us-east-1}

The ``${AWS_REGION:-us-east-1}`` syntax means "use the ``AWS_REGION``
environment variable if set, otherwise default to ``us-east-1``."

.. admonition:: Why use environment variables instead of hardcoding?
   :class: hint

   * **Security** — Keep secrets (API keys, bucket names) out of Git
   * **Portability** — Same manifest works across team members and CI/CD
   * **12-Factor compliance** — Configuration should come from the environment
     (a best practice from the `Twelve-Factor App <https://12factor.net/>`_
     methodology)


Step 7: Overlays — Environment-Specific Customization
------------------------------------------------------

.. admonition:: 💡 Key Concept: Overlays
   :class: tip

   An **overlay** is a set of patches applied on top of a base configuration.
   Think of it like Photoshop layers — you have a base image (your manifest)
   and layers that add or modify specific parts.

   **Why overlays?** You might want:

   * Development: 2 workers, 1G memory, local storage
   * Production: 64 workers, 32G memory, S3 storage
   * CI testing: 1 worker, minimal memory, ephemeral storage

   Rather than maintaining 3 separate manifests (which drift apart over
   time), you maintain ONE base manifest + overlays for differences.

.. code-block:: yaml

   # In the manifest itself
   overlays:
     production:
       targets:
         hpc:
           max_workers: 64
       components:
         gridlabd:
           memory: 64G

     ci:
       targets:
         local:
           max_workers: 1
       components:
         gridlabd:
           memory: 2G
           cpus: 1

To apply an overlay:

.. code-block:: bash

   scalable run ./scalable.yaml --target hpc --overlay production

The overlay merges on top of the base configuration — only the keys specified
in the overlay are changed; everything else stays the same.

.. admonition:: 💡 Key Concept: Deep Merge
   :class: tip

   **Deep merge** means overlays are applied recursively. If your overlay
   specifies ``components.gridlabd.memory: 64G``, it only changes that one
   field — all other ``gridlabd`` settings (``cpus``, ``image``, ``mounts``)
   remain as defined in the base manifest.

   This is different from a **shallow merge** where replacing any key in a
   section would replace the entire section.


Step 8: Programmatic Validation
---------------------------------

You've used ``scalable validate`` from the CLI. You can also validate from
Python:

.. code-block:: python

   from scalable.manifest.parser import load_manifest
   from scalable.manifest.validate import validate_manifest

   # Parse the YAML into a structured object
   manifest = load_manifest("./scalable.yaml")

   # Validate returns a list of errors (empty = valid)
   report = validate_manifest(manifest)

   if not report.ok:
       for issue in report.errors:
           print(f"ERROR: {err}")
   else:
       print("✓ Manifest is valid")

.. admonition:: 💡 Key Concept: Parse vs. Validate
   :class: tip

   These are two distinct steps:

   1. **Parsing** = reading the YAML text and converting it to a Python data
      structure (dict). This catches syntax errors (bad indentation, invalid
      YAML).

   2. **Validating** = checking that the parsed data meets the schema rules.
      This catches semantic errors (missing required fields, invalid
      references, type mismatches).

   You need both: a YAML file can be syntactically valid but semantically
   wrong (like a grammatically correct sentence that makes no sense).


Common Questions
-----------------

**Q: Can I split my manifest into multiple files?**

Not directly — the manifest is a single source of truth. But overlays let you
customize per environment, and environment variables let you inject external
values. This keeps the manifest self-contained and auditable.

**Q: What if I make a typo in a component key?**

The validator catches it. Unknown keys inside ``components`` are rejected
(strict schema). Unknown keys inside ``targets`` are passed through to the
provider (forward compatibility), but invalid provider-specific keys will
fail at runtime with a clear error message.

**Q: YAML vs. JSON vs. TOML — why YAML?**

* **JSON** — No comments, verbose (lots of brackets/braces), hard to edit by hand
* **TOML** — Good for flat config, awkward for deeply nested structures
* **YAML** — Human-readable, supports comments, good for nested data, widely
  used in DevOps (Docker Compose, Kubernetes, GitHub Actions)

The downside of YAML (indentation sensitivity) is mitigated by validation.

**Q: What's the difference between ``project.default_storage`` and
``project.local_cache``?**

* ``default_storage`` = where **outputs** go (can be remote: S3, GCS)
* ``local_cache`` = where **cached intermediate results** are stored (always
  local, for speed)


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Declarative Programming
     - Describing *what* you want rather than *how* to achieve it
   * - YAML
     - Human-readable data serialization format using indentation
   * - Schema
     - Rules defining valid structure for data
   * - Environment Variables
     - System-level key-value settings available to programs
   * - Single Source of Truth
     - One authoritative location for configuration
   * - Provider
     - Abstraction over an execution backend
   * - Overlay
     - Patches applied on top of base configuration
   * - Deep Merge
     - Recursive combination where only specified keys are overridden
   * - Binding
     - Connecting a task name to a component (resource profile)
   * - Parsing
     - Converting text (YAML) into structured data (Python dict)
   * - Validation
     - Checking that structured data meets schema rules
   * - Configuration as Code
     - Storing settings in version-controlled text files


Next Steps
-----------

You now understand how Scalable's manifest system works and the philosophy
behind declarative configuration.

* **Next beginner tutorial:** :ref:`beginner_scaling_strategies` — how
  distributed computing actually works
* **Standard tutorial:** :ref:`tutorial_manifest_system` — advanced manifest
  patterns and production deployment
* **Try it:** Add a second target (copy the ``local`` target, name it
  ``dev``, and change ``max_workers`` to 1). Validate it. Try adding an
  overlay that doubles the memory for production.
