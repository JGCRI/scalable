"""Manifest overlay resolution and deep-merge utilities.

Overlays allow a single ``scalable.yaml`` to carry environment-specific
deltas (e.g. a ``kubernetes-prod`` overlay that overrides worker counts,
images, and resource requests) without duplicating the base manifest.

Merge semantics:
- Dicts are deep-merged recursively (overlay keys win).
- Lists are replaced wholesale (no element-level merge).
- Scalar values are overwritten by the overlay.
- The ``overlays:`` top-level key is stripped from the resolved form
  before validation so it doesn't pollute ``ManifestModel.raw``.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``overlay`` onto ``base``, returning a new dict.

    - Nested dicts are merged recursively.
    - All other types (lists, scalars) are replaced by the overlay value.
    - Neither input is mutated.
    """
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, Mapping)
        ):
            result[key] = deep_merge(result[key], dict(value))
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_overlay(
    raw_doc: dict[str, Any],
    *,
    overlay_name: str | None = None,
    target_name: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve a manifest document with optional overlay application.

    Parameters
    ----------
    raw_doc : dict
        The full parsed YAML document (post env-expansion) including
        ``overlays:`` block.
    overlay_name : str | None
        Explicit overlay to apply. If ``None``, the overlay is inferred
        from ``targets.<target_name>.overlay`` if ``target_name`` is given.
    target_name : str | None
        Target being selected. Used to look up per-target overlay refs.

    Returns
    -------
    tuple[dict, dict | None]
        - The resolved document (with overlay merged in, ``overlays:`` key
          removed) suitable for parsing into ``ManifestModel``.
        - The raw unresolved document (original form minus ``overlays:`` key)
          for provenance tracking, or None if no overlay was applied.
    """
    overlays_block = raw_doc.get("overlays") or {}

    # Determine which overlay to apply
    effective_overlay_name = overlay_name
    if effective_overlay_name is None and target_name is not None:
        targets = raw_doc.get("targets") or {}
        target_spec = targets.get(target_name) or {}
        effective_overlay_name = target_spec.get("overlay")

    # Strip the overlays key from both forms
    raw_unresolved = {k: v for k, v in raw_doc.items() if k != "overlays"}

    if not effective_overlay_name:
        # No overlay applied; return doc without overlays key
        return raw_unresolved, None

    if effective_overlay_name not in overlays_block:
        from scalable.manifest.errors import ManifestSchemaError

        available = sorted(overlays_block.keys()) if overlays_block else []
        raise ManifestSchemaError(
            f"overlay {effective_overlay_name!r} referenced but not defined; "
            f"available overlays: {available}"
        )

    overlay_data = overlays_block[effective_overlay_name]
    if not isinstance(overlay_data, dict):
        from scalable.manifest.errors import ManifestSchemaError

        raise ManifestSchemaError(
            f"overlay {effective_overlay_name!r} must be a mapping"
        )

    # Strip 'overlay' key from target options before merge (it's a reference, not data)
    resolved = deep_merge(raw_unresolved, overlay_data)

    # Ensure overlay reference doesn't pollute the resolved target
    if target_name and "targets" in resolved:
        target_block = resolved["targets"].get(target_name)
        if isinstance(target_block, dict):
            target_block.pop("overlay", None)

    return resolved, raw_unresolved


__all__ = ["deep_merge", "resolve_overlay"]
