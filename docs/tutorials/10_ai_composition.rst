.. _tutorial_ai_composition:

======================================================
Tutorial 10: AI-Assisted Workflow Composition
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Use the AI assistant suite to accelerate workflow development.
* Onboard new model components with ``scalable init-component``.
* Diagnose run failures with ``scalable diagnose``.
* Generate human-readable explanations of execution plans.
* Compose new workflows from natural language descriptions.
* Migrate manifests between providers with ``scalable migrate``.
* Understand heuristic mode vs. LLM-enhanced mode.

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started` and :ref:`tutorial_manifest_system`.
* ``pip install scalable[ai]`` (installs ``jinja2``, ``rich``).
* For LLM-enhanced mode (optional): an API key for OpenAI or a running
  Ollama instance.

Scenario
--------

Your team is onboarding a new model (Stitches) into the climate pipeline.
You need to configure its component definition, write task bindings, and
eventually migrate the entire pipeline from Slurm to Kubernetes. The AI
assistants automate tedious configuration tasks and provide expert guidance
without requiring deep Scalable expertise.

Step 1: Heuristic vs. LLM Modes
---------------------------------

All AI assistants work in two modes:

**Heuristic mode (``--no-ai``, default when ``SCALABLE_AI_BACKEND=none``):**

* Uses deterministic rules, templates, and pattern matching.
* No external API calls. Works offline.
* Fast, reproducible, and auditable.
* Best for CI/CD and automated pipelines.

**LLM-enhanced mode (``SCALABLE_AI_BACKEND=openai`` or ``ollama``):**

* Augments heuristics with a language model for richer explanations and
  more creative workflow composition.
* Requires API credentials and network access.
* May produce varied output across invocations.
* Best for interactive development and exploration.

Configure the backend:

.. code-block:: bash

   # Heuristic only (default)
   export SCALABLE_AI_BACKEND=none

   # OpenAI
   export SCALABLE_AI_BACKEND=openai
   export SCALABLE_AI_MODEL=gpt-4
   export OPENAI_API_KEY=sk-...

   # Ollama (local)
   export SCALABLE_AI_BACKEND=ollama
   export SCALABLE_AI_MODEL=llama3
   export SCALABLE_AI_ENDPOINT=http://localhost:11434

Step 2: Onboarding a New Component
------------------------------------

The ``init-component`` command analyzes a model directory and generates a
component configuration:

.. code-block:: bash

   scalable init-component ./path/to/stitches --name stitches --no-ai

.. code-block:: text

   Analyzing ./path/to/stitches...
   Detected:
     Language: R (via rpy2)
     Dependencies: stitches, dplyr, tidyr
     Entry point: ./run_stitches.R
     Estimated resources: 6 CPUs, 50G memory

   Generated component configuration:

   components:
     stitches:
       image: ghcr.io/jgcri/stitches:latest
       cpus: 6
       memory: 50G
       tags: [climate, downscaling]
       env:
         R_LIBS_USER: /opt/R/library

   Suggested task binding:

   tasks:
     run_stitches:
       component: stitches
       cache: true

   Written to: ./stitches/scalable-component.yaml

**What the analyzer checks:**

* Language detection (Python imports, R scripts, compiled binaries).
* Dependency scanning (``requirements.txt``, ``DESCRIPTION``, ``Makefile``).
* Resource estimation from file sizes and known model profiles.
* Container image inference from Dockerfiles or registry naming conventions.

Python API:

.. code-block:: python

   from scalable.ai import onboard_component

   result = onboard_component(
       "./path/to/stitches",
       name="stitches",
       no_ai=True,
   )

   print(result.component_yaml)
   print(result.task_yaml)
   print(result.recommendations)

Step 3: Diagnosing Run Failures
---------------------------------

After a failed run, use the diagnostic assistant to identify root causes:

.. code-block:: bash

   scalable diagnose --latest --no-ai

.. code-block:: text

   ═══════════════════════════════════════════════════════════
   Diagnosis: run-20260520T041500Z-climate-pipeline-f8e2a1b3
   ═══════════════════════════════════════════════════════════

   Status: failed (13 task failures)

   Root Cause Analysis:
   ─────────────────────
   PRIMARY: Memory exhaustion (8 of 13 failures)
     Pattern: Tasks processing scenarios with >500 grid cells exhaust
     the 16G memory limit during the spatial interpolation step.
     Evidence: All OOM failures occur in run_gcam tasks with
     input_grid_cells > 500.

   SECONDARY: Network timeouts (3 of 13 failures)
     Pattern: External data API (api.climate-data.org) returning 503
     between 04:15-04:20 UTC.
     Evidence: All timeout failures cluster within a 5-minute window.

   TERTIARY: Serialization error (2 of 13 failures)
     Pattern: Return value contains unpicklable threading.Lock object.
     Evidence: TypeError in dill serialization.

   Recommendations:
   ─────────────────
   1. Increase gcam component memory to 32G (or use overlay for
      high-resolution scenarios).
   2. Add retry logic with exponential backoff for external API calls.
   3. Remove threading.Lock from return values — use result dict only.

Programmatic access:

.. code-block:: python

   from scalable.ai import diagnose_run

   result = diagnose_run(
       run_dir=".scalable/runs/run-20260520T041500Z.../",
       no_ai=True,
   )

   print(f"Root cause: {result.summary}")
   for finding in result.findings:
       print(f"  [{finding.severity}] {finding.category}")
       print(f"    Pattern: {finding.pattern}")
       print(f"    Suggestion: {finding.suggestion}")

Step 4: Explaining Execution Plans
------------------------------------

Make execution plans understandable for non-technical stakeholders:

.. code-block:: bash

   # Generate a plan
   scalable plan ./scalable.yaml --target aws --dry-run --output plan.json

   # Explain it in plain language
   scalable explain plan.json

.. code-block:: text

   Plan Explanation
   ═════════════════

   This plan will execute the "climate-pipeline" project on AWS (Fargate)
   in the us-east-1 region.

   What will happen:
   1. A Dask cluster will be created with 10 workers running GCAM (4 vCPU,
      16 GiB each) and 5 workers for post-processing (2 vCPU, 8 GiB each).
   2. Workers auto-scale between 2 (minimum) and 20 (maximum) based on
      task backlog.
   3. Results will be cached to avoid recomputation on retry.
   4. Outputs will be stored in s3://my-bucket/scalable-runs/.

   Estimated cost: $4.82 (2.5 hours of Fargate compute + S3 storage)

   Risks:
   • Network connectivity between scheduler and workers depends on VPC
     routing. Verify subnets have NAT gateway access.
   • Fargate cold-start adds 30-90s to first task execution.

Python API:

.. code-block:: python

   from scalable.ai import explain_plan

   result = explain_plan("plan.json")
   print(result.explanation)
   print(result.risks)
   print(result.cost_summary)

Step 5: Composing Workflows from Natural Language
---------------------------------------------------

The most powerful AI assistant — generate complete workflow configurations
from descriptions:

.. code-block:: bash

   scalable compose "Run GCAM reference scenario for SSP2, \
     then run Stitches to downscale daily climate data, \
     then aggregate results by region and produce summary plots"

.. code-block:: text

   Generated workflow:
   ═══════════════════

   # workflow.py
   from scalable import ScalableSession, cacheable

   @cacheable(return_type=dict, ssp=str)
   def run_gcam_reference(ssp: str) -> dict:
       """Run GCAM reference scenario for the given SSP."""
       # TODO: Implement GCAM execution logic
       return {"database_path": f"./output/gcam_{ssp}/"}

   @cacheable(return_type=dict, gcam_output=str)
   def run_stitches_downscale(gcam_output: str) -> dict:
       """Downscale GCAM output to daily climate using Stitches."""
       # TODO: Implement Stitches execution logic
       return {"daily_climate_path": f"./output/stitches/{gcam_output}"}

   @cacheable(return_type=dict, climate_path=str)
   def aggregate_and_plot(climate_path: str) -> dict:
       """Aggregate by region and produce summary plots."""
       # TODO: Implement aggregation logic
       return {"summary_path": "./output/summary/"}

   def main():
       session = ScalableSession.from_yaml("./scalable.yaml", target="local")
       client = session.start()

       # Stage 1: GCAM
       gcam_result = client.submit(run_gcam_reference, "SSP2", tag="gcam").result()

       # Stage 2: Stitches downscaling
       stitches_result = client.submit(
           run_stitches_downscale,
           gcam_result["database_path"],
           tag="stitches",
       ).result()

       # Stage 3: Aggregation
       final = client.submit(
           aggregate_and_plot,
           stitches_result["daily_climate_path"],
           tag="postprocess",
       ).result()

       print(f"Pipeline complete: {final['summary_path']}")
       session.close()

   if __name__ == "__main__":
       main()

   ═══════════════════
   Suggested manifest additions:

   components:
     gcam:
       cpus: 8
       memory: 32G
       tags: [iam, climate]
     stitches:
       cpus: 6
       memory: 50G
       tags: [climate, downscaling]
     postprocess:
       cpus: 2
       memory: 8G
       tags: [analysis]

   tasks:
     run_gcam_reference:
       component: gcam
       cache: true
     run_stitches_downscale:
       component: stitches
       cache: true
     aggregate_and_plot:
       component: postprocess
       cache: true

Python API for programmatic composition:

.. code-block:: python

   from scalable.ai import compose_workflow

   result = compose_workflow(
       "Run GCAM for SSP1-5, then Stitches for each, then aggregate"
   )

   print(result.workflow_code)
   print(result.manifest_additions)
   print(result.dependencies)

Step 6: Migrating Between Providers
-------------------------------------

Move your workflow from one provider to another:

.. code-block:: bash

   scalable migrate scalable.yaml --to-provider kubernetes

.. code-block:: text

   Migration: slurm → kubernetes
   ══════════════════════════════

   Changes required:
   1. Target 'hpc' → new target 'k8s'
      - Remove: queue, account, walltime, interface
      - Add: namespace, image, adaptive

   2. Components need container images:
      - gcam: needs 'image' field (suggest: gcr.io/project/gcam:7.0)
      - postprocess: needs 'image' field (suggest: gcr.io/project/postprocess:latest)

   3. Environment changes:
      - Slurm module loads → container pre-installed
      - File system mounts → PVC or GCS bucket

   Generated manifest:

   targets:
     k8s:
       provider: kubernetes
       namespace: climate-prod
       image: gcr.io/my-project/climate-model:latest
       adaptive:
         minimum: 2
         maximum: 20

   components:
     gcam:
       image: gcr.io/my-project/gcam:7.0
       cpus: 8
       memory: 32G
       tags: [iam, climate]
       env:
         GCAM_DATA: /data/gcam

     postprocess:
       image: gcr.io/my-project/postprocess:latest
       cpus: 4
       memory: 16G
       tags: [analysis]

   Migration notes:
   • Apptainer mounts must be converted to Kubernetes PVC mounts.
   • Walltime is replaced by pod timeout annotations.
   • Network interface (ib0) is irrelevant for Kubernetes — remove.

Python API:

.. code-block:: python

   from scalable.ai import migrate_manifest

   result = migrate_manifest(
       "scalable.yaml",
       to_provider="kubernetes",
   )

   print(result.migrated_yaml)
   print(result.changes_summary)
   print(result.migration_notes)

Step 7: Integration into Development Workflow
----------------------------------------------

Combine AI assistants into a smooth development loop:

.. code-block:: bash

   # 1. Onboard a new model
   scalable init-component ./new-model --name new-model

   # 2. Compose a workflow incorporating it
   scalable compose "Run existing pipeline then feed results to new-model"

   # 3. Validate the generated configuration
   scalable validate ./scalable.yaml

   # 4. Plan and review (explain for team review)
   scalable plan ./scalable.yaml --target local --dry-run --output plan.json
   scalable explain plan.json

   # 5. Run locally
   scalable run ./scalable.yaml --target local --workflow workflow.py

   # 6. If it fails, diagnose
   scalable diagnose --latest

   # 7. When ready for production, migrate
   scalable migrate scalable.yaml --to-provider kubernetes

Step 8: Customizing AI Heuristics
----------------------------------

The heuristic mode uses rule-based templates that you can inspect and
influence:

.. code-block:: python

   from scalable.ai.heuristics import (
       detect_language,
       estimate_resources,
       suggest_component_config,
   )

   # Language detection
   lang = detect_language("./path/to/model")
   print(f"Detected: {lang}")  # "python", "r", "compiled"

   # Resource estimation from known model profiles
   resources = estimate_resources(
       model_name="gcam",
       input_size_mb=2048,
       num_scenarios=50,
   )
   print(f"Estimated: {resources}")
   # {'cpus': 8, 'memory': '32G', 'walltime': '03:00:00'}

The heuristics are deterministic — same input always produces same output.
This makes them suitable for automated CI/CD pipelines where reproducibility
matters.

Step 9: LLM-Enhanced Mode
---------------------------

For richer, context-aware responses, enable an LLM backend:

.. code-block:: bash

   export SCALABLE_AI_BACKEND=openai
   export SCALABLE_AI_MODEL=gpt-4
   export OPENAI_API_KEY=sk-...

   # Now compose generates more detailed, context-aware workflows
   scalable compose "Build a multi-model ensemble that runs GCAM, Hector, \
     and MAGICC in parallel, compares their climate projections, and \
     produces a weighted average based on historical skill scores"

LLM-enhanced mode adds:

* More detailed code comments and documentation.
* Context-aware parameter suggestions based on model documentation.
* Richer error explanations with links to relevant resources.
* More creative workflow architectures for complex descriptions.

**Important:** LLM output is non-deterministic. For reproducible pipelines,
always use ``--no-ai`` (heuristic mode) in CI/CD.

Step 10: Validating AI-Generated Output
-----------------------------------------

Always validate AI-generated configurations before running:

.. code-block:: python

   from scalable.ai import compose_workflow
   from scalable import ScalableSession

   # Generate workflow
   result = compose_workflow("Run GCAM for all SSPs then aggregate")

   # Write generated manifest additions
   # (merge with your existing scalable.yaml)

   # Validate the result
   session = ScalableSession.from_yaml("./scalable.yaml", target="local")
   report = session.validate()

   if not report.ok:
       print("Generated config has issues:")
       for issue in report.errors:
           print(f"  [{issue.code}] {issue.path}: {issue.message}")
       # Fix issues and re-validate
   else:
       print("Generated config is valid — ready to run")

Troubleshooting
---------------

**"ImportError: jinja2 not installed"**
  Install the AI extra: ``pip install scalable[ai]``.

**AI assistant gives unhelpful generic responses**
  In heuristic mode, the assistant relies on pattern matching. Provide more
  specific input — e.g., a directory with actual code rather than an empty
  scaffold.

**LLM mode is slow**
  LLM API calls typically take 5–30 seconds. For quick iteration, use
  ``--no-ai`` for heuristic mode and only switch to LLM mode for complex
  composition tasks.

**"SCALABLE_AI_BACKEND=openai but no OPENAI_API_KEY"**
  Set your API key: ``export OPENAI_API_KEY=sk-...``. The error is raised
  at call time, not import time.

**Generated workflow has TODO placeholders**
  The AI generates a skeleton with ``# TODO`` markers where domain-specific
  logic belongs. Fill in the function bodies with your actual model execution
  code.

**Migration suggests incompatible changes**
  Migration is advisory — it shows what needs to change but cannot verify that
  cloud infrastructure exists. Always validate the migrated manifest and test
  with ``--dry-run`` before production deployment.

Next Steps
----------

* :ref:`tutorial_getting_started` — If you're new, start from the beginning
  for full context.
* :ref:`tutorial_manifest_system` — Deep-dive into the manifest schema that
  AI assistants generate.
* :ref:`tutorial_kubernetes` — Deploy AI-generated Kubernetes configurations.
* :ref:`tutorial_ml_advanced` — Combine AI composition with ML-driven
  resource optimization.
