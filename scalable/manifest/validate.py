"""Semantic validation for parsed ``scalable.yaml`` manifests.

The parser in :mod:`scalable.manifest.parser` enforces structural schema
shape (required keys, value types, known top-level fields). This module
adds cross-field checks that require seeing the whole manifest at once,
without coupling to provider implementations.

Phase 1 checks:

* every ``tasks[*].component`` exists in ``components``;
* each target references a known provider name;
* component mount paths are absolute on both host and container sides;
* component memory strings are parseable by :func:`dask.utils.parse_bytes`.

The return type is a structured report instead of exceptions so
``scalable validate`` can print multiple issues in one run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from dask.utils import parse_bytes

from .schema import ManifestModel

__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "validate_manifest",
]


@dataclass(frozen=True)
class ValidationIssue:
    """Single validation finding.

    Attributes
    ----------
    path : str
        Manifest path-ish location (e.g. ``targets.local.provider``).
    message : str
        Human-readable message.
    code : str | None
        Stable machine-readable code for tooling (optional in Phase 1).
    """

    path: str
    message: str
    code: str | None = None


@dataclass
class ValidationReport:
    """Structured validation output consumed by CLI and session APIs."""

    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether the manifest passed validation with no errors."""
        return not self.errors


def validate_manifest(
    manifest: ManifestModel,
    *,
    known_providers: set[str] | None = None,
) -> ValidationReport:
    """Validate a parsed manifest and return a structured report.

    Parameters
    ----------
    manifest : ManifestModel
        Parsed model from :func:`scalable.manifest.parser.parse_manifest`.
    known_providers : set[str] | None
        Provider names accepted by this runtime. Defaults to
        ``{"local", "slurm"}`` in Phase 1 and can be replaced by the
        provider registry in WU-4.
    """
    report = ValidationReport()
    providers = known_providers or {"local", "slurm"}

    # ------------------------------------------------------------------
    # Target/provider checks
    # ------------------------------------------------------------------
    if not manifest.targets:
        report.warnings.append(
            ValidationIssue(
                path="targets",
                message="no targets declared; session startup requires a target",
                code="W_NO_TARGETS",
            )
        )
    for target_name, target in manifest.targets.items():
        if target.provider not in providers:
            report.errors.append(
                ValidationIssue(
                    path=f"targets.{target_name}.provider",
                    message=(
                        f"unknown provider {target.provider!r}; "
                        f"known providers: {sorted(providers)}"
                    ),
                    code="E_UNKNOWN_PROVIDER",
                )
            )

    # ------------------------------------------------------------------
    # Component checks
    # ------------------------------------------------------------------
    for component_name, component in manifest.components.items():
        # Memory parseability (shape already type-checked by parser)
        if component.memory is not None:
            try:
                parsed = parse_bytes(component.memory)
            except Exception:
                report.errors.append(
                    ValidationIssue(
                        path=f"components.{component_name}.memory",
                        message=(
                            f"memory value {component.memory!r} is not parseable; "
                            "use values like '8G', '500MB', or '1024MiB'"
                        ),
                        code="E_BAD_MEMORY",
                    )
                )
            else:
                if parsed <= 0:
                    report.errors.append(
                        ValidationIssue(
                            path=f"components.{component_name}.memory",
                            message="memory must be greater than zero",
                            code="E_NONPOSITIVE_MEMORY",
                        )
                    )

        # Mount path absoluteness
        for host_path, container_path in component.mounts.items():
            if not _is_absolute_posix_like(host_path):
                report.errors.append(
                    ValidationIssue(
                        path=f"components.{component_name}.mounts[{host_path!r}]",
                        message="host mount path must be absolute",
                        code="E_RELATIVE_HOST_MOUNT",
                    )
                )
            if not _is_absolute_posix_like(container_path):
                report.errors.append(
                    ValidationIssue(
                        path=(
                            f"components.{component_name}.mounts"
                            f"[{host_path!r}]"
                        ),
                        message="container mount path must be absolute",
                        code="E_RELATIVE_CONTAINER_MOUNT",
                    )
                )

    # ------------------------------------------------------------------
    # Task/component cross references
    # ------------------------------------------------------------------
    known_components = set(manifest.components)
    for task_name, task in manifest.tasks.items():
        if task.component not in known_components:
            report.errors.append(
                ValidationIssue(
                    path=f"tasks.{task_name}.component",
                    message=(
                        f"unknown component {task.component!r}; "
                        f"known components: {sorted(known_components)}"
                    ),
                    code="E_UNKNOWN_COMPONENT",
                )
            )

    if not manifest.tasks:
        report.warnings.append(
            ValidationIssue(
                path="tasks",
                message="no tasks declared; planning will produce an empty task set",
                code="W_NO_TASKS",
            )
        )

    return report


def _is_absolute_posix_like(path: str) -> bool:
    """Return whether a path is absolute in POSIX terms.

    Manifest paths are provider/runtime-oriented (containers, Linux HPC,
    object-store mount shims), so we normalize using POSIX semantics.
    """
    if not isinstance(path, str) or not path:
        return False
    return PurePosixPath(path).is_absolute()

