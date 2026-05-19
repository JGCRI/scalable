"""CLI handler for ``scalable diagnose``."""

from __future__ import annotations

import json
import sys

__all__ = ["run_diagnose"]


def run_diagnose(
    *,
    runs_dir: str | None = None,
    run_id: str | None = None,
    latest: bool = False,
    fmt: str = "text",
    output: str | None = None,
    no_ai: bool = False,
) -> int:
    """Run the diagnose command.

    Parameters
    ----------
    runs_dir : str | None
        Runs directory path.
    run_id : str | None
        Explicit run identifier.
    latest : bool
        Use most recent run.
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

    from scalable.ai.log_diagnosis import diagnose_run

    if not run_id and not latest:
        latest = True  # Default to latest if nothing specified

    try:
        result = diagnose_run(
            runs_dir=runs_dir,
            run_id=run_id,
            latest=latest,
            no_ai=no_ai,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error during diagnosis: {exc}", file=sys.stderr)
        return 1

    # Format output
    if fmt == "json":
        content = json.dumps(result.to_dict(), indent=2, sort_keys=True)
    else:
        content = result.render_text()

    # Write output
    if output:
        Path(output).write_text(content, encoding="utf-8")
        print(f"Diagnosis written to: {output}", file=sys.stderr)
    else:
        print(content)

    return 0
