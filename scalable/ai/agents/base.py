"""Core agent base classes and dependency injection for PydanticAI integration.

This module provides the foundational types for all PydanticAI-based agents
in the Scalable framework:

* :class:`AgentDeps` — dependency injection container passed to agents.
* :class:`AgentConfig` — configuration for agent behavior (model, retries, etc.).
* :class:`AgentResult` — wrapper around PydanticAI run results.
* :class:`ScalableAgent` — base class wrapping PydanticAI ``Agent`` with
  Scalable-specific defaults and heuristic fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

__all__ = [
    "AgentConfig",
    "AgentDeps",
    "AgentResult",
    "ScalableAgent",
]

T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentDeps:
    """Dependency injection container for Scalable AI agents.

    This is passed as ``deps`` to every PydanticAI agent run, providing
    access to shared resources without global state.

    Attributes
    ----------
    run_context : dict[str, Any]
        Contextual data for the current operation (run_id, paths, etc.).
    settings : dict[str, Any]
        Configuration settings (model preferences, timeouts, etc.).
    telemetry : dict[str, Any]
        Telemetry data available for agent analysis.
    tools_enabled : bool
        Whether the agent can use registered tools.
    max_retries : int
        Maximum number of retries for failed operations.
    """

    run_context: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    telemetry: dict[str, Any] = field(default_factory=dict)
    tools_enabled: bool = True
    max_retries: int = 3


@dataclass
class AgentConfig:
    """Configuration for a Scalable AI agent.

    Controls model selection, retry behavior, and validation settings.

    Attributes
    ----------
    model : str | None
        Model identifier (e.g., 'openai:gpt-4o', 'anthropic:claude-sonnet-4-20250514',
        'google-gla:gemini-1.5-pro', 'ollama:llama3'). If None, uses the
        default from SCALABLE_AI_MODEL.
    temperature : float
        Sampling temperature for model completions.
    max_tokens : int
        Maximum tokens for model responses.
    max_retries : int
        Maximum retry attempts on transient failures.
    retry_delay : float
        Base delay between retries (exponential backoff applied).
    timeout : float
        Timeout in seconds for a single agent run.
    result_retries : int
        Number of retries when result validation fails.
    system_prompt : str | None
        Override system prompt (uses agent default if None).
    """

    model: str | None = None
    temperature: float = 0.0
    max_tokens: int = 4096
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 120.0
    result_retries: int = 2
    system_prompt: str | None = None


class AgentResult(Generic[T]):
    """Wrapper around a PydanticAI agent run result.

    Provides uniform access to structured output, metadata, and cost info.

    Attributes
    ----------
    data : T
        The validated Pydantic model output from the agent.
    model_name : str
        Name of the model that generated the response.
    usage : dict[str, int]
        Token usage statistics.
    messages : list[dict[str, Any]]
        Full message history from the agent run.
    retries : int
        Number of retries required.
    """

    def __init__(
        self,
        data: T,
        *,
        model_name: str = "unknown",
        usage: dict[str, int] | None = None,
        messages: list[dict[str, Any]] | None = None,
        retries: int = 0,
    ) -> None:
        self.data = data
        self.model_name = model_name
        self.usage = usage or {}
        self.messages = messages or []
        self.retries = retries

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to a dictionary."""
        return {
            "data": self.data.model_dump() if hasattr(self.data, "model_dump") else str(self.data),
            "model_name": self.model_name,
            "usage": self.usage,
            "retries": self.retries,
        }


class ScalableAgent(Generic[T]):
    """Base class for PydanticAI-powered agents in Scalable.

    Wraps a PydanticAI ``Agent`` with Scalable-specific defaults:
    * Automatic model provider resolution from settings
    * Heuristic fallback when no LLM is available
    * Structured output validation against a Pydantic model
    * Retry with exponential backoff
    * Dependency injection via :class:`AgentDeps`

    Subclasses must implement:
    * :meth:`_build_agent` — construct the PydanticAI Agent
    * :meth:`_heuristic_fallback` — provide non-LLM output

    Parameters
    ----------
    result_type : type[T]
        The Pydantic model class for validated output.
    config : AgentConfig | None
        Agent configuration. Uses defaults if None.
    name : str
        Human-readable agent name for logging.
    system_prompt : str
        Default system prompt for the agent.
    """

    def __init__(
        self,
        result_type: type[T],
        *,
        config: AgentConfig | None = None,
        name: str = "scalable-agent",
        system_prompt: str = "",
    ) -> None:
        self.result_type = result_type
        self.config = config or AgentConfig()
        self.name = name
        self.system_prompt = self.config.system_prompt or system_prompt
        self._agent: Any = None  # Lazy-initialized PydanticAI Agent

    def _get_model_string(self) -> str | None:
        """Resolve the model string from config or environment."""
        if self.config.model:
            return self.config.model

        from scalable.common import settings

        backend = getattr(settings, "ai_backend", "none")
        model = getattr(settings, "ai_model", None)

        if backend == "none" or not backend:
            return None

        if backend == "openai":
            return f"openai:{model or 'gpt-4o'}"
        elif backend == "anthropic":
            return f"anthropic:{model or 'claude-sonnet-4-20250514'}"
        elif backend == "google":
            return f"google-gla:{model or 'gemini-1.5-pro'}"
        elif backend == "ollama":
            return f"ollama:{model or 'llama3'}"
        elif backend == "groq":
            return f"groq:{model or 'llama-3.1-70b-versatile'}"
        else:
            # Allow raw model strings (e.g., "openai:gpt-4o")
            if ":" in backend:
                return backend
            return f"{backend}:{model or 'default'}"

    def _build_agent(self) -> Any:
        """Build and return a PydanticAI Agent instance.

        Returns
        -------
        pydantic_ai.Agent
            Configured agent instance.
        """
        try:
            from pydantic_ai import Agent
        except ImportError as exc:
            raise ImportError(
                "PydanticAI agent framework requires the 'pydantic-ai' package. "
                "Install with: pip install scalable[ai]"
            ) from exc

        model_str = self._get_model_string()
        if model_str is None:
            raise RuntimeError("No model configured for agent")

        agent = Agent(
            model_str,
            result_type=self.result_type,
            system_prompt=self.system_prompt,
            retries=self.config.result_retries,
        )
        return agent

    def get_agent(self) -> Any:
        """Get or lazily build the PydanticAI agent.

        Returns
        -------
        pydantic_ai.Agent
            The underlying PydanticAI agent instance.
        """
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    async def run(
        self,
        prompt: str,
        *,
        deps: AgentDeps | None = None,
        config: AgentConfig | None = None,
    ) -> AgentResult[T]:
        """Run the agent with the given prompt and return validated output.

        This method attempts LLM execution first, falling back to heuristics
        if no backend is available or if the LLM call fails.

        Parameters
        ----------
        prompt : str
            The user prompt to send to the agent.
        deps : AgentDeps | None
            Runtime dependencies for this execution.
        config : AgentConfig | None
            Override config for this specific run.

        Returns
        -------
        AgentResult[T]
            Validated, structured output from the agent.
        """
        effective_config = config or self.config
        effective_deps = deps or AgentDeps()

        # Check if LLM is available
        model_str = self._get_model_string()
        if model_str is None:
            logger.info("No model configured for %s, using heuristic fallback", self.name)
            fallback_data = self._heuristic_fallback(prompt, effective_deps)
            return AgentResult(
                data=fallback_data,
                model_name="heuristic",
                retries=0,
            )

        # Attempt PydanticAI execution with retry
        retries = 0
        last_error: Exception | None = None

        while retries <= effective_config.max_retries:
            try:
                agent = self.get_agent()
                result = await agent.run(
                    prompt,
                    deps=effective_deps,
                )

                # Extract usage info
                usage: dict[str, int] = {}
                if hasattr(result, "usage"):
                    usage_obj = result.usage()
                    if usage_obj:
                        usage = {
                            "request_tokens": getattr(usage_obj, "request_tokens", 0) or 0,
                            "response_tokens": getattr(usage_obj, "response_tokens", 0) or 0,
                            "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                        }

                return AgentResult(
                    data=result.data,
                    model_name=model_str,
                    usage=usage,
                    retries=retries,
                )

            except Exception as exc:
                last_error = exc
                retries += 1
                if retries <= effective_config.max_retries:
                    import asyncio
                    delay = effective_config.retry_delay * (2 ** (retries - 1))
                    logger.warning(
                        "Agent %s attempt %d failed: %s. Retrying in %.1fs...",
                        self.name, retries, exc, delay,
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted — fall back to heuristic
        logger.warning(
            "Agent %s exhausted %d retries (last error: %s). Using heuristic fallback.",
            self.name, effective_config.max_retries, last_error,
        )
        fallback_data = self._heuristic_fallback(prompt, AgentDeps())
        return AgentResult(
            data=fallback_data,
            model_name="heuristic-fallback",
            retries=retries,
        )

    def run_sync(
        self,
        prompt: str,
        *,
        deps: AgentDeps | None = None,
        config: AgentConfig | None = None,
    ) -> AgentResult[T]:
        """Synchronous wrapper around :meth:`run`.

        Uses the PydanticAI ``run_sync`` method for non-async contexts,
        with automatic heuristic fallback.

        Parameters
        ----------
        prompt : str
            The user prompt.
        deps : AgentDeps | None
            Runtime dependencies.
        config : AgentConfig | None
            Override config for this run.

        Returns
        -------
        AgentResult[T]
            Validated output.
        """
        effective_config = config or self.config
        effective_deps = deps or AgentDeps()

        model_str = self._get_model_string()
        if model_str is None:
            fallback_data = self._heuristic_fallback(prompt, effective_deps)
            return AgentResult(
                data=fallback_data,
                model_name="heuristic",
                retries=0,
            )

        try:
            agent = self.get_agent()
            result = agent.run_sync(
                prompt,
                deps=effective_deps,
            )

            usage: dict[str, int] = {}
            if hasattr(result, "usage"):
                usage_obj = result.usage()
                if usage_obj:
                    usage = {
                        "request_tokens": getattr(usage_obj, "request_tokens", 0) or 0,
                        "response_tokens": getattr(usage_obj, "response_tokens", 0) or 0,
                        "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                    }

            return AgentResult(
                data=result.data,
                model_name=model_str,
                usage=usage,
                retries=0,
            )

        except Exception as exc:
            logger.warning(
                "Agent %s sync run failed: %s. Using heuristic fallback.",
                self.name, exc,
            )
            fallback_data = self._heuristic_fallback(prompt, effective_deps)
            return AgentResult(
                data=fallback_data,
                model_name="heuristic-fallback",
                retries=0,
            )

    def _heuristic_fallback(self, prompt: str, deps: AgentDeps) -> T:
        """Provide a heuristic (non-LLM) response.

        Subclasses MUST override this to provide domain-specific
        heuristic logic that works without any LLM backend.

        Parameters
        ----------
        prompt : str
            The original user prompt.
        deps : AgentDeps
            Runtime dependencies.

        Returns
        -------
        T
            A valid instance of the result_type model.
        """
        raise NotImplementedError(
            f"Agent '{self.name}' must implement _heuristic_fallback()"
        )
