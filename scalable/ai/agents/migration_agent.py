"""PydanticAI-based manifest migration agent for Scalable.

Refactors the existing ``manifest_migrate`` module to use structured
PydanticAI output validation.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml

from ..prompts.migrate import MIGRATE_PROMPT, SYSTEM_PROMPT
from .base import AgentConfig, AgentDeps, ScalableAgent
from .models import MigrationOutput

logger = logging.getLogger(__name__)

__all__ = ["MigrationAgent"]

#: Provider migration templates
_PROVIDER_TEMPLATES: dict[str, dict[str, Any]] = {
    "kubernetes": {
        "provider": "kubernetes",
        "namespace": "scalable",
        "worker_service_account": "scalable-worker",
        "adapt_min": 1,
        "adapt_max": 10,
    },
    "aws": {
        "provider": "aws",
        "region": "us-east-1",
        "fargate": True,
        "vpc": "# TODO: specify VPC",
    },
    "gcp": {
        "provider": "gcp",
        "region": "us-central1",
        "project_id": "# TODO: specify GCP project",
    },
}


class MigrationAgent(ScalableAgent[MigrationOutput]):
    """AI agent for analyzing and proposing manifest migrations.

    Proposes manifest changes when migrating between providers,
    upgrading schema versions, or restructuring configurations.

    Example
    -------
    >>> agent = MigrationAgent()
    >>> result = agent.run_sync(
    ...     "Migrate to kubernetes provider",
    ...     deps=AgentDeps(run_context={
    ...         "manifest": manifest_dict,
    ...         "to_provider": "kubernetes",
    ...     }),
    ... )
    >>> print(result.data.overlay_yaml)
    """

    def __init__(self, *, config: AgentConfig | None = None) -> None:
        super().__init__(
            result_type=MigrationOutput,
            config=config,
            name="migration",
            system_prompt=SYSTEM_PROMPT,
        )

    def _build_agent(self) -> Any:
        """Build PydanticAI agent with migration-specific tools."""
        agent = super()._build_agent()

        @agent.tool_plain
        def list_supported_providers() -> str:
            """List providers with migration templates."""
            return ", ".join(_PROVIDER_TEMPLATES.keys())

        @agent.tool_plain
        def get_provider_template(provider: str) -> str:
            """Get the default template for a provider migration."""
            template = _PROVIDER_TEMPLATES.get(provider)
            if template:
                return yaml.dump(template, default_flow_style=False)
            return f"No template for provider: {provider}"

        return agent

    def build_prompt(
        self,
        *,
        manifest_yaml: str,
        goal: str,
        to_provider: str | None = None,
    ) -> str:
        """Build the migration prompt.

        Parameters
        ----------
        manifest_yaml : str
            Current manifest as YAML string.
        goal : str
            Migration goal description.
        to_provider : str | None
            Target provider.

        Returns
        -------
        str
            Formatted prompt.
        """
        return MIGRATE_PROMPT.format(
            manifest_yaml=manifest_yaml,
            goal=goal,
            to_provider=to_provider or "unspecified",
        )

    def _heuristic_fallback(self, prompt: str, deps: AgentDeps) -> MigrationOutput:
        """Provide heuristic-based migration without LLM."""
        context = deps.run_context
        to_provider = context.get("to_provider")
        goal = context.get("goal", "General manifest optimization")
        manifest = context.get("manifest", {})

        if to_provider:
            return self._migrate_provider(manifest, to_provider, goal)

        return MigrationOutput(
            goal=goal,
            changes=["Review manifest for optimization opportunities"],
            overlay_yaml="",
            warnings=["Heuristic migration — review all changes carefully"],
        )

    def _migrate_provider(
        self,
        manifest: dict[str, Any],
        to_provider: str,
        goal: str,
    ) -> MigrationOutput:
        """Generate migration for changing providers."""
        template = _PROVIDER_TEMPLATES.get(to_provider)

        if template is None:
            return MigrationOutput(
                goal=goal,
                changes=[],
                overlay_yaml="",
                warnings=[f"Unknown target provider: {to_provider}"],
            )

        # Build overlay
        overlay: dict[str, Any] = {
            "targets": {
                to_provider: dict(template),
            },
        }
        overlay_yaml = yaml.dump(overlay, default_flow_style=False, sort_keys=False)

        changes = [
            f"Add new target '{to_provider}' with provider defaults",
            f"Provider: {template.get('provider', to_provider)}",
        ]

        if to_provider == "kubernetes":
            changes.extend([
                "Set namespace to 'scalable'",
                "Configure adaptive scaling (min=1, max=10)",
                "Add worker service account",
            ])
        elif to_provider == "aws":
            changes.extend([
                "Set region to 'us-east-1'",
                "Enable Fargate execution",
                "TODO: Configure VPC",
            ])
        elif to_provider == "gcp":
            changes.extend([
                "Set region to 'us-central1'",
                "TODO: Configure GCP project ID",
            ])

        breaking = []
        if to_provider in ("kubernetes", "aws", "gcp"):
            breaking.append("Container images must be accessible from the new provider's registry")

        return MigrationOutput(
            goal=goal,
            changes=changes,
            overlay_yaml=overlay_yaml,
            new_target_config=template,
            breaking_changes=breaking,
            warnings=[
                "Review resource limits for the new provider",
                "Verify network connectivity between components",
            ],
            rollback_steps=[
                "Remove the new target from the manifest",
                "Restore the original target as default",
            ],
        )
