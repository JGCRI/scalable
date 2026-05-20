"""CLI handler for ``scalable init-component``."""

from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["run_init_component"]


def run_init_component(
    path: str,
    *,
    name: str | None = None,
    output: str | None = None,
    no_ai: bool = False,
) -> int:
    """Run the init-component command.

    Parameters
    ----------
    path : str
        Path to model directory to analyze.
    name : str | None
        Component name override.
    output : str | None
        Output file path (default: stdout).
    no_ai : bool
        Skip LLM enhancement.

    Returns
    -------
    int
        Exit code (0 = success).
    """
    from scalable.ai.component_onboarding import onboard_component

    try:
        result = onboard_component(path, name=name, no_ai=no_ai)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error during onboarding: {exc}", file=sys.stderr)
        return 1

    # Output
    content = result.component_yaml

    if output:
        Path(output).write_text(content, encoding="utf-8")
        print(f"Component manifest written to: {output}", file=sys.stderr)
    else:
        print(content)

    # Print warnings to stderr
    if result.warnings:
        print("", file=sys.stderr)
        print("Warnings:", file=sys.stderr)
        for w in result.warnings:
            print(f"  - {w}", file=sys.stderr)

    # Print metadata to stderr
    print(f"\nMethod: {result.method}", file=sys.stderr)
    print(f"Confidence: {result.scan.confidence}", file=sys.stderr)
    if result.scan.languages:
        print(f"Languages: {', '.join(result.scan.languages)}", file=sys.stderr)

    return 0
