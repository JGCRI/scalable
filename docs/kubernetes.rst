Kubernetes Provider
===================

Scalable v2.0.0 supports Kubernetes-based execution through the
``scalable[kubernetes]`` extra, using the Dask Kubernetes Operator.

Installation
------------

.. code-block:: bash

   pip install scalable[kubernetes]

This installs ``dask-kubernetes`` and ``kubernetes`` Python client.

Prerequisites
-------------

1. A Kubernetes cluster with the `Dask Kubernetes Operator
   <https://kubernetes.dask.org/en/latest/operator.html>`_ installed.
2. A valid ``KUBECONFIG`` pointing to the cluster.
3. Appropriate RBAC permissions for creating DaskCluster resources.

Configuration
-------------

The :class:`~scalable.providers.kubernetes.KubernetesProvider` maps manifest
components to Kubernetes worker groups.

Target options:

- ``namespace``: Kubernetes namespace (default: ``"default"``)
- ``image``: Default container image for scheduler/workers
- ``n_workers``: Initial worker count per group
- ``worker_service_account``: Service account for worker pods
- ``adaptive``: Dict with ``minimum`` and ``maximum`` for adaptive scaling
- ``resources``: Default resource requests (cpu, memory)
- ``env``: Extra environment variables for pods
- ``tolerations``: Kubernetes tolerations list
- ``node_selector``: Node selector dict

Example manifest:

.. literalinclude:: examples/scalable.gke.yaml
   :language: yaml

How It Works
------------

1. The provider creates a ``KubeCluster`` via the Dask Kubernetes Operator.
2. Each manifest component becomes a separate worker group with its own
   resource requests and container image.
3. If ``adaptive`` is configured, the cluster auto-scales within the
   specified bounds.
4. Worker groups are labeled with component names for observability.

Validation
----------

Run ``scalable validate`` to check your Kubernetes manifest:

.. code-block:: bash

   scalable validate scalable.yaml --target gke

Run with dry-run for planning:

.. code-block:: bash

   scalable run scalable.yaml --target gke --dry-run

See Also
--------

- :doc:`providers` — Full provider abstraction documentation
- :doc:`cloud` — AWS and GCP cloud providers
- :doc:`overlays` — Environment-specific configuration overrides
