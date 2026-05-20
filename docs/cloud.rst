Cloud Providers
===============

Scalable v2.0.0 supports cloud-based execution through the ``scalable[cloud]``
extra, which provides access to AWS and GCP deployment providers with
integrated cost estimation.

Installation
------------

.. code-block:: bash

   pip install scalable[cloud]

This installs ``dask-cloudprovider``, ``s3fs``, ``gcsfs``, and ``fsspec``.

AWS Provider
------------

The :class:`~scalable.providers.cloud.aws.AWSBatchProvider` wraps
``dask-cloudprovider``'s ``FargateCluster`` or ``EC2Cluster``.

Target options:

- ``region``: AWS region (default: ``us-east-1``)
- ``cluster_type``: ``"fargate"`` (default) or ``"ec2"``
- ``instance_type``: EC2 instance type (for cost estimation)
- ``image``: Docker image for workers
- ``n_workers``: Initial worker count
- ``worker_cpu``: CPU units per worker (Fargate: 256-4096)
- ``worker_mem``: Memory in MiB per worker
- ``vpc``: VPC identifier
- ``subnets``: List of subnet IDs
- ``security_groups``: List of security group IDs
- ``execution_role_arn``: ECS execution role ARN
- ``task_role_arn``: ECS task role ARN
- ``adaptive``: Dict with ``minimum`` and ``maximum`` for adaptive scaling

Example manifest:

.. literalinclude:: examples/scalable.aws.yaml
   :language: yaml

GCP Provider (Scaffold)
-----------------------

The :class:`~scalable.providers.cloud.gcp.GCPProvider` is a validation-only
scaffold in Phase 3. It validates manifest options but raises
``NotImplementedError`` on ``build_cluster()``.

Target options:

- ``region``: GCP region
- ``project_id``: GCP project identifier
- ``instance_type``: GCE machine type (for cost estimation)
- ``image``: Container image
- ``n_workers``: Worker count

Cost Estimation
---------------

Cloud providers include static cost tables for common instance types.
Run ``scalable run --dry-run`` to see estimated costs:

.. code-block:: bash

   scalable run scalable.yaml --target aws --dry-run

The cost estimate is also recorded in telemetry (``cost.jsonl``).
See :doc:`cost` for detailed cost estimation documentation.

See Also
--------

- :doc:`providers` — Full provider abstraction documentation
- :doc:`cost` — Cost estimation primitives and tables
- :doc:`artifacts` — Remote artifact storage with S3/GCS backends
