"""Provider registry and discovery helpers.

Phase 1 supports built-in providers (`local`, `slurm`) and allows optional
third-party provider registration through Python entry points under the
``scalable.providers`` group.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from .base import DeploymentProvider

ProviderFactory = Callable[[], DeploymentProvider] | type[DeploymentProvider]

_REGISTRY: dict[str, ProviderFactory] = {}

__all__ = [
    "clear_registry",
    "get_provider",
    "iter_provider_names",
    "register_provider",
    "register_providers",
]


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a provider factory/class under a stable name."""
    normalized = _normalize_provider_name(name)
    if normalized in _REGISTRY:
        raise ValueError(f"provider {normalized!r} is already registered")
    _REGISTRY[normalized] = factory


def register_providers(items: Iterable[tuple[str, ProviderFactory]]) -> None:
    """Bulk register provider factories."""
    for name, factory in items:
        register_provider(name, factory)


def get_provider(name: str) -> DeploymentProvider:
    """Resolve and instantiate a provider by name.

    Lookup order:
    1. Explicit runtime registry (`register_provider`).
    2. Entry points in group ``scalable.providers``.
    """
    normalized = _normalize_provider_name(name)
    if normalized in _REGISTRY:
        return _instantiate(_REGISTRY[normalized])

    discovered = _load_provider_entrypoint(normalized)
    if discovered is None:
        known = sorted(iter_provider_names(include_entrypoints=True))
        raise KeyError(
            f"unknown provider {normalized!r}; known providers: {known}"
        )
    # Cache discovered providers for next lookup.
    _REGISTRY[normalized] = discovered
    return _instantiate(discovered)


def iter_provider_names(*, include_entrypoints: bool = True) -> set[str]:
    """Return provider names known to the runtime."""
    names = set(_REGISTRY)
    if include_entrypoints:
        for ep in _iter_provider_entrypoints():
            names.add(_normalize_provider_name(ep.name))
    return names


def clear_registry() -> None:
    """Reset runtime registrations (primarily for tests)."""
    _REGISTRY.clear()


def _normalize_provider_name(name: str) -> str:
    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("provider name must be a non-empty string")
    return normalized


def _instantiate(factory: ProviderFactory) -> DeploymentProvider:
    if isinstance(factory, type):
        return factory()
    return factory()


def _iter_provider_entrypoints() -> list[EntryPoint]:
    try:
        eps = entry_points(group="scalable.providers")
        # Python 3.12+ returns EntryPoints object; convert to list.
        return list(eps)
    except TypeError:
        # Compatibility for older return style where group is filtered via
        # select(). Retained for robustness.
        eps = entry_points()
        selected = getattr(eps, "select", None)
        if callable(selected):
            return list(selected(group="scalable.providers"))
        return [ep for ep in eps if getattr(ep, "group", None) == "scalable.providers"]


def _load_provider_entrypoint(name: str) -> ProviderFactory | None:
    normalized = _normalize_provider_name(name)
    for ep in _iter_provider_entrypoints():
        if _normalize_provider_name(ep.name) != normalized:
            continue
        loaded: Any = ep.load()
        if isinstance(loaded, type):
            return loaded
        if callable(loaded):
            return loaded
        raise TypeError(
            f"entry point scalable.providers:{ep.name} must load a class or callable"
        )
    return None

