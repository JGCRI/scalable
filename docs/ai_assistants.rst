AI Assistants
=============

Scalable v2.0.0 includes AI-assisted features (Phase 4) that help users
onboard models, compose workflows, diagnose failures, explain plans, and
migrate manifests.

All features work **without** an LLM backend via deterministic heuristic
fallbacks. LLM enhancement is opt-in via the ``SCALABLE_AI_BACKEND``
environment variable.

Design Philosophy
-----------------

* **AI proposes; Scalable disposes.** All outputs are reviewable artifacts — never auto-executed.
* **Offline-compatible.** Heuristic mode works on air-gapped HPC systems.
* **No hidden science changes.** AI tunes infrastructure only.
* **Inspectable.** All outputs include provenance and confidence indicators.

Configuration
-------------

AI features are configured via a ``.env`` file in your project root (loaded
automatically with override priority) or via environment variables.

By default, Scalable loads a ``.env`` file from the **current working directory**
at import time. If your script or notebook changes directories (e.g.,
``os.chdir()`` to a temp folder), use :func:`~scalable.common.load_env` to
explicitly load credentials from a specific path::

    from scalable.common import load_env

    # Load from an absolute path before changing directories
    load_env("/path/to/your/project/.env")

    # Or load from a relative path (resolved against CWD at call time)
    load_env("../notebooks/.env")

.. tip::

   For Jupyter notebooks in the ``notebooks/`` directory, place a ``.env``
   file there (copy from ``.env.example`` in the project root). The AI tutorial
   notebook (Tutorial 10) calls ``load_env()`` automatically at startup — just
   ensure the ``.env`` file exists in the notebooks directory or update the
   path in the first code cell.

**Recommended generic variables** (provider-agnostic):

* ``AI_PROVIDER`` — Provider selection. Options: ``openai``, ``anthropic``, ``google``, ``xai``, ``groq``, ``ollama``. Default: ``none``.
* ``AI_API_KEY`` — Universal API key (works for any provider requiring auth).
* ``LLM_MODEL_NAME`` — Model identifier for the selected provider.
* ``AI_BASE_URL`` — Custom API endpoint (required for proxies; xAI and Ollama auto-configure).

**Supported providers and example models:**

.. list-table::
   :header-rows: 1
   :widths: 15 15 40

   * - Provider
     - ``AI_PROVIDER``
     - Example models
   * - OpenAI
     - ``openai``
     - ``gpt-4o``, ``gpt-4o-mini``, ``o1``, ``o1-mini``
   * - Anthropic
     - ``anthropic``
     - ``claude-opus-4-20250514``, ``claude-sonnet-4-20250514``, ``claude-haiku-3-20250414``
   * - Google Gemini
     - ``google``
     - ``gemini-2.0-flash``, ``gemini-1.5-pro``, ``gemini-1.5-flash``
   * - xAI (Grok)
     - ``xai``
     - ``grok-3``, ``grok-2``
   * - Groq
     - ``groq``
     - ``llama-3.1-70b-versatile``, ``mixtral-8x7b-32768``
   * - Ollama (local)
     - ``ollama``
     - ``llama3``, ``mistral``, ``codellama``

Example ``.env`` file:

.. code-block:: bash

   AI_PROVIDER=openai
   AI_API_KEY=sk-your-key-here
   LLM_MODEL_NAME=gpt-4o
   # AI_BASE_URL=https://custom-endpoint.example.com/v1

**Advanced: SCALABLE_AI_* overrides** (take priority over generic variables):

* ``SCALABLE_AI_BACKEND`` — Backend selection override.
* ``SCALABLE_AI_MODEL`` — Model name override.
* ``SCALABLE_AI_ENDPOINT`` — API endpoint override.
* ``SCALABLE_AI_API_KEY`` — API key override.

**Provider-specific API keys** (optional, override ``AI_API_KEY`` per-provider):

* ``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, ``GOOGLE_API_KEY``, ``XAI_API_KEY``, ``GROQ_API_KEY``

Install the AI extra for enhanced output formatting::

    pip install scalable[ai]

Commands
--------

scalable init-component
~~~~~~~~~~~~~~~~~~~~~~~

Analyze a model directory and propose a component manifest block::

    scalable init-component ./path/to/model --name gcam --no-ai

Options:

* ``--name`` — Component name (default: directory basename)
* ``--output`` — Write to file instead of stdout
* ``--no-ai`` — Use heuristics only (no LLM)

The assistant inspects build systems, source files, data directories,
and container definitions to propose a complete component YAML block.

scalable diagnose
~~~~~~~~~~~~~~~~~

Classify failures from run telemetry and suggest fixes::

    scalable diagnose --latest --no-ai
    scalable diagnose --run-id run-20260519T120000Z-project-abc

Options:

* ``--runs-dir`` — Custom runs directory
* ``--run-id`` — Specific run to diagnose
* ``--latest`` — Use most recent run (default if no run-id)
* ``--format`` — Output format (``text`` or ``json``)
* ``--output`` — Write to file
* ``--no-ai`` — Use heuristics only

Failure classes detected: ``oom``, ``walltime``, ``mount_missing``,
``import_error``, ``connection``, ``credential``, ``model_runtime``.

scalable explain
~~~~~~~~~~~~~~~~

Render a human-readable explanation of an execution plan::

    scalable explain plan.json
    scalable explain plan.json --format json

Options:

* ``--runs-dir`` — Runs directory for historical context
* ``--format`` — Output format (``text`` or ``json``)
* ``--output`` — Write to file
* ``--no-ai`` — Use heuristics only

scalable compose
~~~~~~~~~~~~~~~~

Generate a workflow from a natural-language description::

    scalable compose "Run GCAM reference scenario then Stitches for daily climate"
    scalable compose "Run Hector model" --output-dir ./generated

Options:

* ``--output-dir`` — Directory for generated files
* ``--format`` — Output format (``text`` or ``json``)
* ``--no-ai`` — Use heuristics only

Known model patterns: GCAM, Stitches, Demeter, Tethys, Xanthos, Hector.

scalable migrate
~~~~~~~~~~~~~~~~

Propose manifest migration changes::

    scalable migrate scalable.yaml --to-provider kubernetes
    scalable migrate scalable.yaml --goal "Add cloud target"

Options:

* ``--to-provider`` — Target provider (``kubernetes``, ``aws``, ``gcp``)
* ``--to-version`` — Target schema version
* ``--goal`` — Free-form migration goal
* ``--format`` — Output format (``text`` or ``json``)
* ``--output`` — Write to file
* ``--no-ai`` — Use heuristics only

Python API
----------

Loading Environment Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :func:`~scalable.common.load_env` to load a ``.env`` file from a custom
location. This is especially useful in notebooks and scripts that change the
working directory::

    from scalable.common import load_env

    # Load from the notebooks directory (before os.chdir)
    load_env("./notebooks/.env")

    # Or equivalently via the top-level package import:
    from scalable import load_env
    load_env("/absolute/path/to/.env")

Parameters:

* ``dotenv_path`` — Path to the ``.env`` file. Defaults to ``<cwd>/.env``.
* ``override`` — Whether to override existing env vars (default: ``True``).

Returns the refreshed :data:`~scalable.common.settings` singleton.

Assistant Functions
~~~~~~~~~~~~~~~~~~~

All assistant functions are available programmatically::

    from scalable.ai import (
        onboard_component,
        diagnose_run,
        explain_plan,
        compose_workflow,
        migrate_manifest,
    )

    # Onboard a model
    result = onboard_component("./gcam-core", name="gcam", no_ai=True)
    print(result.component_yaml)

    # Diagnose a run
    diagnosis = diagnose_run(runs_dir=".scalable/runs", latest=True, no_ai=True)
    print(diagnosis.render_text())

    # Explain a plan
    explanation = explain_plan(plan_path="plan.json", no_ai=True)
    print(explanation.render_text())

Session Planning with Objectives
---------------------------------

``ScalableSession.plan()`` now supports ``objective`` and ``policy`` kwargs::

    session = ScalableSession.from_yaml("scalable.yaml")
    plan = session.plan(
        objective="minimize cost",   # "minimize cost", "minimize time", "balance"
        policy="safe",               # "safe", "aggressive", "manual"
    )

* ``minimize cost`` — Conservative worker allocation
* ``minimize time`` — Scale up workers for parallelism
* ``balance`` — Moderate scaling (default)
* ``safe`` — Use safety margins on resources (default)
* ``aggressive`` — Scale up resources/workers significantly
* ``manual`` — Use exactly what the manifest declares

See Also
--------

- :doc:`manifest` — Manifest schema and session API
- :doc:`ml` — ML-backed resource optimization
- :doc:`emulation` — Model emulation with surrogate dispatch
- :doc:`telemetry` — Run telemetry that powers diagnosis
