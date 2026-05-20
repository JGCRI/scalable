.. _beginner_ai_composition:

======================================================
Beginner Tutorial 10: AI-Assisted Workflow Development
======================================================

.. contents:: In This Tutorial
   :local:
   :depth: 2

The Big Picture
----------------

Writing configuration files, diagnosing errors, and composing workflows
requires expertise — you need to know Scalable's manifest schema, provider
options, component settings, and best practices. What if an AI assistant
could help with these tasks?

Scalable includes AI-powered assistants that can onboard new model components,
diagnose run failures, explain execution plans, compose workflows from
descriptions, and migrate between providers. These assistants work in two
modes: a fast deterministic mode (heuristics) and an intelligent LLM-powered
mode.

This tutorial explains what LLMs are, how Scalable uses them, and how to
leverage AI assistance in your workflow development.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand what Large Language Models (LLMs) are at a high level.
* Know the difference between heuristic and LLM-powered modes.
* Use ``scalable init-component`` to onboard new models.
* Use ``scalable diagnose`` to analyze failures.
* Use ``scalable explain`` to understand execution plans.
* Use ``scalable compose`` to generate workflows from descriptions.
* Use ``scalable migrate`` to convert between providers.
* Understand when to trust (and verify) AI-generated output.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started` and :ref:`beginner_manifest_system`.
* ``pip install scalable[ai]`` (installs ``jinja2``, ``rich``).
* For LLM mode (optional): an API key for OpenAI, or a running Ollama instance.
* Heuristic mode works without any AI setup.


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: What is a Large Language Model (LLM)?
   :class: tip

   A **Large Language Model** is an AI system trained on massive amounts of
   text data that can generate human-like text, answer questions, and perform
   reasoning tasks.

   **How LLMs work (simplified):**

   1. Trained on billions of words from the internet (books, code,
      documentation)
   2. Learns patterns: "given this input text, what text is likely to
      come next?"
   3. At inference time: given your prompt (question), generates a response
      word by word, each word chosen based on what's most likely to follow

   **Examples:** ChatGPT (OpenAI), Claude (Anthropic), Llama (Meta),
   Gemini (Google)

   **Key properties:**

   * Can generate configuration files, code, explanations
   * Not deterministic — same input may give slightly different outputs
   * Can be wrong (hallucination) — always verify output
   * Requires API access (cloud) or local hardware (Ollama)

.. admonition:: 💡 Key Concept: Heuristic vs. AI-Powered
   :class: tip

   Scalable's assistants work in two modes:

   **Heuristic mode** (rules-based):
     * Uses predefined rules, templates, and pattern matching
     * Deterministic: same input → always same output
     * Works offline (no API calls)
     * Fast and free
     * Best for: CI/CD pipelines, reproducible outputs, no AI budget

   **LLM-enhanced mode** (AI-powered):
     * Uses an LLM for intelligent generation and reasoning
     * Non-deterministic: may give slightly different outputs
     * Requires API access (and costs money per call)
     * Slower but more flexible
     * Best for: creative composition, complex diagnosis, migration

   **Why both?** Heuristic mode ensures Scalable works without external
   dependencies. LLM mode adds intelligence for complex tasks. The system
   gracefully degrades: if the LLM is unavailable, it falls back to
   heuristics.

.. admonition:: 💡 Key Concept: Templates
   :class: tip

   A **template** is a pre-structured document with placeholders that get
   filled in with specific values. Think of it like a form letter:

   .. code-block:: text

      Dear {{ name }},
      Your order of {{ item }} will arrive on {{ date }}.

   In Scalable's AI assistants:

   * Heuristic mode uses templates extensively (predictable, fast)
   * LLM mode uses templates as "prompts" — instructions to the AI about
     what to generate

   Templates use **Jinja2** syntax (``{{ variable }}``, ``{% if %}``)
   which is the most popular Python templating language.

.. admonition:: 💡 Key Concept: Prompt Engineering
   :class: tip

   **Prompt engineering** is the art of crafting inputs to LLMs to get
   desired outputs. LLMs are sensitive to how you ask:

   **Bad prompt:**
     "Make me a manifest"

   **Good prompt:**
     "Generate a Scalable manifest for a climate modeling workflow with:
     - 2 targets: local (4 workers) and AWS Fargate
     - 1 component: gridlabd (8 CPUs, 32GB RAM, Apptainer container)
     - 1 task: run_simulation bound to gridlabd"

   Scalable's AI assistants handle prompt engineering internally — they
   construct detailed prompts from your high-level commands.

.. admonition:: 💡 Key Concept: Code Generation
   :class: tip

   **Code generation** is using AI to automatically write code or
   configuration. In Scalable's context:

   * Generate manifest YAML from descriptions
   * Generate component definitions from model documentation
   * Generate migration plans between providers

   **Trust but verify:** AI-generated code should always be reviewed by a
   human. It might be syntactically correct but semantically wrong (e.g.,
   reasonable-looking but incorrect resource allocations).

.. admonition:: 💡 Key Concept: Deterministic vs. Non-Deterministic
   :class: tip

   **Deterministic:** Same input always produces the same output.
     ``2 + 2 = 4`` (always). Heuristic mode is deterministic.

   **Non-deterministic:** Same input may produce different outputs.
     LLMs generate different text each time (due to random sampling in the
     generation process). LLM mode is non-deterministic.

   **Why this matters:**

   * For CI/CD and testing → use heuristic mode (reproducible)
   * For creative tasks → LLM mode is fine (you review the output anyway)

.. admonition:: 💡 Key Concept: API (Application Programming Interface)
   :class: tip

   An **API** is a standardized way for programs to communicate. When
   Scalable uses OpenAI's LLM, it sends a request to OpenAI's API
   (over the internet) and receives the LLM's response.

   .. code-block:: text

      Your computer                     OpenAI servers
      ┌──────────┐    HTTP request     ┌──────────────┐
      │ Scalable │───────────────────▶│  GPT-4 model │
      │          │◀───────────────────│              │
      └──────────┘    JSON response    └──────────────┘

   API keys authenticate you (prove you're allowed to use the service).
   Each API call costs money (typically fractions of a cent).


Step 1: Choosing Your Mode
----------------------------

Configure the AI backend via environment variable or ``.env`` file:

.. code-block:: bash

   # Heuristic mode (default, no AI required)
   export SCALABLE_AI_BACKEND=none

   # OpenAI mode (requires API key)
   export SCALABLE_AI_BACKEND=openai
   export AI_API_KEY=sk-your-key-here

   # Ollama mode (local LLM, no cloud dependency)
   export SCALABLE_AI_BACKEND=ollama
   # (requires Ollama running locally with a model loaded)

For this tutorial, all examples work in **heuristic mode** (no API key
needed). LLM mode enhances the output quality but isn't required.


Step 2: Onboarding a New Component
-------------------------------------

You're adding a new model (WaterShed) to your pipeline. Instead of writing
the component definition manually, let the assistant help:

.. code-block:: bash

   scalable init-component \
     --name watershed \
     --image ghcr.io/watershed/model:3.0 \
     --cpus 4 \
     --memory 16G \
     --description "Hydrological watershed model for runoff simulation"

Output (heuristic mode):

.. code-block:: yaml

   # Generated component definition
   components:
     watershed:
       image: ghcr.io/watershed/model:3.0
       cpus: 4
       memory: 16G
       tags: [hydrology, watershed]
       env:
         WATERSHED_DATA: /data/watershed

   tasks:
     run_watershed:
       component: watershed

.. admonition:: What happened here
   :class: note

   The assistant:

   1. Took your high-level inputs (name, image, resources)
   2. Applied templates with sensible defaults
   3. Inferred tags from the description ("watershed" → hydrology tag)
   4. Generated matching task bindings
   5. Added common environment variable patterns

   In LLM mode, it could also suggest optimal resource allocations based on
   the model type, recommend mount points for data, and generate a
   preload script.


Step 3: Diagnosing Failures
------------------------------

When a run fails, the diagnostic assistant helps identify root causes:

.. code-block:: bash

   scalable diagnose --run run-20260520T...-energy-forecast-abc123

Output:

.. code-block:: text

   ═══════════════════════════════════════
   Diagnosis Report
   ═══════════════════════════════════════

   Failures: 3 of 100 tasks

   Root Cause Analysis:
   ────────────────────
   1. MEMORY_EXHAUSTION (2 tasks)
      Tasks: run_simulation(47), run_simulation(92)
      Evidence: MemoryError raised, peak memory 15.8GB exceeds 16GB limit
      Recommendation: Increase component memory to 24G or add memory-aware
      task splitting

   2. INVALID_INPUT (1 task)
      Task: run_simulation(13)
      Evidence: ValueError raised in 0.1s (fast fail pattern)
      Recommendation: Validate input data before submission or add
      input-checking wrapper

   Suggested Fixes:
   ────────────────
   • Apply overlay to increase memory:
     overlays:
       fix-oom:
         components:
           analysis:
             memory: 24G

.. admonition:: 💡 Key Concept: Root Cause Analysis
   :class: tip

   **Root cause analysis** means identifying the underlying reason for a
   failure, not just the symptom.

   * Symptom: "Task failed with MemoryError"
   * Root cause: "Component memory (16G) is insufficient for scenarios with
     >1000 nodes (which need ~20GB)"

   The diagnostic assistant uses patterns in telemetry (failure timing,
   error types, resource usage) to infer root causes.


Step 4: Explaining Execution Plans
-------------------------------------

Get a human-readable explanation of what a plan will do:

.. code-block:: bash

   scalable explain ./scalable.yaml --target aws

Output:

.. code-block:: text

   Plan Explanation
   ═══════════════

   This execution plan will:

   1. Deploy to AWS Fargate in us-east-1 region
   2. Start with 2 workers, scaling up to 10 based on demand
   3. Each worker has 4 vCPUs and 16GB RAM
   4. Workers run the ghcr.io/energy-model:latest container
   5. Results stored to s3://my-bucket/scalable-runs/

   Estimated cost: $5.38 for a 2-hour run at full scale

   Key decisions:
   • Adaptive scaling chosen (min=2, max=10) — cost-efficient for
     variable workloads
   • Fargate selected — no server management overhead
   • S3 storage — durable, accessible from any future run

This is especially useful for:

* Reviewing a plan before running in production
* Explaining to stakeholders what a workflow does
* Documenting deployment decisions for team members


Step 5: Composing Workflows from Descriptions
------------------------------------------------

The most powerful assistant — generate manifests from natural language:

.. code-block:: bash

   scalable compose \
     --description "Climate modeling pipeline with GridLAB-D simulation \
     (8 CPUs, 32GB RAM, containerized) followed by demand aggregation \
     (2 CPUs, 4GB). Needs local and AWS targets with adaptive scaling."

Output:

.. code-block:: yaml

   # Generated by scalable compose
   version: 1
   project:
     name: climate-modeling

   targets:
     local:
       provider: local
       max_workers: 4
       threads_per_worker: 2
       processes: true
       containers: none

     aws:
       provider: aws
       region: us-east-1
       cluster_type: fargate
       worker_cpu: 8192
       worker_mem: 32768
       image: ${CONTAINER_IMAGE}
       adaptive:
         minimum: 2
         maximum: 20

   components:
     gridlabd:
       cpus: 8
       memory: 32G
       image: ${GRIDLABD_IMAGE}
       tags: [simulation, energy]

     postprocess:
       cpus: 2
       memory: 4G
       tags: [analysis]

   tasks:
     run_gridlabd:
       component: gridlabd

     aggregate_demand:
       component: postprocess

.. admonition:: Heuristic vs. LLM composition
   :class: note

   **Heuristic mode:** Parses your description for keywords (CPUs, memory,
   provider names) and fills templates. Works well for straightforward
   requests.

   **LLM mode:** Understands context and nuance. Can handle complex
   descriptions like "similar to our hydrology pipeline but for energy,
   with larger workers and spot instances for cost savings." Generates
   more tailored output.


Step 6: Migrating Between Providers
--------------------------------------

Moving a workflow from one provider to another:

.. code-block:: bash

   scalable migrate ./scalable.yaml --from slurm --to kubernetes

Output:

.. code-block:: yaml

   # Migration: slurm → kubernetes
   # Changes applied:

   targets:
     k8s:  # Replaces 'hpc' target
       provider: kubernetes
       namespace: team-climate
       image: ${CONTAINER_IMAGE}        # NEW: K8s requires container image
       adaptive:
         minimum: 2
         maximum: 64                    # Mapped from Slurm max_workers

   # Migration notes:
   # - Slurm 'queue: batch' → K8s namespace 'team-climate'
   # - Slurm 'walltime' → K8s resource limits (no direct equivalent)
   # - Slurm 'interface: ib0' → removed (K8s uses pod networking)
   # - NEW: container image required (Slurm used bare metal)

.. admonition:: Why migration is complex
   :class: hint

   Providers have different capabilities and concepts:

   * Slurm has queues, walltimes, accounts → no direct K8s equivalent
   * K8s has namespaces, pod specs, operators → no Slurm equivalent
   * Cloud has regions, instance types, VPCs → not applicable to HPC

   The migration assistant maps concepts where possible and flags
   differences that require human decision.


Step 7: Human-in-the-Loop Verification
-----------------------------------------

.. admonition:: 💡 Key Concept: Human-in-the-Loop
   :class: tip

   **Human-in-the-loop** means AI generates suggestions but a human makes
   the final decision. This is important because:

   * AI can generate plausible-looking but incorrect configuration
   * Resource allocations affect cost and correctness
   * Provider-specific nuances may be missed
   * Security implications (IAM roles, network access) need human review

   **Scalable's approach:** AI generates → human reviews → human applies.
   All generated output requires explicit confirmation before being used.

Best practices for verifying AI-generated output:

1. **Always validate:** Run ``scalable validate`` on generated manifests
2. **Dry-run first:** Use ``--dry-run`` to see effects without committing
3. **Check resource allocations:** Are they sensible for your workload?
4. **Review security:** Are IAM roles, images, and network settings correct?
5. **Test locally first:** Use ``--target local`` before deploying to cloud


Common Questions
-----------------

**Q: Do I need to pay for an LLM API to use the AI features?**

No! Heuristic mode works without any API key and handles most common cases.
LLM mode is an enhancement for complex or creative tasks.

**Q: Is the AI generating code that could be insecure?**

The AI generates configuration (YAML), not executable code. Always review
generated manifests before running, especially for:

* Container image sources (trust the registry?)
* IAM/permission settings
* Network exposure (public vs. private subnets)
* Resource allocations (could generate expensive configurations)

**Q: How much does LLM mode cost?**

Typically $0.01–$0.10 per AI assistant call (depending on the model and
prompt length). The ``explain`` command is cheapest (short output). The
``compose`` command is most expensive (longer generation).

**Q: Can I use a local LLM instead of OpenAI?**

Yes! Set ``SCALABLE_AI_BACKEND=ollama`` and run an Ollama instance locally.
This is free (no API costs) but requires a machine with enough RAM for
the model (8–32GB depending on model size).

**Q: What if the AI gives a wrong answer?**

That's why validation exists. Generated manifests go through the same
validation as hand-written ones. ``scalable validate`` catches structural
errors. Semantic errors (wrong but valid resource allocations) require
human judgment.

**Q: Are heuristic outputs always correct?**

Heuristic mode is deterministic and template-based, so it's predictable.
But it may not handle edge cases as well as LLM mode. For standard
workflows, heuristics work great. For unusual configurations, LLM mode
provides better results.


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Large Language Model (LLM)
     - AI trained on text that can generate human-like responses
   * - Heuristic Mode
     - Rule-based, deterministic processing (no AI required)
   * - LLM-Enhanced Mode
     - AI-powered processing with richer understanding
   * - Template
     - Pre-structured document with fill-in-the-blank placeholders
   * - Prompt Engineering
     - Crafting inputs to LLMs to get desired outputs
   * - Code Generation
     - Using AI to automatically write code or configuration
   * - Deterministic
     - Same input always produces the same output
   * - Non-Deterministic
     - Same input may produce different outputs (LLM behavior)
   * - API
     - Standardized interface for programs to communicate
   * - Human-in-the-Loop
     - AI suggests, human decides and validates
   * - Root Cause Analysis
     - Identifying the underlying reason for a failure
   * - Graceful Degradation
     - Falling back to simpler mode when advanced features unavailable


Next Steps
-----------

You've completed all 10 beginner tutorials! You now have a solid foundation
in:

* Distributed computing and workflow orchestration
* Declarative configuration with manifests
* Scaling strategies and provider architecture
* Caching and performance optimization
* Cloud computing and container technology
* Telemetry and observability
* Error handling and fault tolerance
* Kubernetes and container orchestration
* Machine learning for workflow optimization
* AI-assisted development

**Where to go from here:**

* **Standard tutorials:** Work through :ref:`tutorials` for deeper technical
  content and production patterns
* **API documentation:** Explore the :ref:`api_section` for detailed reference
* **Real project:** Apply what you've learned to your own workflow!
* **Community:** Contribute improvements via :doc:`/how_to_contribute`

.. admonition:: 🎉 Congratulations!
   :class: note

   You've gone from "what is distributed computing?" to understanding ML
   optimization and AI-assisted development. The beginner tutorials gave
   you the conceptual foundation — the standard tutorials and real-world
   practice will build expertise on top of it.
