"""Implementation for ``scalable validate``."""

from __future__ import annotations

import json
import sys
from typing import Any

from scalable.manifest.errors import ManifestError
from scalable.session.session import ScalableSession


def _report_to_dict(report: Any) -> dict[str, Any]:
    return {
        "ok": bool(report.ok),
        "errors": [
            {
                "path": issue.path,
                "message": issue.message,
                "code": issue.code,
            }
            for issue in report.errors
        ],
        "warnings": [
            {
                "path": issue.path,
                "message": issue.message,
                "code": issue.code,
            }
            for issue in report.warnings
        ],
    }


def run_validate(manifest_path: str, *, target: str | None = None) -> int:
    """Validate a manifest and print a structured JSON report."""
    try:
        session = ScalableSession.from_yaml(manifest_path, target=target)
        report = session.validate()
    except (ManifestError, OSError, ValueError, KeyError) as exc:
        payload = {
            "ok": False,
            "errors": [
                {
                    "path": "manifest",
                    "message": str(exc),
                    "code": "E_MANIFEST",
                }
            ],
            "warnings": [],
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stdout)
        return 1

    payload = _report_to_dict(report)
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stdout)
    return 0 if report.ok else 1

