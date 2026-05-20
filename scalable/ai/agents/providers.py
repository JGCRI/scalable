"""Model provider abstraction for PydanticAI integration.

Provides a unified interface for resolving model providers from
environment configuration, supporting seamless switching between:

* OpenAI (GPT-4o, GPT-4, etc.)
* Anthropic (Claude Sonnet, Opus, Haiku)
* Google Gemini (1.5 Pro, Flash)
* Groq (Llama, Mixtral)
* Ollama (local models)
* OpenAI-compatible endpoints (vLLM, LiteLLM, etc.)

The provider layer ensures that changing ``SCALABLE_AI_BACKEND`` or
``SCALABLE_AI_MODEL`` is sufficient to switch models without any code changes.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "ModelProvider",
    "get_model_provider",
    "list_providers",
    "resolve_model_string",
]


@dataclass
class ModelProvider:
    """Represents a configured model provider for PydanticAI.

    Attributes
    ----------
    name : str
        Provider name (e.g., 'openai', 'anthropic', 'google', 'ollama').
    model : str
        Model identifier within the provider.
    model_string : str
        Full PydanticAI model string (e.g., 'openai:gpt-4o').
    endpoint : str | None
        Custom API endpoint URL (for OpenAI-compatible servers).
    api_key : str | None
        API key (resolved from environment if not specified).
    extra_kwargs : dict[str, Any]
        Additional provider-specific keyword arguments.
    """

    name: str
    model: str
    model_string: str
    endpoint: str | None = None
    api_key: str | None = None
    extra_kwargs: dict[str, Any] = field(default_factory=dict)

    def get_pydantic_ai_model(self) -> Any:
        """Construct and return the appropriate PydanticAI model instance.

        Returns a model object suitable for passing to ``pydantic_ai.Agent``.

        Returns
        -------
        Any
            A PydanticAI-compatible model instance or string identifier.
        """
        if self.endpoint and self.name == "openai":
            # OpenAI-compatible endpoint (vLLM, LiteLLM, etc.)
            try:
                from openai import AsyncOpenAI
                from pydantic_ai.models.openai import OpenAIModel

                client = AsyncOpenAI(
                    base_url=self.endpoint,
                    api_key=self.api_key or "unused",
                )
                return OpenAIModel(self.model, openai_client=client)
            except ImportError:
                # Fall back to string-based resolution
                return self.model_string

        if self.endpoint and self.name == "ollama":
            try:
                from openai import AsyncOpenAI
                from pydantic_ai.models.openai import OpenAIModel

                # Ollama exposes an OpenAI-compatible API
                client = AsyncOpenAI(
                    base_url=f"{self.endpoint.rstrip('/')}/v1",
                    api_key="ollama",
                )
                return OpenAIModel(self.model, openai_client=client)
            except ImportError:
                return self.model_string

        # Standard providers use string-based resolution
        return self.model_string

    def is_available(self) -> bool:
        """Check whether this provider's dependencies are available.

        Returns
        -------
        bool
            True if the necessary packages and credentials are present.
        """
        if self.name == "openai":
            try:
                import openai  # noqa: F401
                return bool(os.environ.get("OPENAI_API_KEY") or self.api_key)
            except ImportError:
                return False
        elif self.name == "anthropic":
            try:
                import anthropic  # noqa: F401
                return bool(os.environ.get("ANTHROPIC_API_KEY") or self.api_key)
            except ImportError:
                return False
        elif self.name in ("google", "google-gla"):
            try:
                import google.generativeai  # noqa: F401
                return bool(os.environ.get("GOOGLE_API_KEY") or self.api_key)
            except ImportError:
                return False
        elif self.name == "groq":
            try:
                import groq  # noqa: F401
                return bool(os.environ.get("GROQ_API_KEY") or self.api_key)
            except ImportError:
                return False
        elif self.name == "ollama":
            # Ollama is local — just check if we can reach it
            import urllib.request
            endpoint = self.endpoint or "http://localhost:11434"
            try:
                url = f"{endpoint.rstrip('/')}/api/tags"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3):
                    return True
            except Exception:
                return False
        return False


# ---------------------------------------------------------------------------
# Provider registry and resolution
# ---------------------------------------------------------------------------

#: Default models for each provider
_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "google": "gemini-1.5-pro",
    "google-gla": "gemini-1.5-pro",
    "groq": "llama-3.1-70b-versatile",
    "ollama": "llama3",
}

#: Environment variable mapping for API keys
_API_KEY_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "google-gla": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
}


def resolve_model_string(backend: str | None = None, model: str | None = None) -> str | None:
    """Resolve a full PydanticAI model string from backend/model configuration.

    Parameters
    ----------
    backend : str | None
        Provider backend name or full model string with colon separator.
    model : str | None
        Specific model name within the provider.

    Returns
    -------
    str | None
        Full model string (e.g., 'openai:gpt-4o') or None if no backend configured.
    """
    if not backend or backend == "none":
        return None

    # Already a full model string
    if ":" in backend:
        return backend

    # Map legacy backend names
    provider = backend.lower()
    model_name = model or _DEFAULT_MODELS.get(provider, "default")

    return f"{provider}:{model_name}"


def get_model_provider(
    *,
    backend: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> ModelProvider | None:
    """Get a configured model provider from settings or explicit params.

    Resolves provider configuration from the following sources (in priority order):
    1. Explicit parameters
    2. ``SCALABLE_AI_BACKEND`` / ``SCALABLE_AI_MODEL`` / ``SCALABLE_AI_ENDPOINT``
    3. Returns None if no backend is configured

    Parameters
    ----------
    backend : str | None
        Provider name or full model string.
    model : str | None
        Model name.
    endpoint : str | None
        Custom API endpoint.
    api_key : str | None
        API key override.

    Returns
    -------
    ModelProvider | None
        Configured provider, or None if no AI backend is available.
    """
    from scalable.common import settings

    effective_backend = backend or getattr(settings, "ai_backend", "none")
    effective_model = model or getattr(settings, "ai_model", None)
    effective_endpoint = endpoint or getattr(settings, "ai_endpoint", None)

    if not effective_backend or effective_backend == "none":
        return None

    # Handle full model strings (e.g., "openai:gpt-4o")
    if ":" in effective_backend:
        parts = effective_backend.split(":", 1)
        provider_name = parts[0]
        model_name = effective_model or parts[1]
    else:
        provider_name = effective_backend.lower()
        model_name = effective_model or _DEFAULT_MODELS.get(provider_name, "default")

    model_string = f"{provider_name}:{model_name}"

    # Resolve API key from environment
    resolved_key = api_key
    if not resolved_key:
        env_var = _API_KEY_ENV_VARS.get(provider_name)
        if env_var:
            resolved_key = os.environ.get(env_var)

    return ModelProvider(
        name=provider_name,
        model=model_name,
        model_string=model_string,
        endpoint=effective_endpoint,
        api_key=resolved_key,
    )


def list_providers() -> list[dict[str, Any]]:
    """List all supported model providers with their status.

    Returns
    -------
    list[dict[str, Any]]
        Provider information including name, default model, and availability.
    """
    providers: list[dict[str, Any]] = []

    for name, default_model in _DEFAULT_MODELS.items():
        provider = ModelProvider(
            name=name,
            model=default_model,
            model_string=f"{name}:{default_model}",
        )
        providers.append({
            "name": name,
            "default_model": default_model,
            "model_string": f"{name}:{default_model}",
            "available": provider.is_available(),
            "api_key_env": _API_KEY_ENV_VARS.get(name),
        })

    return providers
