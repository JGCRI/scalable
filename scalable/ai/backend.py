"""Pluggable AI/LLM backend protocol and registry.

The backend system supports:

* ``none`` — heuristic-only mode (no LLM calls)
* ``openai`` — OpenAI-compatible API (requires ``openai`` package)
* ``ollama`` — local Ollama server (requires running Ollama instance)

Backend selection is controlled by ``SCALABLE_AI_BACKEND`` env var.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from scalable.common import settings

logger = logging.getLogger(__name__)

__all__ = [
    "AIBackend",
    "NoOpBackend",
    "get_ai_backend",
]


@runtime_checkable
class AIBackend(Protocol):
    """Protocol for pluggable LLM/AI backends."""

    name: str

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a completion from the given prompt."""
        ...

    def available(self) -> bool:
        """Check whether this backend is currently usable."""
        ...


class NoOpBackend:
    """Fallback backend that signals no LLM is available.

    All assistants detect this and use their heuristic code path instead.
    """

    name: str = "none"

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        raise RuntimeError(
            "No AI backend configured. Set SCALABLE_AI_BACKEND to enable LLM features, "
            "or use --no-ai for heuristic-only mode."
        )

    def available(self) -> bool:
        return False


class OpenAIBackend:
    """OpenAI-compatible backend (requires ``openai`` package)."""

    name: str = "openai"

    def __init__(
        self,
        *,
        model: str | None = None,
        endpoint: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._model = model or getattr(settings, "ai_model", None) or "gpt-4o"
        self._endpoint = endpoint or getattr(settings, "ai_endpoint", None)
        self._api_key = api_key

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        try:
            import openai  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "OpenAI backend requires the 'openai' package. "
                "Install with: pip install openai"
            ) from exc

        kwargs: dict[str, Any] = {}
        if self._endpoint:
            kwargs["base_url"] = self._endpoint
        if self._api_key:
            kwargs["api_key"] = self._api_key

        client = openai.OpenAI(**kwargs)
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def available(self) -> bool:
        try:
            import openai  # type: ignore[import-untyped] # noqa: F401
            return True
        except ImportError:
            return False


class OllamaBackend:
    """Local Ollama backend for offline/HPC environments."""

    name: str = "ollama"

    def __init__(
        self,
        *,
        model: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        self._model = model or getattr(settings, "ai_model", None) or "llama3"
        self._endpoint = endpoint or getattr(settings, "ai_endpoint", None) or "http://localhost:11434"

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        import json
        import urllib.request

        url = f"{self._endpoint.rstrip('/')}/api/generate"
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return str(result.get("response", ""))
        except Exception as exc:
            raise RuntimeError(f"Ollama backend error: {exc}") from exc

    def available(self) -> bool:
        import urllib.request

        try:
            url = f"{self._endpoint.rstrip('/')}/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False


_BACKEND_REGISTRY: dict[str, type] = {
    "none": NoOpBackend,
    "openai": OpenAIBackend,
    "ollama": OllamaBackend,
}

_cached_backend: AIBackend | None = None


def get_ai_backend(*, force_name: str | None = None) -> AIBackend:
    """Get the configured AI backend instance.

    Parameters
    ----------
    force_name : str | None
        Override the backend name (bypasses SCALABLE_AI_BACKEND setting).

    Returns
    -------
    AIBackend
        The configured backend instance.
    """
    global _cached_backend

    name = force_name or getattr(settings, "ai_backend", "none") or "none"

    if _cached_backend is not None and getattr(_cached_backend, "name", None) == name:
        return _cached_backend

    backend_cls = _BACKEND_REGISTRY.get(name)
    if backend_cls is None:
        logger.warning("Unknown AI backend %r; falling back to 'none'", name)
        backend_cls = NoOpBackend

    backend = backend_cls()
    _cached_backend = backend
    return backend


def reset_backend_cache() -> None:
    """Reset the cached backend (for testing)."""
    global _cached_backend
    _cached_backend = None
