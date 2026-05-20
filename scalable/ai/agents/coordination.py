"""Multi-agent coordination patterns for PydanticAI.

Provides composable patterns for orchestrating multiple agents:

* :class:`AgentChain` — sequential execution of agents, passing context forward.
* :class:`AgentPipeline` — transform-style pipeline where each agent refines
  the output of the previous.
* :class:`DelegatingAgent` — orchestrator that delegates sub-tasks to
  specialized agents based on context.

These patterns allow composing simple single-purpose agents into complex
reasoning chains and collaborative workflows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from .base import AgentDeps, AgentResult, ScalableAgent

logger = logging.getLogger(__name__)

__all__ = [
    "AgentChain",
    "AgentPipeline",
    "DelegatingAgent",
]

T = TypeVar("T", bound=BaseModel)


@dataclass
class ChainStep:
    """A single step in an agent chain.

    Attributes
    ----------
    agent : ScalableAgent
        The agent to execute at this step.
    prompt_template : str | None
        Template for constructing the prompt. Can reference ``{previous_result}``
        and ``{original_prompt}`` placeholders.
    name : str
        Human-readable step name for logging.
    """

    agent: ScalableAgent[Any]
    prompt_template: str | None = None
    name: str = "step"


class AgentChain:
    """Sequential chain of agents where each builds on the previous result.

    Each agent in the chain receives context from previous agents'
    outputs, allowing progressive refinement of analysis.

    Example
    -------
    >>> chain = AgentChain(steps=[
    ...     ChainStep(agent=classifier_agent, name="classify"),
    ...     ChainStep(agent=analyzer_agent, name="analyze",
    ...               prompt_template="Analyze this classified issue: {previous_result}"),
    ...     ChainStep(agent=fixer_agent, name="fix",
    ...               prompt_template="Suggest fixes: {previous_result}"),
    ... ])
    >>> result = await chain.run("Error: OOM killed")
    """

    def __init__(self, steps: list[ChainStep]) -> None:
        self.steps = steps

    async def run(
        self,
        prompt: str,
        *,
        deps: AgentDeps | None = None,
    ) -> list[AgentResult[Any]]:
        """Execute all steps sequentially.

        Parameters
        ----------
        prompt : str
            Initial prompt to start the chain.
        deps : AgentDeps | None
            Shared dependencies for all steps.

        Returns
        -------
        list[AgentResult]
            Results from each step in order.
        """
        results: list[AgentResult[Any]] = []
        current_prompt = prompt

        for i, step in enumerate(self.steps):
            logger.info("Chain step %d/%d: %s", i + 1, len(self.steps), step.name)

            if step.prompt_template and results:
                # Format prompt with previous result context
                prev_data = results[-1].data
                prev_str = prev_data.model_dump_json(indent=2) if hasattr(prev_data, "model_dump_json") else str(prev_data)
                current_prompt = step.prompt_template.format(
                    previous_result=prev_str,
                    original_prompt=prompt,
                )

            result = await step.agent.run(current_prompt, deps=deps)
            results.append(result)

        return results

    def run_sync(
        self,
        prompt: str,
        *,
        deps: AgentDeps | None = None,
    ) -> list[AgentResult[Any]]:
        """Execute all steps sequentially (synchronous).

        Parameters
        ----------
        prompt : str
            Initial prompt.
        deps : AgentDeps | None
            Shared dependencies.

        Returns
        -------
        list[AgentResult]
            Results from each step.
        """
        results: list[AgentResult[Any]] = []
        current_prompt = prompt

        for i, step in enumerate(self.steps):
            logger.info("Chain step %d/%d: %s", i + 1, len(self.steps), step.name)

            if step.prompt_template and results:
                prev_data = results[-1].data
                prev_str = prev_data.model_dump_json(indent=2) if hasattr(prev_data, "model_dump_json") else str(prev_data)
                current_prompt = step.prompt_template.format(
                    previous_result=prev_str,
                    original_prompt=prompt,
                )

            result = step.agent.run_sync(current_prompt, deps=deps)
            results.append(result)

        return results


@dataclass
class PipelineStage:
    """A stage in an agent pipeline with optional condition.

    Attributes
    ----------
    agent : ScalableAgent
        The agent for this stage.
    condition : Callable | None
        Optional condition function; if provided, stage is skipped when
        the condition returns False. Receives the previous AgentResult.
    transform_prompt : Callable | None
        Optional function to transform the prompt between stages.
        Receives (original_prompt, previous_result) and returns new prompt.
    name : str
        Stage name for logging.
    """

    agent: ScalableAgent[Any]
    condition: Any = None  # Callable[[AgentResult], bool] | None
    transform_prompt: Any = None  # Callable[[str, AgentResult], str] | None
    name: str = "stage"


class AgentPipeline:
    """Transform-style pipeline where each agent refines previous output.

    Unlike :class:`AgentChain`, pipelines support conditional execution
    of stages and custom prompt transformations between stages.

    Example
    -------
    >>> pipeline = AgentPipeline(stages=[
    ...     PipelineStage(agent=triage_agent, name="triage"),
    ...     PipelineStage(
    ...         agent=deep_analysis_agent,
    ...         name="deep_analysis",
    ...         condition=lambda r: r.data.severity == "critical",
    ...     ),
    ... ])
    >>> final = await pipeline.run("System failure detected")
    """

    def __init__(self, stages: list[PipelineStage]) -> None:
        self.stages = stages

    async def run(
        self,
        prompt: str,
        *,
        deps: AgentDeps | None = None,
    ) -> AgentResult[Any]:
        """Execute pipeline stages, returning the final result.

        Parameters
        ----------
        prompt : str
            Initial prompt.
        deps : AgentDeps | None
            Shared dependencies.

        Returns
        -------
        AgentResult
            Final stage result (or last executed stage if conditions skip later ones).
        """
        current_prompt = prompt
        last_result: AgentResult[Any] | None = None

        for i, stage in enumerate(self.stages):
            # Check condition
            if stage.condition and last_result:
                should_run = stage.condition(last_result)
                if not should_run:
                    logger.info(
                        "Pipeline stage %d/%d '%s' skipped (condition not met)",
                        i + 1, len(self.stages), stage.name,
                    )
                    continue

            # Transform prompt if configured
            if stage.transform_prompt and last_result:
                current_prompt = stage.transform_prompt(prompt, last_result)

            logger.info("Pipeline stage %d/%d: %s", i + 1, len(self.stages), stage.name)
            last_result = await stage.agent.run(current_prompt, deps=deps)

        if last_result is None:
            raise RuntimeError("Pipeline produced no results (all stages skipped)")

        return last_result

    def run_sync(
        self,
        prompt: str,
        *,
        deps: AgentDeps | None = None,
    ) -> AgentResult[Any]:
        """Execute pipeline stages synchronously."""
        current_prompt = prompt
        last_result: AgentResult[Any] | None = None

        for i, stage in enumerate(self.stages):
            if stage.condition and last_result:
                should_run = stage.condition(last_result)
                if not should_run:
                    logger.info(
                        "Pipeline stage %d/%d '%s' skipped (condition not met)",
                        i + 1, len(self.stages), stage.name,
                    )
                    continue

            if stage.transform_prompt and last_result:
                current_prompt = stage.transform_prompt(prompt, last_result)

            logger.info("Pipeline stage %d/%d: %s", i + 1, len(self.stages), stage.name)
            last_result = stage.agent.run_sync(current_prompt, deps=deps)

        if last_result is None:
            raise RuntimeError("Pipeline produced no results (all stages skipped)")

        return last_result


class DelegatingAgent:
    """Orchestrator agent that delegates sub-tasks to specialized agents.

    Routes requests to the appropriate specialist agent based on task
    classification, then aggregates results.

    Example
    -------
    >>> delegator = DelegatingAgent(
    ...     name="orchestrator",
    ...     agents={
    ...         "diagnose": diagnosis_agent,
    ...         "explain": explanation_agent,
    ...         "compose": compose_agent,
    ...     },
    ...     router=lambda prompt, deps: "diagnose" if "error" in prompt.lower() else "explain",
    ... )
    >>> result = await delegator.run("Error: container OOM killed")
    """

    def __init__(
        self,
        *,
        name: str = "delegator",
        agents: dict[str, ScalableAgent[Any]] | None = None,
        router: Any = None,  # Callable[[str, AgentDeps], str | list[str]]
    ) -> None:
        self.name = name
        self.agents = agents or {}
        self.router = router

    def register_agent(self, key: str, agent: ScalableAgent[Any]) -> None:
        """Register a specialist agent.

        Parameters
        ----------
        key : str
            Routing key for this agent.
        agent : ScalableAgent
            The agent to register.
        """
        self.agents[key] = agent

    def set_router(self, router: Any) -> None:
        """Set the routing function.

        Parameters
        ----------
        router : Callable[[str, AgentDeps], str | list[str]]
            Function that decides which agent(s) to delegate to.
            Returns a single key or list of keys for parallel execution.
        """
        self.router = router

    async def run(
        self,
        prompt: str,
        *,
        deps: AgentDeps | None = None,
    ) -> dict[str, AgentResult[Any]]:
        """Route and execute the appropriate agent(s).

        Parameters
        ----------
        prompt : str
            The user prompt to route.
        deps : AgentDeps | None
            Shared dependencies.

        Returns
        -------
        dict[str, AgentResult]
            Results keyed by agent routing key.
        """
        effective_deps = deps or AgentDeps()

        if self.router is None:
            raise RuntimeError("No router configured for DelegatingAgent")

        targets = self.router(prompt, effective_deps)
        if isinstance(targets, str):
            targets = [targets]

        results: dict[str, AgentResult[Any]] = {}

        for target in targets:
            agent = self.agents.get(target)
            if agent is None:
                logger.warning("No agent registered for key '%s', skipping", target)
                continue

            logger.info("Delegator '%s' routing to '%s'", self.name, target)
            result = await agent.run(prompt, deps=effective_deps)
            results[target] = result

        return results

    def run_sync(
        self,
        prompt: str,
        *,
        deps: AgentDeps | None = None,
    ) -> dict[str, AgentResult[Any]]:
        """Route and execute synchronously."""
        effective_deps = deps or AgentDeps()

        if self.router is None:
            raise RuntimeError("No router configured for DelegatingAgent")

        targets = self.router(prompt, effective_deps)
        if isinstance(targets, str):
            targets = [targets]

        results: dict[str, AgentResult[Any]] = {}

        for target in targets:
            agent = self.agents.get(target)
            if agent is None:
                logger.warning("No agent registered for key '%s', skipping", target)
                continue

            logger.info("Delegator '%s' routing to '%s'", self.name, target)
            result = agent.run_sync(prompt, deps=effective_deps)
            results[target] = result

        return results
