"""Implementation for ``scalable report``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from scalable.telemetry.collectors import render_text_report, resolve_run_dir, summarize_run


def run_report(
    *,
    runs_dir: str,
    run_id: str | None,
    latest: bool,
    fmt: str,
    output: str | None,
) -> int:
    """Load telemetry for one run and emit a report payload."""
    try:
        run_dir = resolve_run_dir(runs_dir=runs_dir, run_id=run_id, latest=latest)
    except (FileNotFoundError, ValueError) as exc:
        print(f"report failed: {exc}", file=sys.stderr)
        return 1

    summary = summarize_run(run_dir)

    if fmt == "json":
        rendered = json.dumps(summary, indent=2, sort_keys=True)
    elif fmt == "text":
        rendered = render_text_report(summary)
    else:
        print(f"report failed: unsupported format {fmt!r}", file=sys.stderr)
        return 2

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")

    print(rendered, file=sys.stdout)
    return 0


__all__ = ["run_report"]

