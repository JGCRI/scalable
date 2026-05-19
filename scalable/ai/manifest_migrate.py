"""AI-assisted manifest migration for Scalable.

Proposes manifest changes when migrating between providers,
upgrading schema versions, or restructuring configurations.
Outputs overlay YAML or annotated diffs for review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from scalable.manifest.parser import load_manifest
from scalable.manifest.schema import SCHEMA_VERSION, ManifestModel

from .backend import AIBackend, get_ai_backend
from .prompts.migrate import MIGRATE_PROMPT, SYSTEM_PROMPT

__all__ = ["MigrationResult", "migrate_manifest"]


#: Provider migration templates
_PROVIDER_TEMPLATES: dict[str, dict[str, Any]] = {
    "kubernetes": {
        "provider": "kubernetes",
        "namespace": "scalable",
        "worker_service_account": "scalable-worker",
        "adapt_min": 1,
        "adapt_max": 10,
    },
    "aws": {
        "provider": "aws",
        "region": "us-east-1",
        "fargate": True,
        "vpc": "# TODO: specify VPC",
    },
    "gcp": {
        "provider": "gcp",
        "region": "us-central1",
        "project_id": "# TODO: specify GCP project",
    },
}


@dataclass
class MigrationResult:
    """Result of manifest migration analysis."""

    source_path: str | None
    goal: str
    overlay_yaml: str | None
    changes_description: str
    new_target: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    method: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "goal": self.goal,
            "method": self.method,
            "warnings": self.warnings,
            "overlay_yaml": self.overlay_yaml,
            "changes_description": self.changes_description,
            "new_target": self.new_target,
        }

    def render_text(self) -> str:
        """Render migration result as human-readable text."""
        lines = [
            "Manifest Migration Proposal",
            "=" * 27,
            "",
            f"Goal: {self.goal}",
            f"Method: {self.method}",
            "",
        ]

        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
            lines.append("")

        lines.append("Changes:")
        lines.append(self.changes_description)
        lines.append("")

        if self.overlay_yaml:
            lines.append("Proposed overlay:")
            lines.append("```yaml")
            lines.append(self.overlay_yaml)
            lines.append("```")

        return "\n".join(lines)


def migrate_manifest(
    manifest_path: str | Path | None = None,
    *,
    manifest: ManifestModel | None = None,
    to_provider: str | None = None,
    to_version: int | None = None,
    goal: str | None = None,
    backend: AIBackend | None = None,
    no_ai: bool = False,
) -> MigrationResult:
    """Analyze and propose manifest migration changes.

    Parameters
    ----------
    manifest_path : str | Path | None
        Path to the manifest to migrate.
    manifest : ManifestModel | None
        Pre-loaded manifest (alternative to path).
    to_provider : str | None
        Target provider to migrate to.
    to_version : int | None
        Target schema version.
    goal : str | None
        Free-form migration goal description.
    backend : AIBackend | None
        AI backend for enhanced migration.
    no_ai : bool
        If True, skip LLM enhancement.

    Returns
    -------
    MigrationResult
        Proposed changes with overlay or description.
    """
    # Load manifest if needed
    if manifest is None:
        if manifest_path is None:
            raise ValueError("Must provide either manifest_path or manifest")
        manifest = load_manifest(str(manifest_path))

    source = str(manifest_path) if manifest_path else manifest.source_path

    # Determine migration goal
    effective_goal = goal or ""
    if to_provider:
        effective_goal = f"Migrate to {to_provider} provider"
    elif to_version is not None:
        effective_goal = f"Upgrade schema to version {to_version}"
    elif not effective_goal:
        effective_goal = "General manifest optimization"

    # Try AI enhancement
    if not no_ai:
        ai_backend = backend or get_ai_backend()
        if ai_backend.available():
            try:
                return _migrate_with_ai(manifest, source, effective_goal, to_provider, ai_backend)
            except Exception:
                pass  # Fall through to heuristic

    # Heuristic migration
    if to_provider:
        return _migrate_provider(manifest, source, to_provider, effective_goal)
    elif to_version is not None:
        return _migrate_version(manifest, source, to_version, effective_goal)
    else:
        return _migrate_optimize(manifest, source, effective_goal)


def _migrate_provider(
    manifest: ManifestModel,
    source: str | None,
    to_provider: str,
    goal: str,
) -> MigrationResult:
    """Generate migration for changing providers."""
    template = _PROVIDER_TEMPLATES.get(to_provider)
    if template is None:
        return MigrationResult(
            source_path=source,
            goal=goal,
            overlay_yaml=None,
            changes_description=f"No template available for provider '{to_provider}'. "
                               f"Available providers: {', '.join(_PROVIDER_TEMPLATES.keys())}",
            warnings=[f"Unknown target provider: {to_provider}"],
            method="heuristic",
        )

    # Detect current provider from first target
    current_providers = [t.provider for t in manifest.targets.values()]
    from_provider = current_providers[0] if current_providers else "unknown"

    # Build new target
    target_name = to_provider
    new_target: dict[str, Any] = dict(template)

    # Build overlay
    overlay: dict[str, Any] = {
        "targets": {
            target_name: new_target,
        }
    }

    # Add component adjustments for cloud/k8s
    component_notes: list[str] = []
    if to_provider in ("kubernetes", "aws", "gcp"):
        for comp_name, comp in manifest.components.items():
            if comp.mounts:
                component_notes.append(
                    f"Component '{comp_name}' has local mounts that need "
                    f"cloud-compatible paths (PVCs, S3, etc.)"
                )

    overlay_yaml = yaml.dump(overlay, default_flow_style=False, sort_keys=False)

    changes = [
        f"Add new target '{target_name}' with {to_provider} provider",
        f"Current provider(s): {', '.join(current_providers)}",
    ]
    if component_notes:
        changes.append("")
        changes.append("Component adjustments needed:")
        changes.extend(f"  - {note}" for note in component_notes)

    warnings: list[str] = []
    if from_provider == "slurm" and to_provider in ("kubernetes", "aws", "gcp"):
        warnings.append("Migrating from HPC to cloud requires updating mount paths")
        warnings.append("Container images must be accessible from cloud environment")
    if to_provider == "gcp":
        warnings.append("GCP provider is scaffold-only (build_cluster not yet implemented)")

    return MigrationResult(
        source_path=source,
        goal=goal,
        overlay_yaml=overlay_yaml,
        changes_description="\n".join(changes),
        new_target=new_target,
        warnings=warnings,
        method="heuristic",
    )


def _migrate_version(
    manifest: ManifestModel,
    source: str | None,
    to_version: int,
    goal: str,
) -> MigrationResult:
    """Generate migration for schema version upgrade."""
    current_version = manifest.version

    if to_version == current_version:
        return MigrationResult(
            source_path=source,
            goal=goal,
            overlay_yaml=None,
            changes_description=f"Already at schema version {current_version}. No changes needed.",
            method="heuristic",
        )

    if to_version < current_version:
        return MigrationResult(
            source_path=source,
            goal=goal,
            overlay_yaml=None,
            changes_description=f"Cannot downgrade from version {current_version} to {to_version}.",
            warnings=["Schema version downgrade is not supported"],
            method="heuristic",
        )

    if to_version > SCHEMA_VERSION:
        return MigrationResult(
            source_path=source,
            goal=goal,
            overlay_yaml=None,
            changes_description=(
                f"Target version {to_version} is not yet supported. "
                f"Current max supported version: {SCHEMA_VERSION}"
            ),
            warnings=[f"Schema version {to_version} not recognized"],
            method="heuristic",
        )

    # Same version - no actual migration needed for v1→v1
    return MigrationResult(
        source_path=source,
        goal=goal,
        overlay_yaml=None,
        changes_description=f"Schema version {to_version} is current. No migration needed.",
        method="heuristic",
    )


def _migrate_optimize(
    manifest: ManifestModel,
    source: str | None,
    goal: str,
) -> MigrationResult:
    """General manifest optimization suggestions."""
    suggestions: list[str] = []
    warnings: list[str] = []

    # Check for missing recommended fields
    for comp_name, comp in manifest.components.items():
        if not comp.memory:
            suggestions.append(f"Component '{comp_name}': add explicit memory allocation")
        if not comp.image:
            suggestions.append(f"Component '{comp_name}': specify container image")
        if not comp.tags:
            suggestions.append(f"Component '{comp_name}': add descriptive tags")

    # Check tasks
    for task_name, task in manifest.tasks.items():
        if not task.cache:
            suggestions.append(f"Task '{task_name}': consider enabling cache for reproducibility")
        if not task.outputs:
            suggestions.append(f"Task '{task_name}': declare outputs for artifact tracking")

    # Check targets
    if len(manifest.targets) == 1:
        suggestions.append("Consider adding a 'local' target for development/testing")

    if not suggestions:
        suggestions.append("Manifest looks well-configured. No optimization suggestions.")

    return MigrationResult(
        source_path=source,
        goal=goal,
        overlay_yaml=None,
        changes_description="\n".join(f"- {s}" for s in suggestions),
        warnings=warnings,
        method="heuristic",
    )


def _migrate_with_ai(
    manifest: ManifestModel,
    source: str | None,
    goal: str,
    to_provider: str | None,
    backend: AIBackend,
) -> MigrationResult:
    """AI-enhanced manifest migration."""
    current_yaml = yaml.dump(manifest.raw, default_flow_style=False, sort_keys=True)

    # Determine providers
    current_providers = [t.provider for t in manifest.targets.values()]
    from_provider = current_providers[0] if current_providers else "unknown"

    prompt = MIGRATE_PROMPT.format(
        current_manifest=current_yaml[:4000],
        goal=goal,
        from_provider=from_provider,
        to_provider=to_provider or "optimize",
    )

    response = backend.complete(prompt, system=SYSTEM_PROMPT)

    # Try to extract YAML from response
    overlay_yaml = _extract_yaml(response)

    return MigrationResult(
        source_path=source,
        goal=goal,
        overlay_yaml=overlay_yaml,
        changes_description=response if not overlay_yaml else "See overlay YAML below.",
        warnings=["AI-generated migration - review carefully before applying"],
        method="ai-enhanced",
    )


def _extract_yaml(text: str) -> str | None:
    """Extract YAML block from text response."""
    import re

    # Try to find YAML in code blocks
    match = re.search(r"```(?:yaml)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        try:
            yaml.safe_load(candidate)
            return candidate
        except Exception:
            pass

    # Try the whole response as YAML
    try:
        yaml.safe_load(text)
        return text.strip()
    except Exception:
        pass

    return None
