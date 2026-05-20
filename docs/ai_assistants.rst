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

AI features are controlled via environment variables:

* ``SCALABLE_AI_BACKEND`` — Backend selection (``none``, ``openai``, ``ollama``). Default: ``none``.
* ``SCALABLE_AI_MODEL`` — Model name for the selected backend.
* ``SCALABLE_AI_ENDPOINT`` — API endpoint override for the backend.

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
