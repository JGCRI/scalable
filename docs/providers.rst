Provider Abstraction (Phase 1)
==============================

Phase 1 adds a provider-neutral execution seam.

Built-in providers
------------------

* ``local`` via ``LocalProvider``
* ``slurm`` via ``SlurmProvider``

Provider contract
-----------------

Each provider follows the ``DeploymentProvider`` protocol:

* ``validate(spec)``
* ``build_cluster(spec)``
* ``scale(cluster, plan)``
* ``close(cluster)``

The provider layer consumes ``DeploymentSpec`` and applies a ``ScalePlan``.

Local provider
--------------

``LocalProvider`` runs a Dask ``LocalCluster`` for laptop and CI execution.
It supports tag-aware scheduling compatible with
``ScalableClient.submit(..., tag=...)``.

Slurm provider
--------------

``SlurmProvider`` is a thin translation layer over the legacy ``SlurmCluster``
path and preserves existing behavior while exposing a v2 manifest/session API.

Registry and discovery
----------------------

The provider registry supports:

* explicit runtime registration
* lazy built-in resolution
* optional Python entry-point discovery under ``scalable.providers``

This is the extension hook for future cloud and Kubernetes providers.

