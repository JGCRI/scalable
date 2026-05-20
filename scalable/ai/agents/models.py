"""Structured output models for PydanticAI agents.

All agent responses are validated against these Pydantic models,
ensuring predictable, type-safe outputs regardless of which LLM
provider generates the response.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ComposeOutput",
    "DiagnosisOutput",
    "ExplanationOutput",
    "FailureDetail",
    "MigrationOutput",
    "OnboardingOutput",
    "WorkflowComponent",
]


# ---------------------------------------------------------------------------
# Diagnosis Models
# ---------------------------------------------------------------------------


class FailureDetail(BaseModel):
    """A single failure classification with evidence and fixes."""

    failure_class: str = Field(
        description="Category of failure (oom, walltime, mount_missing, import_error, "
        "connection, credential, model_runtime, config_error, unknown)"
    )
    confidence: str = Field(
        description="Confidence level: high, medium, or low"
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence lines supporting this classification",
    )
    suggested_fixes: list[str] = Field(
        default_factory=list,
        description="Ordered list of suggested fixes (most likely first)",
    )
    affected_component: str | None = Field(
        default=None,
        description="Name of the affected component, if identifiable",
    )


class DiagnosisOutput(BaseModel):
    """Structured output for failure diagnosis agent."""

    summary: str = Field(
        description="One-paragraph summary of the diagnosis"
    )
    classifications: list[FailureDetail] = Field(
        default_factory=list,
        description="Ordered list of failure classifications",
    )
    root_cause: str = Field(
        default="unknown",
        description="Primary root cause of the failure",
    )
    severity: str = Field(
        default="medium",
        description="Overall severity: critical, high, medium, low",
    )
    requires_manual_intervention: bool = Field(
        default=False,
        description="Whether the issue requires human intervention",
    )


# ---------------------------------------------------------------------------
# Explanation Models
# ---------------------------------------------------------------------------


class ExplanationOutput(BaseModel):
    """Structured output for plan explanation agent."""

    overview: str = Field(
        description="High-level overview of the execution plan"
    )
    resource_narrative: str = Field(
        default="",
        description="Explanation of resource allocation decisions",
    )
    strategy_narrative: str = Field(
        default="",
        description="Explanation of execution strategy choices",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations for the plan",
    )
    estimated_cost: str | None = Field(
        default=None,
        description="Estimated cost narrative if applicable",
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Potential risk factors identified in the plan",
    )


# ---------------------------------------------------------------------------
# Compose Models
# ---------------------------------------------------------------------------


class WorkflowComponent(BaseModel):
    """A single component in a composed workflow."""

    name: str = Field(description="Component name")
    image: str | None = Field(default=None, description="Container image")
    runtime: str = Field(default="docker", description="Runtime type")
    cpus: int = Field(default=1, description="CPU cores per worker")
    memory: str = Field(default="4G", description="Memory allocation")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Names of upstream components this depends on",
    )
    tags: list[str] = Field(default_factory=list, description="Component tags")
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables",
    )


class ComposeOutput(BaseModel):
    """Structured output for workflow composition agent."""

    description: str = Field(
        description="Natural-language description of the generated workflow"
    )
    components: list[WorkflowComponent] = Field(
        default_factory=list,
        description="Ordered list of workflow components",
    )
    execution_order: list[str] = Field(
        default_factory=list,
        description="Topologically sorted execution order",
    )
    parallelism_groups: list[list[str]] = Field(
        default_factory=list,
        description="Groups of components that can execute in parallel",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings or caveats about the generated workflow",
    )
    scaffold_code: str = Field(
        default="",
        description="Generated Python workflow scaffold code",
    )


# ---------------------------------------------------------------------------
# Migration Models
# ---------------------------------------------------------------------------


class MigrationOutput(BaseModel):
    """Structured output for manifest migration agent."""

    goal: str = Field(
        description="Description of the migration goal"
    )
    changes: list[str] = Field(
        default_factory=list,
        description="List of changes to be made",
    )
    overlay_yaml: str = Field(
        default="",
        description="Generated overlay YAML content",
    )
    new_target_config: dict[str, Any] = Field(
        default_factory=dict,
        description="New target configuration as a dictionary",
    )
    breaking_changes: list[str] = Field(
        default_factory=list,
        description="Any breaking changes that require attention",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Migration warnings",
    )
    rollback_steps: list[str] = Field(
        default_factory=list,
        description="Steps to rollback this migration if needed",
    )


# ---------------------------------------------------------------------------
# Onboarding Models
# ---------------------------------------------------------------------------


class OnboardingOutput(BaseModel):
    """Structured output for component onboarding agent."""

    name: str = Field(description="Component name")
    language: str = Field(
        default="unknown",
        description="Primary programming language detected",
    )
    runtime: str = Field(
        default="docker",
        description="Suggested container runtime",
    )
    image: str | None = Field(
        default=None,
        description="Suggested base image",
    )
    cpus: int = Field(default=1, description="Recommended CPU cores")
    memory: str = Field(default="4G", description="Recommended memory")
    mounts: dict[str, str] = Field(
        default_factory=dict,
        description="Suggested mount points (host: container)",
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Recommended environment variables",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Suggested component tags",
    )
    run_command: str | None = Field(
        default=None,
        description="Detected or suggested run command",
    )
    build_steps: list[str] = Field(
        default_factory=list,
        description="Steps to build the component container",
    )
    confidence: str = Field(
        default="low",
        description="Confidence in the analysis: high, medium, low",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes or recommendations",
    )
