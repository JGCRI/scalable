"""PydanticAI-based plan explanation agent for Scalable.

Refactors the existing ``plan_explain`` module to use structured
PydanticAI output validation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..prompts.explain import EXPLAIN_PROMPT, SYSTEM_PROMPT
from .base import AgentConfig, AgentDeps, AgentResult, ScalableAgent
from .models import ExplanationOutput

logger = logging.getLogger(__name__)

__all__ = ["ExplanationAgent"]


class ExplanationAgent(ScalableAgent[ExplanationOutput]):
    """AI agent for explaining Scalable execution plans.

    Renders human-readable narratives about execution plans, resource
    allocation, and cost/time implications.

    Example
    -------
    >>> agent = ExplanationAgent()
    >>> result = agent.run_sync(
    ...     "Explain this plan",
    ...     deps=AgentDeps(run_context={"plan": plan_dict}),
    ... )
    >>> print(result.data.overview)
    """

    def __init__(self, *, config: AgentConfig | None = None) -> None:
        super().__init__(
            result_type=ExplanationOutput,
            config=config,
            name="explanation",
            system_prompt=SYSTEM_PROMPT,
        )

    def build_prompt(self, plan: dict[str, Any]) -> str:
        """Build the explanation prompt from a plan dictionary.

        Parameters
        ----------
        plan : dict
            The execution plan to explain.

        Returns
        -------
        str
            Formatted prompt for the agent.
        """
        return EXPLAIN_PROMPT.format(plan_json=json.dumps(plan, indent=2))

    def _heuristic_fallback(self, prompt: str, deps: AgentDeps) -> ExplanationOutput:
        """Provide heuristic-based plan explanation without LLM."""
        plan = deps.run_context.get("plan", {})

        # Overview
        target = plan.get("target", "unknown")
        provider = plan.get("provider", "unknown")
        task_map = plan.get("task_to_component", {})

        overview_lines = [
            f"This plan deploys a workflow on the '{target}' target using the '{provider}' provider.",
        ]
        if task_map:
            overview_lines.append(f"It contains {len(task_map)} tasks mapped to components.")

        # Resource narrative
        scale_plan = plan.get("scale_plan", {})
        workers = scale_plan.get("workers_by_tag", {})
        resources = scale_plan.get("resources_by_tag", {})

        resource_lines = ["Resource allocation per component:"]
        for tag in sorted(workers.keys()):
            worker_count = workers[tag]
            res = resources.get(tag, {})
            cpus = res.get("cpus", "?")
            memory = res.get("memory", "?")
            resource_lines.append(
                f"  {tag}: {worker_count} worker(s), {cpus} CPUs, {memory} memory"
            )

        if not workers:
            resource_lines.append("  (no workers defined)")

        # Strategy narrative
        strategy_lines = [f"Provider: {provider}, Target: {target}"]
        if provider == "local":
            strategy_lines.append("Running locally — suitable for development and testing.")
        elif provider == "slurm":
            strategy_lines.append("HPC batch scheduling via Slurm.")
        elif provider == "kubernetes":
            strategy_lines.append("Kubernetes pod-based execution.")

        total_workers = sum(workers.values())
        total_cpus = sum(
            workers.get(tag, 0) * resources.get(tag, {}).get("cpus", 1)
            for tag in workers
        )
        strategy_lines.append(f"Total workers: {total_workers}, Total CPUs: {total_cpus}")

        # Recommendations
        recommendations: list[str] = []
        if total_cpus == 0:
            recommendations.append("No workers allocated — check component definitions")
        if all(w == 1 for w in workers.values()) and len(workers) > 1:
            recommendations.append("All components have 1 worker — consider scaling for parallelism")

        # Risk factors
        risk_factors: list[str] = []
        if any(not resources.get(tag, {}).get("memory") for tag in workers):
            risk_factors.append("Some components have no memory specified")

        return ExplanationOutput(
            overview="\n".join(overview_lines),
            resource_narrative="\n".join(resource_lines),
            strategy_narrative="\n".join(strategy_lines),
            recommendations=recommendations,
            risk_factors=risk_factors,
        )
