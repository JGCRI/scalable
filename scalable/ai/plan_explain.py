"""AI-assisted execution plan explanation for Scalable.

Renders human-readable narratives explaining execution plans,
resource allocation decisions, and cost/time implications.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .backend import AIBackend, get_ai_backend
from .prompts.explain import EXPLAIN_PROMPT, SYSTEM_PROMPT

__all__ = ["ExplanationResult", "explain_plan"]


@dataclass
class ExplanationResult:
    """Result of plan explanation."""

    plan_source: str
    narrative: str
    sections: dict[str, str] = field(default_factory=dict)
    method: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_source": self.plan_source,
            "method": self.method,
            "sections": self.sections,
            "narrative": self.narrative,
        }

    def render_text(self) -> str:
        """Render the explanation as formatted text."""
        return self.narrative


def explain_plan(
    plan_path: str | Path | None = None,
    *,
    plan_data: dict[str, Any] | None = None,
    runs_dir: str | Path | None = None,
    backend: AIBackend | None = None,
    no_ai: bool = False,
) -> ExplanationResult:
    """Explain a Scalable execution plan in human-readable form.

    Parameters
    ----------
    plan_path : str | Path | None
        Path to plan.json file.
    plan_data : dict | None
        Pre-loaded plan dictionary (alternative to plan_path).
    runs_dir : str | Path | None
        Runs directory for historical context.
    backend : AIBackend | None
        AI backend for enhanced explanation.
    no_ai : bool
        If True, skip LLM enhancement.

    Returns
    -------
    ExplanationResult
        Structured explanation with narrative and sections.
    """
    # Load plan
    if plan_data is not None:
        plan = plan_data
        source = "<provided>"
    elif plan_path is not None:
        path = Path(plan_path)
        if not path.exists():
            raise FileNotFoundError(f"Plan file not found: {path}")
        plan = json.loads(path.read_text(encoding="utf-8"))
        source = str(path)
    else:
        raise ValueError("Must provide either plan_path or plan_data")

    # Try AI enhancement
    if not no_ai:
        ai_backend = backend or get_ai_backend()
        if ai_backend.available():
            try:
                return _explain_with_ai(plan, source, runs_dir, ai_backend)
            except Exception:
                pass  # Fall through to heuristic

    # Heuristic explanation
    return _explain_heuristic(plan, source, runs_dir)


def _explain_heuristic(
    plan: dict[str, Any],
    source: str,
    runs_dir: str | Path | None,
) -> ExplanationResult:
    """Generate plan explanation using heuristics."""
    sections: dict[str, str] = {}

    # Overview section
    target = plan.get("target", "unknown")
    provider = plan.get("provider", "unknown")
    manifest_lock = plan.get("manifest_lock", "unknown")[:12]

    overview_lines = [
        f"This plan deploys a workflow on the '{target}' target using the '{provider}' provider.",
        f"Manifest fingerprint: {manifest_lock}...",
    ]

    task_map = plan.get("task_to_component", {})
    if task_map:
        overview_lines.append("")
        overview_lines.append(f"Tasks ({len(task_map)}):")
        for task_name, component in sorted(task_map.items()):
            overview_lines.append(f"  - {task_name} → component '{component}'")

    sections["overview"] = "\n".join(overview_lines)

    # Resource allocation section
    scale_plan = plan.get("scale_plan", {})
    workers = scale_plan.get("workers_by_tag", {})
    resources = scale_plan.get("resources_by_tag", {})

    resource_lines = ["Resource allocation per component:"]
    for tag in sorted(workers.keys()):
        worker_count = workers[tag]
        res = resources.get(tag, {})
        cpus = res.get("cpus", "?")
        memory = res.get("memory", "?")
        walltime = res.get("walltime", "not set")
        gpus = res.get("gpus")

        resource_lines.append("")
        resource_lines.append(f"  {tag}:")
        resource_lines.append(f"    Workers: {worker_count}")
        resource_lines.append(f"    CPUs per worker: {cpus}")
        resource_lines.append(f"    Memory per worker: {memory}")
        resource_lines.append(f"    Walltime: {walltime}")
        if gpus:
            resource_lines.append(f"    GPUs: {gpus}")

    if not workers:
        resource_lines.append("  (no workers defined)")

    sections["resources"] = "\n".join(resource_lines)

    # Execution strategy section
    strategy_lines = [
        "Execution strategy:",
        f"  Provider: {provider}",
        f"  Target: {target}",
    ]

    if provider == "local":
        strategy_lines.append("  Mode: local execution (no container isolation by default)")
        strategy_lines.append("  Suitable for: development, testing, small workloads")
    elif provider == "slurm":
        strategy_lines.append("  Mode: HPC batch scheduling via Slurm")
        strategy_lines.append("  Workers run as containerized Dask workers in Slurm allocations")
    elif provider == "kubernetes":
        strategy_lines.append("  Mode: Kubernetes pod-based execution")
        strategy_lines.append("  Workers deploy as pods with component-specific resource requests")
    elif provider == "aws":
        strategy_lines.append("  Mode: AWS cloud execution (Fargate/EC2)")
    else:
        strategy_lines.append(f"  Mode: {provider} execution")

    total_cpus = sum(
        workers.get(tag, 0) * resources.get(tag, {}).get("cpus", 1)
        for tag in workers
    )
    strategy_lines.append("")
    strategy_lines.append(f"  Total workers: {sum(workers.values())}")
    strategy_lines.append(f"  Total CPU cores: {total_cpus}")

    sections["strategy"] = "\n".join(strategy_lines)

    # Recommendations section
    rec_lines = ["Recommendations:"]
    if total_cpus == 0:
        rec_lines.append("  ⚠ No workers allocated - check component definitions")
    if all(w == 1 for w in workers.values()) and len(workers) > 1:
        rec_lines.append("  ℹ All components have 1 worker - consider scaling for parallelism")
    if any(not resources.get(tag, {}).get("memory") for tag in workers):
        rec_lines.append("  ⚠ Some components have no memory specified - may use provider defaults")

    # Historical context
    if runs_dir:
        history_note = _get_history_context(runs_dir, plan)
        if history_note:
            rec_lines.append(f"  ℹ {history_note}")

    sections["recommendations"] = "\n".join(rec_lines)

    # Build full narrative
    narrative_parts = [
        "Plan Explanation",
        "=" * 16,
        "",
        sections["overview"],
        "",
        sections["resources"],
        "",
        sections["strategy"],
        "",
        sections["recommendations"],
    ]
    narrative = "\n".join(narrative_parts)

    return ExplanationResult(
        plan_source=source,
        narrative=narrative,
        sections=sections,
        method="heuristic",
    )


def _explain_with_ai(
    plan: dict[str, Any],
    source: str,
    runs_dir: str | Path | None,
    backend: AIBackend,
) -> ExplanationResult:
    """Generate AI-enhanced plan explanation."""
    history_context = "No historical data available."
    cost_context = "No cost estimate available."

    if runs_dir:
        note = _get_history_context(runs_dir, plan)
        if note:
            history_context = note

    prompt = EXPLAIN_PROMPT.format(
        plan_json=json.dumps(plan, indent=2)[:4000],
        history_context=history_context,
        cost_context=cost_context,
    )

    response = backend.complete(prompt, system=SYSTEM_PROMPT)

    return ExplanationResult(
        plan_source=source,
        narrative=response,
        sections={"ai_explanation": response},
        method="ai-enhanced",
    )


def _get_history_context(runs_dir: str | Path | None, plan: dict[str, Any]) -> str | None:
    """Get historical context from past runs."""
    if not runs_dir:
        return None

    try:
        from scalable.telemetry.collectors import iter_run_dirs
        run_dirs = iter_run_dirs(runs_dir)
        if run_dirs:
            return f"Found {len(run_dirs)} historical run(s) for comparison."
    except Exception:
        pass

    return None
