"""CLI handler for ``scalable compose``."""

from __future__ import annotations

import json
import sys

__all__ = ["run_compose"]


def run_compose(
    description: str,
    *,
    output_dir: str | None = None,
    fmt: str = "text",
    no_ai: bool = False,
) -> int:
    """Run the compose command.

    Parameters
    ----------
    description : str
        Natural-language workflow description.
    output_dir : str | None
        Directory to write generated files.
    fmt : str
        Output format ("text" or "json").
    no_ai : bool
        Skip LLM enhancement.

    Returns
    -------
    int
        Exit code (0 = success).
    """

    from scalable.ai.workflow_compose import compose_workflow

    if not description.strip():
        print("Error: description cannot be empty", file=sys.stderr)
        return 1

    try:
        result = compose_workflow(
            description,
            output_dir=output_dir,
            no_ai=no_ai,
        )
    except Exception as exc:
        print(f"Error during composition: {exc}", file=sys.stderr)
        return 1

    if fmt == "json":
        content = json.dumps(result.to_dict(), indent=2, sort_keys=True)
        print(content)
    else:
        if output_dir:
            print(f"Workflow files written to: {output_dir}")
            written = [
                f"  - {output_dir}/workflow.py",
                f"  - {output_dir}/components.yaml",
                f"  - {output_dir}/README.generated.md",
            ]
            print("\n".join(written))
        else:
            # Print to stdout when no output dir
            print("=== workflow.py ===")
            print(result.workflow_py)
            print("\n=== components.yaml ===")
            print(result.components_yaml)
            print("\n=== README.generated.md ===")
            print(result.readme)

    # Print metadata
    if result.detected_models:
        print(f"\nDetected models: {', '.join(result.detected_models)}", file=sys.stderr)
    print(f"Method: {result.method}", file=sys.stderr)
    if result.warnings:
        print("Warnings:", file=sys.stderr)
        for w in result.warnings:
            print(f"  - {w}", file=sys.stderr)

    return 0
