"""AWS cloud provider using dask-cloudprovider.

Provides :class:`AWSBatchProvider` which wraps ``dask_cloudprovider``'s
``FargateCluster`` or ``EC2Cluster`` behind the Scalable
:class:`DeploymentProvider` protocol.
"""

from __future__ import annotations

from typing import Any

from scalable.common import logger
from scalable.manifest.validate import ValidationIssue, ValidationReport
from scalable.providers.base import (
    ClusterHandle,
    DeploymentSpec,
    ScalePlan,
)

from .base import CloudProvider


def _import_dask_cloudprovider():
    """Import dask-cloudprovider with a clear error."""
    try:
        import dask_cloudprovider

        return dask_cloudprovider
    except ImportError as exc:
        raise ImportError(
            "dask-cloudprovider is required for AWS provider. "
            "Install with: pip install scalable[cloud]"
        ) from exc


class AWSBatchProvider(CloudProvider):
    """AWS provider using dask-cloudprovider's FargateCluster.

    Target options:
    - ``region``: AWS region (default: ``us-east-1``)
    - ``instance_type``: EC2 instance type for cost estimation
    - ``cluster_type``: ``"fargate"`` (default) or ``"ec2"``
    - ``image``: Docker image for workers
    - ``n_workers``: Initial worker count
    - ``worker_cpu``: CPU units per worker (Fargate: 256-4096)
    - ``worker_mem``: Memory in MiB per worker
    - ``vpc``: VPC identifier
    - ``subnets``: List of subnet IDs
    - ``security_groups``: List of security group IDs
    - ``execution_role_arn``: ECS execution role ARN
    - ``task_role_arn``: ECS task role ARN
    """

    name: str = "aws"

    _KNOWN_OPTIONS: frozenset[str] = frozenset({
        "region",
        "instance_type",
        "cluster_type",
        "image",
        "n_workers",
        "worker_cpu",
        "worker_mem",
        "vpc",
        "subnets",
        "security_groups",
        "execution_role_arn",
        "task_role_arn",
        "scheduler_timeout",
        "environment",
        "tags",
        "spot",
        "adaptive",
    })

    def validate(self, spec: DeploymentSpec) -> ValidationReport:
        """Validate AWS-specific target options."""
        report = ValidationReport()
        options = spec.target.options

        unknown = set(options) - self._KNOWN_OPTIONS
        for key in sorted(unknown):
            report.warnings.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.{key}",
                    message=f"unknown AWS provider option {key!r}",
                    code="W_UNKNOWN_AWS_OPTION",
                )
            )

        cluster_type = options.get("cluster_type", "fargate")
        if cluster_type not in ("fargate", "ec2"):
            report.errors.append(
                ValidationIssue(
                    path=f"targets.{spec.target_name}.cluster_type",
                    message=f"cluster_type must be 'fargate' or 'ec2', got {cluster_type!r}",
                    code="E_INVALID_CLUSTER_TYPE",
                )
            )

        return report

    def build_cluster(self, spec: DeploymentSpec) -> ClusterHandle:
        """Create an AWS Dask cluster via dask-cloudprovider."""
        _import_dask_cloudprovider()  # validate availability early
        options = spec.target.options

        cluster_type = options.get("cluster_type", "fargate")
        region = options.get("region", "us-east-1")
        image = options.get("image")
        n_workers = options.get("n_workers", 1)

        kwargs: dict[str, Any] = {
            "region_name": region,
            "n_workers": n_workers,
        }
        if image:
            kwargs["image"] = image
        if "worker_cpu" in options:
            kwargs["worker_cpu"] = options["worker_cpu"]
        if "worker_mem" in options:
            kwargs["worker_mem"] = options["worker_mem"]
        if "vpc" in options:
            kwargs["vpc"] = options["vpc"]
        if "subnets" in options:
            kwargs["subnets"] = options["subnets"]
        if "security_groups" in options:
            kwargs["security_groups"] = options["security_groups"]
        if "execution_role_arn" in options:
            kwargs["execution_role_arn"] = options["execution_role_arn"]
        if "task_role_arn" in options:
            kwargs["task_role_arn"] = options["task_role_arn"]
        if "environment" in options:
            kwargs["environment"] = options["environment"]
        if "tags" in options:
            kwargs["tags"] = options["tags"]

        logger.info("creating AWS %s cluster in %s", cluster_type, region)

        if cluster_type == "fargate":
            from dask_cloudprovider.aws import FargateCluster

            cluster = FargateCluster(**kwargs)
        else:
            from dask_cloudprovider.aws import EC2Cluster

            cluster = EC2Cluster(**kwargs)

        # Adaptive scaling if requested
        adaptive = options.get("adaptive")
        if isinstance(adaptive, dict):
            cluster.adapt(
                minimum=adaptive.get("minimum", 1),
                maximum=adaptive.get("maximum", 10),
            )

        from scalable.client import ScalableClient

        def _client_factory() -> ScalableClient:
            from distributed import Client

            client = Client(cluster)
            return ScalableClient(client=client)

        return ClusterHandle(
            backend=cluster,
            client_factory=_client_factory,
            metadata={"provider": "aws", "region": region, "cluster_type": cluster_type},
        )

    def scale(self, cluster: ClusterHandle, plan: ScalePlan) -> None:
        """Scale the AWS cluster to match the plan."""
        backend = cluster.backend
        total_workers = sum(plan.workers_by_tag.values())
        if hasattr(backend, "scale"):
            backend.scale(total_workers)


__all__ = ["AWSBatchProvider"]
