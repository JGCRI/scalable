Manifest-Driven Workflows (Phase 1)
===================================

Scalable v2.0.0 introduces a declarative manifest entry point, ``scalable.yaml``.
This becomes the source of truth for targets, components, and task bindings.

Schema v1 (required keys)
-------------------------

Top-level keys:

* ``version`` (must be ``1``)
* ``project``
* ``targets``
* ``components``
* ``tasks``

Minimal example:

.. code-block:: yaml

    version: 1
    project:
      name: demo

    targets:
      local:
        provider: local
        max_workers: 2
        threads_per_worker: 1
        processes: false
        containers: none

    components:
      gcam:
        image: /containers/gcam.sif
        cpus: 2
        memory: 8G
        mounts:
          /host/data: /data

    tasks:
      run_gcam:
        component: gcam

Validation commands
-------------------

Validate a manifest:

.. code-block:: bash

    scalable validate ./scalable.yaml

Generate a deterministic dry-run plan:

.. code-block:: bash

    scalable plan ./scalable.yaml --target local --dry-run --output plan.json

Phase 1 writes:

* ``plan.json`` (provider-neutral plan payload)
* ``manifest.lock`` (SHA-256 fingerprint of canonicalized manifest content)

Environment variables
---------------------

* ``SCALABLE_MANIFEST``: default manifest path used by CLI/session
* ``SCALABLE_TARGET``: default target override for auto-selection paths

Migration note from imperative API
----------------------------------

Legacy imperative APIs remain supported in Phase 1:

* ``SlurmCluster(...)``
* ``cluster.add_container(...)``
* ``cluster.add_workers(...)``

The new manifest/session path is additive and can be adopted incrementally.

Example manifests
-----------------

Reference examples are included in:

* ``docs/examples/scalable.minimal.yaml``
* ``docs/examples/scalable.gcam_stitches.yaml``
