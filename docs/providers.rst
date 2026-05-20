Provider Abstraction
====================

Scalable v2.0.0 introduces a provider-neutral execution layer that decouples
workflow definitions from infrastructure. Providers implement the
:class:`~scalable.providers.base.DeploymentProvider` protocol and are
selected via the ``provider:`` field in manifest target blocks.

Built-in providers
------------------

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Provider
     - Name in manifest
     - Backing implementation
   * - :class:`~scalable.providers.local.LocalProvider`
     - ``local``
     - Dask ``LocalCluster`` for laptop/CI execution
   * - :class:`~scalable.providers.slurm.SlurmProvider`
     - ``slurm``
     - Legacy ``SlurmCluster`` / ``SlurmJob`` path
   * - :class:`~scalable.providers.kubernetes.KubernetesProvider`
     - ``kubernetes``
     - Dask Kubernetes Operator (requires ``scalable[kubernetes]``)
   * - :class:`~scalable.providers.cloud.aws.AWSBatchProvider`
     - ``aws``
     - Fargate/EC2 via dask-cloudprovider (requires ``scalable[cloud]``)
   * - :class:`~scalable.providers.cloud.gcp.GCPProvider`
     - ``gcp``
     - Validation-only scaffold (requires ``scalable[cloud]``)

Provider contract
-----------------

Each provider follows the ``DeploymentProvider`` protocol:

* ``validate(spec)`` — validate a deployment specification
* ``build_cluster(spec)`` — create and return a cluster handle
* ``scale(cluster, plan)`` — apply a scale plan to the cluster
* ``close(cluster)`` — shut down the cluster
* ``estimate_cost(spec, plan)`` — (optional) return a cost estimate

The provider layer consumes :class:`~scalable.providers.base.DeploymentSpec`
and applies a :class:`~scalable.providers.base.ScalePlan`.

Local provider
--------------

``LocalProvider`` runs a Dask ``LocalCluster`` for laptop and CI execution.
It supports tag-aware scheduling compatible with
``ScalableClient.submit(..., tag=...)``.

.. code-block:: yaml

   targets:
     local:
       provider: local
       max_workers: 4
       threads_per_worker: 1
       processes: false
       containers: none

Slurm provider
--------------

``SlurmProvider`` is a thin translation layer over the legacy ``SlurmCluster``
path and preserves existing behavior while exposing a v2 manifest/session API.

.. code-block:: yaml

   targets:
     hpc:
       provider: slurm
       queue: short
       account: GCIMS
       walltime: "02:00:00"
       interface: ib0
       container_runtime: apptainer

Kubernetes provider
-------------------

``KubernetesProvider`` maps manifest components to Dask Kubernetes Operator
worker groups. See :doc:`kubernetes` for details.

.. code-block:: yaml

   targets:
     gke:
       provider: kubernetes
       namespace: scalable
       image: ghcr.io/jgcri/scalable-worker:latest
       n_workers: 4
       adaptive:
         minimum: 1
         maximum: 16

AWS provider
------------

``AWSBatchProvider`` wraps ``dask-cloudprovider``'s Fargate/EC2 clusters
with cost estimation support. See :doc:`cloud` for details.

.. code-block:: yaml

   targets:
     aws:
       provider: aws
       region: us-east-1
       cluster_type: fargate
       n_workers: 4
       worker_cpu: 1024
       worker_mem: 4096

GCP provider (scaffold)
-----------------------

``GCPProvider`` validates manifest options but raises ``NotImplementedError``
on ``build_cluster()``. Full implementation planned for a future release.

Registry and discovery
----------------------

The provider registry supports:

* Explicit runtime registration
* Lazy built-in resolution
* Optional Python entry-point discovery under ``scalable.providers``

.. code-block:: python

   from scalable.providers.registry import get_provider, register_provider

   # Get a built-in provider
   provider = get_provider("local")

   # Register a custom provider
   register_provider("custom", MyCustomProvider)

This is the extension hook for custom or third-party providers.
