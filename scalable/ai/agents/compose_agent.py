"""PydanticAI-based workflow composition agent for Scalable.

Refactors the existing ``workflow_compose`` module to use structured
PydanticAI output validation with component-level type safety.
"""

from __future__ import annotations

import logging
from typing import Any

from ..prompts.compose import COMPOSE_PROMPT, SYSTEM_PROMPT
from .base import AgentConfig, AgentDeps, ScalableAgent
from .models import ComposeOutput, WorkflowComponent

logger = logging.getLogger(__name__)

__all__ = ["ComposeAgent"]

#: Known model patterns for heuristic composition
_KNOWN_MODELS: dict[str, dict[str, Any]] = {
    "gcam": {
        "full_name": "GCAM",
        "language": "c++",
        "cpus": 6,
        "memory": "20G",
        "runtime": "apptainer",
        "tags": ["iam", "climate", "compiled"],
        "description": "Global Change Assessment Model",
    },
    "stitches": {
        "full_name": "Stitches",
        "language": "python",
        "cpus": 1,
        "memory": "50G",
        "runtime": "docker",
        "tags": ["climate", "python"],
        "description": "Climate pattern scaling",
    },
    "demeter": {
        "full_name": "Demeter",
        "language": "python",
        "cpus": 2,
        "memory": "8G",
        "runtime": "docker",
        "tags": ["land-use", "python"],
        "description": "Land use spatial downscaling",
    },
    "tethys": {
        "full_name": "Tethys",
        "language": "python",
        "cpus": 2,
        "memory": "8G",
        "runtime": "docker",
        "tags": ["water", "python"],
        "description": "Water demand model",
    },
    "xanthos": {
        "full_name": "Xanthos",
        "language": "python",
        "cpus": 2,
        "memory": "16G",
        "runtime": "docker",
        "tags": ["hydrology", "python"],
        "description": "Global hydrology model",
    },
    "hector": {
        "full_name": "Hector",
        "language": "c++",
        "cpus": 1,
        "memory": "4G",
        "runtime": "docker",
        "tags": ["climate", "compiled"],
        "description": "Simple climate model",
    },
}


class ComposeAgent(ScalableAgent[ComposeOutput]):
    """AI agent for generating workflow compositions from descriptions.

    Generates workflow skeletons including component definitions,
    execution order, and parallelism groups.

    Example
    -------
    >>> agent = ComposeAgent()
    >>> result = agent.run_sync(
    ...     "Create a workflow with GCAM feeding into Demeter and Tethys",
    ... )
    >>> for comp in result.data.components:
    ...     print(f"{comp.name}: {comp.cpus} CPUs, {comp.memory}")
    """

    def __init__(self, *, config: AgentConfig | None = None) -> None:
        super().__init__(
            result_type=ComposeOutput,
            config=config,
            name="compose",
            system_prompt=SYSTEM_PROMPT,
        )

    def _build_agent(self) -> Any:
        """Build PydanticAI agent with composition-specific tools."""
        agent = super()._build_agent()

        @agent.tool_plain
        def list_known_models() -> str:
            """List known scientific models and their default configurations."""
            lines = []
            for key, info in _KNOWN_MODELS.items():
                lines.append(
                    f"- {info['full_name']} ({key}): {info['description']}, "
                    f"{info['cpus']} CPUs, {info['memory']} memory, "
                    f"runtime={info['runtime']}"
                )
            return "\n".join(lines)

        @agent.tool_plain
        def get_model_defaults(model_name: str) -> str:
            """Get default configuration for a known model."""
            info = _KNOWN_MODELS.get(model_name.lower())
            if info:
                return (
                    f"Model: {info['full_name']}\n"
                    f"Language: {info['language']}\n"
                    f"CPUs: {info['cpus']}\n"
                    f"Memory: {info['memory']}\n"
                    f"Runtime: {info['runtime']}\n"
                    f"Tags: {', '.join(info['tags'])}"
                )
            return f"Unknown model: {model_name}"

        return agent

    def build_prompt(self, description: str) -> str:
        """Build the composition prompt.

        Parameters
        ----------
        description : str
            Natural-language workflow description.

        Returns
        -------
        str
            Formatted prompt.
        """
        return COMPOSE_PROMPT.format(description=description)

    def _heuristic_fallback(self, prompt: str, deps: AgentDeps) -> ComposeOutput:
        """Provide heuristic-based workflow composition without LLM."""
        description = prompt
        detected = self._detect_models(description)

        if not detected:
            return self._compose_generic(description)

        return self._compose_from_detected(description, detected)

    def _detect_models(self, description: str) -> list[str]:
        """Detect known model names in the description."""
        desc_lower = description.lower()
        detected: list[str] = []
        for model_key, info in _KNOWN_MODELS.items():
            if model_key in desc_lower or info["full_name"].lower() in desc_lower:
                detected.append(model_key)
        return detected

    def _compose_generic(self, description: str) -> ComposeOutput:
        """Generate a generic workflow template."""
        component = WorkflowComponent(
            name="main",
            runtime="docker",
            cpus=2,
            memory="8G",
            tags=["generic"],
        )
        return ComposeOutput(
            description=description,
            components=[component],
            execution_order=["main"],
            parallelism_groups=[["main"]],
            warnings=["Generic template — customize component settings for your use case"],
            scaffold_code=self._generic_scaffold(),
        )

    def _compose_from_detected(
        self, description: str, detected: list[str]
    ) -> ComposeOutput:
        """Generate workflow from detected model names."""
        components: list[WorkflowComponent] = []
        for model_key in detected:
            info = _KNOWN_MODELS[model_key]
            comp = WorkflowComponent(
                name=model_key,
                runtime=info["runtime"],
                cpus=info["cpus"],
                memory=info["memory"],
                tags=info["tags"],
            )
            components.append(comp)

        # Simple dependency ordering: first model feeds into subsequent ones
        execution_order = [c.name for c in components]

        # Set dependencies
        for comp in components[1:]:
            comp.dependencies = [components[0].name]

        # Parallelism: first component alone, rest in parallel
        parallelism_groups: list[list[str]] = []
        if components:
            parallelism_groups.append([components[0].name])
            if len(components) > 1:
                parallelism_groups.append([c.name for c in components[1:]])

        return ComposeOutput(
            description=description,
            components=components,
            execution_order=execution_order,
            parallelism_groups=parallelism_groups,
            warnings=[],
            scaffold_code=self._model_scaffold(components),
        )

    def _generic_scaffold(self) -> str:
        """Generate generic workflow scaffold code."""
        return '''"""Auto-generated Scalable workflow scaffold."""

from scalable import ScalableWorkflow


def build_workflow():
    wf = ScalableWorkflow(name="generated-workflow")

    # TODO: Define components and connections
    wf.add_component("main", image="TODO", cpus=2, memory="8G")

    return wf


if __name__ == "__main__":
    wf = build_workflow()
    wf.run()
'''

    def _model_scaffold(self, components: list[WorkflowComponent]) -> str:
        """Generate workflow scaffold for detected models."""
        lines = [
            '"""Auto-generated Scalable workflow scaffold."""',
            "",
            "from scalable import ScalableWorkflow",
            "",
            "",
            "def build_workflow():",
            '    wf = ScalableWorkflow(name="generated-workflow")',
            "",
        ]

        for comp in components:
            lines.append(
                f'    wf.add_component("{comp.name}", '
                f'runtime="{comp.runtime}", '
                f"cpus={comp.cpus}, "
                f'memory="{comp.memory}")'
            )

        # Add connections
        lines.append("")
        for comp in components:
            if comp.dependencies:
                for dep in comp.dependencies:
                    lines.append(f'    wf.connect("{dep}", "{comp.name}")')

        lines.extend([
            "",
            "    return wf",
            "",
            "",
            'if __name__ == "__main__":',
            "    wf = build_workflow()",
            "    wf.run()",
            "",
        ])

        return "\n".join(lines)
