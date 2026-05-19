"""Implementation for ``scalable plan``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from scalable.manifest.errors import ManifestError
from scalable.session.session import ScalableSession


def run_plan(
    manifest_path: str,
    *,
    target: str | None,
    dry_run: bool,
    output: str,
) -> int:
    """Build a deterministic plan and write ``plan.json`` + ``manifest.lock``."""
    if not dry_run:
        print(
            "Phase 1 only supports dry-run planning. Re-run with --dry-run.",
            file=sys.stderr,
        )
        return 2

    try:
        session = ScalableSession.from_yaml(manifest_path, target=target)
        plan = session.plan(dry_run=True)
    except (ManifestError, OSError, ValueError, KeyError) as exc:
        print(f"planning failed: {exc}", file=sys.stderr)
        return 1

    payload = plan.to_dict()
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lock_path = output_path.parent / "manifest.lock"
    lock_path.write_text(plan.manifest_lock + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stdout)
    return 0

