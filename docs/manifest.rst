Manifest-Driven Workflows
=========================

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

Optional keys:

* ``overlays`` — environment-specific configuration deltas (see :doc:`overlays`)

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

Project configuration
---------------------

The ``project`` block supports:

* ``name`` — project identifier (used in run directory naming)
* ``default_storage`` — URI for artifact/output storage (e.g. ``s3://bucket/path/``)
* ``local_cache`` — local cache directory override

.. code-block:: yaml

    project:
      name: integrated-assessment
      default_storage: s3://my-bucket/scalable-runs/
      local_cache: ./.scalable/cache

CLI commands
------------

Validate a manifest:

.. code-block:: bash

    scalable validate ./scalable.yaml

Generate a deterministic dry-run plan:

.. code-block:: bash

    scalable plan ./scalable.yaml --target local --dry-run --output plan.json

Run a workflow:

.. code-block:: bash

    scalable run ./scalable.yaml --target local --workflow workflow.py
    scalable run ./scalable.yaml --target aws --dry-run

The plan outputs:

* ``plan.json`` (provider-neutral plan payload)
* ``manifest.lock`` (SHA-256 fingerprint of canonicalized manifest content)

The ``run`` command validates, plans, estimates cost (for cloud targets), and
optionally executes a workflow file. Use ``--dry-run`` to preview the plan and
cost estimate without launching workers.

Session API
-----------

.. code-block:: python

    from scalable import ScalableSession

    session = ScalableSession.from_yaml("./scalable.yaml", target="local")
    plan = session.plan(dry_run=True)
    print(plan.manifest_lock)

    # With planning objectives and policies
    plan = session.plan(
        objective="minimize cost",   # "minimize cost", "minimize time", "balance"
        policy="safe",               # "safe", "aggressive", "manual"
    )

Environment variables
---------------------

* ``SCALABLE_MANIFEST``: default manifest path used by CLI/session
* ``SCALABLE_TARGET``: default target override for auto-selection paths

Migration note from imperative API
----------------------------------

Legacy imperative APIs remain supported:

* ``SlurmCluster(...)``
* ``cluster.add_container(...)``
* ``cluster.add_workers(...)``

The new manifest/session path is additive and can be adopted incrementally.
Legacy ``ModelConfig`` Dockerfile/config auto-discovery emits a
``DeprecationWarning`` when used outside the manifest adapter context.

Example manifests
-----------------

Reference examples are included in:

* ``docs/examples/scalable.minimal.yaml``
* ``docs/examples/scalable.gcam_stitches.yaml``
* ``docs/examples/scalable.aws.yaml``
* ``docs/examples/scalable.gke.yaml``
* ``docs/examples/scalable.overlays.yaml``

