"""Model provider abstraction for PydanticAI integration.

Provides a unified interface for resolving model providers from
environment configuration, supporting seamless switching between:

* OpenAI (GPT-4o, GPT-4, etc.)
* Anthropic (Claude Opus, Sonnet, Haiku)
* Google Gemini (1.5 Pro, Flash, 2.0)
* xAI (Grok-2, Grok-3)
* Groq (Llama, Mixtral)
* Ollama (local models)
* OpenAI-compatible endpoints (vLLM, LiteLLM, etc.)

The provider layer ensures that changing ``AI_PROVIDER`` (or ``SCALABLE_AI_BACKEND``)
and ``LLM_MODEL_NAME`` (or ``SCALABLE_AI_MODEL``) is sufficient to switch models
without any code changes.

Configuration
-------------
The following environment variables are used (in priority order):

1. ``SCALABLE_AI_BACKEND`` / ``AI_PROVIDER`` — provider name
2. ``SCALABLE_AI_MODEL`` / ``LLM_MODEL_NAME`` — model identifier
3. ``SCALABLE_AI_ENDPOINT`` / ``AI_BASE_URL`` — custom API endpoint
4. ``SCALABLE_AI_API_KEY`` / ``AI_API_KEY`` — universal API key fallback
5. Provider-specific keys (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, etc.)
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
        Handles OpenAI-compatible providers (including xAI/Grok) via custom
        endpoints.

        Returns
        -------
        Any
            A PydanticAI-compatible model instance or string identifier.
        """
        if self.name in ("openai", "xai") and self.endpoint:
            # OpenAI-compatible endpoint (vLLM, LiteLLM, xAI/Grok, etc.)
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

        if self.name == "xai" and not self.endpoint:
            # xAI always needs its endpoint configured
            try:
                from openai import AsyncOpenAI
                from pydantic_ai.models.openai import OpenAIModel

                client = AsyncOpenAI(
                    base_url=_DEFAULT_ENDPOINTS["xai"],
                    api_key=self.api_key or "unused",
                )
                return OpenAIModel(self.model, openai_client=client)
            except ImportError:
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

        Checks for:
        1. Provider-specific API key env var (e.g. ``OPENAI_API_KEY``)
        2. Universal ``AI_API_KEY`` / ``SCALABLE_AI_API_KEY`` fallback
        3. Explicit ``api_key`` on this instance

        Returns
        -------
        bool
            True if the necessary packages and credentials are present.
        """
        universal_key = (
            os.environ.get("SCALABLE_AI_API_KEY")
            or os.environ.get("AI_API_KEY")
        )

        if self.name == "openai":
            try:
                import openai  # noqa: F401
                return bool(
                    os.environ.get("OPENAI_API_KEY")
                    or self.api_key
                    or universal_key
                )
            except ImportError:
                return False
        elif self.name == "anthropic":
            try:
                import anthropic  # noqa: F401
                return bool(
                    os.environ.get("ANTHROPIC_API_KEY")
                    or self.api_key
                    or universal_key
                )
            except ImportError:
                return False
        elif self.name in ("google", "google-gla"):
            try:
                import google.generativeai  # noqa: F401
                return bool(
                    os.environ.get("GOOGLE_API_KEY")
                    or self.api_key
                    or universal_key
                )
            except ImportError:
                return False
        elif self.name == "xai":
            try:
                import openai  # noqa: F401
                return bool(
                    os.environ.get("XAI_API_KEY")
                    or self.api_key
                    or universal_key
                )
            except ImportError:
                return False
        elif self.name == "groq":
            try:
                import groq  # noqa: F401
                return bool(
                    os.environ.get("GROQ_API_KEY")
                    or self.api_key
                    or universal_key
                )
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
    "google": "gemini-2.0-flash",
    "google-gla": "gemini-2.0-flash",
    "xai": "grok-3",
    "groq": "llama-3.1-70b-versatile",
    "ollama": "llama3",
}

#: Environment variable mapping for provider-specific API keys.
#: The universal ``AI_API_KEY`` / ``SCALABLE_AI_API_KEY`` serves as a
#: fallback when provider-specific keys are not set.
_API_KEY_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "google-gla": "GOOGLE_API_KEY",
    "xai": "XAI_API_KEY",
    "groq": "GROQ_API_KEY",
}

#: Default API endpoint overrides for providers that need them.
_DEFAULT_ENDPOINTS: dict[str, str] = {
    "xai": "https://api.x.ai/v1",
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

    1. Explicit parameters passed to this function
    2. Settings (``SCALABLE_AI_BACKEND`` / ``AI_PROVIDER``, etc.)
    3. Provider-specific env vars (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, etc.)
    4. Universal key fallback (``SCALABLE_AI_API_KEY`` / ``AI_API_KEY``)
    5. Returns None if no backend is configured

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

    # Resolve API key: explicit > provider-specific env var > universal fallback
    resolved_key = api_key
    if not resolved_key:
        env_var = _API_KEY_ENV_VARS.get(provider_name)
        if env_var:
            resolved_key = os.environ.get(env_var)
    if not resolved_key:
        # Universal fallback from settings (reads SCALABLE_AI_API_KEY / AI_API_KEY)
        resolved_key = getattr(settings, "ai_api_key", None)

    # Resolve endpoint: explicit > settings > provider defaults
    effective_endpoint = effective_endpoint or _DEFAULT_ENDPOINTS.get(provider_name)

    # For xAI, remap the model_string to use openai: prefix since it's
    # OpenAI-compatible (PydanticAI resolves via model string prefix)
    if provider_name == "xai":
        model_string = f"openai:{model_name}"

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
