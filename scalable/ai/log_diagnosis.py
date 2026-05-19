"""AI-assisted failure diagnosis for Scalable runs.

Reads telemetry from a run directory and classifies failures with
evidence and suggested fixes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scalable.telemetry.collectors import read_jsonl, resolve_run_dir

from .backend import AIBackend, get_ai_backend
from .heuristics import FailureClassification, classify_failure
from .prompts.diagnose import DIAGNOSIS_PROMPT, SYSTEM_PROMPT

__all__ = ["DiagnosisResult", "diagnose_run"]


@dataclass
class DiagnosisResult:
    """Complete diagnosis of a failed or problematic run."""

    run_id: str
    run_dir: str
    classifications: list[FailureClassification]
    summary: str
    method: str  # "heuristic" or "ai-enhanced"
    task_summary: dict[str, int] = field(default_factory=dict)
    resource_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "method": self.method,
            "task_summary": self.task_summary,
            "resource_summary": self.resource_summary,
            "classifications": [
                {
                    "failure_class": c.failure_class,
                    "confidence": c.confidence,
                    "evidence": c.evidence,
                    "suggested_fixes": c.suggested_fixes,
                }
                for c in self.classifications
            ],
            "summary": self.summary,
        }

    def render_text(self) -> str:
        """Render a human-readable diagnosis report."""
        lines = [
            f"Diagnosis for {self.run_id}",
            "=" * (len(f"Diagnosis for {self.run_id}")),
            "",
        ]

        if not self.classifications:
            lines.append("No failures detected in this run.")
            if self.task_summary:
                lines.append("")
                lines.append("Task summary:")
                for state, count in sorted(self.task_summary.items()):
                    lines.append(f"  {state}: {count}")
            return "\n".join(lines)

        for i, cls in enumerate(self.classifications, 1):
            if len(self.classifications) > 1:
                lines.append(f"--- Failure #{i} ---")
                lines.append("")

            lines.append(f"Likely failure: {cls.failure_class}")
            lines.append(f"Confidence: {cls.confidence}")
            lines.append("")
            lines.append("Evidence:")
            for ev in cls.evidence:
                lines.append(f"  - {ev}")
            lines.append("")
            lines.append("Suggested fixes:")
            for j, fix in enumerate(cls.suggested_fixes, 1):
                lines.append(f"  {j}. {fix}")
            lines.append("")

        if self.task_summary:
            lines.append("Task summary:")
            for state, count in sorted(self.task_summary.items()):
                lines.append(f"  {state}: {count}")

        return "\n".join(lines)


def diagnose_run(
    runs_dir: str | Path | None = None,
    *,
    run_id: str | None = None,
    run_dir: str | Path | None = None,
    latest: bool = False,
    backend: AIBackend | None = None,
    no_ai: bool = False,
) -> DiagnosisResult:
    """Diagnose a Scalable run from its telemetry.

    Parameters
    ----------
    runs_dir : str | Path | None
        Root runs directory. Defaults to .scalable/runs.
    run_id : str | None
        Explicit run identifier.
    run_dir : str | Path | None
        Direct path to a run directory.
    latest : bool
        If True, use the most recent run.
    backend : AIBackend | None
        AI backend for enhanced diagnosis.
    no_ai : bool
        If True, skip LLM enhancement.

    Returns
    -------
    DiagnosisResult
        Complete failure diagnosis with evidence and fixes.
    """
    # Resolve the run directory
    if run_dir is not None:
        resolved_dir = Path(run_dir)
    else:
        from scalable.common import settings
        effective_runs_dir = runs_dir or settings.runs_dir
        resolved_dir = resolve_run_dir(
            runs_dir=effective_runs_dir,
            run_id=run_id,
            latest=latest,
        )

    if not resolved_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {resolved_dir}")

    # Load telemetry
    run_meta = _load_run_meta(resolved_dir)
    failures = read_jsonl(resolved_dir / "failures.jsonl")
    tasks = read_jsonl(resolved_dir / "tasks.jsonl")
    resources = read_jsonl(resolved_dir / "resources.jsonl")

    detected_run_id = run_meta.get("run_id", resolved_dir.name)

    # Build task summary
    task_states: dict[str, str] = {}
    for t in tasks:
        tid = str(t.get("task_id", ""))
        state = str(t.get("state", "unknown"))
        if tid:
            task_states[tid] = state

    from collections import Counter
    state_counts = dict(Counter(task_states.values()))

    # Build resource summary
    resource_summary: dict[str, Any] = {}
    for r in resources:
        comp = r.get("component")
        if comp and comp not in resource_summary:
            resource_summary[comp] = {
                "cpus": r.get("requested_cpus"),
                "memory": r.get("requested_memory"),
            }

    # Classify failures
    classifications: list[FailureClassification] = []

    if failures:
        for failure in failures:
            # Get related task/resource events for context
            task_id = failure.get("task_id")
            related_tasks = [t for t in tasks if t.get("task_id") == task_id] if task_id else []
            related_resources = [r for r in resources if r.get("entity_id") == task_id] if task_id else []

            cls = classify_failure(
                failure_class=failure.get("failure_class"),
                message=failure.get("message", ""),
                details=failure.get("details", {}),
                task_events=related_tasks,
                resource_events=related_resources,
            )
            classifications.append(cls)
    elif state_counts.get("failed", 0) > 0:
        # No explicit failure events but tasks failed - check task errors
        for t in tasks:
            if t.get("state") == "failed" and t.get("error_message"):
                cls = classify_failure(
                    failure_class=t.get("error_type"),
                    message=t.get("error_message", ""),
                    details={"task_name": t.get("task_name")},
                    task_events=[t],
                    resource_events=[r for r in resources if r.get("entity_id") == t.get("task_id")],
                )
                classifications.append(cls)

    # Try AI enhancement
    method = "heuristic"
    if not no_ai and classifications:
        ai_backend = backend or get_ai_backend()
        if ai_backend.available():
            try:
                enhanced = _diagnose_with_ai(
                    run_meta, failures, tasks, resources, ai_backend
                )
                if enhanced:
                    classifications = enhanced
                    method = "ai-enhanced"
            except Exception:
                pass  # Fall through to heuristic results

    # Build summary
    if classifications:
        primary = classifications[0]
        summary = (
            f"Primary failure: {primary.failure_class} "
            f"(confidence: {primary.confidence}). "
            f"{len(classifications)} failure(s) detected."
        )
    else:
        summary = "No failures detected in this run."

    return DiagnosisResult(
        run_id=detected_run_id,
        run_dir=str(resolved_dir),
        classifications=classifications,
        summary=summary,
        method=method,
        task_summary=state_counts,
        resource_summary=resource_summary,
    )


def _load_run_meta(run_dir: Path) -> dict[str, Any]:
    """Load run.json metadata."""
    run_json = run_dir / "run.json"
    if run_json.exists():
        return json.loads(run_json.read_text(encoding="utf-8"))
    return {}


def _diagnose_with_ai(
    run_meta: dict[str, Any],
    failures: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    backend: AIBackend,
) -> list[FailureClassification] | None:
    """Attempt AI-enhanced diagnosis."""
    # Limit context to avoid token overload
    prompt = DIAGNOSIS_PROMPT.format(
        run_metadata=json.dumps(run_meta, indent=2)[:2000],
        failure_events=json.dumps(failures[:10], indent=2)[:3000],
        task_events=json.dumps(
            [t for t in tasks if t.get("state") in ("failed", "cancelled")][:10],
            indent=2,
        )[:2000],
        resource_events=json.dumps(resources[:10], indent=2)[:2000],
    )

    try:
        response = backend.complete(prompt, system=SYSTEM_PROMPT)
        # Parse AI response into classifications
        return _parse_ai_diagnosis(response)
    except Exception:
        return None


def _parse_ai_diagnosis(response: str) -> list[FailureClassification] | None:
    """Parse AI diagnosis response into structured classifications."""
    # Simple parsing - look for key fields in the response
    lines = response.strip().splitlines()

    failure_class = "unknown"
    confidence = "medium"
    evidence: list[str] = []
    fixes: list[str] = []

    for line in lines:
        line_lower = line.lower().strip()
        if "failure" in line_lower and ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                value = parts[1].strip().lower()
                for known_class in ("oom", "walltime", "mount_missing", "import_error",
                                    "connection", "credential", "model_runtime"):
                    if known_class in value:
                        failure_class = known_class
                        break

        elif "confidence" in line_lower and ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                value = parts[1].strip().lower()
                if "high" in value:
                    confidence = "high"
                elif "low" in value:
                    confidence = "low"

        elif line.strip().startswith("-") or line.strip().startswith("*"):
            text = line.strip().lstrip("-*").strip()
            if text:
                if any(kw in line_lower for kw in ("fix", "suggest", "recommend", "action")):
                    fixes.append(text)
                else:
                    evidence.append(text)

    if failure_class == "unknown" and not evidence:
        return None

    return [FailureClassification(
        failure_class=failure_class,
        confidence=confidence,
        evidence=evidence or ["AI analysis (see raw response for details)"],
        suggested_fixes=fixes or ["Review the full error output"],
    )]
