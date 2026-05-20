"""CLI handler for ``scalable migrate``."""

from __future__ import annotations

import json
import sys

__all__ = ["run_migrate"]


def run_migrate(
    manifest: str | None = None,
    *,
    to_provider: str | None = None,
    to_version: int | None = None,
    goal: str | None = None,
    fmt: str = "text",
    output: str | None = None,
    no_ai: bool = False,
) -> int:
    """Run the migrate command.

    Parameters
    ----------
    manifest : str | None
        Path to manifest to migrate.
    to_provider : str | None
        Target provider.
    to_version : int | None
        Target schema version.
    goal : str | None
        Free-form migration goal.
    fmt : str
        Output format ("text" or "json").
    output : str | None
        Output file path.
    no_ai : bool
        Skip LLM enhancement.

    Returns
    -------
    int
        Exit code (0 = success).
    """
    from pathlib import Path

    from scalable.ai.manifest_migrate import migrate_manifest
    from scalable.common import settings

    effective_manifest = manifest or settings.manifest_path

    if not effective_manifest:
        print("Error: no manifest specified and SCALABLE_MANIFEST not set", file=sys.stderr)
        return 1

    if not Path(effective_manifest).exists():
        print(f"Error: manifest not found: {effective_manifest}", file=sys.stderr)
        return 1

    if not to_provider and to_version is None and not goal:
        print(
            "Error: must specify at least one of --to-provider, --to-version, or --goal",
            file=sys.stderr,
        )
        return 1

    try:
        result = migrate_manifest(
            manifest_path=effective_manifest,
            to_provider=to_provider,
            to_version=to_version,
            goal=goal,
            no_ai=no_ai,
        )
    except Exception as exc:
        print(f"Error during migration: {exc}", file=sys.stderr)
        return 1

    # Format output
    if fmt == "json":
        content = json.dumps(result.to_dict(), indent=2, sort_keys=True)
    else:
        content = result.render_text()

    # Write output
    if output:
        Path(output).write_text(content, encoding="utf-8")
        print(f"Migration proposal written to: {output}", file=sys.stderr)
    else:
        print(content)

    return 0
