Telemetry and Run Reports
=========================

Scalable v2.0.0 includes a deterministic run history store for manifest-driven
sessions. Every run records structured telemetry for debugging, auditing,
resource advising, and ML model training.

Run directory layout
--------------------

Each run is recorded under ``.scalable/runs/``:

.. code-block:: text

    .scalable/
      runs/
        run-<timestamp>-<project>-<hash>/
          manifest.yaml
          plan.json
          manifest.lock
          run.json
          tasks.jsonl
          resources.jsonl
          workers.jsonl
          failures.jsonl
          cache.jsonl
          artifacts.jsonl
          cost.jsonl
          summary.json

JSONL is the canonical storage format. Optional parquet snapshots are emitted
when telemetry parquet support is enabled.

Event types
-----------

The telemetry system records the following event categories:

- **Task events** — submission, start, completion, failure, retry
- **Worker events** — launch, ready, lost, removed
- **Resource events** — CPU/memory allocation and usage
- **Cache events** — hit/miss for ``@cacheable`` decorated functions
- **Failure events** — error classification and stack traces
- **Artifact events** — output registration and storage references
- **Cost events** — cloud provider cost estimates (Phase 3+)
- **Emulation events** — emulator dispatch decisions (Phase 5)

CLI reporting
-------------

Generate a report from the most recent run:

.. code-block:: bash

    scalable report --latest

Machine-readable report output:

.. code-block:: bash

    scalable report --latest --format json --output report.json

Report from a specific run:

.. code-block:: bash

    scalable report --run-id run-20260519T120000Z-project-abc

Report options:

- ``--runs-dir`` — Custom runs directory (default: ``.scalable/runs``)
- ``--run-id`` — Specific run identifier
- ``--latest`` — Use most recent run (default when no run-id given)
- ``--format`` — Output format (``text`` or ``json``)
- ``--output`` — Write to file instead of stdout

Session integration
-------------------

``ScalableSession`` automatically initializes and finalizes telemetry for
manifest-driven runs:

.. code-block:: python

    from scalable import ScalableSession

    session = ScalableSession.from_yaml("scalable.yaml", target="local")
    # Telemetry is automatically recorded during the session lifecycle

    # Record custom artifacts
    session.record_artifact("output.csv", kind="result")

``ScalableClient.submit`` and ``ScalableClient.map`` emit task lifecycle
telemetry through future callbacks when telemetry is active.

Configuration
-------------

The telemetry system supports these environment variables:

* ``SCALABLE_RUNS_DIR`` — Local runs directory (default: ``.scalable/runs``)
* ``SCALABLE_TELEMETRY`` — Enable/disable telemetry (default: ``1``)
* ``SCALABLE_TELEMETRY_PARQUET`` — Emit parquet snapshots (default: ``0``)
* ``SCALABLE_RUNS_DIR_REMOTE`` — Remote storage for telemetry sync (optional)

Downstream consumers
--------------------

Telemetry data feeds:

* :doc:`advising` — heuristic resource recommendations from run history
* :doc:`ml` — ML-backed prediction models trained on telemetry features
* ``scalable diagnose`` — failure classification and fix suggestions
* ``scalable report`` — run summary and cost reporting

