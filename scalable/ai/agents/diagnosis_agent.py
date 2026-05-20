"""PydanticAI-based diagnosis agent for Scalable.

Refactors the existing ``log_diagnosis`` module to use the PydanticAI
agent framework with structured output validation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..heuristics import classify_failure
from ..prompts.diagnose import DIAGNOSIS_PROMPT, SYSTEM_PROMPT
from .base import AgentConfig, AgentDeps, ScalableAgent
from .models import DiagnosisOutput, FailureDetail

logger = logging.getLogger(__name__)

__all__ = ["DiagnosisAgent"]


class DiagnosisAgent(ScalableAgent[DiagnosisOutput]):
    """AI agent for diagnosing failed Scalable runs.

    Uses telemetry data (task events, failures, resource usage) to classify
    failures and suggest fixes. Falls back to rule-based heuristics when
    no LLM is available.

    Example
    -------
    >>> agent = DiagnosisAgent()
    >>> result = agent.run_sync(
    ...     "Diagnose run abc123",
    ...     deps=AgentDeps(telemetry={"failures": [...], "tasks": [...]}),
    ... )
    >>> print(result.data.summary)
    """

    def __init__(self, *, config: AgentConfig | None = None) -> None:
        super().__init__(
            result_type=DiagnosisOutput,
            config=config,
            name="diagnosis",
            system_prompt=SYSTEM_PROMPT,
        )

    def _build_agent(self) -> Any:
        """Build PydanticAI agent with diagnosis-specific tools."""
        agent = super()._build_agent()

        # Register diagnosis-specific tools
        @agent.tool_plain
        def get_failure_categories() -> str:
            """Get the list of known failure categories."""
            return (
                "Known failure categories: oom, walltime, mount_missing, "
                "import_error, connection, credential, model_runtime, "
                "config_error, unknown"
            )

        return agent

    def build_prompt(
        self,
        *,
        run_metadata: dict[str, Any] | None = None,
        failures: list[dict[str, Any]] | None = None,
        tasks: list[dict[str, Any]] | None = None,
        resources: list[dict[str, Any]] | None = None,
    ) -> str:
        """Build the diagnosis prompt from telemetry data.

        Parameters
        ----------
        run_metadata : dict | None
            Run metadata (run_id, timestamps, etc.)
        failures : list[dict] | None
            Failure event records.
        tasks : list[dict] | None
            Task event records.
        resources : list[dict] | None
            Resource event records.

        Returns
        -------
        str
            Formatted prompt for the agent.
        """
        return DIAGNOSIS_PROMPT.format(
            run_metadata=json.dumps(run_metadata or {}, indent=2),
            failure_events=json.dumps(failures or [], indent=2),
            task_events=json.dumps(tasks or [], indent=2),
            resource_events=json.dumps(resources or [], indent=2),
        )

    def _heuristic_fallback(self, prompt: str, deps: AgentDeps) -> DiagnosisOutput:
        """Provide heuristic-based diagnosis without LLM.

        Uses the rule-based :func:`classify_failure` from the heuristics
        module to analyze telemetry data.
        """
        telemetry = deps.telemetry
        failures = telemetry.get("failures", [])
        tasks = telemetry.get("tasks", [])
        resources = telemetry.get("resources", [])

        classifications: list[FailureDetail] = []

        if failures:
            for failure in failures:
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
                classifications.append(FailureDetail(
                    failure_class=cls.failure_class,
                    confidence=cls.confidence,
                    evidence=cls.evidence,
                    suggested_fixes=cls.suggested_fixes,
                ))
        elif any(t.get("state") == "failed" for t in tasks):
            for t in tasks:
                if t.get("state") == "failed" and t.get("error_message"):
                    cls = classify_failure(
                        failure_class=t.get("error_type"),
                        message=t.get("error_message", ""),
                        details={"task_name": t.get("task_name")},
                        task_events=[t],
                        resource_events=[
                            r for r in resources
                            if r.get("entity_id") == t.get("task_id")
                        ],
                    )
                    classifications.append(FailureDetail(
                        failure_class=cls.failure_class,
                        confidence=cls.confidence,
                        evidence=cls.evidence,
                        suggested_fixes=cls.suggested_fixes,
                    ))

        # Build summary
        if classifications:
            primary = classifications[0]
            summary = (
                f"Primary failure: {primary.failure_class} "
                f"(confidence: {primary.confidence}). "
                f"Total issues found: {len(classifications)}."
            )
            root_cause = primary.failure_class
            severity = "high" if primary.confidence == "high" else "medium"
        else:
            summary = "No failures detected in the analyzed telemetry data."
            root_cause = "none"
            severity = "low"

        return DiagnosisOutput(
            summary=summary,
            classifications=classifications,
            root_cause=root_cause,
            severity=severity,
            requires_manual_intervention=any(
                c.confidence == "low" for c in classifications
            ),
        )
