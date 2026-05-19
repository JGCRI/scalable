"""CLI handler for ``scalable explain``."""

from __future__ import annotations

import json
import sys

__all__ = ["run_explain"]


def run_explain(
    plan: str | None = None,
    *,
    runs_dir: str | None = None,
    fmt: str = "text",
    output: str | None = None,
    no_ai: bool = False,
) -> int:
    """Run the explain command.

    Parameters
    ----------
    plan : str | None
        Path to plan.json file.
    runs_dir : str | None
        Runs directory for historical context.
    fmt : str
        Output format ("text" or "json").
    output : str | None
        Output file path (default: stdout).
    no_ai : bool
        Skip LLM enhancement.

    Returns
    -------
    int
        Exit code (0 = success).
    """
    from pathlib import Path

    from scalable.ai.plan_explain import explain_plan

    if plan is None:
        # Try default location
        plan = "plan.json"

    try:
        result = explain_plan(
            plan_path=plan,
            runs_dir=runs_dir,
            no_ai=no_ai,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error during explanation: {exc}", file=sys.stderr)
        return 1

    # Format output
    if fmt == "json":
        content = json.dumps(result.to_dict(), indent=2, sort_keys=True)
    else:
        content = result.render_text()

    # Write output
    if output:
        Path(output).write_text(content, encoding="utf-8")
        print(f"Explanation written to: {output}", file=sys.stderr)
    else:
        print(content)

    return 0
