"""Exception hierarchy for the manifest layer.

Each error type carries enough context (path, key, value) to drive the
``scalable validate`` CLI's structured report and the Phase 4 AI migration
assistant's diff output. They subclass :class:`ValueError` so legacy
callers' ``except ValueError`` clauses keep working.
"""

from __future__ import annotations


class ManifestError(ValueError):
    """Base class for all manifest-layer errors."""


class ManifestParseError(ManifestError):
    """Raised when YAML parsing or env-var expansion fails."""


class ManifestSchemaError(ManifestError):
    """Raised when the document violates the v1 schema (missing required
    fields, wrong types, unknown top-level keys, version mismatch).
    """


class ManifestValidationError(ManifestError):
    """Raised when cross-field validation fails (unknown component
    reference, unresolvable provider, malformed memory string, ...).
    """


__all__ = [
    "ManifestError",
    "ManifestParseError",
    "ManifestSchemaError",
    "ManifestValidationError",
]
