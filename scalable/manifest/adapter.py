"""Manifest -> legacy cluster adapter functions (Phase 1 WU-7)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from scalable.utilities import model_config_adapter_context

if TYPE_CHECKING:
    from scalable.providers.base import DeploymentSpec

__all__ = [
    "add_components_to_legacy_cluster",
    "build_slurm_cluster_kwargs",
    "create_legacy_slurm_cluster",
]


def build_slurm_cluster_kwargs(spec: DeploymentSpec) -> dict[str, Any]:
    """Translate ``targets.<name>`` options into ``SlurmCluster`` kwargs."""
    options = spec.target.options
    kwargs: dict[str, Any] = {
        "queue": options.get("queue"),
        "account": options.get("account"),
        "walltime": options.get("walltime"),
        "interface": options.get("interface"),
        "name": options.get("name"),
        "logs_location": options.get("logs_location"),
        "suppress_logs": options.get("suppress_logs", False),
    }
    if "comm_port" in options:
        kwargs["comm_port"] = options["comm_port"]
    return kwargs


def create_legacy_slurm_cluster(spec: DeploymentSpec, *, cluster_cls: Any) -> Any:
    """Instantiate a legacy Slurm cluster under adapter compatibility context.

    This suppresses the direct ``ModelConfig`` deprecation warning emitted by
    :class:`scalable.utilities.ModelConfig`, since this call path is the
    intentional bridge from manifests to legacy APIs.
    """
    kwargs = build_slurm_cluster_kwargs(spec)
    with model_config_adapter_context():
        return cluster_cls(**kwargs)


def add_components_to_legacy_cluster(
    spec: DeploymentSpec,
    cluster: Any,
    *,
    components: Iterable[str] | None = None,
) -> list[str]:
    """Apply manifest components to a legacy cluster via ``add_container``.

    Parameters
    ----------
    spec
        Deployment spec containing parsed components.
    cluster
        Object exposing ``add_container(...)`` (e.g. ``SlurmCluster``).
    components
        Optional subset of component names to add. Defaults to all components.

    Returns
    -------
    list[str]
        Component names that were added.
    """
    if not hasattr(cluster, "add_container"):
        raise TypeError("cluster does not expose add_container(...)")

    if components is None:
        selected = list(spec.components)
    else:
        selected = list(components)

    added: list[str] = []
    for component_name in selected:
        component = spec.components[component_name]
        cluster.add_container(
            tag=component_name,
            dirs=dict(component.mounts),
            path=component.image,
            cpus=component.cpus,
            memory=component.memory,
            preload_script=component.preload_script,
        )
        added.append(component_name)

    return added
