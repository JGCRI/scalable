"""PydanticAI-based agent framework for Scalable.

This package provides a model-agnostic AI agent layer built on PydanticAI,
enabling:

* **Structured output validation** — all agent responses validated against
  Pydantic models for predictable, type-safe outputs.
* **Model-agnostic providers** — seamless switching between OpenAI, Anthropic,
  Google Gemini, and local models without business logic changes.
* **Dependency injection** — type-safe dependencies passed to agents at runtime.
* **Tool registration** — declarative tool definitions with automatic schema
  generation.
* **Retry mechanisms** — configurable retry with exponential backoff and
  result validators.
* **Multi-agent coordination** — chains, delegation hierarchies, and
  collaborative pipelines.

Usage
-----
>>> from scalable.ai.agents import get_agent, AgentDeps
>>> agent = get_agent("diagnose")
>>> result = await agent.run(prompt, deps=AgentDeps(...))
"""

from __future__ import annotations

from .base import AgentConfig, AgentDeps, AgentResult, ScalableAgent
from .coordination import AgentChain, AgentPipeline, DelegatingAgent
from .models import (
    ComposeOutput,
    DiagnosisOutput,
    ExplanationOutput,
    MigrationOutput,
    OnboardingOutput,
)
from .providers import ModelProvider, get_model_provider, list_providers
from .tools import ToolRegistry, tool
from .validators import OutputValidator, validate_output

__all__ = [
    "AgentChain",
    "AgentConfig",
    "AgentDeps",
    "AgentPipeline",
    "AgentResult",
    "ComposeOutput",
    "DelegatingAgent",
    "DiagnosisOutput",
    "ExplanationOutput",
    "MigrationOutput",
    "ModelProvider",
    "OnboardingOutput",
    "OutputValidator",
    "ScalableAgent",
    "ToolRegistry",
    "get_model_provider",
    "list_providers",
    "tool",
    "validate_output",
]
