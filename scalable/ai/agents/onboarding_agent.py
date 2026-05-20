"""PydanticAI-based component onboarding agent for Scalable.

Refactors the existing ``component_onboarding`` module to use structured
PydanticAI output validation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..heuristics import DirectoryScanResult, find_run_commands, scan_model_directory
from ..prompts.onboarding import ANALYSIS_PROMPT, SYSTEM_PROMPT
from .base import AgentConfig, AgentDeps, AgentResult, ScalableAgent
from .models import OnboardingOutput

logger = logging.getLogger(__name__)

__all__ = ["OnboardingAgent"]


class OnboardingAgent(ScalableAgent[OnboardingOutput]):
    """AI agent for onboarding model components into Scalable.

    Inspects a model directory and proposes a ``ComponentConfig``-compatible
    configuration for inclusion in ``scalable.yaml``.

    Example
    -------
    >>> agent = OnboardingAgent()
    >>> result = agent.run_sync(
    ...     "Analyze /path/to/model",
    ...     deps=AgentDeps(run_context={
    ...         "scan": scan_result,
    ...         "name": "my-model",
    ...     }),
    ... )
    >>> print(result.data.runtime, result.data.cpus, result.data.memory)
    """

    def __init__(self, *, config: AgentConfig | None = None) -> None:
        super().__init__(
            result_type=OnboardingOutput,
            config=config,
            name="onboarding",
            system_prompt=SYSTEM_PROMPT,
        )

    def _build_agent(self) -> Any:
        """Build PydanticAI agent with onboarding-specific tools."""
        agent = super()._build_agent()

        @agent.tool_plain
        def get_runtime_recommendations() -> str:
            """Get container runtime recommendations based on language."""
            return (
                "Recommendations:\n"
                "- Python models: docker (with conda/pip base image)\n"
                "- C/C++/Fortran models: apptainer (HPC-optimized)\n"
                "- R models: docker (rocker base images)\n"
                "- Java models: docker (OpenJDK base)\n"
                "- Multi-language: apptainer (custom build)"
            )

        @agent.tool_plain
        def estimate_resources_for_language(language: str) -> str:
            """Estimate default resource requirements for a language."""
            defaults = {
                "python": "CPUs: 1-2, Memory: 4-8G",
                "c++": "CPUs: 4-8, Memory: 16-32G",
                "fortran": "CPUs: 4-16, Memory: 16-64G",
                "r": "CPUs: 1-4, Memory: 4-16G",
                "java": "CPUs: 2-4, Memory: 8-16G",
            }
            return defaults.get(language.lower(), "CPUs: 2, Memory: 8G (default)")

        return agent

    def build_prompt(self, scan: DirectoryScanResult, name: str) -> str:
        """Build the onboarding prompt from directory scan results.

        Parameters
        ----------
        scan : DirectoryScanResult
            Results from scanning the model directory.
        name : str
            Proposed component name.

        Returns
        -------
        str
            Formatted prompt.
        """
        return ANALYSIS_PROMPT.format(
            path=scan.path,
            name=name,
            file_listing="(see scan results)",
            build_systems=", ".join(scan.build_systems) or "none",
            languages=", ".join(scan.languages) or "unknown",
            container_files=", ".join(scan.container_files) or "none",
            data_directories=", ".join(scan.data_directories) or "none",
            config_files=", ".join(scan.config_files[:10]) or "none",
        )

    def _heuristic_fallback(self, prompt: str, deps: AgentDeps) -> OnboardingOutput:
        """Provide heuristic-based onboarding without LLM."""
        context = deps.run_context
        scan: DirectoryScanResult | None = context.get("scan")
        name = context.get("name", "unknown-component")

        if scan is None:
            return OnboardingOutput(
                name=name,
                confidence="low",
                notes=["No scan data available — provide a valid model directory"],
            )

        # Build from scan results
        mounts: dict[str, str] = {}
        if scan.suggested_mounts:
            mounts = dict(scan.suggested_mounts)

        env: dict[str, str] = {}
        if scan.estimated_cpus > 1:
            env["OMP_NUM_THREADS"] = str(scan.estimated_cpus)

        notes: list[str] = []
        if scan.confidence == "low":
            notes.append("Low confidence scan — review all fields carefully")
        if not scan.container_files:
            notes.append("No container definition found — image field needs manual setup")
        if not scan.data_directories:
            notes.append("No data directories detected — verify mount paths")

        return OnboardingOutput(
            name=name,
            language=scan.languages[0] if scan.languages else "unknown",
            runtime=scan.suggested_runtime or "docker",
            image=scan.suggested_base_image,
            cpus=scan.estimated_cpus,
            memory=scan.estimated_memory,
            mounts=mounts,
            env=env,
            tags=scan.suggested_tags,
            run_command=scan.run_commands[0] if scan.run_commands else None,
            confidence=scan.confidence,
            notes=notes,
        )
