Telemetry and Run Reports
=========================

Phase 2 introduces a deterministic run history store for manifest-driven
sessions.

Run directory layout
--------------------

Each run is recorded under ``.scalable/runs/``:

.. code-block:: text

    .scalable/
      runs/
        run-.../
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
          summary.json

JSONL is the canonical storage format. Optional parquet snapshots are emitted
when telemetry parquet support is enabled.

CLI reporting
-------------

Generate a report from the most recent run:

.. code-block:: bash

    scalable report --latest

Machine-readable report output:

.. code-block:: bash

    scalable report --latest --format json --output report.json

Configuration
-------------

The telemetry system supports these environment variables:

* ``SCALABLE_RUNS_DIR``
* ``SCALABLE_TELEMETRY``
* ``SCALABLE_TELEMETRY_PARQUET``

