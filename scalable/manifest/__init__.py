"""Declarative ``scalable.yaml`` manifest layer (v2.0.0 Phase 1).

This package is the durable, provider-neutral source of truth for a Scalable
project. It supersedes the legacy ``Dockerfile``-as-config discovery driven
by :class:`scalable.utilities.ModelConfig`, which is preserved with a
deprecation warning during the v2.0.0 transition.

Public Phase 1 surface (populated by subsequent work units):

* :mod:`scalable.manifest.schema` -- frozen schema dataclasses + ``SCHEMA_VERSION``.
* :mod:`scalable.manifest.parser` -- YAML loader with ``${VAR}`` expansion.
* :mod:`scalable.manifest.validate` -- cross-field validation + report types.
* :mod:`scalable.manifest.adapter` -- pure ``ManifestModel`` -> legacy
  :class:`scalable.core.JobQueueCluster` translation reused by every provider.
* :mod:`scalable.manifest.errors` -- exception hierarchy.

The schema is versioned (``version: 1``) so Phase 3 cloud overlays and Phase 4
AI migration assistants can evolve without breaking existing manifests.
"""

from __future__ import annotations

__all__: list[str] = []
